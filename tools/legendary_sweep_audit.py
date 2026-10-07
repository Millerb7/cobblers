#!/usr/bin/env python
"""Independent audit of the 2026-10-06 legendaries sweep (Giratina, Darkrai) and the catchable Hoopa.

Written by an agent that built neither (the builder's own checks are tools/legendary_sweep.py, tools/hoopa_cradle.py
`problems()` and tests/test_legendary_sweep.py, tests/test_hoopa_cradle.py). Nothing here imports
tools/legendary_sweep.py, tools/hidden_sites.py or tools/adopted_sites.py, and no expectation is read from
data/adopted_legendary_sites.json `sweep_sites`, which is the builder's measurement record: that record is only
COMPARED with what this file measures.

WHERE EACH EXPECTATION COMES FROM

  the pastes      data/placements.json (the position the server is given) and the template NBT itself, read from the
                  installed jars and datapacks (--server-dir, default the offline server snapshot): its size, its
                  summon block, its slab, its containers, its loot tables and its entities.
  the item        the summon block's own class in the LumyMon jar: which ModItems constant it names (GiratinaAltar ->
                  RED_CHAIN, DarkraiShrine -> NIGHTMARE_WEAVER, BROKEN_RED_CHAIN being the reward it hands back), and
                  every Pokemon spec string in it (the levels it can roll).
  the ground      tools/ground.py (the canonical heightmap, rounded), column by column in this file's own loop; the
                  sea level from data/world.json; the lakes from data/landmarks.json basin polygons (own ray casting).
  the rules       data/route_paths.json (segment distance, not vertex distance), data/habitat_blocks.json,
                  data/portals.json rules.min_from_legendary_mouth, every legendary site in data/placements.json,
                  data/legendaries.json, data/sapling_celebi.json, data/research_station.json and data/hoopa_cradle.json,
                  every authored coordinate in data/ (own walker), and the keep-outs and 96 / 800 / 128 / 28 of
                  docs/world-building/HIDDEN_LEGENDARIES.md and tests/test_resident_siting.py.
  the caps        rctmod's cap is the lowest level among the player's NEXT trainers, 100 with none left
                  (docs/mechanics/LEAGUE_LEVEL_CAP.md section 1). After gym 8 the next trainer is kanto_league_lorelei,
                  whose level is read from data/league_trainers.json plus relativeLevelCap from
                  modpack/config/rctmod-server.toml; after kanto_champion_blue there is none (100).
  the caches      the GENERATED rewards pack (tools/rewards_pack.py run into a temporary folder): its advancement
                  predicate and its function, read as Minecraft would read them.
  the extras      a sweep record's `extra_caches` (added 2026-10-09 for the Griseous Core) is the one thing read from
                  `sweep_sites`, and only as a CLAIM: which data/rewards.json records the site owns beside the
                  activation cache. A declared record is spared that site's clearance rule and nothing else; it is held
                  to the jars (each item ships a model), data/progression.json (the gate), the generated pack (one of
                  each, the gate in the predicate) and the template's extent (its trigger box). An undeclared record
                  at the altar still fails the clearance rule; a second item in the activation cache still fails.
  the Hoopa       the GENERATED cobblers_hoopa_cradle pack (tools/hoopa_cradle.py build), RUN in this file's own model
                  of the commands it uses (execute, scoreboard, selectors, macros, return, schedule) and of its two
                  MoLang callbacks, against scenarios whose expected outcome is the owner's decision
                  (data/hoopa_cradle.json `decision`) and data/relic_underground.json's cradle: a player without
                  rift_crisis_resolved never gets one; a player with it gets exactly one, at the cradle's centre, at
                  level 60; it comes back after respawn_after_ticks once lost; only its owner's ball holds; after the
                  catch nothing more appears. A command the model does not know is a PROBLEM, not a pass.

INDEPENDENCE IS PROVED BY MUTATING THE GENERATORS (tests/test_legendary_sweep_audit.py): the Hoopa keeper without its
flag check or its caught check, its spawn moved one block, its respawn shortened, its ball check opened; the rewards
predicate without `type_specific`; a cache giving two; the paste one block off. Each must turn this audit red with the
authored data untouched.

KNOWN (reported, not failed; a KNOWN entry that stops reproducing fails until it is removed here):

  giratina_dome_sealed   the Red Chain cache's trigger box is inside the template's closed glass dome: no passable path
                         reaches it from outside the template; a player must break the glass to earn the chain.

WHAT THIS DOES NOT COVER (validity is not behaviour, .claude/rules/testing.md):

  * whether /place template, the altar, the shrine, the advancement, the keeper or the callbacks do any of this in a
    running server. The command and MoLang models here are this file's reading of vanilla 1.21.1 and Cobblemon 1.8.0
    semantics, not the game. Proof is the staging checks in data/hoopa_cradle.json runtime_checks.
  * whether the altar CONSUMES the item. The class files say it decrements a stack (SummonAltar calls
    ItemStack.decrement, method_7934) and GiratinaAltar hands back a BROKEN_RED_CHAIN, whose only reforging recipe is in
    the disabled Sinnoh pack: evidence, not proof. Reported as a fact.
  * whether datapacks/extra is really disabled in the world (the world's level.dat is never read here); the audit
    treats it as disabled, as CLAUDE.md states.
  * trees and anything WorldPainter or a mod put in the world that no file in data/ authors (CLAUDE.md "Our list is not
    the world"); natural trees under Newmoon Island are not modelled.
  * a /give by an operator, and raid-den Hoopa (a separate Hoopa caught there grants nothing, which IS modelled).

  python tools/legendary_sweep_audit.py [--server-dir DIR] [--source-root DIR]
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import math
import os
import re
import sys
import tempfile
import zipfile
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data"
SNAPSHOT = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05")

# docs/world-building/HIDDEN_LEGENDARIES.md "The rule a hidden site is held to" (the brief's numbers), and
# tests/test_resident_siting.py (128 from a route path, a 28-block leash on an activated Habitat Block's range)
CLEARANCE = 96
SPREAD = 800
ROUTE_CLEAR = 128
LEASH = 28
KEEP_OUT_BOX = (3450, 4700, 4250, 5450)
KEEP_OUT_POINTS = ((3556, 6112), (4530, 5850), (3708, 5716))
KEEP_OUT_RADIUS = 300
SIGHT_RADIUS = 1200
CHAMPION_CAP = 100          # rctmod LevelUtils.maxLevel(): no next trainer (docs/mechanics/LEAGUE_LEVEL_CAP.md 1)
MAP = 8192

# KNOWN findings: reported every run, never failed; one that stops reproducing fails until removed here
KNOWN = {
    "giratina_dome_sealed": "sweep_red_chain's trigger box is reachable only by breaking the template's glass dome",
}

# a block a player walks through (or opens): exact paths, then suffixes. Never a substring test: "air" is in "stairs"
PASSABLE_EXACT = {"air", "cave_air", "void_air", "light", "vine", "ladder", "cobweb", "structure_void", "short_grass",
                  "tall_grass", "fern", "large_fern", "snow", "glow_lichen", "sculk_vein", "tripwire", "lever",
                  "dead_bush", "torch", "wall_torch", "soul_torch", "soul_wall_torch", "redstone_torch", "rail",
                  "brown_mushroom", "red_mushroom", "string", "spruce_ladder"}
PASSABLE_SUFFIX = ("_door", "_trapdoor", "_fence_gate", "_carpet", "_button", "_pressure_plate", "_sign", "_wall_sign",
                   "_hanging_sign", "_banner", "_wall_banner", "_sapling", "_rail", "_vines", "_ladder")


class Unmodelled(Exception):
    """A command or MoLang statement this file's model does not know: the audit cannot vouch for it."""


def _j(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ============================================================================================ the installed packs


class Packs:
    """The loaded sources of a server: datapacks/<folder>, datapacks/*.zip (higher priority), then mods/*.jar.
    datapacks/extra is NOT loaded (CLAUDE.md: disabled since the first export) and is kept apart for the report."""

    def __init__(self, server_dir):
        import runtime_guard
        self.root = runtime_guard.check(Path(server_dir), "read the installed packs in")
        dp = self.root / "datapacks"
        self.loaded = []          # (label, kind, handle)
        for d in sorted(glob.glob(str(dp / "*"))):
            if os.path.isdir(d) and os.path.basename(d) != "extra":
                self.loaded.append((os.path.basename(d), "dir", Path(d)))
        for z in sorted(glob.glob(str(dp / "*.zip"))):
            self.loaded.append((os.path.basename(z), "zip", zipfile.ZipFile(z)))
        for j in sorted(glob.glob(str(self.root / "mods" / "*.jar"))):
            try:
                self.loaded.append((os.path.basename(j), "zip", zipfile.ZipFile(j)))
            except (zipfile.BadZipFile, OSError) as e:
                raise SystemExit("legendary_sweep_audit: unreadable jar %s: %s" % (j, e))
        self.extra = [(os.path.basename(z), "zip", zipfile.ZipFile(z)) for z in sorted(glob.glob(str(dp / "extra" / "*.zip")))]
        if not any(lbl.lower().startswith("lumymon") for lbl, _, _ in self.loaded):
            raise SystemExit("legendary_sweep_audit: no LumyMon jar under %s/mods" % self.root)

    @staticmethod
    def _names(kind, h):
        if kind == "zip":
            return h.namelist()
        return [p.relative_to(h).as_posix() for p in h.rglob("*") if p.is_file()]

    @staticmethod
    def _read(kind, h, name):
        return h.read(name) if kind == "zip" else (h / name).read_bytes()

    def find(self, rel, sources=None):
        """(label, bytes) of the first loaded source holding rel, or None."""
        for lbl, kind, h in (sources if sources is not None else self.loaded):
            if kind == "zip":
                try:
                    h.getinfo(rel)
                except KeyError:
                    continue
                return lbl, h.read(rel)
            if (h / rel).is_file():
                return lbl, (h / rel).read_bytes()
        return None

    def files(self, sources=None, prefix="data/"):
        for lbl, kind, h in (sources if sources is not None else self.loaded):
            for n in self._names(kind, h):
                if n.startswith(prefix) and not n.endswith("/"):
                    yield lbl, kind, h, n

    def template(self, tid):
        ns, rel = tid.split(":", 1)
        for path in ("data/%s/structure/%s.nbt" % (ns, rel), "data/%s/structures/%s.nbt" % (ns, rel)):
            hit = self.find(path)
            if hit:
                import nbt
                return hit[0], nbt.loads(hit[1])[1]
        return None

    def jar(self, prefix):
        for lbl, kind, h in self.loaded:
            if kind == "zip" and lbl.lower().startswith(prefix.lower()):
                return h
        return None


def _strings(b):
    return set(s.decode("latin1") for s in re.findall(rb"[ -~]{3,}", b))


def summon_class(packs, block_id):
    """What the summon block's own class says: its activation item, the reward item, and the levels it can roll.

    The block lumymon:giratina_altar is class GiratinaAltar. Its ModItems constants that are LumyMon items are the
    candidates; one that names the block's REWARD (spawnRewardItem) is the item handed back, the other the item used.
    Every 'species level=N ...' constant string is a spec the altar can roll."""
    ns, path = block_id.split(":", 1)
    jar = packs.jar("lumymon")
    cls = "com/lumyverse/lumymon/block/custom/%s.class" % "".join(w.capitalize() for w in path.split("_"))
    try:
        b = jar.read(cls)
    except KeyError:
        return {"error": "no class %s in the LumyMon jar for %s" % (cls, block_id)}
    items = _strings(jar.read("com/lumyverse/lumymon/item/ModItems.class"))
    s = _strings(b)
    consts = sorted(x for x in s if re.fullmatch(r"[A-Z][A-Z_]+", x) and x.lower() in items)
    reward = [c for c in consts if c.startswith("BROKEN_")] if "spawnRewardItem" in s else []
    use = [c for c in consts if c not in reward]
    levels = sorted({int(m) for x in s for m in re.findall(r"\blevel=(\d+)", x)})
    base = jar.read("com/lumyverse/lumymon/block/custom/SummonAltar.class")
    return {"class": cls, "activation": ["%s:%s" % (ns, c.lower()) for c in use],
            "reward": ["%s:%s" % (ns, c.lower()) for c in reward], "levels": levels,
            "base_decrements_a_stack": b"method_7934" in base}


# ============================================================================================ templates


def _walk_values(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from _walk_values(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _walk_values(v)
    else:
        yield o


def loot_yields(packs, table, item, seen=None):
    """True if the loaded loot table (or a table or tag it names) can yield `item`. A table that cannot be found is
    returned as the string 'unresolved:<id>'."""
    seen = set() if seen is None else seen
    if table in seen:
        return False
    seen.add(table)
    ns, rel = table.split(":", 1)
    hit = None
    for folder in ("loot_table", "loot_tables"):
        hit = packs.find("data/%s/%s/%s.json" % (ns, folder, rel))
        if hit:
            break
    if not hit:
        return "unresolved:%s" % table
    doc = json.loads(hit[1])
    for v in _walk_values(doc):
        if v == item:
            return True
    for e in _entries(doc):
        if e.get("type") in ("minecraft:loot_table", "loot_table"):
            ref = e.get("value") or e.get("name")
            if isinstance(ref, str):
                r = loot_yields(packs, ref, item, seen)
                if r:
                    return r
        if e.get("type") in ("minecraft:tag", "tag") and isinstance(e.get("name"), str):
            tns, trel = e["name"].lstrip("#").split(":", 1)
            th = packs.find("data/%s/tags/item/%s.json" % (tns, trel)) or packs.find("data/%s/tags/items/%s.json" % (tns, trel))
            if th and item in json.dumps(json.loads(th[1])):
                return True
    return False


def _entries(o):
    if isinstance(o, dict):
        if "type" in o and ("name" in o or "value" in o):
            yield o
        for v in o.values():
            yield from _entries(v)
    elif isinstance(o, list):
        for v in o:
            yield from _entries(v)


def template_facts(tdoc):
    pal = tdoc.get("palette") or tdoc["palettes"][0]
    names = [p["Name"] for p in pal]
    grid = {tuple(b["pos"]): names[b["state"]] for b in tdoc["blocks"]}
    return names, grid


def full_slab_top(tdoc, grid):
    """The highest layer L such that every layer 0..L is solid over the whole footprint, or None."""
    sx, sy, sz = tdoc["size"]
    top = None
    for y in range(sy):
        if all(not _passable(grid.get((x, y, z), "minecraft:air")) for x in range(sx) for z in range(sz)):
            top = y
        else:
            break
    return top


def _passable(name):
    path = name.split("[", 1)[0].split(":", 1)[-1]
    return path in PASSABLE_EXACT or path.endswith(PASSABLE_SUFFIX)


def reachable_cells(tdoc, grid, floor):
    """Cells at or above `floor` reached through passable cells from the template's open sides and top."""
    sx, sy, sz = tdoc["size"]
    seen = set()
    q = deque()
    for x in range(sx):
        for y in range(floor, sy):
            for z in range(sz):
                if (x in (0, sx - 1) or z in (0, sz - 1) or y == sy - 1) and _passable(grid.get((x, y, z), "minecraft:air")):
                    seen.add((x, y, z))
                    q.append((x, y, z))
    while q:
        x, y, z = q.popleft()
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            p = (x + dx, y + dy, z + dz)
            if 0 <= p[0] < sx and floor <= p[1] < sy and 0 <= p[2] < sz and p not in seen \
                    and _passable(grid.get(p, "minecraft:air")):
                seen.add(p)
                q.append(p)
    return seen


# ============================================================================================ data


def placements():
    return _j(DATA / "placements.json")["placements"]


def declared_extras(sid):
    """The `extra_caches` the sweep record scheduled as `sid` DECLARES. A declaration is a claim to be checked, not an
    expectation: it names which data/rewards.json records the site owns besides its activation item's cache, and every
    one is then held, by extra_cache_audit, to the jars (the items exist), data/progression.json (the gate is a flag),
    the GENERATED rewards pack (gate, items, one of each) and the template's own extent (the position)."""
    rec = [s for s in _j(DATA / "adopted_legendary_sites.json").get("sweep_sites") or [] if s.get("scheduled_as") == sid]
    return list(rec[0].get("extra_caches") or []) if len(rec) == 1 else []


def sweep_placements(pl=None):
    """The pastes the sweep scheduled: data/placements.json records carrying `sweep_site`."""
    return [q for q in (pl if pl is not None else placements()) if q.get("sweep_site")]


def box_of(q):
    x, z = q["position"]["x"], q["position"]["z"]
    sx, _, sz = q["size"]
    if q.get("rotation", "none") in ("clockwise_90", "counterclockwise_90"):
        raise Unmodelled("%s: rotation %s is not modelled by this audit" % (q["id"], q["rotation"]))
    if q.get("rotation", "none") not in ("none",) or q.get("mirror", "none") != "none":
        raise Unmodelled("%s: rotation/mirror %s/%s is not modelled by this audit" % (q["id"], q.get("rotation"), q.get("mirror")))
    return (x, z, x + sx - 1, z + sz - 1)


def edge(box, x, z):
    x0, z0, x1, z1 = box
    return math.hypot(max(x0 - x, 0, x - x1), max(z0 - z, 0, z - z1))


def seg_edge(box, a, b):
    """Least distance from the footprint rectangle to the segment a-b (sampled at 0.5 blocks)."""
    n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) * 2))
    return min(edge(box, a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1))


def authored_points(skip_ids):
    """(x, z, file) for every coordinate authored in data/*.json and data/*/*.json: a dict with numeric x and z, or a
    [x, z] / [x, y, z] list inside the map; records whose id is in skip_ids are skipped whole."""
    out = []

    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    def walk(o, src):
        if isinstance(o, dict):
            if o.get("id") in skip_ids:
                return
            if num(o.get("x")) and num(o.get("z")) and 0 <= o["x"] < MAP and 0 <= o["z"] < MAP:
                out.append((float(o["x"]), float(o["z"]), src))
            for v in o.values():
                walk(v, src)
        elif isinstance(o, list):
            if len(o) in (2, 3) and all(num(v) for v in o) and 0 <= o[0] < MAP and 0 <= o[-1] < MAP \
                    and (len(o) == 2 or -64 <= o[1] <= 640):
                out.append((float(o[0]), float(o[-1]), src))
                return
            for v in o:
                walk(v, src)

    for f in sorted(glob.glob(str(DATA / "*.json"))) + sorted(glob.glob(str(DATA / "*" / "*.json"))):
        walk(_j(f), os.path.relpath(f, ROOT).replace("\\", "/"))
    return out


def legendary_centres(pl):
    """{name: (x, z)} of every legendary site the repository authors, from the files that author them."""
    out = {}
    for q in pl:
        if q.get("adopted_site") or q.get("sweep_site") or str(q.get("id", "")).startswith("legendary_"):
            if q.get("position") and q.get("size"):
                out["placements:" + q["id"]] = (q["position"]["x"] + q["size"][0] / 2.0, q["position"]["z"] + q["size"][2] / 2.0)
    adopted = _j(DATA / "adopted_legendary_sites.json")
    for s in adopted.get("sites") or []:
        p = s.get("placement")
        if p and "scheduled_as" not in s:
            c = p.get("corner")
            if isinstance(c, list) and s.get("size"):
                out["adopted:" + s["id"]] = (c[0] + s["size"][0] / 2.0, c[-1] + s["size"][2] / 2.0)
    for e in _j(DATA / "legendaries.json")["encounters"]:
        for k in ("mouth", "portal", "at", "centre"):
            v = e.get(k)
            if isinstance(v, list) and len(v) >= 2 and all(isinstance(n, (int, float)) for n in v):
                out["legendaries:" + e["id"]] = (v[0], v[-1])
                break
    cel = _j(DATA / "sapling_celebi.json")["position"]
    out["sapling_celebi"] = (cel[0], cel[2])
    rs = _j(DATA / "research_station.json")["shrine"]["centre"]
    out["research_station_eon_shrine"] = tuple(rs)
    hp = _j(DATA / "hoopa_cradle.json")["spot"]
    out["hoopa_cradle"] = (hp[0], hp[2])
    return out


def in_poly(x, z, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        x1, z1 = ring[i][0], ring[i][-1]
        x2, z2 = ring[(i + 1) % n][0], ring[(i + 1) % n][-1]
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
            inside = not inside
    return inside


def lake_bodies():
    out = []
    for l in _j(DATA / "landmarks.json")["landmarks"]:
        wb = l.get("water_body") or {}
        if wb.get("level_y") is not None:
            out.append((l["id"], int(wb["level_y"]), wb.get("basin_polygons") or []))
    return out


def rct_cap_after_gym8():
    """rctmod's cap with Lorelei next: her team's top level plus relativeLevelCap (rctmod-server.toml)."""
    lt = [t for t in _j(DATA / "league_trainers.json")["trainers"] if t.get("upstream_trainer_id") == "kanto_league_lorelei"]
    if len(lt) != 1:
        return None, "data/league_trainers.json has %d kanto_league_lorelei records" % len(lt)
    top = max(lt[0]["levels"] + [lt[0]["ace"]["level"]])
    rel = 0
    toml = ROOT / "modpack" / "config" / "rctmod-server.toml"
    if toml.is_file():
        m = re.search(r"^\s*relativeLevelCap\s*=\s*(-?\d+)", toml.read_text(encoding="utf-8"), re.M)
        rel = int(m.group(1)) if m else 0
    return max(0, min(100, top + rel)), None


# ============================================================================================ the report


class Report:
    def __init__(self):
        self.problems = []
        self.facts = {}
        self.known = {}

    def check(self, area, ok, msg):
        if not ok:
            self.problems.append((area, msg))
        return ok

    def fact(self, key, value):
        self.facts[key] = value


# ============================================================================================ 1. the pastes


def paste_audit(R, packs, g, pl=None, donor=None, sightlines=True):
    """Template, item, seat, rules, sightlines and the emitted paste commands for every sweep placement."""
    pl = pl if pl is not None else placements()
    if donor is None:
        import place_donor as donor
    sites = sweep_placements(pl)
    R.check("pastes", len(sites) == 2, "data/placements.json has %d sweep_site records, the sweep named 2" % len(sites))
    out = {}
    for q in sites:
        sid = q["id"]
        hit = packs.template(q["pack_template"])
        if not R.check(sid, hit is not None, "%s: template %s is not in any loaded pack" % (sid, q["pack_template"])):
            continue
        src, t = hit
        names, grid = template_facts(t)
        R.fact(sid + ".template_source", src)
        R.check(sid, list(t["size"]) == list(q["size"]), "%s: size %s, the template is %s" % (sid, q["size"], t["size"]))
        try:
            box = box_of(q)
        except Unmodelled as e:
            R.check(sid, False, str(e))
            continue
        x0, y0, z0 = q["position"]["x"], q["position"]["y"], q["position"]["z"]
        summons = [(names_, pos) for pos, names_ in grid.items()
                   if names_.startswith("lumymon:") and ("altar" in names_ or "shrine" in names_)]
        anchors = [pos for pos, n in grid.items() if n == "lumymon:summon_anchor"]
        if not R.check(sid, len(summons) == 1, "%s: %d LumyMon summon blocks in the template" % (sid, len(summons))):
            continue
        block, spos = summons[0]
        altar = (x0 + spos[0], y0 + spos[1], z0 + spos[2])
        R.fact(sid + ".summon", {"block": block, "world": altar, "anchors": [(x0 + a[0], y0 + a[1], z0 + a[2]) for a in anchors]})
        R.check(sid, len(anchors) >= 1, "%s: no lumymon:summon_anchor in the template; the altar has nowhere to summon" % sid)
        sc = summon_class(packs, block)
        if not R.check(sid, "error" not in sc, "%s: %s" % (sid, sc.get("error"))):
            continue
        R.check(sid, len(sc["activation"]) == 1, "%s: %s names %s as its item(s); expected one" % (sid, sc["class"], sc["activation"]))
        item = sc["activation"][0] if sc["activation"] else None
        R.fact(sid + ".activation_item", item)
        R.fact(sid + ".reward_item", sc["reward"])
        R.fact(sid + ".levels", sc["levels"])
        R.fact(sid + ".altar_decrements_a_stack", sc["base_decrements_a_stack"])
        out[sid] = {"item": item, "levels": sc["levels"], "altar": altar, "box": box, "q": q, "template": t,
                    "grid": grid, "names": names}

        # --- no container, no entity and no loot table in the template hands out the item
        for b in t["blocks"]:
            nb = b.get("nbt") or {}
            if not nb:
                continue
            if item in [v for v in _walk_values(nb) if isinstance(v, str)]:
                R.check(sid, False, "%s: the template's %s at %s holds %s: a free legendary"
                        % (sid, names[b["state"]], b["pos"], item))
            lt = nb.get("LootTable")
            if isinstance(lt, str):
                r = loot_yields(packs, lt, item)
                R.check(sid, r is False, "%s: the %s at %s draws loot table %s, which %s"
                        % (sid, names[b["state"]], b["pos"], lt, "yields " + item if r is True else "is " + str(r)))
        for e in t.get("entities") or []:
            if item in [v for v in _walk_values(e.get("nbt") or {}) if isinstance(v, str)]:
                R.check(sid, False, "%s: a template entity at %s carries %s" % (sid, e.get("blockPos"), item))

        # --- the seat, from the heightmap in this file's own loop
        bx0, bz0, bx1, bz1 = box
        hs = [[g(x, z) for x in range(bx0, bx1 + 1)] for z in range(bz0, bz1 + 1)]
        flat = [h for row in hs for h in row]
        gmin, gmax = min(flat), max(flat)
        R.fact(sid + ".ground", {"min": gmin, "max": gmax, "columns": len(flat)})
        slab = full_slab_top(t, grid)
        sea = _j(DATA / "world.json")["vertical"]["sea_level"]
        if slab is not None:
            # sunk: the template's own solid slab is buried, its top layer at the footprint's cheapest seat
            best = None
            for y in range(gmin, gmax + 1):
                cost = sum(abs(h - y) for h in flat)
                if best is None or cost < best[1]:
                    best = (y, cost)
            top = y0 + slab
            cut = sum(h - top for h in flat if h > top)
            fill = sum(top - h for h in flat if h < top)
            R.fact(sid + ".seat", {"kind": "sunk", "slab_top_layer": slab, "slab_top_y": top, "cheapest_seat": best[0],
                                   "cut_blocks": cut, "cut_columns": sum(1 for h in flat if h > top),
                                   "fill_blocks": fill, "fill_columns": sum(1 for h in flat if h < top)})
            R.check(sid, top == best[0], "%s: the slab's top layer %d stands at y%d; the footprint's cheapest seat is y%d"
                    % (sid, slab, top, best[0]))
            wet = 0
            bodies = lake_bodies()
            for z in range(bz0, bz1 + 1):
                for x in range(bx0, bx1 + 1):
                    h = hs[z - bz0][x - bx0]
                    if h < sea or any(h < lvl and any(in_poly(x, z, ring) for ring in rings) for _, lvl, rings in bodies):
                        wet += 1
            R.fact(sid + ".wet_columns", wet)
            R.check(sid, wet == 0, "%s: %d footprint columns are under painted water" % (sid, wet))
            R.check(sid, gmin > sea, "%s: ground as low as y%d against sea level y%d" % (sid, gmin, sea))
        else:
            # floating: no full slab; the whole template must hang over the ground
            bottom = min(p[1] for p, n in grid.items() if not _passable(n))
            R.fact(sid + ".seat", {"kind": "floating", "bottom_y": y0 + bottom, "gap_over_highest_ground": y0 + bottom - gmax,
                                   "sea_columns": sum(1 for h in flat if h < sea), "land_columns": sum(1 for h in flat if h >= sea)})
            R.check(sid, y0 + bottom > gmax, "%s: a floating template's lowest block y%d is not above the highest ground y%d"
                    % (sid, y0 + bottom, gmax))
            # nothing authored stands under it and reaches its bottom
            under = []
            for o in pl:
                if o is q or not o.get("position") or not o.get("size"):
                    continue
                try:
                    ob = box_of(o)
                except Unmodelled:
                    ob = (o["position"]["x"] - max(o["size"]), o["position"]["z"] - max(o["size"]),
                          o["position"]["x"] + max(o["size"]), o["position"]["z"] + max(o["size"]))
                if ob[0] <= bx1 and ob[2] >= bx0 and ob[1] <= bz1 and ob[3] >= bz0:
                    under.append(o["id"])
            R.fact(sid + ".placements_under", under)
            R.check(sid, not under, "%s: data/placements.json records under the floating footprint: %s" % (sid, under))
        height = t["size"][1]
        dim = _j(ROOT / "modpack" / "datapacks" / "cobblers_height" / "data" / "minecraft" / "dimension_type" / "overworld.json")
        rt = dim["min_y"] + dim["height"] - 1
        R.check(sid, y0 + height - 1 <= rt, "%s: top layer y%d over the runtime top y%d" % (sid, y0 + height - 1, rt))

        # --- the siting rules, re-measured
        rp = _j(DATA / "route_paths.json")["paths"]
        dmin = None
        for pid, pts in rp.items():
            for a, b in zip(pts, pts[1:]):
                if edge(box, *a) - math.hypot(b[0] - a[0], b[1] - a[1]) > ROUTE_CLEAR + 50:
                    continue
                d = seg_edge(box, a, b)
                dmin = d if dmin is None or d < dmin else dmin
            if len(pts) == 1:
                d = edge(box, *pts[0])
                dmin = d if dmin is None or d < dmin else dmin
        if dmin is None:   # every segment pruned: nothing within ROUTE_CLEAR + 50 + a segment's length
            dmin = min(edge(box, *p) for pts in rp.values() for p in pts)
        R.fact(sid + ".route_path_edge", round(dmin))
        R.check(sid, dmin >= ROUTE_CLEAR, "%s: a route path %d from the footprint edge (rule %d)" % (sid, dmin, ROUTE_CLEAR))
        hab = [b for b in _j(DATA / "habitat_blocks.json")["blocks"] if b.get("style") == "activated"]
        hm = min((edge(box, b["position"]["x"], b["position"]["z"]) - b["activated"]["spawn_range"] - LEASH, b["id"]) for b in hab)
        R.fact(sid + ".habitat_margin", round(hm[0]))
        R.check(sid, hm[0] >= 0, "%s: inside Habitat Block %s's spawn range plus %d (margin %d)" % (sid, hm[1], LEASH, hm[0]))
        po = _j(DATA / "portals.json")
        prule = po["rules"]["min_from_legendary_mouth"]
        pe = min((edge(box, *p["at"][:1], p["at"][-1]), p["id"]) for p in po["portals"])
        R.fact(sid + ".portal_edge", round(pe[0]))
        R.check(sid, pe[0] >= prule, "%s: portal %s %d from the footprint edge (rule %d)" % (sid, pe[1], pe[0], prule))
        cx, cz = (bx0 + bx1 + 1) / 2.0, (bz0 + bz1 + 1) / 2.0
        spread = sorted((math.hypot(cx - a, cz - b), k) for k, (a, b) in legendary_centres(pl).items()
                        if k != "placements:" + sid)
        R.fact(sid + ".spread_nearest", (round(spread[0][0]), spread[0][1]))
        for d, k in spread:
            R.check(sid, d >= SPREAD, "%s: %s is %d from this site's centre (spread %d)" % (sid, k, d, SPREAD))
        # skipped: the activation item's cache, and the extra caches THIS site declares (each one held to the carve,
        # its items and its gate by extra_cache_audit; a record declared nowhere, or on another site, is not skipped)
        skip = {sid, q.get("sweep_site")} | {r["id"] for r in _j(DATA / "rewards.json")["rewards"]
                                              if any(c.get("item") == item for c in r.get("contents") or [])} \
            | {d.get("source") for d in declared_extras(sid)}
        pts = authored_points(skip)
        near = min((edge(box, x, z), src, x, z) for x, z, src in pts)
        R.fact(sid + ".nearest_authored", (round(near[0]), near[1], near[2], near[3]))
        R.check(sid, near[0] >= CLEARANCE, "%s: authored point (%d, %d) in %s is %d from the footprint edge (rule %d)"
                % (sid, near[2], near[3], near[1], near[0], CLEARANCE))
        if not (box[2] < KEEP_OUT_BOX[0] or box[0] > KEEP_OUT_BOX[2] or box[3] < KEEP_OUT_BOX[1] or box[1] > KEEP_OUT_BOX[3]):
            R.check(sid, False, "%s: footprint overlaps the Mega farm keep-out" % sid)
        for kp in KEEP_OUT_POINTS:
            R.check(sid, edge(box, *kp) >= KEEP_OUT_RADIUS, "%s: %d from the keep-out point %s" % (sid, edge(box, *kp), kp))

        # --- hidden: no route path vertex within SIGHT_RADIUS sees the template's top over bare terrain. The top is the
        # highest block that STAYS: a jigsaw whose final state is air is not something anyone sees
        jig_air = {tuple(b["pos"]) for b in t["blocks"] if names[b["state"]] == "minecraft:jigsaw"
                   and ((b.get("nbt") or {}).get("final_state") or "minecraft:air").split("[")[0] in ("minecraft:air", "minecraft:structure_void")}
        topy = y0 + max(p[1] for p, n in grid.items() if not _passable(n) and p not in jig_air)
        R.fact(sid + ".visible_top_y", topy)
        out[sid]["visible_top_y"] = topy
        seen, near_n = 0, 0
        for pts_ in (rp.values() if sightlines else ()):
            for vx, vz in pts_[::2]:
                d = math.hypot(vx - cx, vz - cz)
                if d > SIGHT_RADIUS:
                    continue
                near_n += 1
                if _sees(g, (vx, vz, g(vx, vz) + 1.62), (cx, cz, topy), box):
                    seen += 1
        R.fact(sid + ".route_sightings", {"seen": seen, "route_vertices_within": near_n, "every_2nd_vertex": True})
        R.check(sid, seen == 0, "%s: %d route-path vertices within %d see the template's top (y%d) over bare terrain"
                % (sid, seen, SIGHT_RADIUS, topy))

        # --- the emitted paste: place template at the position, jigsaws resolved, the summon blocks untouched
        cmds = donor.commands(q, [])
        jig = donor.jigsaw_commands(q, {"palette": t.get("palette") or t["palettes"][0], "blocks": t["blocks"]})
        places = [c for c in cmds if c.startswith("place template")]
        want = "place template %s %d %d %d none none" % (q["pack_template"], x0, y0, z0)
        R.check(sid, len(places) == 1 and places[0].startswith(want),
                "%s: the paste command is %s, not %r" % (sid, places, want))
        jigs = [(b["pos"], (b.get("nbt") or {}).get("final_state")) for b in t["blocks"] if names[b["state"]] == "minecraft:jigsaw"]
        for pos, final in jigs:
            w = "setblock %d %d %d %s" % (x0 + pos[0], y0 + pos[1], z0 + pos[2], final or "minecraft:air")
            R.check(sid, w in jig, "%s: the jigsaw at template %s is not set to its own final state (%s)" % (sid, pos, w))
        keep = {altar} | {(x0 + a[0], y0 + a[1], z0 + a[2]) for a in anchors}
        for c in cmds + jig:
            m = re.match(r"setblock (-?\d+) (-?\d+) (-?\d+) ", c)
            if m and tuple(int(v) for v in m.groups()) in keep:
                R.check(sid, False, "%s: %r overwrites a summon block" % (sid, c))
            m = re.match(r"fill .* replace (\S+)", c)
            if m and m.group(1).split("[")[0] in (block, "lumymon:summon_anchor"):
                R.check(sid, False, "%s: %r replaces the summon blocks" % (sid, c))
        R.fact(sid + ".jigsaws", len(jigs))

        # --- how it is found by eye: the record names one observer per site; the observer's position comes from the
        # file that authors it, and the line of sight from this file's own loop
        rec = [s for s in _j(DATA / "adopted_legendary_sites.json").get("sweep_sites") or [] if s.get("scheduled_as") == sid]
        by_eye = json.dumps((rec[0].get("how_it_is_found") or {}).get("by_eye", "")) if rec else ""
        obs = None
        if "major_river" in by_eye:
            lm = [l for l in _j(DATA / "landmarks.json")["landmarks"] if l["id"] == "major_river"][0]["anchor"]
            obs = ("landmark major_river's anchor", lm["x"], lm["z"], g(lm["x"], lm["z"]) + 1.62)
        elif "Zapdos" in by_eye:
            zq = [o for o in pl if o["id"] == "legendary_zapdos_tower"][0]
            zx, zz = zq["position"]["x"] + zq["size"][0] / 2.0, zq["position"]["z"] + zq["size"][2] / 2.0
            obs = ("the top of Zapdos's tower", zx, zz, zq["position"]["y"] + zq["size"][1] - 1 + 1 + 1.62)
        if obs is not None:
            mid = y0 + (min(p[1] for p, n in grid.items() if not _passable(n)) + topy - y0) / 2.0
            aim = topy if "major_river" in by_eye else mid
            seen_by = _sees(g, (obs[1], obs[2], obs[3]), (cx, cz, aim), box)
            R.fact(sid + ".found_by_eye", {"from": obs[0], "at": (obs[1], obs[2], round(obs[3], 1)), "aim_y": aim,
                                          "distance": round(math.hypot(cx - obs[1], cz - obs[2])), "seen": seen_by})
            R.check(sid, seen_by, "%s: the record says it is found by eye from %s, which does not see y%d over bare terrain"
                    % (sid, obs[0], aim))
        else:
            R.check(sid, False, "%s: the record names no observer this audit knows (major_river, Zapdos)" % sid)
    return out


def _sees(g, eye, target, box):
    """Bare-terrain line of sight from eye (x, z, y) to target (x, z, y); the target's own footprint is not terrain."""
    (ax, az, ay), (bx, bz, by) = eye, target
    d = math.hypot(bx - ax, bz - az)
    n = max(1, int(d // 2))
    for i in range(1, n):
        f = i / n
        sx, sz = ax + (bx - ax) * f, az + (bz - az) * f
        if box[0] <= sx <= box[2] and box[1] <= sz <= box[3]:
            return True
        if g(int(sx), int(sz)) >= ay + (by - ay) * f:
            return False
    return True


# ============================================================================================ 2. one source of each item


PRODUCER_FREE = ("/advancement/", "/advancements/", "/rctmod/mobs/")


def producers(packs, item):
    """[(source, file)] of every loaded JSON or template that names the item, except advancements (a criterion is
    not a source) and rctmod mob files (a signature item is display), and the verdict for each."""
    needle = item.encode()
    out = []
    for lbl, kind, h, n in packs.files():
        if not n.endswith((".json", ".nbt", ".mcfunction")) or any(s in n for s in PRODUCER_FREE):
            continue
        b = Packs._read(kind, h, n)
        if n.endswith(".nbt"):
            try:
                b = gzip.decompress(b)
            except OSError:
                pass
        if needle in b:
            out.append((lbl, n))
    return out


def trainer_never_spawns(packs, trainer_id):
    """An rctmod trainer with spawnWeightFactor 0 that no data/ file and no loaded template names."""
    hit = packs.find("data/rctmod/mobs/trainers/single/%s.json" % trainer_id)
    if not hit or json.loads(hit[1]).get("spawnWeightFactor", 1) != 0:
        return False
    for f in glob.glob(str(DATA / "**" / "*.json"), recursive=True):
        if trainer_id in Path(f).read_text(encoding="utf-8") and not f.endswith(("adopted_legendary_sites.json", "rewards.json")):
            return False
    return True


def source_audit(R, packs, sites):
    for sid, s in sites.items():
        item = s["item"]
        if not item:
            continue
        bad = []
        caches = {r["id"] for r in _j(DATA / "rewards.json")["rewards"]
                  if any(c.get("item") == item for c in r.get("contents") or [])}
        for lbl, n in producers(packs, item):
            # an installed copy of OUR cache's own function is the one source, not a second one
            if lbl == "cobblers_rewards" and re.fullmatch(r"data/cobblers/(function/reward|advancement/reward)/(\w+)\.(mcfunction|json)", n) \
                    and re.fullmatch(r"data/cobblers/\w+/reward/(\w+)\.\w+", n).group(1) in caches:
                continue
            m = re.match(r"data/rctmod/loot_table/trainers/single/(.+)\.json$", n)
            if m and trainer_never_spawns(packs, m.group(1)):
                continue
            bad.append("%s %s" % (lbl, n))
        R.fact(sid + ".other_loaded_sources", bad)
        R.check("sources", not bad, "%s: %s has loaded sources besides its cache: %s" % (sid, item, bad))
        extra = [(lbl, n) for lbl, kind, h, n in packs.files(packs.extra) if n.endswith(".json")
                 and item.encode() in Packs._read(kind, h, n) and "/advancement" not in n]
        R.fact(sid + ".sources_in_disabled_extra", ["%s %s" % e for e in extra])


# ============================================================================================ 3. the caches


def _cache_cells(s, lo, hi):
    """([standable template cells in the predicate box], [those reached from outside the template])."""
    q = s["q"]
    x0, y0, z0 = q["position"]["x"], q["position"]["y"], q["position"]["z"]
    grid, t = s["grid"], s["template"]
    feet = []
    for x in range(int(math.floor(lo[0])), int(math.ceil(hi[0]))):
        for y in range(int(math.floor(lo[1])), int(math.ceil(hi[1]))):
            for z in range(int(math.floor(lo[2])), int(math.ceil(hi[2]))):
                c = (x - x0, y - y0, z - z0)
                if _passable(grid.get(c, "minecraft:air")) and _passable(grid.get((c[0], c[1] + 1, c[2]), "minecraft:air")) \
                        and not _passable(grid.get((c[0], c[1] - 1, c[2]), "minecraft:air")):
                    feet.append(c)
    slab = full_slab_top(t, grid)
    reach = reachable_cells(t, grid, (slab + 1) if slab is not None else 0)
    return feet, [c for c in feet if c in reach]


def _generated_rewards(rewards, doc):
    """({id: advancement}, {id: function lines}) of the rewards pack as `rewards` (tools/rewards_pack.py) writes it."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "cobblers_rewards"
        rewards.write(doc, out)
        advs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (out / "data" / "cobblers" / "advancement" / "reward").glob("*.json")}
        fns = {p.stem: p.read_text(encoding="utf-8").splitlines() for p in (out / "data" / "cobblers" / "function" / "reward").glob("*.mcfunction")}
    return advs, fns


def item_is_real(packs, item):
    """An item id the loaded jars ship a model for (assets/<ns>/models/item/<path>.json), the same evidence each
    data/rewards.json `verification` cites. A vanilla id is not in the snapshot's jars and is not vouched for here."""
    if not isinstance(item, str) or ":" not in item:
        return False
    ns, path = item.split(":", 1)
    return packs.find("assets/%s/models/item/%s.json" % (ns, path)) is not None


def extra_cache_audit(R, packs, sites, rewards=None):
    """Every `extra_caches` declaration of a sweep site, held to everything the activation cache is held to except the
    one-item rule: the record exists once and is a cache; its items exist in the loaded jars, are not the activation
    item, and the GENERATED function gives exactly one of each and nothing else; its gate is real progression flags and
    the GENERATED advancement requires every one; its predicate box is an overworld box inside the template's extent
    (corner to corner, bottom layer to top) and holds a cell a player can stand on. A declaration on a sweep record no
    paste was audited for is a problem: nothing would hold it to a carve."""
    if rewards is None:
        import rewards_pack as rewards
    doc = _j(DATA / "rewards.json")
    flags = {f["id"] for f in _j(DATA / "progression.json")["flags"]}
    advs, fns = _generated_rewards(rewards, doc)
    for rec in _j(DATA / "adopted_legendary_sites.json").get("sweep_sites") or []:
        if rec.get("extra_caches") and rec.get("scheduled_as") not in sites:
            R.check("extras", False, "%s declares extra_caches but its paste %r was not audited"
                    % (rec.get("id"), rec.get("scheduled_as")))
    for sid, s in sites.items():
        decl = declared_extras(sid)
        R.fact(sid + ".extra_caches", [d.get("source") for d in decl])
        q, t = s["q"], s["template"]
        x0, y0, z0 = q["position"]["x"], q["position"]["y"], q["position"]["z"]
        sx, sy, sz = t["size"]
        seen = set()
        for d in decl:
            src = d.get("source")
            tag = "%s: extra cache %r" % (sid, src)
            if not R.check(sid, isinstance(src, str) and src not in seen, "%s is unnamed or declared twice" % tag):
                continue
            seen.add(src)
            hits = [r for r in doc["rewards"] if r.get("id") == src]
            if not R.check(sid, len(hits) == 1, "%s names %d data/rewards.json records" % (tag, len(hits))):
                continue
            r = hits[0]
            R.check(sid, r.get("kind") == "cache", "%s is a %s, not a cache" % (tag, r.get("kind")))
            want = list(d.get("items") or [])
            R.check(sid, bool(want) and len(set(want)) == len(want), "%s declares items %s" % (tag, want))
            for it in want:
                R.check(sid, item_is_real(packs, it), "%s: %s is not an item any loaded jar ships" % (tag, it))
            R.check(sid, s["item"] not in want and s["item"] not in [c.get("item") for c in r.get("contents") or []],
                    "%s hands out the activation item %s" % (tag, s["item"]))
            gate = d.get("flags")
            R.check(sid, isinstance(gate, list) and bool(gate) and all(f in flags for f in gate),
                    "%s's gate %r is not a list of data/progression.json flags" % (tag, gate))
            # the generated function: one of each declared item, nothing else
            lines = fns.get(src)
            if not R.check(sid, lines is not None and src in advs, "%s: the rewards pack has no reward/%s" % (tag, src)):
                continue
            gives = [l for l in lines if l.startswith("give ")]
            got = []
            for l in gives:
                m = re.fullmatch(r"give @s ([a-z0-9_.-]+:[a-z0-9_./-]+)(\[[^\]]*\])? (\d+)", l)
                got.append((m.group(1), int(m.group(3))) if m else (l, None))
            R.check(sid, sorted(got) == sorted((it, 1) for it in want),
                    "%s: cobblers:reward/%s gives %s, the site declares one each of %s" % (tag, src, got, want))
            adv = advs[src]
            R.check(sid, adv.get("rewards", {}).get("function") == "cobblers:reward/%s" % src,
                    "%s: the advancement's reward is %s" % (tag, adv.get("rewards")))
            crit = adv.get("criteria") or {}
            R.check(sid, len(crit) == 1, "%s: %d criteria" % (tag, len(crit)))
            for c in crit.values():
                R.check(sid, c.get("trigger") == "minecraft:location", "%s: trigger %s" % (tag, c.get("trigger")))
                preds = [x.get("predicate") or {} for x in (c.get("conditions") or {}).get("player") or []
                         if x.get("condition") == "minecraft:entity_properties" and x.get("entity") == "this"]
                need = {"cobblers:flag/%s" % f: True for f in (gate if isinstance(gate, list) else [])}
                R.check(sid, bool(need) and any((p.get("type_specific") or {}).get("type") in ("minecraft:player", "player")
                                                and all(((p.get("type_specific") or {}).get("advancements") or {}).get(k) == v
                                                        for k, v in need.items()) for p in preds),
                        "%s: earning reward/%s does not require %s" % (tag, src, sorted(need)))
                boxes = []
                for p in preds:
                    loc = p.get("location") or {}
                    pos = loc.get("position") or {}
                    if loc.get("dimension") == "minecraft:overworld" and all(k in pos for k in "xyz"):
                        boxes.append(([pos[k]["min"] for k in "xyz"], [pos[k]["max"] for k in "xyz"]))
                if not R.check(sid, len(boxes) == 1, "%s: the advancement's location is not one overworld box" % tag):
                    continue
                lo, hi = boxes[0]
                # the predicate reads feet as a double: the template's extent is [corner, corner + size]
                inside = (x0 <= lo[0] and hi[0] <= x0 + sx and y0 <= lo[1] and hi[1] <= y0 + sy
                          and z0 <= lo[2] and hi[2] <= z0 + sz)
                R.fact(sid + ".extra." + src + ".box", (lo, hi))
                if not R.check(sid, inside, "%s: its trigger box %s-%s is not inside the template's extent (%d, %d, %d)-(%d, %d, %d)"
                               % (tag, lo, hi, x0, y0, z0, x0 + sx, y0 + sy, z0 + sz)):
                    continue
                feet, ok = _cache_cells(s, lo, hi)
                R.fact(sid + ".extra." + src + ".standable_cells", len(feet))
                R.check(sid, len(feet) > 0, "%s: no cell in its box is somewhere a player can stand" % tag)
                if feet and not ok:
                    # inside the same sealed shell as the activation cache (run after cache_audit): one finding, not
                    # two. Sealed when the activation cache is not: a finding of its own, unlisted, so it fails
                    key = "giratina_dome_sealed" if "giratina" in sid else sid + "_sealed"
                    if key in R.known:
                        R.known[key] += "; so is extra cache %s" % src
                    else:
                        R.known[src + "_sealed"] = "%s: none of the %d cells in its box is reached from outside" % (tag, len(feet))


def cache_audit(R, sites, rewards=None):
    """Generate the rewards pack and read each sweep cache as Minecraft would: who earns it, where, how often, what."""
    if rewards is None:
        import rewards_pack as rewards
    doc = _j(DATA / "rewards.json")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "cobblers_rewards"
        rewards.write(doc, out)
        advs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (out / "data" / "cobblers" / "advancement" / "reward").glob("*.json")}
        fns = {p.stem: p.read_text(encoding="utf-8").splitlines() for p in (out / "data" / "cobblers" / "function" / "reward").glob("*.mcfunction")}
        every = [p for p in out.rglob("*") if p.is_file()]
        all_text = {p: p.read_text(encoding="utf-8") for p in every}
    champion = _j(DATA / "progression.json")
    cflag = [f for f in champion["flags"] if f["id"] == "champion_cleared"]
    R.check("caches", len(cflag) == 1 and "kanto_champion_blue" in json.dumps(cflag[0].get("set_by")),
            "data/progression.json champion_cleared is not set by defeating kanto_champion_blue")
    for sid, s in sites.items():
        item = s["item"]
        givers = [(p, l) for p, txt in all_text.items() for l in txt.splitlines()
                  if l.startswith("give ") and re.search(r"\b%s\b" % re.escape(item), l)]
        R.check(sid, len(givers) == 1, "%s: the rewards pack gives %s on %d lines" % (sid, item, len(givers)))
        if len(givers) != 1:
            continue
        rid = givers[0][0].stem
        line = givers[0][1]
        m = re.fullmatch(r"give @s %s(\[[^\]]*\])? (\d+)" % re.escape(item), line)
        R.check(sid, bool(m) and int(m.group(2)) == 1, "%s: %s gives %r, not one %s to the earning player" % (sid, rid, line, item))
        R.check(sid, sum(1 for l in fns.get(rid, []) if l.startswith("give ")) == 1,
                "%s: cobblers:reward/%s gives more than the item" % (sid, rid))
        adv = advs.get(rid)
        if not R.check(sid, adv is not None, "%s: no advancement grants cobblers:reward/%s" % (sid, rid)):
            continue
        R.check(sid, adv.get("rewards", {}).get("function") == "cobblers:reward/%s" % rid,
                "%s: the advancement's reward is %s" % (sid, adv.get("rewards")))
        crit = adv.get("criteria") or {}
        R.check(sid, len(crit) == 1, "%s: %d criteria" % (sid, len(crit)))
        for c in crit.values():
            R.check(sid, c.get("trigger") == "minecraft:location", "%s: trigger %s" % (sid, c.get("trigger")))
            conds = (c.get("conditions") or {}).get("player") or []
            preds = [x.get("predicate") or {} for x in conds if x.get("condition") == "minecraft:entity_properties"
                     and x.get("entity") == "this"]
            gates = [p.get("type_specific") or {} for p in preds]
            need = {"cobblers:flag/champion_cleared": True}
            ok = any(gt.get("type") in ("minecraft:player", "player") and all(
                (gt.get("advancements") or {}).get(k) == v for k, v in need.items()) for gt in gates)
            R.check(sid, ok, "%s: earning %s does not require cobblers:flag/champion_cleared" % (sid, rid))
            locs = [p.get("location") or {} for p in preds]
            hit = False
            for loc in locs:
                pos = loc.get("position") or {}
                if loc.get("dimension") != "minecraft:overworld" or not all(k in pos for k in "xyz"):
                    continue
                ax, ay, az = s["altar"]
                # the box the predicate accepts (feet as a double) must hold a standable cell beside the altar
                lo = [pos[k]["min"] for k in "xyz"]
                hi = [pos[k]["max"] for k in "xyz"]
                if not (lo[0] - 2 <= ax <= hi[0] + 1 and lo[2] - 2 <= az <= hi[2] + 1 and lo[1] - 2 <= ay <= hi[1] + 1):
                    continue
                hit = (lo, hi)
            if not R.check(sid, bool(hit), "%s: the advancement's location is not an overworld box at the altar %s"
                           % (sid, s["altar"])):
                continue
            lo, hi = hit
            feet, ok = _cache_cells(s, lo, hi)
            R.fact(sid + ".cache_standable_cells", len(feet))
            R.check(sid, len(feet) > 0, "%s: no cell in the cache's box is somewhere a player can stand" % sid)
            R.fact(sid + ".cache_cells_reached_from_outside", len(ok))
            if feet and not ok:
                R.known["giratina_dome_sealed" if "giratina" in sid else sid + "_sealed"] = (
                    "%s: none of the %d cells in the cache's box is reached from outside the template through passable "
                    "blocks: a player must break in" % (sid, len(feet)))
        # once per player: nothing revokes the reward advancement anywhere in the tools or the authored packs
        rev = []
        for f in glob.glob(str(ROOT / "tools" / "*.py")) + glob.glob(str(ROOT / "modpack" / "datapacks" / "**" / "*.mcfunction"), recursive=True):
            if Path(f).resolve() == Path(__file__).resolve():
                continue
            txt = Path(f).read_text(encoding="utf-8", errors="replace")
            if re.search(r"advancement revoke[^\n]*(reward/%s|reward/\*|everything)" % rid, txt):
                rev.append(os.path.relpath(f, ROOT))
        R.check(sid, not rev, "%s: cobblers:reward/%s can be revoked by %s (the cache is no longer once per player)" % (sid, rid, rev))


# ============================================================================================ 4. the levels


def level_audit(R, sites):
    for sid, s in sites.items():
        lv = s["levels"]
        R.check(sid, bool(lv), "%s: no level strings read from the summon block's class" % sid)
        if lv:
            R.check(sid, max(lv) <= CHAMPION_CAP, "%s: the altar rolls up to %d over the Champion cap %d" % (sid, max(lv), CHAMPION_CAP))
            below = [l for l in lv if l > 62]
            R.fact(sid + ".levels_needing_champion_cap", below)


# ============================================================================================ 5. the Hoopa model


class Ent:
    def __init__(self, kind, name, pos, dim="minecraft:overworld", **kw):
        self.kind, self.name, self.pos, self.dim = kind, name, list(pos), dim
        self.tags, self.adv, self.extra = set(), set(), dict(kw)
        self.gamemode = "survival"


class Return(Exception):
    def __init__(self, value):
        self.value = value


class Model:
    """A small reading of the commands the Hoopa pack uses. An unknown command raises Unmodelled."""

    def __init__(self, files, ns_fn):
        self.files = files
        self.ns_fn = ns_fn
        self.ents = []
        self.scores = {}          # (holder, objective) -> int
        self.objectives = set()
        self.time = 0
        self.schedule = {}
        self.chat = []
        self.spawned = []
        self.n = 0

    # ---- files
    def fn_lines(self, fid):
        ns, path = fid.split(":", 1)
        rel = "data/%s/function/%s.mcfunction" % (ns, path)
        if rel not in self.files:
            raise Unmodelled("function %s is not in the pack" % fid)
        return self.files[rel].splitlines()

    def call(self, fid, ctx, macro=None):
        try:
            for line in self.fn_lines(fid):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("$"):
                    if macro is None:
                        raise Unmodelled("macro line without arguments in %s" % fid)
                    line = re.sub(r"\$\((\w+)\)", lambda m: str(macro[m.group(1)]), line[1:])
                self.run(line, ctx)
        except Return as r:
            return r.value
        return 1

    # ---- holders and selectors
    def holder(self, tok, ctx):
        if tok.startswith("#"):
            return tok
        if tok == "@s":
            if ctx["as"] is None:
                raise Unmodelled("@s with no executor")
            return ctx["as"].name
        raise Unmodelled("score holder %s" % tok)

    def split_args(self, s):
        out, depth, cur = [], 0, ""
        for ch in s:
            if ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
            if ch == "," and depth == 0:
                out.append(cur)
                cur = ""
            else:
                cur += ch
        if cur:
            out.append(cur)
        return out

    def select(self, tok, ctx):
        m = re.fullmatch(r"(@[aes])(?:\[(.*)\])?", tok)
        if not m:
            hit = [e for e in self.ents if e.name == tok]
            return hit
        kind, args = m.group(1), m.group(2) or ""
        if kind == "@s":
            cands = [ctx["as"]] if ctx["as"] is not None else []
        elif kind == "@a":
            cands = [e for e in self.ents if e.kind == "player"]
        else:
            cands = list(self.ents)
        origin = list(ctx["pos"])
        dist = None
        limit, sort = None, None
        filters = []
        for a in self.split_args(args):
            k, v = a.split("=", 1)
            if k in ("x", "y", "z"):
                origin["xyz".index(k)] = float(v)
            elif k == "distance":
                lo, _, hi = v.partition("..") if ".." in v else (v, "", v)
                dist = (float(lo) if lo else None, float(hi) if hi else None)
            elif k == "type":
                want = v
                filters.append(lambda e, want=want: (e.kind == "player" and want == "minecraft:player") or
                               (e.kind == "pokemon" and want == "cobblemon:pokemon"))
            elif k == "tag":
                neg = v.startswith("!")
                t = v.lstrip("!")
                filters.append(lambda e, t=t, neg=neg: (t in e.tags) != neg)
            elif k == "gamemode":
                neg = v.startswith("!")
                gm = v.lstrip("!")
                filters.append(lambda e, gm=gm, neg=neg: e.kind == "player" and (e.gamemode == gm) != neg)
            elif k == "advancements":
                req = {}
                for kv in self.split_args(v.strip("{}")):
                    ak, av = kv.rsplit("=", 1)
                    req[ak] = av == "true"
                filters.append(lambda e, req=req: e.kind == "player" and all((ak in e.adv) == av for ak, av in req.items()))
            elif k == "nbt":
                mm = re.fullmatch(r'\{Pokemon:\{Species:"([^"]+)",PokemonOriginalTrainerType:"([^"]+)"\}\}', v)
                if not mm:
                    raise Unmodelled("nbt selector %s" % v)
                sp, ot = mm.groups()
                filters.append(lambda e, sp=sp, ot=ot: e.kind == "pokemon" and e.extra.get("species") == sp
                               and e.extra.get("ot", "NONE") == ot)
            elif k == "limit":
                limit = int(v)
            elif k == "sort":
                sort = v
            else:
                raise Unmodelled("selector argument %s" % k)
        out = []
        for e in cands:
            if e is None or not all(f(e) for f in filters):
                continue
            if dist is not None:
                if e.dim != ctx["dim"]:
                    continue
                d = math.dist(e.pos, origin)
                if (dist[0] is not None and d < dist[0]) or (dist[1] is not None and d > dist[1]):
                    continue
            out.append(e)
        if sort == "nearest":
            out.sort(key=lambda e: math.dist(e.pos, origin))
        elif sort not in (None, "arbitrary"):
            raise Unmodelled("sort=%s" % sort)
        return out[:limit] if limit else out

    def score(self, h, o):
        return self.scores.get((h, o))

    def matches(self, v, rng):
        if v is None:
            return False
        if ".." in rng:
            lo, hi = rng.split("..")
            return (lo == "" or v >= int(lo)) and (hi == "" or v <= int(hi))
        return v == int(rng)

    # ---- commands
    def run(self, line, ctx):
        toks = line.split(" ")
        head = toks[0]
        if head == "execute":
            return self.execute(toks[1:], ctx)
        if head == "return":
            if toks[1] == "run":
                v = self.run(" ".join(toks[2:]), ctx)
                raise Return(v)
            raise Return(int(toks[1]))
        if head == "function":
            fid = toks[1]
            macro = None
            if len(toks) > 2:
                macro = self.macro_args(" ".join(toks[2:]))
            return self.call(fid, ctx, macro)
        if head == "scoreboard":
            return self.scoreboard(toks[1:], ctx)
        if head == "schedule":
            # schedule function <id> <n>t replace
            if toks[1] != "function" or not toks[3].endswith("t"):
                raise Unmodelled(line)
            self.schedule[toks[2]] = self.time + int(toks[3][:-1])
            return 1
        if head == "time" and toks[1:] == ["query", "gametime"]:
            return self.time
        if head == "tag":
            for e in self.select(toks[1], ctx):
                (e.tags.add if toks[2] == "add" else e.tags.discard)(toks[3])
            return 1
        if head == "data" and toks[1:3] == ["merge", "entity"]:
            for e in self.select(toks[3], ctx):
                if "PersistenceRequired:1b" in line:
                    e.extra["persistent"] = True
                else:
                    raise Unmodelled(line)
            return 1
        if head == "tp":
            for e in self.select(toks[1], ctx):
                e.pos = [float(v) for v in toks[2:5]]
            return 1
        if head == "tellraw":
            for e in self.select(toks[1], ctx):
                self.chat.append((e.name, json.loads(line.split(" ", 2)[2])["text"]))
            return 1
        if head == "advancement" and toks[1] == "grant" and toks[3] == "only":
            for e in self.select(toks[2], ctx):
                e.adv.add(toks[4])
            return 1
        if head == "spawnpokemonat":
            x, y, z = (float(v) for v in toks[1:4])
            props = toks[4:]
            species = props[0] if ":" in props[0] else "cobblemon:" + props[0]
            level = None
            for p in props[1:]:
                if p.startswith("level="):
                    level = int(p.split("=", 1)[1])
                elif "=" not in p:
                    raise Unmodelled("spawn property %s" % p)
            self.n += 1
            e = Ent("pokemon", "pokemon#%d" % self.n, (x, y, z), ctx["dim"], species=species, level=level, ot="NONE")
            self.ents.append(e)
            self.spawned.append(e)
            return 1
        raise Unmodelled("command %r" % line)

    def macro_args(self, s):
        out = {}
        for kv in self.split_args(s.strip()[1:-1]):
            k, v = kv.split(":", 1)
            out[k] = v[1:-1] if v.startswith('"') else v
        return out

    def scoreboard(self, toks, ctx):
        if toks[0] == "objectives" and toks[1] == "add":
            self.objectives.add(toks[2])
            return 1
        if toks[0] != "players":
            raise Unmodelled("scoreboard %s" % " ".join(toks))
        op = toks[1]
        h = self.holder(toks[2], ctx)
        o = toks[3]
        if o not in self.objectives:
            raise Unmodelled("objective %s used before it is added" % o)
        if op == "set":
            self.scores[(h, o)] = int(toks[4])
        elif op == "add":
            self.scores[(h, o)] = (self.score(h, o) or 0) + int(toks[4])
        elif op == "reset":
            self.scores.pop((h, o), None)
        elif op == "operation":
            sym, h2, o2 = toks[4], self.holder(toks[5], ctx), toks[6]
            b = self.score(h2, o2) or 0
            a = self.score(h, o) or 0
            if sym == "=":
                self.scores[(h, o)] = b
            elif sym == "-=":
                self.scores[(h, o)] = a - b
            elif sym == "+=":
                self.scores[(h, o)] = a + b
            else:
                raise Unmodelled("operation %s" % sym)
        else:
            raise Unmodelled("scoreboard players %s" % op)
        return 1

    def execute(self, toks, ctx):
        i = 0
        ctxs = [dict(ctx)]
        store = None
        while i < len(toks):
            t = toks[i]
            if t == "run":
                rest = " ".join(toks[i + 1:])
                last = 0
                for c in ctxs:
                    last = self.run(rest, c)
                    if store:
                        h = self.holder(store[0], c)
                        self.scores[(h, store[1])] = int(last)
                return last
            if t == "in":
                for c in ctxs:
                    c["dim"] = toks[i + 1]
                i += 2
            elif t == "positioned":
                p = [float(v) for v in toks[i + 1:i + 4]]
                for c in ctxs:
                    c["pos"] = list(p)
                i += 4
            elif t == "as":
                new = []
                for c in ctxs:
                    for e in self.select(toks[i + 1], c):
                        d = dict(c)
                        d["as"] = e
                        new.append(d)
                ctxs = new
                i += 2
            elif t == "at":
                new = []
                for c in ctxs:
                    for e in self.select(toks[i + 1], c):
                        d = dict(c)
                        d["pos"], d["dim"] = list(e.pos), e.dim
                        new.append(d)
                ctxs = new
                i += 2
            elif t in ("if", "unless"):
                want = t == "if"
                kind = toks[i + 1]
                if kind == "score":
                    if toks[i + 4] == "matches":
                        f = lambda c, a=toks[i + 2], o=toks[i + 3], r=toks[i + 5]: self.matches(self.score(self.holder(a, c), o), r)
                        i += 6
                    elif toks[i + 4] in ("=", "<", ">", "<=", ">="):
                        def f(c, a=toks[i + 2], o=toks[i + 3], op=toks[i + 4], b=toks[i + 5], o2=toks[i + 6]):
                            va, vb = self.score(self.holder(a, c), o), self.score(self.holder(b, c), o2)
                            if va is None or vb is None:
                                return False
                            return {"=": va == vb, "<": va < vb, ">": va > vb, "<=": va <= vb, ">=": va >= vb}[op]
                        i += 7
                    else:
                        raise Unmodelled("execute if score ... %s" % toks[i + 4])
                elif kind == "entity":
                    f = lambda c, s=toks[i + 2]: bool(self.select(s, c))
                    i += 3
                else:
                    raise Unmodelled("execute %s %s" % (t, kind))
                ctxs = [c for c in ctxs if f(c) == want]
                if not ctxs:
                    return 0
            elif t == "store":
                if toks[i + 1] != "result" or toks[i + 2] != "score":
                    raise Unmodelled("execute store %s" % toks[i + 1])
                store = (toks[i + 3], toks[i + 4])
                i += 5
            else:
                raise Unmodelled("execute subcommand %s" % t)
        return len(ctxs)

    # ---- MoLang: the two callbacks' statements, nothing else
    def molang(self, text, binds):
        vars_ = {}
        stack = [True]
        for raw in text.splitlines():
            s = raw.strip()
            if not s or (s.startswith("'") and s.endswith("';")):
                continue
            if s == "};":
                stack.pop()
                continue
            m = re.fullmatch(r"(.+) \? \{", s)
            if m:
                stack.append(stack[-1] and self._mcond(m.group(1), vars_, binds))
                continue
            if not stack[-1]:
                continue
            m = re.fullmatch(r"t\.(\w+) = (q\.[\w.]+);", s)
            if m:
                vars_[m.group(1)] = self._mref(m.group(2), vars_, binds)
                continue
            m = re.fullmatch(r"t\.(\w+)\.(add_tag|remove_tag)\('([^']+)'\);", s)
            if m:
                e = vars_[m.group(1)]
                (e.tags.add if m.group(2) == "add_tag" else e.tags.discard)(m.group(3))
                continue
            m = re.fullmatch(r"q\.run_command\((.+)\);", s)
            if m:
                cmd = self._mstr(m.group(1), vars_, binds)
                p = binds.get("q.player") or binds.get("q.thrower")
                self.run(cmd, {"as": None, "pos": list(p.pos), "dim": p.dim})
                continue
            if s == "q.set_shakes(0);":
                binds["shakes"] = 0
                continue
            raise Unmodelled("MoLang statement %r" % s)
        return binds

    def _mref(self, ref, vars_, binds):
        if ref.startswith("t."):
            parts = ref.split(".")
            o = vars_[parts[1]]
            rest = parts[2:]
        else:
            parts = ref.split(".")
            key = ".".join(parts[:2])
            if key not in binds:
                raise Unmodelled("MoLang %s" % key)
            o = binds[key]
            rest = parts[2:]
        for r in rest:
            if r == "uuid":
                o = o.name
            elif r == "is_player":
                o = o.kind == "player"
            elif r == "species":
                o = ("species", o)
            elif r == "identifier" and isinstance(o, tuple):
                o = o[1].extra["species"]
            else:
                raise Unmodelled("MoLang .%s" % r)
        return o

    def _mcond(self, c, vars_, binds):
        m = re.fullmatch(r"t\.(\w+)\.has_tag\('([^']+)'\)", c)
        if m:
            return m.group(2) in vars_[m.group(1)].tags
        m = re.fullmatch(r"t\.(\w+)\.is_player", c)
        if m:
            return vars_[m.group(1)].kind == "player"
        m = re.fullmatch(r"t\.(\w+) == '([^']+)'", c)
        if m:
            return vars_[m.group(1)] == m.group(2)
        raise Unmodelled("MoLang condition %r" % c)

    def _mstr(self, expr, vars_, binds):
        out = ""
        for part in re.findall(r"'[^']*'|[tq]\.[\w.]+", expr):
            out += part[1:-1] if part.startswith("'") else str(self._mref(part, vars_, binds))
        return out

    # ---- driving
    def tick_to(self, t):
        while self.time < t:
            self.time += 1
            for fid, due in list(self.schedule.items()):
                if due <= self.time:
                    del self.schedule[fid]
                    self.call(fid, {"as": None, "pos": [0.0, 0.0, 0.0], "dim": "minecraft:overworld"})


def hoopa_audit(R, mod=None):
    """Build the Hoopa pack with the generator under test and run it through the scenarios."""
    if mod is None:
        import hoopa_cradle as mod
    doc = _j(DATA / "hoopa_cradle.json")
    relic = _j(DATA / "relic_underground.json")
    cr = relic["geometry"]["cradle"]
    spot = (cr["centre"][0] + 0.5, cr["floor_y"] + 1, cr["centre"][1] + 0.5)       # the cradle's own centre and floor
    binder = relic["geometry"]["release"]["at"]
    flag = "cobblers:flag/rift_crisis_resolved"
    files = mod.build(mod.load())
    load_fn = [json.loads(v)["values"] for k, v in files.items() if k.endswith("tags/function/load.json")]
    if not R.check("hoopa", len(load_fn) == 1 and len(load_fn[0]) == 1, "the pack's load tag is %s" % load_fn):
        return
    cap, err = rct_cap_after_gym8()
    R.check("hoopa", err is None, str(err))
    R.fact("hoopa.cap_after_gym8", cap)
    thr = []

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("threshold_advancements"), list):
                thr.append(o["threshold_advancements"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(relic)
    R.fact("hoopa.cradle_pass_thresholds", thr)
    R.check("hoopa", bool(thr) and all("cobblers:flag/gym8_cleared" in t for t in thr),
            "data/relic_underground.json: the pass into the cradle does not require gym8_cleared, so the cap there "
            "is not known to be the after-gym-8 cap")
    # the flag is granted by ONE transition (first, before anything that could fail), run by ONE dialogue node, and that
    # transition needs both HQ wins: so holding the flag means the player released Hoopa at the binder
    grants, runs = [], []
    for qd in _j(DATA / "quests.json")["quests"]:
        for tr in qd.get("transitions") or []:
            fx = tr.get("effects") or []
            if any(e.get("function") == flag + "/grant" for e in fx):
                grants.append((tr["id"], fx.index(next(e for e in fx if e.get("function") == flag + "/grant")),
                               sorted((c.get("field") or "", str(c.get("value"))) for c in tr.get("conditions") or [])))

    def walk_dlg(o, path):
        if isinstance(o, dict):
            nid = o.get("id", path)
            for k, v in o.items():
                if k == "transition" and isinstance(v, str) and any(v == g_[0] for g_ in grants):
                    runs.append(nid)
                walk_dlg(v, nid)
        elif isinstance(o, list):
            for v in o:
                walk_dlg(v, path)
    walk_dlg(_j(DATA / "dialogue.json"), None)
    R.fact("hoopa.flag_granted_by", grants)
    R.fact("hoopa.release_run_by", runs)
    R.check("hoopa", len(grants) == 1 and grants[0][1] == 0, "%s is granted by %s (want one transition, first effect)" % (flag, grants))
    R.check("hoopa", len(runs) == 1, "the granting transition is run by %d dialogue nodes %s, not 1" % (len(runs), runs))
    if grants:
        conds = dict(grants[0][2])
        R.check("hoopa", conds.get("quest.main_worldshift_reveal.brann_defeated") == "True"
                and conds.get("quest.main_worldshift_reveal.elara_defeated") == "True",
                "the release does not require both HQ wins: %s" % grants[0][2])
    cap_cb = [k for k in files if "poke_ball_capture_calculated" in k]
    got_cb = [k for k in files if "/callbacks/pokemon_captured/" in k]
    R.check("hoopa", len(cap_cb) == 1 and len(got_cb) == 1, "the pack's callbacks are %s / %s" % (cap_cb, got_cb))
    respawn = doc["keeper"]["respawn_after_ticks"]
    period = doc["keeper"]["period_ticks"]
    R.fact("hoopa.respawn_after_ticks", respawn)

    def fresh():
        m = Model(files, None)
        m.call(load_fn[0][0], {"as": None, "pos": [0.0, 0.0, 0.0], "dim": "minecraft:overworld"})
        return m

    def player(m, name, at, flagged):
        p = Ent("player", name, at)
        if flagged:
            p.adv.add(flag)
        m.ents.append(p)
        return p

    def hoopas(m, owner=None):
        out = [e for e in m.ents if e.kind == "pokemon" and e.extra["species"] == "cobblemon:hoopa"]
        if owner is not None:
            pid = m.score(owner.name, doc["objectives"]["id"])
            out = [e for e in out if pid is not None and m.score(e.name, doc["objectives"]["own"]) == pid]
        return out

    def throw(m, thrower, target):
        b = {"q.thrower": thrower, "q.pokemon": target, "q.player": thrower}
        m.molang(files[cap_cb[0]], b)
        return b.get("shakes") != 0

    def capture(m, catcher, target):
        m.ents.remove(target)
        m.molang(files[got_cb[0]], {"q.player": catcher, "q.pokemon": target})

    try:
        # S1: a player without the flag, at the binder, for a long time: nothing
        m = fresh()
        a = player(m, "nobody", (binder[0] + 0.5, binder[1], binder[2] + 0.5), False)
        m.tick_to(3000)
        R.check("hoopa", not hoopas(m), "a player without %s got %d Hoopa(s)" % (flag, len(hoopas(m))))

        # S2: a released player at the binder: one Hoopa within a keeper period, at the cradle's centre, level 60
        m = fresh()
        a = player(m, "alice", (binder[0] + 0.5, binder[1], binder[2] + 0.5), True)
        m.tick_to(period + 1)
        hs = hoopas(m)
        R.check("hoopa", len(hs) == 1, "a released player at the binder has %d Hoopa(s) after %d ticks, not 1" % (len(hs), period + 1))
        if hs:
            h = hs[0]
            R.check("hoopa", tuple(h.pos) == spot, "the Hoopa appears at %s, not the cradle's centre %s" % (tuple(h.pos), spot))
            R.check("hoopa", h.extra.get("level") == 60, "the Hoopa is level %s, not 60" % h.extra.get("level"))
            R.check("hoopa", cap is not None and h.extra.get("level", 999) <= cap,
                    "the Hoopa's level %s is over the cap %s a player has at the cradle" % (h.extra.get("level"), cap))
            R.check("hoopa", h.extra.get("persistent"), "the Hoopa is not PersistenceRequired")
            R.check("hoopa", hoopas(m, a) == [h], "the Hoopa is not bound to the player who released")
        m.tick_to(4000)
        R.check("hoopa", len(hoopas(m)) == 1, "after 4000 ticks the released player has %d Hoopas, not 1" % len(hoopas(m)))

        # S3: the Hoopa is lost: nothing before respawn_after_ticks, one again after it
        if hoopas(m):
            m.ents.remove(hoopas(m)[0])
            lost = m.time
            back = None
            while m.time < lost + respawn + 4 * period:
                m.tick_to(m.time + 1)
                if hoopas(m):
                    back = m.time
                    break
            R.check("hoopa", back is not None, "a lost Hoopa never came back within %d ticks" % (respawn + 4 * period))
            if back is not None:
                R.fact("hoopa.came_back_after", back - lost)
                R.check("hoopa", back - lost >= respawn, "a lost Hoopa came back after %d ticks, under %d" % (back - lost, respawn))
                R.check("hoopa", len(hoopas(m)) == 1, "%d Hoopas came back" % len(hoopas(m)))

        # S4: a second released player gets their own; neither gets a second
        b = player(m, "bob", (spot[0] + 3, spot[1], spot[2]), True)
        m.tick_to(m.time + 3 * period)
        R.check("hoopa", len(hoopas(m, a)) == 1 and len(hoopas(m, b)) == 1 and len(hoopas(m)) == 2,
                "two released players have %d and %d Hoopas (%d in all)" % (len(hoopas(m, a)), len(hoopas(m, b)), len(hoopas(m))))

        # S5: balls. Only the owner's holds; an unreleased thrower and another released player are refused
        c = player(m, "carol", (spot[0] - 3, spot[1], spot[2]), False)
        if hoopas(m, a) and hoopas(m, b):
            ha, hb = hoopas(m, a)[0], hoopas(m, b)[0]
            R.check("hoopa", not throw(m, c, ha), "a player without the flag can catch a cradle Hoopa")
            R.check("hoopa", not throw(m, b, ha), "a released player can catch ANOTHER player's Hoopa")
            R.check("hoopa", throw(m, a, ha), "the owner's ball does not hold their own Hoopa")
            R.check("hoopa", throw(m, b, hb), "the second owner's ball does not hold their own Hoopa")
            R.check("hoopa", not any("cobblers.hoopa_hit" in e.tags or "cobblers.hoopa_refuse" in e.tags for e in m.ents),
                    "a ball check left its working tags behind")
            # S6: the owner catches theirs: the caught advancement, and never another
            capture(m, a, ha)
            R.check("hoopa", doc["caught_advancement"] in a.adv, "catching at the cradle did not grant %s" % doc["caught_advancement"])
            m.tick_to(m.time + respawn * 3)
            R.check("hoopa", not hoopas(m, a), "the player who caught theirs got another %d Hoopa(s)" % len(hoopas(m, a)))
            R.check("hoopa", len(hoopas(m, b)) == 1, "the other player's Hoopa went away when the first was caught")
        # S7: a Hoopa caught far away (a raid den) grants nothing
        far = player(m, "dave", (100.0, 70.0, 100.0), True)
        den = Ent("pokemon", "den_hoopa", (101.0, 70.0, 100.0), species="cobblemon:hoopa", level=50, ot="NONE")
        m.ents.append(den)
        capture(m, far, den)
        R.check("hoopa", doc["caught_advancement"] not in far.adv, "a Hoopa caught far from the cradle granted the cradle's catch")
        # S8: a released player outside the cradle gets nothing until they come in
        m2 = fresh()
        e = player(m2, "erin", (spot[0] + 40, spot[1], spot[2]), True)
        m2.tick_to(1000)
        R.check("hoopa", not hoopas(m2), "a released player 40 blocks off the spot got a Hoopa")
    except Unmodelled as ex:
        R.check("hoopa", False, "the Hoopa pack uses something this audit does not model: %s" % ex)


# ============================================================================================ 6. the catalogue


def catalogue_audit(R, packs):
    cat = _j(DATA / "adopted_legendary_sites.json").get("catalogue_2026_10_06", {}).get("templates") or []
    wrong = []
    for t in cat:
        tid = t.get("template", "")
        if ":" not in tid or "*" in tid or " " in tid:
            continue
        ns, rel = tid.split(":", 1)
        path = "data/%s/structure/%s.nbt" % (ns, rel)
        # a catalogue entry names a template, or a jigsaw structure whose pieces sit in a folder of that name
        loaded = packs.find(path) is not None or any(
            n.startswith("data/%s/structure/%s/" % (ns, rel)) and n.endswith(".nbt")
            for _l, _k, _h, n in packs.files(prefix="data/%s/structure/" % ns))
        if t.get("loaded") is not None and bool(t["loaded"]) != loaded:
            wrong.append("%s loaded=%s, measured %s" % (tid, t["loaded"], loaded))
    R.fact("catalogue.templates", len(cat))
    R.check("catalogue", not wrong, "catalogue_2026_10_06 'loaded' disagrees with the installed packs: %s" % wrong)


# ============================================================================================ the run


def audit(server_dir, ground, pl=None, hoopa=None, rewards=None, donor=None, sections=None):
    R = Report()
    sections = sections or ("pastes", "sources", "caches", "levels", "hoopa", "catalogue")
    packs = Packs(server_dir) if any(s in sections for s in ("pastes", "sources", "caches", "levels", "catalogue")) else None
    sites = {}
    if packs is not None:
        try:
            sites = paste_audit(R, packs, ground, pl, donor) if ground is not None else {}
        except Unmodelled as e:
            R.check("pastes", False, str(e))
    if "sources" in sections:
        source_audit(R, packs, sites)
    if "caches" in sections:
        cache_audit(R, sites, rewards)
        extra_cache_audit(R, packs, sites, rewards)
    if "levels" in sections:
        level_audit(R, sites)
    if "hoopa" in sections:
        hoopa_audit(R, hoopa)
    if "catalogue" in sections:
        catalogue_audit(R, packs)
    for k in KNOWN:
        if "caches" in sections and k not in R.known:
            R.check("known", False, "KNOWN %s no longer reproduces; remove it from KNOWN in this file" % k)
    for k in R.known:
        if k not in KNOWN:
            R.check("known", False, "unlisted finding: %s" % R.known[k])
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--server-dir", default=os.environ.get("COBBLERS_AUDIT_SERVER_DIR") or str(SNAPSHOT),
                    help="a server tree holding mods/ and datapacks/ (default: the offline snapshot)")
    ap.add_argument("--source-root")
    ap.add_argument("--out", help="write the full report here (JSON)")
    a = ap.parse_args(argv)
    import ground as G
    R = audit(a.server_dir, G.load(a.source_root))
    rep = {"problems": ["%s: %s" % p for p in R.problems], "known": R.known, "facts": R.facts}
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(rep, indent=1, default=str) + "\n", encoding="utf-8")
    for p in rep["problems"]:
        print("PROBLEM %s" % p)
    for k, v in R.known.items():
        print("KNOWN %s: %s" % (k, v))
    print("legendary_sweep_audit: %s (%d problem(s), %d known, %d facts)"
          % ("FAIL" if R.problems else "PASS", len(R.problems), len(R.known), len(R.facts)))
    return 1 if R.problems else 0


if __name__ == "__main__":
    sys.exit(main())
