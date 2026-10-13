#!/usr/bin/env python
"""INDEPENDENT audit of the dungeon draw (docs/mechanics/DUNGEON_DRAW.md sections 2-4) and of where the rips stand.

Independent means: the EXPECTATIONS here come from the spec (the design, the owner's answers D1-D5) and from
data/dungeon_prize_roster.json (first_band and gate per dungeon), never from the generator's own helpers.

  * The draw is checked by RUNNING the functions tools/dungeon.py emits, on the existing function simulator
    (tests/pocket_sim.py through tests/test_dungeon.py's DW), against scenarios built from the roster. No expectation
    is read from dungeon.py's `draw`, `candidates` or `eligible` code.
  * Rip siting is re-measured from tools/ground.py (the canonical heightmap, ROUNDED) and from data/*.json read here.
    tools/dungeon_rips.py is not imported for a single number: its siting rules are the thing being audited.
  * Independence is proved by MUTATING THE GENERATOR (tools/dungeon.py source, with data/ untouched): `--mutate` rebuilds
    the pack from a mutated copy of the source and requires the audit to FAIL. A mutation that only edited data would
    move the expectation and the output together and prove nothing.

  python tools/dungeon_draw_audit.py --out <file>                 the whole audit; one verdict line on stdout
  python tools/dungeon_draw_audit.py --out <file> --only siting   the heightmap part only (seconds)
  python tools/dungeon_draw_audit.py --out <file> --only draw     the simulator part only (minutes)
  python tools/dungeon_draw_audit.py --mutate NAME --out <file>   rebuild from the mutation NAME and run the draw part

What this does NOT cover (CLAUDE.md "Our list is not the world"; testing.md): any of it in a running Minecraft. That
`random value 0..2^30-1` and `scoreboard players operation %=` behave in a function on a server as the simulator models
them, that a rip's click reaches its door through the advancement reward, that the oval stands where the siting says,
and that a tree or a mod structure is not in a plane. Nether rips are not sited (DUNGEON_DRAW.md section 5). The co-op
party draw (2.5) is deferred and unbuilt. The siting is checked against data/ and the heightmap, never against a world.
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import math
import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data"
OW = "minecraft:overworld"
OLD_TEST_RIPS_COMMIT = "6249332e"   # the 13 test rips' positions, as the owner played them (git show 6249332e:data/dungeons.json)
MAP = 8192

# the spec's numbers (DUNGEON_DRAW.md 2.6), written here and not read from the tool under audit
CLEARANCE = 30          # blocks from every authored data/ coordinate
SPAWN_FREE_MARGIN = 0   # "No rip inside a spawn-free town precinct": the footprint must not touch one

BAND_CAPS = {1: (1, 25), 2: (26, 35), 3: (36, 45), 4: (46, 55), 5: (56, 62), 6: (63, 100)}   # DUNGEON_DRAW.md 1 / 2.2: the cap that makes each band
CAP_FOR_BAND = {1: 20, 2: 30, 3: 40, 4: 50, 5: 60, 6: 100}

# the dungeons the draw draws from, by roster id; the roster also lists three that are not built (cistern, temple_calendar,
# zero_dig): the audit only judges the ones in data/dungeons.json
ROSTER = DATA / "dungeon_prize_roster.json"


# ------------------------------------------------------------------------------------------------- the spec's expectations


def roster_expectations(roster=None, built_ids=None):
    """{dungeon id: (first_band, gate flag id or None)} from the roster's own fields. The roster's gate is prose such as
    'gym8_cleared (proposed, ...)': the flag is the leading token."""
    roster = roster if roster is not None else json.loads(ROSTER.read_text(encoding="utf-8"))
    out = {}
    for d in roster["dungeons"]:
        if built_ids is not None and d["id"] not in built_ids:
            continue
        g = d.get("gate")
        flag = None
        if g:
            m = re.match(r"([a-z0-9_]+_cleared)\b", g)
            if not m:
                raise ValueError("roster gate %r of %s does not start with a flag" % (g, d["id"]))
            flag = m.group(1)
        out[d["id"]] = (int(d["first_band"]), flag)
    return out


def eligible(band, held, expect):
    """The spec's rule (2.2): in the draw at band B when first_band <= B and the gate flag, if any, is held."""
    return {i for i, (fb, flag) in expect.items() if fb <= band and (flag is None or flag in held)}


# ------------------------------------------------------------------------------------------------- siting (heightmap, data)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _walk(obj, out, src):
    """Every authored coordinate: a dict with numeric x and z (or cx, cz); a list of two numbers read as (x, z); a list of three
    read as (x, y, z). A list of four is a BOX, an area and not a coordinate: boxes are held by the precinct and the gated-zone
    checks, where 'inside' is what matters. Over-inclusive otherwise on purpose: a stray list of small numbers is a false point
    near the map's corner, not a missed one."""
    if isinstance(obj, dict):
        for kx, kz in (("x", "z"), ("cx", "cz")):
            if _num(obj.get(kx)) and _num(obj.get(kz)):
                out.append((float(obj[kx]), float(obj[kz]), src))
        for v in obj.values():
            _walk(v, out, src)
    elif isinstance(obj, list):
        if obj and all(_num(v) for v in obj):
            if len(obj) == 2:
                out.append((float(obj[0]), float(obj[1]), src))
            elif len(obj) == 3:
                out.append((float(obj[0]), float(obj[2]), src))
            return
        for v in obj:
            _walk(v, out, src)


def authored_points(data_dir=DATA, skip_files=(), drop=None):
    """[(x, z, file)] for every coordinate in data/*.json and data/*/*.json. `drop(rel, doc)` may edit a document first (the
    rips' own probes are the rips' coordinates over again)."""
    out = []
    files = sorted(glob.glob(str(Path(data_dir) / "*.json"))) + sorted(glob.glob(str(Path(data_dir) / "*" / "*.json")))
    for f in files:
        rel = Path(f).relative_to(Path(data_dir).parent).as_posix()
        if rel in skip_files:
            continue
        doc = json.loads(Path(f).read_text(encoding="utf-8"))
        if drop:
            drop(rel, doc)
        pts = []
        _walk(doc, pts, rel)
        out += [p for p in pts if 0 <= p[0] < MAP and 0 <= p[1] < MAP]
    return out


def _drop_rip_probes(rel, doc):
    if rel == "data/world_probes.json":
        doc.get("places", {}).pop("dungeon_rips", None)


def ring_contains(ring, x, z):
    c, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, zi = ring[i][0], ring[i][1]
        xj, zj = ring[j][0], ring[j][1]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / float(zj - zi) + xi:
            c = not c
        j = i
    return c


def polys_contain(polys, x, z):
    return any(ring_contains(r, x, z) for r in polys)


def footprint(r):
    """(x0, z0, x1, z1) of what a rip occupies: its plane (x0..x1 at z), the click one in front and the exit point three in
    front. Read from the record's own frame/click/outside, not from the tool's window."""
    f = r["frame"]
    xs = [f["x0"], f["x1"], r["click"][0], math.floor(r["outside"][0])]
    zs = [f["z"], r["click"][2], math.floor(r["outside"][2])]
    return (min(xs), min(zs), max(xs), max(zs))


def box_gap(a, b):
    """Edge-to-edge distance between two boxes (x0, z0, x1, z1), 0 when they touch or overlap."""
    return math.hypot(max(a[0] - b[2], 0, b[0] - a[2]), max(a[1] - b[3], 0, b[1] - a[3]))


def point_gap(box, x, z):
    return math.hypot(max(box[0] - x, 0, x - box[2]), max(box[1] - z, 0, z - box[3]))


def water_world(data_dir=DATA):
    """(sea level, [(level_y, basin rings)]) read from data/world.json and data/landmarks.json."""
    w = json.loads((Path(data_dir) / "world.json").read_text(encoding="utf-8"))
    sea = int(w["vertical"]["sea_level"])
    lakes = []
    for l in json.loads((Path(data_dir) / "landmarks.json").read_text(encoding="utf-8"))["landmarks"]:
        wb = l.get("water_body") or {}
        if wb.get("level_y") is not None and wb.get("basin_polygons"):
            lakes.append((int(wb["level_y"]), [[tuple(q) for q in ring] for ring in wb["basin_polygons"]]))
    return sea, lakes


def precinct_boxes(data_dir=DATA):
    """[(x0, z0, x1, z1, label)]: the spawn-free zones and every town footprint, as data/ authors them."""
    out = []
    sup = json.loads((Path(data_dir) / "spawn_suppression.json").read_text(encoding="utf-8"))
    for z in sup.get("spawn_free_zones") or []:
        b = z["box"]
        out.append((b[0], b[1], b[2], b[3], "spawn_free_zone " + z["id"]))
    for t in json.loads((Path(data_dir) / "towns.json").read_text(encoding="utf-8"))["towns"]:
        f = t.get("footprint") or {}
        if all(k in f for k in ("min_x", "min_z", "max_x", "max_z")):
            out.append((f["min_x"], f["min_z"], f["max_x"], f["max_z"], "town " + t["id"]))
    return out


def region_polygons(data_dir=DATA):
    return {r["id"]: r["polygons"] for r in json.loads((Path(data_dir) / "regions.json").read_text(encoding="utf-8"))["regions"]}


def siting_problems(rips, ground, sea, lakes, points, boxes, regions, clearance=CLEARANCE, notes=None):
    """[problem] for a list of rips: dry, `clearance` blocks from every point, outside every precinct, inside its own
    region. All inputs are values, so a fixture can hand it a synthetic world with hand-computable answers. The test-trail
    rips are exempt from the clearance only (they were sited by the owner's play on the old mine's trail, not by the rule);
    they are held to dry, precinct and region."""
    bad = []
    for r in rips:
        rid = r["id"]
        fp = footprint(r)
        test = r.get("kind") == "test_trail"
        wet = None
        for x in range(fp[0], fp[2] + 1):
            for z in range(fp[1], fp[3] + 1):
                gy = ground(x, z)
                if gy < sea:
                    wet = (x, z, "sea", gy, sea)
                for level, basin in lakes:
                    if gy < level and polys_contain(basin, x, z):
                        wet = (x, z, "a lake", gy, level)
                if wet:
                    break
            if wet:
                break
        if wet:
            bad.append("%s: (%d, %d) is under %s: ground y%d, water y%d" % (rid, wet[0], wet[1], wet[2], wet[3], wet[4]))
        if not test:
            g = ground(r["click"][0], r["click"][2])
            if r["frame"]["y"] != g + 1:
                bad.append("%s: frame.y %d is not round(ground) + 1 = %d" % (rid, r["frame"]["y"], g + 1))
            near = min(((point_gap(fp, p[0], p[1]), p) for p in points), key=lambda t: t[0], default=(float("inf"), None))
            if near[0] < clearance:
                bad.append("%s: authored (%d, %d) in %s is %.1f blocks from the footprint; the rule is %d"
                           % (rid, near[1][0], near[1][1], near[1][2], near[0], clearance))
        for b in boxes:
            if box_gap(fp, b) <= SPAWN_FREE_MARGIN:
                bad.append("%s: the footprint touches %s" % (rid, b[4]))
        # the test rips stand where the owner played them (DUNGEON_DRAW.md 2.6: they stay until the owner has played): a region
        # defect of theirs is a NOTE for the owner, not a failure of the siting rule they were never sited by
        sink = notes if (test and notes is not None) else bad
        polys = regions.get(r.get("region"))
        if polys is None:
            sink.append("%s: region %r is not in data/regions.json" % (rid, r.get("region")))
        else:
            for x, z in ((fp[0], fp[1]), (fp[2], fp[1]), (fp[0], fp[3]), (fp[2], fp[3])):
                if not polys_contain(polys, x, z):
                    sink.append("%s: footprint corner (%d, %d) is outside region %s" % (rid, x, z, r["region"]))
                    break
    return bad


def old_test_rip_positions(old_doc, rips):
    """[problem]: the 13 test rips' frame, click and outside against the dungeon records of 6249332e (`old_doc`), matched by
    legacy_dungeon, not by order."""
    bad = []
    by_dungeon = {r.get("legacy_dungeon"): r for r in rips if r.get("kind") == "test_trail"}
    for d in old_doc["dungeons"]:
        old = d["rip"]
        new = by_dungeon.get(d["id"])
        if new is None:
            bad.append("test rip for %s: gone" % d["id"])
            continue
        for k in ("frame", "click", "outside"):
            if new[k] != old[k]:
                bad.append("test rip for %s: %s was %r, is %r" % (d["id"], k, old[k], new[k]))
    if len(by_dungeon) != len(old_doc["dungeons"]):
        bad.append("%d test rips, 6249332e had %d" % (len(by_dungeon), len(old_doc["dungeons"])))
    return bad


def run_siting(out):
    import ground as G
    g = G.load()
    rips = json.loads((DATA / "dungeon_rips.json").read_text(encoding="utf-8"))["rips"]
    sea, lakes = water_world()
    pts = authored_points(skip_files=("data/dungeon_rips.json",), drop=_drop_rip_probes)
    notes = []
    if not pts:
        raise RuntimeError("the walk over data/ found no authored coordinate: every clearance would pass vacuously")
    bad = siting_problems(rips, g, sea, lakes, pts, precinct_boxes(), region_polygons(), notes=notes)
    out["siting_notes"] = notes
    out["siting"] = {"rips": len(rips), "region_rips": sum(r["kind"] == "region" for r in rips), "points_read": len(pts)}
    import subprocess
    old = subprocess.run(["git", "show", "%s:data/dungeons.json" % OLD_TEST_RIPS_COMMIT], cwd=str(ROOT), capture_output=True, text=True)
    if old.returncode != 0:
        out["siting"]["old_positions"] = "NOT_EXECUTED: git show %s failed: %s" % (OLD_TEST_RIPS_COMMIT, old.stderr.strip()[:200])
    else:
        bad += old_test_rip_positions(json.loads(old.stdout), rips)
        out["siting"]["old_positions"] = "checked"
    zones = json.loads((DATA / "rift_zones.json").read_text(encoding="utf-8"))
    bad += gated_zone_problems(rips, zones)
    bad += ["siting tool: " + p for p in sc_siting_tool_rejects_sites_that_break_a_rule(load_rips_module(None), g)]
    # a keep-out the owner drew for the far south's own places: a note for the owner, not a rule of the spec (the box says it
    # binds "the far south's own places"; a rip is not one)
    regs = region_polygons()
    notes += ["D5 (about one rip per region): region %s has no rip" % rid for rid in sorted(regs) if rid not in {r.get("region") for r in rips}]
    out["siting"]["regions"] = len(regs)
    fs = json.loads((DATA / "far_south.json").read_text(encoding="utf-8"))["rules"]["keep_out_box"]["box"]
    notes += ["%s: stands inside data/far_south.json rules.keep_out_box %s" % (r["id"], fs) for r in rips if box_gap(footprint(r), tuple(fs)) == 0]
    return bad


# ------------------------------------------------------------------------------------------------- gated zones (data/rift_zones.json)


def gated_zone_problems(rips, rift_zones):
    """[problem]: a rip whose footprint stands inside a box of a rift zone whose `pass` needs badges or a flag. Those zones span
    the whole height (rift_zones.json `y` -64..575), so a player short of the pass is turned back from every column of
    them: a rip there is not a find for the early bands (DUNGEON_DRAW.md 2.6 'a rip is a find, not a queue')."""
    bad = []
    for zid, z in sorted((rift_zones.get("zones") or {}).items()):
        if not isinstance(z, dict) or not z.get("pass") or not z.get("boxes"):
            continue
        for r in rips:
            fp = footprint(r)
            for b in z["boxes"]:
                if box_gap(fp, tuple(b[:4])) == 0:
                    p = z["pass"]
                    bad.append("%s: the footprint stands inside rift zone %s (%s), whose pass is %s %s; a player without it is turned back"
                               % (r["id"], zid, z.get("name"), p.get("kind"), p.get("threshold", "")))
                    break
    return bad


# ------------------------------------------------------------------------------------------------- the simulator part


SPEC_CAPS = {20: 1, 25: 1, 30: 2, 35: 2, 40: 3, 45: 3, 50: 4, 55: 4, 60: 5, 62: 5, 100: 6}   # DUNGEON_DRAW.md 1: band by RCT cap
ALL_FLAGS = ("gym6_cleared", "gym8_cleared", "champion_cleared")
PLAYTEST_TAG = "cobblers.dg_playtest"       # DUNGEON_DRAW.md 5 and STATE: staging only
# the names the scenarios read; each is checked to exist in the pack before a scenario runs, so a rename fails closed
CONTRACT = ("dg.st", "dg.dun", "dg.rip", "dg.band", "dg.ptdun", "dg.up", "dg.own")
# functions the draw path never calls: a room, a shell, a block placement. They are 99 per cent of the pack's bytes.
SKIP_FILES = re.compile(r"/(room|shells|place)(/|\.)|/place/|/lure|/reset\.")


def load_sim():
    """(DW, FAKES, PS): tests/test_dungeon.py's simulator subclass, without building a pack. That module builds the whole
    dungeon pack when imported (minutes), so it is imported with the build stubbed and removed from sys.modules again, which
    leaves a later real import (pytest's own) to build as it always did."""
    sys.path.insert(0, str(ROOT / "tests"))
    import dungeon as D
    import pocket_sim as PS
    if "test_dungeon" in sys.modules:
        TD = sys.modules["test_dungeon"]
    else:
        real = D.build
        D.build = lambda doc, **kw: {}
        try:
            import test_dungeon as TD
        finally:
            D.build = real
            sys.modules.pop("test_dungeon", None)
    return TD.DW, TD.FAKES, PS


def load_module(mutation=None):
    """The dungeon generator: the real tools/dungeon.py, or a MUTATED COPY of its source compiled as module `dungeon_mut`.
    data/ is untouched in both: a mutation of the generator is the only kind that tests independence."""
    import dungeon as D
    if not mutation:
        return D
    old, new = MUTATIONS[mutation]["edit"]
    src = (ROOT / "tools" / "dungeon.py").read_text(encoding="utf-8")
    if src.count(old) != 1:
        raise RuntimeError("mutation %s: its target text occurs %d times in tools/dungeon.py (want 1); the generator changed, "
                           "update the mutation, do not loosen it" % (mutation, src.count(old)))
    mod = type(sys)("dungeon_mut")
    mod.__file__ = str(ROOT / "tools" / "dungeon.py")
    exec(compile(src.replace(old, new), mod.__file__, "exec"), mod.__dict__)
    return mod


class Env:
    """One simulated world over one built pack, shared by the scenarios (a fresh player and fresh slots for each)."""

    def __init__(self, files, doc, tmp):
        DW, FAKES, PS = load_sim()
        self.PS, self.doc = PS, doc
        self.ds = [d["id"] for d in doc["dungeons"]]
        self.shorts = {d["id"]: d["short"] for d in doc["dungeons"]}
        self.rips = doc["rips"]
        self.sig = doc["engine"]["sigils"]["ladder"]
        self.lockout = doc["engine"]["lockout_ticks"]
        self.keeper = doc["engine"]["keeper"]["period_ticks"]
        self.files = files
        out = Path(tmp)
        n = 0
        for path, text in files.items():
            if SKIP_FILES.search("/" + path):
                continue
            f = out / path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
            n += 1
        self.written = n
        fakes = dict(FAKES)
        fakes["cobblers:levelcap/battle_check"] = ["$scoreboard players operation @s cobblers.lc_cap = @s capwant$(x)"]
        for s in doc_slots(doc):
            fakes["cobblers:dungeons/slot/s%d/reset" % s] = ["# the slot's block reset, not under test here"]
        w = DW(out, fakes)
        w.objectives |= {"cobblers.lc_cap", "tailend", "stale", "capwant"}
        w.boot()
        self.w = w
        blob = "\n".join(t for p, t in files.items() if p.endswith(".mcfunction"))
        self.missing = [o for o in CONTRACT if o not in blob]
        self.rip_fn = rip_click_functions(files, self.rips)
        self.n_players = 0

    def lk(self, did):
        return "dg.lk_%s" % self.shorts[did]

    def fresh(self):
        """Free every slot, restart the uptime well above any lockout, drop every player."""
        w = self.w
        for (h, o) in list(w.scores):
            if o == "dg.own":
                w.scores[(h, o)] = 0
        w.set("#up", "dg.up", 1_000_000)
        for p in list(w.players()):
            w.ents.remove(p)
        w.random_values.clear()

    def player(self, band_cap=20, flags=(), tags=(), sigils=200, sigil_band=None, at=None):
        self.n_players += 1
        r = at or self.rips[0]
        sb = sigil_band or SPEC_CAPS[band_cap]
        p = self.w.player("A%d" % self.n_players, "minecraft:overworld", tuple(r["outside"][:3]),
                          advancements=["cobblers:flag/%s" % f for f in flags])
        p.tags.update(tags)
        if sigils:
            p.inventory.append([self.sig[sb - 1]["item"], {"cobblers_dg_sigil": sb}, sigils])
        self.w.set(p.name, "capwant", band_cap)
        return p

    def sigil_count(self, p):
        return sum(i[2] for i in p.inventory if i[0] in {s["item"] for s in self.sig})

    def click(self, p, rip=None):
        r = rip or self.rips[0]
        self.w.call(self.rip_fn[r["id"]], self.PS.Ctx(p, p.dim, p.pos))

    def entered(self, p):
        """The dungeon id the last click opened for p, else None (refused)."""
        if self.w.get(p.name, "dg.st") != 1:
            return None
        n = self.w.get(p.name, "dg.dun")
        return self.ds[n - 1] if n else None

    def backout(self, p):
        """What the player does after the draw, in the way the game offers: the back rip, once the arrival has put them in the
        entry room (dg.st 2). The slot is freed by the run's own end (m/end), the sigil refunded. Time passes a keeper pass."""
        w = self.w
        w.set(p.name, "dg.st", 2)
        w.call("cobblers:dungeons/back", self.PS.Ctx(p, p.dim, p.pos))
        w.set("#up", "dg.up", w.get("#up", "dg.up") + self.keeper)

    def draws(self, p, n, rip=None):
        out = []
        for _ in range(n):
            self.click(p, rip)
            d = self.entered(p)
            out.append(d)
            if d is None:
                break
            self.backout(p)
        return out

    def last_door(self):
        """The short whose own door the last click called, from the simulator's call log (a refusal is logged too)."""
        for name, _who in reversed(self.w.calls):
            m = re.fullmatch(r"cobblers:dungeons/door/([a-z0-9]+)", name)
            if m and not m.group(1).startswith(("rip_", "refuse_", "go_")):
                return m.group(1)
        return None


def doc_slots(doc):
    """Global slot numbers 1..N: engine.slots.per_dungeon for each dungeon, in file order (data/dungeons.json engine.slots.why)."""
    return list(range(1, doc["engine"]["slots"]["per_dungeon"] * len(doc["dungeons"]) + 1))


def rip_click_functions(files, rips):
    """{rip id: reward function id}: the function a right-click on the rip's interaction runs, found the way
    the game finds it and without the generator's naming: the interaction summoned at the rip's click (in a rips/ function),
    the tag it carries that an advancement's click criterion listens for, and that advancement's reward."""
    listens = {}
    for path, text in files.items():
        if path.startswith("data/cobblers/advancement/dungeons/") and path.endswith(".json"):
            j = json.loads(text)
            crit = (j.get("criteria") or {}).get("click")
            if crit:
                nbt = crit["conditions"]["entity"][0]["predicate"].get("nbt", "")
                for t in re.findall(r'"([^"]+)"', nbt):
                    listens[t] = j["rewards"]["function"]
    summons = []
    for path, text in files.items():
        if "/rips/" in path and path.endswith(".mcfunction"):
            for m in re.finditer(r"summon minecraft:interaction (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) \{[^\n]*?Tags:\[([^\]]*)\]", text):
                summons.append((float(m.group(1)), float(m.group(2)), float(m.group(3)), re.findall(r'"([^"]+)"', m.group(4))))
    out = {}
    for r in rips:
        x, y, z = r["click"]
        for sx, sy, sz, tags in summons:
            if abs(sx - (x + 0.5)) < 0.01 and abs(sy - y) < 0.01 and abs(sz - (z + 0.5)) < 0.01:
                fns = {listens[t] for t in tags if t in listens}
                if len(fns) == 1:
                    out[r["id"]] = fns.pop()
    return out


# ------------------------------------------------------------------------------------------------- the scenarios
# Each returns [problem]. The expectation is derived from the spec and the roster in the scenario, never from the generator.


def _permutation_windows(seq, want):
    """[problem]: every run of len(want) consecutive draws must be each wanted dungeon exactly once (least recently entered
    wins: with n candidates and nothing else changing, the draw is a rotation through all n before any repeat)."""
    n = len(want)
    bad = []
    for i in range(0, len(seq) - n + 1):
        if sorted(seq[i:i + n]) != sorted(want):
            bad.append("draws %d..%d are %s, not each of %s once" % (i + 1, i + n, seq[i:i + n], sorted(want)))
            break
    return bad


def sc_band_from_cap(env, expect):
    bad = []
    for cap, band in SPEC_CAPS.items():
        env.fresh()
        p = env.player(cap, ALL_FLAGS)
        env.click(p)
        if env.entered(p) is None:
            bad.append("cap %d: a click with the right sigil and every flag was refused" % cap)
            continue
        got = env.w.get(p.name, "dg.band")
        if got != band:
            bad.append("cap %d: the band is %s, the spec's is %d" % (cap, got, band))
    return bad


def sc_reachable_sets(env, expect):
    """For every flag set and every band: the dungeons the draw can open are EXACTLY those the spec makes eligible (first_band
    at or under the band, the gate held), and each is reached within three rotations."""
    bad = []
    caps = (20, 30, 40, 50, 60, 100)
    flagsets = [()] + [(f,) for f in ALL_FLAGS] + [("gym6_cleared", "gym8_cleared"), ALL_FLAGS]
    for fl in flagsets:
        for cap in caps:
            band = SPEC_CAPS[cap]
            want = eligible(band, set(fl), expect)
            env.fresh()
            p = env.player(cap, fl)
            got = env.draws(p, 3 * len(want) + 2)
            if None in got:
                bad.append("band %d flags %s: a click was refused with a sigil and %d eligible dungeons" % (band, list(fl), len(want)))
                continue
            if set(got) != want:
                bad.append("band %d flags %s: drew %s; extra %s, never drawn %s"
                           % (band, list(fl), sorted(set(got)), sorted(set(got) - want), sorted(want - set(got))))
            bad += ["band %d flags %s: %s" % (band, list(fl), m) for m in _permutation_windows(got, want)]
    return bad


def sc_every_band_has_a_candidate(env, expect):
    bad = []
    for band in range(1, 7):
        if not eligible(band, set(ALL_FLAGS), expect):
            bad.append("band %d has no candidate in the roster" % band)
    return bad


def sc_lockout_skips(env, expect):
    bad = []
    band1 = sorted(eligible(1, set(), expect))
    for locked in band1:
        env.fresh()
        p = env.player(20)
        up = env.w.get("#up", "dg.up")
        env.w.set(p.name, env.lk(locked), up - 1000)          # entered 1000 ticks ago, the lockout is an hour
        got = env.draws(p, 2 * len(band1))
        if None in got:
            bad.append("%s locked out: a click was refused although four others are open" % locked)
        elif locked in got:
            bad.append("%s locked out an hour and drawn anyway: %s" % (locked, got))
        elif set(got) != set(band1) - {locked}:
            bad.append("%s locked out: the others drawn were %s" % (locked, sorted(set(got))))
        env.w.set(p.name, env.lk(locked), env.w.get("#up", "dg.up") - 10 * env.lockout)   # long past
        if locked not in env.draws(p, 2 * len(band1)):
            bad.append("%s was never drawn again after its lockout ran out" % locked)
    # every open dungeon locked out: the click is refused, nothing is taken and it is not a draw
    env.fresh()
    p = env.player(20)
    up = env.w.get("#up", "dg.up")
    for d in band1:
        env.w.set(p.name, env.lk(d), up - 1000)
    before = env.sigil_count(p)
    env.click(p)
    if env.entered(p) is not None:
        bad.append("every band-1 dungeon locked out and a click still opened %s" % env.entered(p))
    if env.sigil_count(p) != before:
        bad.append("a click refused for the lockout took a sigil")
    return bad


def sc_full_falls_through(env, expect):
    bad = []
    band1 = sorted(eligible(1, set(), expect))
    per = env.doc["engine"]["slots"]["per_dungeon"]
    for full in band1:
        env.fresh()
        idx = env.ds.index(full) + 1
        for k in range(per):                                    # the playtest path names the dungeon: it fills the slots
            t = env.player(20, tags=(PLAYTEST_TAG,))
            env.w.set(t.name, "dg.ptdun", idx)
            env.click(t)
            if env.entered(t) != full:
                bad.append("could not seat occupant %d in %s through the playtest path: %s" % (k + 1, full, env.entered(t)))
                break
        p = env.player(20)
        got = env.draws(p, 2 * len(band1))
        if None in got or full in got or set(got) != set(band1) - {full}:
            bad.append("%s full: a regular player drew %s" % (full, got))
    env.fresh()
    idxs = [env.ds.index(d) + 1 for d in band1]
    for idx in idxs:
        for _ in range(per):
            t = env.player(20, tags=(PLAYTEST_TAG,))
            env.w.set(t.name, "dg.ptdun", idx)
            env.click(t)
    p = env.player(20)
    before = env.sigil_count(p)
    env.click(p)
    if env.entered(p) is not None:
        bad.append("every band-1 dungeon full and a click still opened %s" % env.entered(p))
    if env.sigil_count(p) != before:
        bad.append("a click refused for busy slots took a sigil")
    return bad


def sc_ties_are_random(env, expect, trials=400):
    """Five never-drawn band-1 dungeons tie. Over `trials` independent first clicks each must come up about trials/5 times.
    The bound is 5 standard deviations of a fair draw (sd = sqrt(400 * .2 * .8) = 8 around 80), not a number fitted to the data."""
    band1 = sorted(eligible(1, set(), expect))
    n = len(band1)
    env.fresh()
    counts = {d: 0 for d in band1}
    rolls0 = len(env.w.random_log)
    for _ in range(trials):
        p = env.player(20)
        env.click(p)
        d = env.entered(p)
        if d is not None:
            counts[d] += 1
            env.backout(p)
        env.w.ents.remove(p)
    bad = []
    mean = trials / float(n)
    sd = (trials * (1.0 / n) * (1 - 1.0 / n)) ** 0.5
    for d, c in counts.items():
        if abs(c - mean) > 5 * sd:
            bad.append("tie-break: %s was drawn %d of %d first clicks; a fair draw gives %.0f +- %.0f" % (d, c, trials, mean, 5 * sd))
    if len(env.w.random_log) - rolls0 < trials // 2:
        bad.append("tie-break: %d random rolls for %d tied draws" % (len(env.w.random_log) - rolls0, trials))
    return bad


def _door_dungeon(env, short):
    return next((d for d, s in env.shorts.items() if s == short), None)


def sc_refused_click_is_not_a_draw(env, expect):
    """A click that is refused takes nothing and does not count as a draw: with the same roll the next click that is let
    through opens the SAME dungeon the refused click would have, whatever the refusal was."""
    bad = []
    for label, weak in (("no sigil", False), ("a lower band's sigil", True)):
        env.fresh()
        cap = 30                                            # band 2
        p = env.player(cap, sigils=0)
        if weak:
            p.inventory.append([env.sig[0]["item"], {"cobblers_dg_sigil": 1}, 3])
        before = env.sigil_count(p)
        env.w.random_values[:] = [123456789]
        env.click(p)
        refused_to = _door_dungeon(env, env.last_door())
        if env.entered(p) is not None:
            bad.append("%s: the click was not refused" % label)
            continue
        if env.sigil_count(p) != before:
            bad.append("%s: a refused click changed the sigils from %d to %d" % (label, before, env.sigil_count(p)))
        if env.w.get(p.name, "dg.rip"):
            bad.append("%s: a refused click recorded a way out" % label)
        for _ in range(4):                                  # refusing again and again must not change what is next
            env.w.random_values[:] = [123456789]
            env.click(p)
        p.inventory[:] = [[env.sig[1]["item"], {"cobblers_dg_sigil": 2}, 5]]
        env.w.random_values[:] = [123456789]
        env.click(p)
        opened = env.entered(p)
        if opened is None:
            bad.append("%s: with the right sigil the click was still refused" % label)
        elif opened != refused_to:
            bad.append("%s: the refused click had drawn %s, the next click with the same roll opened %s: the refusal counted as a draw"
                       % (label, refused_to, opened))
    return bad


def sc_playtest_path(env, expect):
    bad = []
    ab = env.ds.index("ash_bell") + 1
    env.fresh()
    p = env.player(60, tags=(PLAYTEST_TAG,))
    env.w.set(p.name, "dg.ptdun", ab)
    env.click(p)
    if env.entered(p) != "ash_bell":
        bad.append("the playtest tag with dg.ptdun = ash_bell opened %s (gate bypass is the playtest path)" % env.entered(p))
    env.fresh()
    q = env.player(60)
    env.w.set(q.name, "dg.ptdun", ab)
    got = env.draws(q, 12)
    if "ash_bell" in got:
        bad.append("without the playtest tag, dg.ptdun forced or opened a gated dungeon: %s" % got)
    return bad


def sc_every_rip_draws_and_leaves_by_itself(env, expect):
    bad = []
    if len(env.rip_fn) != len(env.rips):
        bad.append("%d of %d rips have a click that reaches a function (an interaction at the click carrying a tag an advancement "
                   "listens for)" % (len(env.rip_fn), len(env.rips)))
    if len(set(env.rip_fn.values())) != len(env.rip_fn):
        bad.append("two rips share a click function")
    for k, r in enumerate(env.rips, 1):
        if r["id"] not in env.rip_fn:
            continue
        env.fresh()
        p = env.player(20)
        p.pos = [0.5, 200.0, 0.5]
        have = env.sigil_count(p)
        env.click(p, r)
        d = env.entered(p)
        if d is None:
            bad.append("%s: a click with a sigil at band 1 opened nothing" % r["id"])
            continue
        if env.w.get(p.name, "dg.rip") != k:
            bad.append("%s: dg.rip is %s, its place in data/dungeon_rips.json is %d" % (r["id"], env.w.get(p.name, "dg.rip"), k))
        if env.sigil_count(p) != have - 1:
            bad.append("%s: one entry took %d sigils" % (r["id"], have - env.sigil_count(p)))
        env.backout(p)
        want = [float(v) for v in r["outside"][:3]]
        if p.dim != OW or any(abs(a - b) > 0.01 for a, b in zip(p.pos, want)):
            bad.append("%s: the way out left the player at %s in %s, not at the rip's outside %s" % (r["id"], [round(v, 2) for v in p.pos], p.dim, want))
        if env.sigil_count(p) != have:
            bad.append("%s: the back rip did not refund the sigil (%d of %d)" % (r["id"], env.sigil_count(p), have))
    return bad


def sc_rips_are_placed(env, expect):
    """R16DR places every rip in data/dungeon_rips.json: its blocks (the themed patch under the oval, at the oval's middle
    column), its interaction at the click, and its oval; and the reapply step list carries the step with the right count."""
    files, bad = env.files, []
    blocks = {}
    for path, text in files.items():
        if path.startswith("data/cobblers/function/dungeons/rips/blocks_"):
            for m in re.finditer(r"^setblock (-?\d+) (-?\d+) (-?\d+) ", text, re.M):
                blocks.setdefault(path, set()).add(tuple(int(v) for v in m.groups()))
    place = files.get("data/cobblers/function/dungeons/rips/place.mcfunction", "")
    called = set(re.findall(r"function cobblers:dungeons/(rips/blocks_[a-z0-9_]+)", place))
    ovals = []
    for path, text in files.items():
        if "/rips/" in path and path.endswith(".mcfunction"):
            for m in re.finditer(r"summon minecraft:item_display (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)", text):
                ovals.append(tuple(float(v) for v in m.groups()))
    for r in env.rips:
        f = r["frame"]
        mid = (f["x0"] + f["x1"]) // 2
        cell = (mid, f["y"] - 1, f["z"] + 1)
        homes = [p for p, cells in blocks.items() if cell in cells]
        if len(homes) != 1:
            bad.append("%s: the patch under the oval (%s) is set by %d rips/blocks_* functions" % (r["id"], cell, len(homes)))
        elif homes[0][len("data/cobblers/function/dungeons/"):-len(".mcfunction")] not in called:
            bad.append("%s: its blocks function is not called by rips/place, so R16DR never lays it" % r["id"])
        if not any(abs(ox - (mid + 0.5)) < 0.01 and f["z"] + 1 <= oz <= f["z"] + 2 and f["y"] <= oy <= f["y"] + 4 for ox, oy, oz in ovals):
            bad.append("%s: no oval is summoned in front of its opening" % r["id"])
    if len(called) != len(env.rips):
        bad.append("rips/place calls %d blocks functions for %d rips" % (len(called), len(env.rips)))
    return bad


def sc_reapply_wires_r16dr(env, expect, mod):
    bad = []
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    if "DG.reapply_steps()" not in src:
        bad.append("tools/reapply.py does not extend its step list with dungeon.reapply_steps()")
    steps = mod.reapply_steps(env.doc)
    r16dr = [s for s in steps if s[0] == "R16DR"]
    if len(r16dr) != 1:
        bad.append("%d R16DR steps" % len(r16dr))
    else:
        m = re.search(r"(\d+) rips", r16dr[0][1])
        if not m or int(m.group(1)) != len(env.rips):
            bad.append("R16DR says %s rips, data/dungeon_rips.json has %d" % (m and m.group(1), len(env.rips)))
        if ("fn", "cobblers:dungeons/rips/place") not in r16dr[0][2]:
            bad.append("R16DR does not run cobblers:dungeons/rips/place")
    return bad


def sc_record_matches_roster(env, expect):
    """data/dungeons.json carries, for each dungeon, the first_band and gate the roster proposes (the owner took them as written)."""
    bad = []
    for d in env.doc["dungeons"]:
        fb, flag = expect[d["id"]]
        if d.get("first_band") != fb:
            bad.append("%s: first_band %s, the roster's is %d" % (d["id"], d.get("first_band"), fb))
        want = "cobblers:flag/%s" % flag if flag else None
        if d.get("gate_flag") != want:
            bad.append("%s: gate_flag %s, the roster's is %s" % (d["id"], d.get("gate_flag"), want))
    if env.lockout != 72000:
        bad.append("engine.lockout_ticks is %d, the spec's one hour of uptime is 72000" % env.lockout)
    return bad


SCENARIOS = (
    ("record_matches_roster", sc_record_matches_roster),
    ("every_band_has_a_candidate", sc_every_band_has_a_candidate),
    ("band_from_cap", sc_band_from_cap),
    ("reachable_sets", sc_reachable_sets),
    ("lockout_skips", sc_lockout_skips),
    ("full_falls_through", sc_full_falls_through),
    ("ties_are_random", sc_ties_are_random),
    ("refused_click_is_not_a_draw", sc_refused_click_is_not_a_draw),
    ("playtest_path", sc_playtest_path),
    ("every_rip_draws_and_leaves_by_itself", sc_every_rip_draws_and_leaves_by_itself),
    ("rips_are_placed", sc_rips_are_placed),
)


# ------------------------------------------------------------------------------------------------- mutations of the GENERATOR
# Each edits ONE spot of tools/dungeon.py's source (data/ untouched) and must make run_draw return problems.

_STAMP = '"scoreboard players operation @s %s = #up %s" % (dr_obj(d), O["up"]),'

MUTATIONS = {
    "floor_one_band_low": {
        "why": "a dungeon is drawn one band below its first_band (the < for <= slip)",
        "edit": ('fb, gf = d.get("first_band", 1), d.get("gate_flag")', 'fb, gf = d.get("first_band", 1) - 1, d.get("gate_flag")')},
    "floor_one_band_high": {
        "why": "a dungeon is not drawn at its own first_band (the <= for < slip)",
        "edit": ('fb, gf = d.get("first_band", 1), d.get("gate_flag")', 'fb, gf = d.get("first_band", 1) + 1, d.get("gate_flag")')},
    "lockout_dropped": {
        "why": "the draw no longer skips a dungeon the player is locked out of",
        "edit": ('matches 0..%d run "', 'matches -2147483648..-%d run "')},
    "full_dropped": {
        "why": "the draw no longer skips a dungeon with no free slot",
        "edit": ('if score #f%d %s matches 1 unless', 'if score #f%d %s matches 0..1 unless')},
    "gate_inverted": {
        "why": "a gated dungeon is drawn only WITHOUT its flag",
        "edit": ('if entity @s[advancements={%s=true}] run scoreboard players set #c', 'unless entity @s[advancements={%s=true}] run scoreboard players set #c')},
    "gate_open_to_all": {
        "why": "the playtest bypass opens every gate to everyone who is not a playtester",
        "edit": ('if entity @s[tag=%s] run scoreboard players set #c%d', 'if entity @s[tag=!%s] run scoreboard players set #c%d')},
    "never_drawn_is_youngest": {
        "why": "a dungeon never drawn counts as the most recent, so the one just drawn wins again",
        "edit": ('"scoreboard players set #a%d %s 2147483000" % (i, O["t"]),', '"scoreboard players set #a%d %s 0" % (i, O["t"]),')},
    "refusal_stamps": {
        "why": "a refused click stamps the dungeon it drew, so the refusal counts as a draw",
        "edit": ('"execute unless score #why %s matches 0 run return run function %s" % (O["t"], F("door/refuse_%s" % sh)),',
                 _STAMP + '\n               "execute unless score #why %s matches 0 run return run function %s" % (O["t"], F("door/refuse_%s" % sh)),')},
    "backout_not_counted": {
        "why": "the draw is not stamped at the go, so a backed-out dungeon can be drawn again at once (a free re-roll)",
        "edit": (_STAMP, '"# mutated: no stamp",')},
    "way_out_is_the_dungeons": {
        "why": "the run does not remember which rip it was entered by, so m/out falls back to one fixed rip per dungeon",
        "edit": ('"execute if score #rip %s matches 1.. run scoreboard players operation @s %s = #rip %s" % (O["t"], O["rip"], O["t"]),',
                 '"# mutated: dg.rip not recorded",')},
    "tie_is_not_random": {
        "why": "the tie-break roll is always 0, so the first tied dungeon always wins",
        "edit": ('random value 0..1073741823', 'random value 0..0')},
}


# ------------------------------------------------------------------------------------------------- the siting TOOL, on sites of my own


RIPS_MUTATIONS = {
    "clearance_shrunk": {
        "why": "tools/dungeon_rips.py holds a site to 3 blocks from an authored coordinate instead of 30",
        "edit": ("CLEARANCE = 30\n", "CLEARANCE = 3\n")},
    "precinct_ignored": {
        "why": "tools/dungeon_rips.py no longer refuses a site beside a spawn-free zone or a town",
        "edit": ("        if box_distance(win, b) < CLEARANCE:", "        if False and box_distance(win, b) < CLEARANCE:")},
}


def load_rips_module(mutation=None):
    import dungeon_rips as R
    if not mutation:
        return R
    old, new = RIPS_MUTATIONS[mutation]["edit"]
    src = (ROOT / "tools" / "dungeon_rips.py").read_text(encoding="utf-8")
    if src.count(old) != 1:
        raise RuntimeError("mutation %s: its target text occurs %d times in tools/dungeon_rips.py (want 1)" % (mutation, src.count(old)))
    mod = type(sys)("dungeon_rips_mut")
    mod.__file__ = str(ROOT / "tools" / "dungeon_rips.py")
    exec(compile(src.replace(old, new), mod.__file__, "exec"), mod.__dict__)
    return mod


def sc_siting_tool_rejects_sites_that_break_a_rule(R, g=None):
    """tools/dungeon_rips.py is the tool that SITES the rips. Here it is handed sites made to break one rule each, with the
    ground from tools/ground.py, and must name each. The control is a real region rip with nothing near it. The distances are
    chosen from the spec's 30 and 300 (DUNGEON_DRAW.md 2.6), never from the tool's own constants."""
    import ground as G
    g = g or G.load()
    rips = json.loads((DATA / "dungeon_rips.json").read_text(encoding="utf-8"))["rips"]
    base = next(r for r in rips if r["id"] == "rip_pine_isles")
    f, rid, region = base["frame"], base["id"], base["region"]
    mx, z = (f["x0"] + f["x1"]) // 2, f["z"]
    polys = region_polygons()
    bad = []

    def run(frame=None, pts=(), boxes=(), polys_=None, others=(), reg=region):
        return R.site_problems(g, rid, reg, frame or f, list(pts), polys_ or polys, list(boxes), list(others))

    if run():
        bad.append("control: the real rip with no neighbours is refused: %s" % run()[:2])
    edge = mx + 4      # the footprint's east edge is x1 = mx + 2; the tool's own window runs to mx + 4: points beyond it are further from both
    if not any("authored" in p for p in run(pts=[(edge + 15.0, z + 2.0, "f")])):
        bad.append("an authored coordinate 15 blocks from the window is not refused (the spec's clearance is 30)")
    if run(pts=[(edge + 45.0, z + 2.0, "f")]):
        bad.append("an authored coordinate 45 blocks away is refused")
    if not run(boxes=[(edge + 1, z - 10, edge + 40, z + 10, "town x")]):
        bad.append("a town footprint one block from the window is not refused")
    if run(boxes=[(edge + 60, z - 10, edge + 90, z + 10, "town x")]):
        bad.append("a town footprint 60 blocks away is refused")
    if not run(polys_=polys, reg="the_rift"):
        bad.append("a rip outside the region it names is not refused")
    if not any("spread" in p for p in run(others=[("rip_other", mx + 100, z)])):
        bad.append("a region rip 100 blocks from another is not refused (the spread is 300)")
    if run(others=[("rip_other", mx + 400, z)]):
        bad.append("a region rip 400 blocks from another is refused")
    # wet ground: the first 9 x 7 window of flat sea floor found on a coarse walk of the heightmap, a column under the sea
    sea = water_world()[0]
    wet = None
    for zz in range(200, 8000, 64):
        for xx in range(200, 8000, 64):
            h = g.box(xx - 4, zz - 1, xx + 4, zz + 5)
            if int(h.max()) == int(h.min()) and int(h.min()) < sea - 10:
                wet = (xx, zz, int(h.min()))
                break
        if wet:
            break
    if wet is None:
        bad.append("NOT_EXECUTED: no flat sea-floor window found to test the dry rule")
    else:
        wf = {"x0": wet[0] - 2, "x1": wet[0] + 2, "z": wet[1], "y": wet[2] + 1, "height": 4}
        if not run(frame=wf):
            bad.append("a rip on the sea floor at (%d, %d), y%d, is not refused" % (wet[0], wet[1], wet[2]))
    return bad


def run_draw(mod, tmp):
    """(problems by scenario, facts): build the pack with `mod`, run every scenario on the simulator."""
    t0 = time.time()
    doc = mod.load()
    files = mod.build(doc)
    built = time.time() - t0
    expect = roster_expectations(built_ids={d["id"] for d in doc["dungeons"]})
    env = Env(files, doc, tmp)
    out = {}
    if env.missing:
        out["contract_names"] = ["the pack never mentions %s: a name the scenarios read was renamed" % ", ".join(env.missing)]
    for name, fn in SCENARIOS:
        t = time.time()
        try:
            out[name] = fn(env, expect)
        except Exception as e:                      # a function the pack lacks, an unsupported command: a finding, not a pass
            out[name] = ["the scenario raised %s: %s" % (type(e).__name__, str(e)[:300])]
        out[name + "__seconds"] = round(time.time() - t, 1)
    try:
        out["reapply_wires_r16dr"] = sc_reapply_wires_r16dr(env, expect, mod)
    except Exception as e:
        out["reapply_wires_r16dr"] = ["the scenario raised %s: %s" % (type(e).__name__, str(e)[:300])]
    facts = {"build_seconds": round(built, 1), "functions_written": env.written, "dungeons": len(env.ds), "rips": len(env.rips)}
    return out, facts


# ------------------------------------------------------------------------------------------------- the CLI


def failures(result):
    return {k: v for k, v in result.items() if isinstance(v, list) and v and not k.endswith("__seconds")}


def novel(base, mutated):
    """{scenario: [problem]}: the problems a MUTATED generator's run has that the unmutated run did not. A mutation is caught
    only by a problem that is new, so a defect the real generator already has cannot make a mutation look caught."""
    seen = {(k, p) for k, v in failures(base).items() for p in v}
    out = {}
    for k, v in failures(mutated).items():
        fresh = [p for p in v if (k, p) not in seen]
        if fresh:
            out[k] = fresh
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--out", required=True, help="where the full result is written (JSON)")
    ap.add_argument("--only", choices=("siting", "draw"), help="run one part")
    ap.add_argument("--mutate", help="comma list of mutation names, or 'all': rebuild from a mutated generator; the audit must FAIL")
    a = ap.parse_args(argv)
    result = {"audit": "dungeon draw", "spec": "docs/mechanics/DUNGEON_DRAW.md 2-4, data/dungeon_prize_roster.json"}
    verdict = []
    if a.mutate:
        names = list(MUTATIONS) + list(RIPS_MUTATIONS) if a.mutate == "all" else a.mutate.split(",")
        # the control first: the unmutated generator must pass, or a mutated failure proves nothing
        res = {}
        base = {}
        if any(n in MUTATIONS for n in names):
            with tempfile.TemporaryDirectory() as tmp:
                base, facts = run_draw(load_module(None), tmp)
        base["siting_tool"] = sc_siting_tool_rejects_sites_that_break_a_rule(load_rips_module(None))
        res["control"] = {"problems": sum(len(v) for v in failures(base).values()), "scenarios_failing": sorted(failures(base))}
        for n in names:
            if n in RIPS_MUTATIONS:
                got = {"siting_tool": sc_siting_tool_rejects_sites_that_break_a_rule(load_rips_module(n))}
                why = RIPS_MUTATIONS[n]["why"]
            else:
                with tempfile.TemporaryDirectory() as tmp:
                    got, _ = run_draw(load_module(n), tmp)
                why = MUTATIONS[n]["why"]
            f = novel(base, got)
            res[n] = {"caught": bool(f), "why": why, "caught_by": sorted(f), "first_problem": next(iter(sum(f.values(), [])), None)}
        result["mutations"] = res
        missed = [n for n in names if not res[n]["caught"]]
        Path(a.out).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print("MUTATIONS: %d of %d caught%s; control %s" % (len(names) - len(missed), len(names), (" (MISSED: %s)" % ", ".join(missed)) if missed else "",
                                                         "clean" if not res["control"]["problems"] else "FAILS %s" % res["control"]["scenarios_failing"]))
        return 1 if missed or res["control"]["problems"] else 0
    if a.only in (None, "siting"):
        t = time.time()
        bad = run_siting(result)
        result["siting_problems"] = bad
        result["siting_seconds"] = round(time.time() - t, 1)
        verdict.append("siting %d problem(s)%s" % (len(bad), "" if result["siting"]["old_positions"] == "checked" else " [test-rip positions NOT_EXECUTED]"))
    if a.only in (None, "draw"):
        with tempfile.TemporaryDirectory() as tmp:
            got, facts = run_draw(load_module(None), tmp)
        result["draw"] = got
        result["draw_facts"] = facts
        f = failures(got)
        verdict.append("draw %d problem(s) in %d of %d scenarios" % (sum(len(v) for v in f.values()), len(f), len(SCENARIOS) + 1))
    n = len(result.get("siting_problems", [])) + sum(len(v) for v in failures(result.get("draw", {})).values())
    Path(a.out).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("%s: %s -> %s" % ("PASS" if n == 0 else "FAIL", "; ".join(verdict), a.out))
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
