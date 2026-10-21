#!/usr/bin/env python
"""Independent audit of the undoing of Groudon's quake cavern (2026-10-21) and the return of its sealed chamber.

The owner, 2026-10-21: "undo groudon cave", then "Old chamber back". tools/groudon_cavern.py emits a cleanup (in
cobblers_legendaries, run by R14L before any summon) and tools/legendaries.py carves the old chamber again. This audit
checks the two together, and it does NOT import tools/groudon_cavern.py: no model, no mask, no band function. It reads

  - the cavern AS THE WORLD RECEIVED IT: build/groudon_cavern_applied (the carve and the three cuts, as text), held to the
    sha256 frozen in data/legendaries.json (groudon retired_sites quake_cavern_v1 applied), so a later change of the model
    cannot slip a different cavern under the check;
  - the cleanup AS EMITTED: the retire_quake_cavern_v1 functions of build/datapacks/cobblers_legendaries, as text;
  - the canonical heightmap through tools/ground.py (the natural terrain: solid to the ground, air over it);
  - the declared intent: the model box and the rim's wall block (data/groudon_cavern.json), the retired site's terrain,
    pedestal and probe block, the record, the Red Orb's container (data/rewards.json), and its own copy of the chamber's
    ORIGINAL numbers (git show 9d764bcc^:data/legendaries.json, groudon), derived through tools/legendaries_audit.py
    own_old_site, the audit-side derivation, never tools/legendaries.py geometry();

and REPLAYS: the natural terrain, then the record (carve_once and its parts, then stages 2, 3 and 4, following calls, a
conditional call as if its condition held), then the owner's removal of the lake's walls, then the cleanup's restore
(following its calls; a `fill ... replace <block>` touches only cells holding that block). On the result:

  record    the record's sha256 is the frozen one; the replay wrote more than 100,000 cells (never vacuous)
  void      no cell the cavern wrote at or under its column's ground is air afterwards (no void left in the envelope, no
            air pocket in the ravine's fill)
  lava      no lava anywhere in the model box afterwards
  wall      no wall block anywhere in the model box afterwards (the rim's guards and the lake's)
  surface   every column the cut lowered stands at round(ground(x, z)) again, with the site's surface block on top
  terrain   every written cell at or under the ground holds the site's terrain block for its depth (deep, under, surface)
  over      nothing the cavern wrote over the ground is anything but air afterwards
  reach     the restore writes no cell the cavern did not write (unfiltered), and over the ground it writes only air in
            place of the rim's wall block (so stones placed by hand over the ground stay)
  held      every cell a player could stand in that the restore fills (air or lava before, rock after) lies in a box the act
            tags as held; the kill and both restore calls are refused while anyone is held; the chain counts the held
  act       the restore is called only while #built is 1 or the dais's pedestal holds its block (the record wrote that block
            there, the restore puts rock there), clears the chamber's open score first, writes the pedestal LAST, then sets
            #built and #quake to 0; the kill is the record's tag, the pokemon type and a box holding the hall and the
            Groudon the owner moved onto the lava, and not the chamber's Groudon
  chunks    the chain force-loads one box (at most 256 chunks) holding every restore write; the restore and its parts carry no
            forceload of their own and name the chain as what loads them; the number of chunks held is reported
  order     R14L runs the cleanup, waits, reads 0 held back, before any chamber step and before Groudon's carve_once
  chamber   Groudon's record is the sealed chamber with its original numbers; its carve, replayed onto the terrain, leaves the
            ladder shaft, the plug, the chamber and the smooth_basalt pedestal where own_old_site puts them; carve_once is
            held only by the open score the restore clears; the Red Orb's container is that pedestal; `met` still exists
  withdrawn the cavern's two packs are in tools/reapply.py WITHDRAWN and in no install list, nothing calls a
            cobblers:groudon_cavern function, and no copy is left in build/datapacks

NOT PROVEN: anything in a running game (that the chain's look sees Groudon, that `kill` takes it, that 88 force-loaded
chunks load within the chain's wait, that the fills land); the real world's blocks (the 85 hand-placed stones are not
modelled: the restore writes rock at or under the ground where they may stand, and nothing over it but air for walls);
the surface block itself (the site's terrain.surface_verified is false); that the live world's #built is 1 (relayed).

  python tools/groudon_revert_audit.py [--legendaries DIR] [--applied DIR] [--source-root R]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

PACKS = ROOT / "build" / "datapacks"
LEG_PACK = PACKS / "cobblers_legendaries"
APPLIED = ROOT / "build" / "groudon_cavern_applied"
DATA = ROOT / "data"
RID, SID = "groudon", "quake_cavern_v1"
WITHDRAWN_PACKS = ("cobblers_groudon_cavern", "cobblers_groudon_cavern_build")
APPLIED_ENTRY = "cobblers:legendary/groudon/carve_once"
APPLIED_STAGES = ("cobblers:groudon_cavern/stage/2", "cobblers:groudon_cavern/stage/3", "cobblers:groudon_cavern/stage/4")
HELD = "cobblers_leg_retire_held"
OWNER_GROUDON = (6763.5, 65.0, 5612.5)      # relayed: the owner moved it onto the lava (brief of 2026-10-21)
MIN_WRITTEN = 100_000
# the chamber as it stood before 2026-10-20: git show 9d764bcc^:data/legendaries.json, record groudon; bore, shell_margin and
# pedestal_block are that file's defaults (unchanged since)
ORIGINAL = {"portal": [6672, 5508], "approach": {"bearing_deg": 180, "drop": 40, "passage": 14},
            "chamber": {"width": 21, "length": 21, "height": 11, "alcove": 0}, "plug_depth": 8,
            "bore": 3, "shell_margin": 4, "pedestal_block": "minecraft:smooth_basalt"}

AIR, SOLID, LAVA, WALL = 0, 1, 2, 3
AIRS = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
NUM = r"(-?\d+)"
FILL = re.compile(r"^fill\s+%s\s+%s\s+%s\s+%s\s+%s\s+%s\s+(\S+)(?:\s+(\S+)(?:\s+(\S+))?)?$" % ((NUM,) * 6))
SETBLOCK = re.compile(r"^setblock\s+%s\s+%s\s+%s\s+(\S+)(?:\s+(\S+))?$" % ((NUM,) * 3))
CALL = re.compile(r"(?:^|\brun\s+)function\s+(\S+)\s*$")
VOL = re.compile(r"x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(-?\d+),dy=(-?\d+),dz=(-?\d+)")
FORCELOAD = re.compile(r"^forceload\s+(add|remove)\s+%s\s+%s\s+%s\s+%s$" % ((NUM,) * 4))


class Report:
    def __init__(self):
        self.errors, self.checks, self.notes = [], 0, []

    def check(self, ok, msg):
        self.checks += 1
        if not ok:
            self.errors.append(msg)
        return bool(ok)


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def bare(name):
    return name.split("[", 1)[0].split("{", 1)[0]


def cls_of(name):
    n = bare(name)
    if n in AIRS:
        return AIR
    if n == "minecraft:lava":
        return LAVA
    if n.endswith("_wall"):
        return WALL
    return SOLID


class Pack:
    """Function text by id, from one or more folders laid out as a datapack (pack.mcmeta not needed)."""

    def __init__(self, *dirs):
        self.fns, self.files = {}, {}
        for d in dirs:
            d = Path(d)
            if not (d / "data").is_dir():
                continue
            for f in sorted((d / "data").glob("*/function/**/*.mcfunction")):
                rel = f.relative_to(d / "data").parts
                fid = "%s:%s" % (rel[0], "/".join(rel[2:])[:-len(".mcfunction")])
                text = f.read_text(encoding="utf-8")
                self.fns[fid] = text.splitlines()
                self.files[f.relative_to(d).as_posix()] = text

    def body(self, fid):
        return [l.strip() for l in self.fns.get(fid, []) if l.strip() and not l.strip().startswith("#")]


def record_digest(files):
    """sha256 over the files sorted by path: path, newline, text (the generator's own rule, written here again)."""
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(rel.encode("utf-8") + b"\n" + files[rel].encode("utf-8"))
    return h.hexdigest()


class World:
    """The model box: natural terrain from the heightmap, then replayed writes (a name per cell; 0 = natural)."""

    def __init__(self, ground, box):
        x0, y0, z0, x1, y1, z1 = box
        self.o = (x0, y0, z0)
        self.shape = (x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1)
        self.G = np.asarray(ground.box(x0, z0, x1, z1)).T.astype(np.int32)    # (nx, nz)
        assert self.G.shape == (self.shape[0], self.shape[2]), self.G.shape
        ys = (y0 + np.arange(self.shape[1]))[None, :, None]
        self.rel = ys - self.G[:, None, :]
        self.names = ["natural"]
        self.nid = np.zeros(self.shape, np.int16)
        self.outside = []

    def copy(self):
        w = World.__new__(World)
        w.o, w.shape, w.G, w.rel = self.o, self.shape, self.G, self.rel
        w.names, w.nid, w.outside = list(self.names), self.nid.copy(), list(self.outside)
        return w

    def name_id(self, n):
        if n not in self.names:
            self.names.append(n)
        return self.names.index(n)

    def sl(self, box):
        x0, y0, z0, x1, y1, z1 = box
        ox, oy, oz = self.o
        i0, j0, k0, i1, j1, k1 = x0 - ox, y0 - oy, z0 - oz, x1 - ox, y1 - oy, z1 - oz
        if min(i0, j0, k0) < 0 or i1 >= self.shape[0] or j1 >= self.shape[1] or k1 >= self.shape[2]:
            return None
        return (slice(i0, i1 + 1), slice(j0, j1 + 1), slice(k0, k1 + 1))

    def write(self, box, block, filt=None, track=None):
        s = self.sl(box)
        if s is None:
            self.outside.append((box, block))
            return None
        nid = self.name_id(bare(block))
        if filt is None:
            m = np.ones(self.nid[s].shape, bool)
        else:
            ids = [i for i, n in enumerate(self.names) if n != "natural" and bare(n) == bare(filt)]
            m = np.isin(self.nid[s], ids)
        self.nid[s] = np.where(m, nid, self.nid[s])
        if track is not None:
            track[s] |= m
        return m

    def classes(self):
        """Per cell AIR / SOLID / LAVA / WALL (natural: solid to the ground, air over it)."""
        lut = np.array([AIR] + [cls_of(n) for n in self.names[1:]], np.int8)
        c = lut[self.nid]
        nat = self.nid == 0
        c[nat] = np.where(self.rel[nat] <= 0, SOLID, AIR)
        return c

    def name_at(self, x, y, z):
        i, j, k = x - self.o[0], y - self.o[1], z - self.o[2]
        n = self.names[int(self.nid[i, j, k])]
        if n == "natural":
            return "natural_solid" if self.rel[i, j, k] <= 0 else "minecraft:air"
        return n


def replay(pack, fid, world, filtered=False, track=None, seen=None, depth=0, log=None):
    """Apply fid's fill and setblock lines (following function calls) to world. `track` collects every cell written."""
    seen = [] if seen is None else seen
    if depth > 12 or fid not in pack.fns:
        return seen
    seen.append(fid)
    for line in pack.body(fid):
        m = FILL.match(line)
        if m:
            v = [int(a) for a in m.groups()[:6]]
            box = (min(v[0], v[3]), min(v[1], v[4]), min(v[2], v[5]), max(v[0], v[3]), max(v[1], v[4]), max(v[2], v[5]))
            mode, filt = m.group(8), m.group(9)
            if log is not None:
                log.append(("fill", box, m.group(7), mode, filt))
            world.write(box, m.group(7), filt if (mode == "replace" and filt) else None, track)
            continue
        m = SETBLOCK.match(line)
        if m:
            x, y, z = (int(a) for a in m.groups()[:3])
            if log is not None:
                log.append(("setblock", (x, y, z, x, y, z), m.group(4), m.group(5), None))
            world.write((x, y, z, x, y, z), m.group(4), None, track)
            continue
        m = CALL.search(line)
        if m and m.group(1) in pack.fns:
            replay(pack, m.group(1), world, filtered, track, seen, depth + 1, log)
    return seen


def vol_box(m):
    x, y, z, dx, dy, dz = (int(v) for v in m.groups())
    return (x, y, z, x + dx, y + dy, z + dz)


def inside(c, b):
    return all(b[i] <= c[i] <= b[i + 3] for i in range(3))


# ------------------------------------------------------------------------------------------------------------ the audit


def audit(legendaries=LEG_PACK, applied=APPLIED, ground=None, leg=None, gdoc=None, rewards=None, reapply_mod=None,
          steps=None):
    rep = Report()
    if ground is None:
        import ground as G
        ground = G.Ground()
    leg = leg or jload(DATA / "legendaries.json")
    gdoc = gdoc or jload(DATA / "groudon_cavern.json")
    rewards = rewards or jload(DATA / "rewards.json")
    ns, obj, prefix = leg["namespace"], leg["objective"], leg["tag_prefix"]
    rec = next((r for r in leg["encounters"] if r["id"] == RID), None)
    if not rep.check(rec is not None, "data/legendaries.json has no %s" % RID):
        return rep
    site = next((s for s in rec.get("retired_sites") or [] if s.get("id") == SID), None)
    if not rep.check(site is not None and site.get("kind") == "quake_cavern",
                     "%s: no retired site %s of kind quake_cavern" % (RID, SID)):
        return rep
    terrain = site["terrain"]
    b = gdoc["box"]
    box = (b["x"][0], b["y"][0], b["z"][0], b["x"][1], b["y"][1], b["z"][1])
    q = gdoc["quake"]["objective"]
    wall_block = gdoc["palette"]["rim_guard"]
    base = "%s:legendary/%s/retire_%s" % (ns, RID, SID)
    restore = base + "_restore"
    holder = "legret_%s_%s" % (RID, SID)

    # ---- record: what the world received ---------------------------------------------------------------------------
    rec_pack = Pack(applied)
    rep.check(bool(rec_pack.files), "no record of what the world received at %s (python tools/groudon_cavern.py build)"
              % applied)
    sha = record_digest(rec_pack.files)
    rep.check(sha == (site.get("applied") or {}).get("sha256"),
              "the record's sha256 %s is not the frozen %s: the cavern it replays is not the one that was built"
              % (sha[:12], ((site.get("applied") or {}).get("sha256") or "")[:12]))
    rep.check(APPLIED_ENTRY in rec_pack.fns and all(s in rec_pack.fns for s in APPLIED_STAGES),
              "the record lacks carve_once or a stage: %s" % sorted(rec_pack.fns))

    natural = World(ground, box)
    before = natural.copy()
    wrote_before = np.zeros(before.shape, bool)
    replay(rec_pack, APPLIED_ENTRY, before, track=wrote_before)
    for s in APPLIED_STAGES:
        replay(rec_pack, s, before, track=wrote_before)
    rep.check(not before.outside, "the record writes outside the model box: %s" % before.outside[:2])
    rep.check(int(wrote_before.sum()) > MIN_WRITTEN, "NOTHING TO CHECK: the record wrote %d cells" % int(wrote_before.sum()))
    # the owner removed the lake's walls by hand (relayed); they are under the ground
    cb = before.classes()
    lake_walls = (cb == WALL) & (before.rel <= 0)
    before.nid[lake_walls] = before.name_id("minecraft:air")
    rep.notes.append("record: %d cells written, %d lake wall cells removed as the owner did" %
                     (int(wrote_before.sum()), int(lake_walls.sum())))
    cb = before.classes()
    top_before = np.where(cb == SOLID, np.arange(before.shape[1])[None, :, None] + box[1], -10_000).max(axis=1)
    lowered = top_before < before.G

    # ---- the cleanup, as emitted --------------------------------------------------------------------------------------
    lp = Pack(legendaries)
    for fid in (base, base + "_look", base + "_act", base + "_done", restore):
        rep.check(fid in lp.fns, "the legendaries pack has no %s" % fid)
    after = before.copy()
    wrote = np.zeros(after.shape, bool)          # cells an UNFILTERED restore write touched
    log = []
    called = replay(lp, restore, after, log=log)
    for _kind, bx, _blk, _mode, filt in log:
        s = after.sl(bx)
        if s is not None and not filt:
            wrote[s] = True
    rep.check(not after.outside, "the restore writes outside the model box: %s" % after.outside[:2])
    parts = [f for f in called if f.startswith(restore + "_p_")]
    rep.check(bool(parts), "the restore calls no part")
    ca = after.classes()
    touched = wrote_before
    under = after.rel <= 0

    def first(mask):
        idx = np.argwhere(mask)[:3]
        return [tuple(int(v) + o for v, o in zip(c, box[:3])) for c in idx]

    m = touched & under & (ca == AIR)
    rep.check(not m.any(), "void: %d cell(s) the cavern wrote at or under the ground are still air, e.g. %s"
              % (int(m.sum()), first(m)))
    m = ca == LAVA
    rep.check(not m.any(), "lava: %d lava cell(s) left, e.g. %s" % (int(m.sum()), first(m)))
    m = ca == WALL
    rep.check(not m.any(), "wall: %d wall cell(s) left, e.g. %s" % (int(m.sum()), first(m)))
    m = touched & ~under & (ca != AIR)
    rep.check(not m.any(), "over: %d cell(s) the cavern wrote over the ground are not air, e.g. %s"
              % (int(m.sum()), first(m)))
    # terrain by depth
    band = {0: terrain["surface"], -1: terrain["under"], -2: terrain["under"]}
    lut = np.array([n for n in after.names], object)
    have = lut[after.nid]
    exp_deep = touched & (after.rel <= -3)
    exp_under = touched & (after.rel >= -2) & (after.rel <= -1)
    exp_surf = touched & (after.rel == 0)
    bad = (exp_deep & (have != terrain["deep"])) | (exp_under & (have != band[-1])) | (exp_surf & (have != band[0]))
    rep.check(not bad.any(), "terrain: %d written cell(s) at or under the ground do not hold the site's terrain block for "
              "their depth, e.g. %s" % (int(bad.sum()), first(bad)))
    # surface of every column the cut lowered
    ys = np.arange(after.shape[1])[None, :, None] + box[1]
    top_after = np.where(ca == SOLID, ys, -10_000).max(axis=1)
    rep.check(int(lowered.sum()) > 100, "NOTHING TO CHECK: only %d column(s) were lowered by the cut" % int(lowered.sum()))
    off = lowered & (top_after != after.G)
    rep.check(not off.any(), "surface: %d column(s) the cut lowered do not stand at round(ground) again, e.g. %s"
              % (int(off.sum()), [(int(i) + box[0], int(k) + box[2], int(top_after[i, k]), int(after.G[i, k]))
                                  for i, k in np.argwhere(off)[:3]]))
    gi = (after.G - box[1]).clip(0, after.shape[1] - 1)
    top_names = have[np.arange(after.shape[0])[:, None], gi, np.arange(after.shape[2])[None, :]]
    off = lowered & (top_names != terrain["surface"])
    rep.check(not off.any(), "surface: %d lowered column(s) are not topped with %s" % (int(off.sum()), terrain["surface"]))
    rep.notes.append("surface: %d columns the cut lowered, all back at round(ground)" % int(lowered.sum()))
    # reach
    m = wrote & ~touched
    rep.check(not m.any(), "reach: the restore writes %d cell(s) the cavern never wrote, e.g. %s" % (int(m.sum()), first(m)))
    m = wrote & ~under
    rep.check(not m.any(), "reach: the restore writes %d cell(s) over the ground without a filter (a hand-placed stone there "
              "would go), e.g. %s" % (int(m.sum()), first(m)))
    airs = [e for e in log if cls_of(e[2]) == AIR]
    rep.check(all(e[3] == "replace" and e[4] and bare(e[4]) == bare(wall_block) for e in airs),
              "reach: an air write in the restore is not `replace %s`: %s"
              % (wall_block, [e for e in airs if not (e[3] == "replace" and e[4] == wall_block)][:2]))
    rep.check(all(cls_of(e[2]) == AIR for e in log if e[4]), "reach: a filtered write puts something other than air")

    # ---- the act --------------------------------------------------------------------------------------------------------
    guard = "@a[tag=%s]" % HELD
    act = lp.body(base + "_act")
    held_boxes, gates, kills, stray, cleared = [], [], [], [], False
    sel_kill = None
    px, py, pz = (int(v) for v in site["pedestal"])
    for s in act:
        mm = re.match(r"^tag @a\[(%s)\] add %s$" % (VOL.pattern, HELD), s)
        if mm:
            held_boxes.append(vol_box(VOL.search(mm.group(1))))
            continue
        if s == "tag @a remove %s" % HELD:
            cleared = not held_boxes
            continue
        if s == "scoreboard objectives add %s dummy" % q or s.startswith("scoreboard players set #%s_seen" % holder) \
                or s.startswith("schedule function %s_done" % base):
            continue
        mm = re.match(r"^execute unless entity %s run kill @e\[(.*)\]$" % re.escape(guard), s)
        if mm:
            kills.append(mm.group(1))
            continue
        mm = re.match(r"^execute unless entity %s (if .*) run function (\S+)$" % re.escape(guard), s)
        if mm and mm.group(2) == restore:
            gates.append(mm.group(1))
            continue
        stray.append(s)
    rep.check(not stray, "act: lines this audit does not recognise: %s" % stray[:3])
    rep.check(cleared, "act: the held tag is not cleared before it is given")
    rep.check(bool(held_boxes), "held: the act tags no player as held")
    danger = touched & under & np.isin(cb, (AIR, LAVA))
    covered = np.zeros(after.shape, bool)
    for hb in held_boxes:
        s = after.sl(tuple(max(hb[i], box[i]) if i < 3 else min(hb[i], box[i]) for i in range(6)))
        if s is not None:
            covered[s] = True
    m = danger & ~covered
    rep.check(int(danger.sum()) > 1000, "NOTHING TO CHECK: %d cells a player could stand in" % int(danger.sum()))
    rep.check(not m.any(), "held: %d cell(s) a player could stand in that the restore fills lie in no held box, e.g. %s"
              % (int(m.sum()), first(m)))
    rep.check(sorted(gates) == sorted(["if score #built %s matches 1" % q,
                                       "if block %d %d %d %s" % (px, py, pz, site["pedestal_block"])]),
              "act: the restore is not called exactly on #built 1 and on the pedestal: %s" % gates)
    rep.check(bare(before.name_at(px, py, pz)) == site["pedestal_block"],
              "act: the pedestal probe (%d, %d, %d) is %s in the cavern as built, not %s"
              % (px, py, pz, before.name_at(px, py, pz), site["pedestal_block"]))
    rep.check(bare(after.name_at(px, py, pz)) != site["pedestal_block"],
              "act: the restore leaves the pedestal's block, so it would run again")
    tag = "tag=%s%s" % (prefix, RID)
    if rep.check(len(kills) == 1, "act: %d kill line(s), not one" % len(kills)):
        sel = kills[0]
        vm = VOL.search(sel)
        kb = vol_box(vm) if vm else None
        own = None
        try:
            import legendaries_audit as LA
            own = LA.own_old_site(dict(ORIGINAL), ground)
        except Exception as e:  # noqa: BLE001
            rep.errors.append("chamber: own_old_site failed: %s" % e)
        hall_spot = (px, py + 1, pz)
        ok = bool(kb) and "type=cobblemon:pokemon" in sel.split(",") and tag in sel.split(",") \
            and inside(tuple(int(np.floor(v)) for v in OWNER_GROUDON), kb) and inside(hall_spot, kb) \
            and not (own and inside(own["legendary"], kb))
        rep.check(ok, "act: the kill is not the record's tag and the pokemon type in a box holding the Groudon on the lava "
                      "and the dais, and not the chamber's Groudon: %s" % sel)
    done = lp.body(base + "_done")
    rep.check(any("store result score #%s cobblers_chunk_look if entity @e[tag=%s]" % (holder, HELD) in l for l in done),
              "held: the chain does not count the held players, so a refused cleanup would read as done")
    rb = lp.body(restore)
    rep.check(bool(rb) and rb[0] == "scoreboard players set #%s %s 0" % (RID, obj),
              "act: the restore does not clear the chamber's open score first: %s" % rb[:1])
    writes = [i for i, l in enumerate(rb) if l.startswith(("fill ", "setblock ", "function "))]
    rep.check(bool(writes) and rb[writes[-1]].startswith("setblock %d %d %d " % (px, py, pz)),
              "act: the pedestal is not the restore's last write")
    tail = rb[writes[-1] + 1:] if writes else []
    rep.check(sorted(tail) == sorted(["scoreboard players set #built %s 0" % q, "scoreboard players set #quake %s 0" % q]),
              "act: after the pedestal the restore must set #built and #quake to 0 and nothing else: %s" % tail)

    # ---- chunks ---------------------------------------------------------------------------------------------------------
    fl_add = [FORCELOAD.match(l) for l in lp.body(base)]
    fl_add = [tuple(int(v) for v in m_.groups()[1:]) for m_ in fl_add if m_ and m_.group(1) == "add"]
    fl_rm = [FORCELOAD.match(l) for l in done]
    fl_rm = [tuple(int(v) for v in m_.groups()[1:]) for m_ in fl_rm if m_ and m_.group(1) == "remove"]
    if rep.check(len(fl_add) == 1, "chunks: the chain's entry force-loads %d box(es), not one" % len(fl_add)):
        x0, z0, x1, z1 = fl_add[0]
        n = (max(x0, x1) // 16 - min(x0, x1) // 16 + 1) * (max(z0, z1) // 16 - min(z0, z1) // 16 + 1)
        rep.check(n <= 256, "chunks: the box is %d chunks; forceload refuses more than 256" % n)
        rep.check(fl_rm == fl_add, "chunks: the chain does not release the box it holds: %s" % fl_rm)
        outside_ = [e for e in log if not (min(x0, x1) <= e[1][0] and e[1][3] <= max(x0, x1)
                                           and min(z0, z1) <= e[1][2] and e[1][5] <= max(z0, z1))]
        rep.check(not outside_, "chunks: %d restore write(s) outside the held box, e.g. %s" % (len(outside_), outside_[:2]))
        rep.notes.append("chunks: the chain holds %d chunks at once (x%d-%d z%d-%d) for its life; the restore holds none of "
                         "its own" % (n, x0, x1, z0, z1))
    for fid in [restore] + parts:
        raw = lp.fns.get(fid, [])
        rep.check(not any(l.strip().startswith("forceload") for l in raw), "chunks: %s force-loads on its own" % fid)
        rep.check(any(l.strip().startswith("# chunks-loaded-by: %s" % base) for l in raw),
                  "chunks: %s does not name the chain as what loads it" % fid)

    # ---- order ----------------------------------------------------------------------------------------------------------
    if steps is None:
        import legendaries as L
        steps = L.placement_steps(L.load(), ground)
    want_fn = ("fn", base)
    if rep.check(want_fn in steps, "order: R14L does not run the cleanup"):
        i = steps.index(want_fn)
        chk = steps[i + 2] if i + 2 < len(steps) else None
        rep.check(steps[i + 1][0] == "wait" and chk and chk[0] == "check" and chk[1][0] == "chunk_look"
                  and chk[1][1] == holder and chk[1][2] == 0, "order: the cleanup is not followed by a wait and 0 held read back")
        firsts = [j for j, s_ in enumerate(steps) if (s_[0] == "cmd" and s_[1].startswith("forceload add"))
                  or (s_[0] == "fn" and (s_[1].endswith("/place") or s_[1].endswith("/carve_once")))]
        rep.check(firsts and i < min(firsts), "order: the cleanup does not run before every chamber step")
        co = ("fn", "%s:legendary/%s/carve_once" % (ns, RID))
        rep.check(co in steps and steps.index(co) > i, "order: Groudon's carve_once is not run after the cleanup")

    # ---- chamber --------------------------------------------------------------------------------------------------------
    for k in ("portal", "approach", "chamber", "plug_depth"):
        rep.check(rec.get(k) == ORIGINAL[k], "chamber: %s is %s, the original was %s" % (k, rec.get(k), ORIGINAL[k]))
    rep.check(rec.get("kind") == "sealed_chamber" and rec.get("status") == "sited", "chamber: the record is not a sited "
              "sealed_chamber")
    d = leg["defaults"]
    for k in ("bore", "shell_margin", "pedestal_block"):
        rep.check(d.get(k) == ORIGINAL[k], "chamber: defaults.%s is %s, it was carved with %s" % (k, d.get(k), ORIGINAL[k]))
    rep.check(rec.get("gate", {}).get("flags") == ["gym8_cleared"], "chamber: the gate is not gym8_cleared")
    import legendaries_audit as LA
    own = LA.own_old_site(dict(ORIGINAL), ground)
    hull = own["hull"]
    cw = World(ground, (hull[0] - 1, hull[1] - 1, hull[2] - 1, hull[3] + 1, own["my"] + 4, hull[5] + 1))
    replay(lp, "%s:legendary/%s/carve" % (ns, RID), cw)
    rep.check(not cw.outside, "chamber: the carve writes outside its own hull: %s" % cw.outside[:2])
    cc = cw.classes()

    def cells(bx):
        s = cw.sl(bx)
        return (cc[s], np.array([cw.names[i] for i in cw.nid[s].ravel()], object).reshape(cc[s].shape)) if s else (None, None)

    lad = own["ladder"]
    sh_c, sh_n = cells(own["shaft"])
    lad_c, lad_n = cells(lad)
    rep.check(sh_c is not None and lad_n is not None and all(bare(n) == "minecraft:ladder" for n in lad_n.ravel())
              and int((sh_c == AIR).sum()) == sh_c.size - lad_c.size,
              "chamber: the shaft %s is not air with its ladder %s" % (own["shaft"], lad))
    pc, _pn = cells(own["plug"])
    rep.check(pc is not None and (pc == SOLID).all(), "chamber: the plug %s is not solid" % (own["plug"],))
    chc, chn = cells(own["chamber"])
    rep.check(chc is not None and int(((chc == AIR) | np.vectorize(lambda n: "lantern" in n)(chn)).sum()) == chc.size,
              "chamber: the chamber %s is not hollow" % (own["chamber"],))
    pac, _ = cells(own["passage"])
    rep.check(pac is not None and (pac == AIR).all(), "chamber: the passage %s is not hollow" % (own["passage"],))
    ped = own["pedestal"][:3]
    rep.check(bare(cw.name_at(*ped)) == ORIGINAL["pedestal_block"], "chamber: the pedestal %s is %s"
              % (ped, cw.name_at(*ped)))
    rep.check(cc[tuple(v - o for v, o in zip(own["legendary"], cw.o))] == AIR, "chamber: Groudon's cell is not air")
    co_body = lp.body("%s:legendary/%s/carve_once" % (ns, RID))
    rep.check(co_body == ["execute unless score #%s %s matches 1 run function %s:legendary/%s/carve" % (RID, obj, ns, RID)],
              "chamber: carve_once is not held by the open score alone: %s" % co_body)
    orb = next((r for r in rewards.get("rewards") or [] if r.get("id") == "groudon_red_orb"), {})
    rep.check((orb.get("container") or {}).get("at") == list(ped)
              and (orb.get("container") or {}).get("block") == ORIGINAL["pedestal_block"],
              "chamber: the Red Orb's container %s is not the chamber's pedestal %s" % (orb.get("container"), list(ped)))
    rep.check((Path(legendaries) / "data" / ns / "advancement" / "legendary" / RID / "met.json").is_file(),
              "chamber: the pack no longer defines %s:legendary/%s/met (Rayquaza's gate reads it)" % (ns, RID))
    rep.notes.append("chamber: shaft %s, plug %s, chamber %s, pedestal %s" % (own["shaft"], own["plug"], own["chamber"], ped))

    # ---- withdrawn ------------------------------------------------------------------------------------------------------
    if reapply_mod is None:
        import reapply as reapply_mod
    wd = getattr(reapply_mod, "WITHDRAWN", {})
    for name in WITHDRAWN_PACKS:
        rep.check(name in wd, "withdrawn: %s is not in tools/reapply.py WITHDRAWN" % name)
        rep.check(name not in reapply_mod.SERVER_PACKS and name not in reapply_mod.WORLD_LOCAL,
                  "withdrawn: %s is still in an install list" % name)
        rep.check(not (Path(legendaries).parent / name).exists(), "withdrawn: %s is still built in %s"
                  % (name, Path(legendaries).parent))
    callers = sorted({fid for fid, lines in lp.fns.items() for l in lines
                      if not l.strip().startswith("#") and "cobblers:groudon_cavern/" in l})
    rep.check(not callers, "withdrawn: functions still call the cavern's runtime: %s" % callers[:3])
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--legendaries", default=str(LEG_PACK))
    ap.add_argument("--applied", default=str(APPLIED))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    rep = audit(a.legendaries, a.applied, G.Ground(a.source_root))
    for n in rep.notes:
        print("  " + n)
    for e in rep.errors:
        print("FAIL " + e)
    print("groudon revert audit: %d checks, %d failures" % (rep.checks, len(rep.errors)))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
