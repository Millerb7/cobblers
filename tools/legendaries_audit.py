#!/usr/bin/env python
"""Offline, fail-closed audit of the legendary chambers: data/legendaries.json against the heightmap, the
water plan, the progression registry and the generated pack.

FAIL CLOSED means, here, five things:
  1. an audit that finds nothing to check FAILS. No emitted encounter, no carve function, no checked write,
     or no checked gate is an error, not a pass. (docs/STATE.md 'Re-export readiness': audits passing on
     empty output were one of the four fail-open defects.)
  2. nothing is taken from the artifact being checked. The geometry is recomputed from data/legendaries.json
     and tools/ground.py; the generated functions are then read as TEXT and every write they contain is
     tested against that independent geometry. An expectation read out of the pack would not be one.
  3. "not checkable" is a failure. A record whose keep zone, gate flag or quest field cannot be resolved
     fails; it is never skipped.
  4. a record that is not `sited` must have NO functions in the pack, and every record that is must have all
     of them.
  5. the gate is parsed, not assumed: every line that can open a chamber must carry the full advancement
     predicate, and a line that opens one without it fails (WATER_BUILD_PLAN 4.5 audit 4).
  6. a gate nobody can ever satisfy fails unless the record admits it. `legendary/<id>/met` is granted by one
     command, emitted only for a SITED encounter, so a sited chamber that requires the met of an unsited one
     is built and permanently shut. That is allowed only where gate.unsatisfiable_until names exactly those
     prerequisites, so a new dead end cannot appear silently and a stale admission fails too.
  7. a lake grotto's mouth is checked against the lake, not against the chamber: data/landmarks.json's basin
     outline and water level say whether the mouth is really in deep water in its own lake, and its
     water_export block must say whether the mouth was measured BEFORE the export (a keep zone protects it)
     or AFTER it (data/world.json's heightmap sha must still be the one it was measured on). Neither fails.

  python tools/legendaries_audit.py [--pack build/datapacks/cobblers_legendaries] [--source-root DIR]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import legendaries as L  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_legendaries"
FILL_LIMIT = 32768
MIN_BATTLE_AREA = 100      # walkable columns in the outer chamber: a legendary battle needs room to stand
MIN_HEADROOM = 5           # the air chamber is a room, not a crawl
MAX_LAKE_PASSAGE = 20      # WATER_BUILD_PLAN 3.3: "a passage of no more than 20 blocks"
GRID = 8                   # the spawn-box grid the route boxes share
MIN_GROTTO_DEPTH = 18      # a grotto mouth is deep water, not a paddle: 18 below the lake's own level

TRAINERS = ROOT / "data" / "trainers.json"
RCT_OVERLAY = ROOT / "modpack" / "config" / "rctmod-server.toml"
RCT_BASE = ROOT / "base-pack" / "cobbleverse" / "config" / "rctmod-server.toml"
RCT_MAX_LEVEL = 100        # LevelUtils.maxLevel() at rctmod v0.19.0-beta


def rct_caps(trainers=None, toml_text=None):
    """The level cap a player holds after each gate flag, computed the way rctmod does, from the trainers and the
    RCT config -- never from data/legendaries.json, whose `cap_at_gate` is the claim being checked.

    rctmod v0.19.0-beta LevelUtils (docs/mechanics/LEAGUE_LEVEL_CAP.md 1): the cap is max(initialLevelCap,
    min over the NEXT trainers of trainerLevel), where trainerLevel = max(team top + relativeLevelCap, the
    trainerLevel of every trainer that must be beaten first); with no next trainer it is maxLevel() = 100, and
    completing a series never resets it. Our series is Cobbleverse's 13-trainer Kanto chain (gyms 1-8, the four
    Elite Four in order, the Champion; COBBLEVERSE-RCT-DP-v20 requiredDefeats, read 2026-10-02), carrying our
    teams from data/trainers.json. No trainer overrides relativeLevelCap (the owner, 2026-10-02: 60 after gym 8
    is kept), so the config's value applies to every one; an override would have to be modelled here.

    Returns {flag: cap} for every gymN_cleared and champion_cleared, plus None for "nothing cleared yet".
    """
    if trainers is None:
        trainers = json.loads(TRAINERS.read_text(encoding="utf-8"))
    if toml_text is None:
        toml_text = (RCT_OVERLAY if RCT_OVERLAY.is_file() else RCT_BASE).read_text(encoding="utf-8")
    init = int(re.search(r"^\s*initialLevelCap\s*=\s*(-?\d+)", toml_text, re.M).group(1))
    rel = int(re.search(r"^\s*relativeLevelCap\s*=\s*(-?\d+)", toml_text, re.M).group(1))
    by_class = {}
    for t in trainers["trainers"]:
        by_class.setdefault(t.get("class"), []).append(t)
    chain = []
    for cls, n in (("gym_leader", 8), ("elite_four", 4), ("champion", 1)):
        group = sorted(by_class.get(cls) or [], key=lambda t: t["order"])
        if len(group) != n or [t["order"] for t in group] != list(range(1, n + 1)):
            raise ValueError("expected %d %s trainers ordered 1..%d in data/trainers.json, found %s"
                             % (n, cls, n, [t.get("order") for t in group]))
        chain += group
    levels, floor = [], 0
    for t in chain:
        top = max(m["level"] for m in t["team"])
        floor = max(min(RCT_MAX_LEVEL, max(0, top + rel)), floor)
        levels.append(floor)
    after = lambda i: max(init, levels[i + 1]) if i + 1 < len(levels) else RCT_MAX_LEVEL  # noqa: E731
    caps = {None: max(init, levels[0])}
    for n in range(1, 9):
        caps["gym%d_cleared" % n] = after(n - 1)
    caps["champion_cleared"] = after(len(chain) - 1)
    return caps


NUM = r"(-?\d+)"
FILL = re.compile(r"^fill %s %s %s %s %s %s\s+(\S+)" % ((NUM,) * 6))
SETBLOCK = re.compile(r"^setblock %s %s %s\s+(\S+)" % ((NUM,) * 3))


class Report:
    def __init__(self):
        self.errors = []
        self.checks = 0

    def check(self, ok, msg):
        self.checks += 1
        if not ok:
            self.errors.append(msg)
        return ok


def _inside(inner, outer):
    return (inner[0] >= outer[0] and inner[1] >= outer[1] and inner[2] >= outer[2]
            and inner[3] <= outer[3] and inner[4] <= outer[4] and inner[5] <= outer[5])


def _margin_ok(void, envelope, m):
    """Every face of `void` stands at least m blocks inside `envelope`."""
    return (void[0] - envelope[0] >= m and void[1] - envelope[1] >= m and void[2] - envelope[2] >= m
            and envelope[3] - void[3] >= m and envelope[4] - void[4] >= m and envelope[5] - void[5] >= m)


def _in_polygons(polys, x, z):
    """Even-odd point in polygon over a list of block-coordinate rings."""
    for ring in polys or []:
        hit = False
        n = len(ring)
        j = n - 1
        for i in range(n):
            xi, zi = ring[i]
            xj, zj = ring[j]
            if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / float(zj - zi) + xi:
                hit = not hit
            j = i
        if hit:
            return True
    return False


def _in_the_lake(rec, g, landmarks, rep):
    """The mouth of a lake grotto is really in its lake, and really in deep water.

    Independent of everything this repo generates: the basin outline and the water level come from
    data/landmarks.json, which is surveyed from the heightmap, and the mouth's Y from tools/ground.py.
    A mouth that drifted onto a shelf, onto an island or outside the lake fails here even when its
    envelope arithmetic is perfect.
    """
    rid = rec["id"]
    lm = next((l for l in (landmarks or {}).get("landmarks") or [] if l.get("id") == rec.get("site")), None)
    if lm is None:
        rep.errors.append("%s: data/landmarks.json has no landmark %r for this grotto's site" % (rid, rec.get("site")))
        return False
    wb = lm.get("water_body") or {}
    level = wb.get("level_y")
    if not isinstance(level, int):
        rep.errors.append("%s: landmark %s has no water_body.level_y, so the mouth's depth cannot be checked"
                          % (rid, lm["id"]))
        return False
    mx, mz = g["anchor"]
    if not _in_polygons(wb.get("basin_polygons") or [], mx, mz):
        rep.errors.append("%s: the mouth (%d, %d) is outside %s's basin outline" % (rid, mx, mz, lm["id"]))
        return False
    depth = level - g["mouth_y"]
    if depth < MIN_GROTTO_DEPTH:
        rep.errors.append("%s: the mouth stands %d blocks under %s's water level y%d, under the %d a grotto needs"
                          % (rid, depth, lm["id"], level, MIN_GROTTO_DEPTH))
        return False
    return True


def _export_provenance(rec, g, doc, water, landmarks, ground, world, rep):
    """A lake grotto's mouth is either protected from the water export or measured after it. Never neither.

    Two honest forms, and nothing else:
      keep_zone   the mouth was measured on the OLD bed, so data/water_shape.json must keep that patch of
                  bed unchanged (Mesprit, Azelf).
      applied     the mouth was measured on the bed the export already wrote, so it needs no keep zone --
                  but then the heightmap it was measured on must still be the canonical one (Uxie).
    """
    rid = rec["id"]
    we = rec.get("water_export") or {}
    if we.get("keep_zone"):
        return _keep_covers(rec, g, doc, water, landmarks, ground, rep)
    if not we.get("applied"):
        rep.errors.append("%s: water_export declares neither a keep_zone (mouth measured before the export) "
                          "nor applied + measured_on_sha256 (mouth measured after it)" % rid)
        return False
    want = ((world or {}).get("heightmap") or {}).get("sha256")
    got = we.get("measured_on_sha256")
    if not want:
        rep.errors.append("%s: data/world.json declares no heightmap sha256 to check the mouth against" % rid)
        return False
    if got != want:
        rep.errors.append("%s: measured on heightmap %s, but data/world.json's canonical heightmap is %s: the bed "
                          "under the mouth is not the bed it was sited on" % (rid, str(got)[:12], str(want)[:12]))
        return False
    return True


def _met_is_reachable(rec, doc, rep):
    """A sited chamber must not depend on a `met` no player can ever earn.

    `legendary/<id>/met` is granted by one command, in the met function of a SITED encounter. A sited
    record that requires the met of a record which is not sited is therefore built and permanently shut,
    and nothing in the world says so. That is allowed only when the record admits it in
    gate.unsatisfiable_until, which names exactly the prerequisites that are still unbuilt -- so the
    dead end is a written decision, and a NEW one cannot be introduced silently. A stale admission (an
    id that is sited after all, or one that is not a prerequisite) fails too.
    """
    rid = rec["id"]
    by_id = {r["id"]: r for r in doc["encounters"]}
    unbuilt = sorted(m for m in rec["gate"].get("requires_met") or []
                     if (by_id.get(m) or {}).get("status") != "sited")
    admitted = sorted(rec["gate"].get("unsatisfiable_until") or [])
    if unbuilt != admitted:
        rep.errors.append(
            "%s: its gate cannot be satisfied until %s %s built, because nothing grants the met of a record "
            "that is not sited; gate.unsatisfiable_until says %s"
            % (rid, ", ".join(unbuilt) or "(nothing)", "is" if len(unbuilt) == 1 else "are",
               admitted or "(nothing)"))
        return False
    return True


def audit(doc, ground, pack, water=None, progression=None, landmarks=None, world=None, caps=None):
    rep = Report()
    caps = rct_caps() if caps is None else caps
    d = doc["defaults"]
    m = int(d["shell_margin"])
    clear = int(d["clearance_blocks"])
    sited = L.emitted(doc)
    gate_only = L.gate_only(doc)

    # ---- 1. nonempty -------------------------------------------------------
    rep.check(bool(sited), "NOTHING TO CHECK: no encounter is sited, so this audit would pass vacuously")
    rep.check(pack.is_dir(), "no generated pack at %s: run tools/legendaries.py first" % pack)
    if not sited or not pack.is_dir():
        return rep

    fn_dir = pack / "data" / doc["namespace"] / "function" / "legendary"
    adv_dir = pack / "data" / doc["namespace"] / "advancement" / "legendary"
    flags = {f.get("id") for f in (progression or {}).get("flags") or []}
    fields = {f.get("id") for f in (progression or {}).get("quest_fields") or []}
    rep.check(bool(flags), "data/progression.json declares no flags: the gates cannot be resolved")

    # ---- 2. a blocked record writes nothing --------------------------------
    for rec in doc["encounters"]:
        if rec["status"] == "sited":
            continue
        rep.check(not (fn_dir / rec["id"] / "carve.mcfunction").exists(),
                  "%s is %s but the pack carries a carve function for it" % (rec["id"], rec["status"]))
        rep.check(bool(rec.get("blocked_by")) and len(rec.get("blocked_why") or "") > 40,
                  "%s: a record that is not sited needs blocked_by and a blocked_why that says something" % rec["id"])
        rep.check((adv_dir / rec["id"] / "met.json").exists(),
                  "%s: its met advancement must exist even when blocked, or a gate naming it is a command error"
                  % rec["id"])

    # ---- 3. every record's levels and gate are declared --------------------
    for rec in doc["encounters"]:
        rid = rec["id"]
        # the REAL cap its gate reaches (rct_caps), not the record's own cap_at_gate: until 2026-10-02 this
        # compared the level with cap_at_gate, which still held an invented table (Regigigas 70, Lugia 80), so a
        # legendary placed above the cap passed. Holding every flag means having cleared the latest of them.
        gflags = rec["gate"]["flags"]
        unknown = [f for f in gflags if f not in caps]
        rep.check(not unknown, "%s: no RCT cap can be derived for gate flag(s) %s" % (rid, unknown))
        if not unknown:
            real = max(caps[f] for f in gflags) if gflags else caps[None]
            rep.check(int(rec["level"]) <= real,
                      "%s: level %s is above the RCT cap %s its gate %s reaches, so data/level_cap.json makes it "
                      "uncatchable" % (rid, rec["level"], real, gflags))
            rep.check(rec.get("cap_at_gate") == real,
                      "%s: cap_at_gate %s is not the RCT cap %s its gate %s reaches" % (rid, rec.get("cap_at_gate"),
                                                                                       real, gflags))
        rep.check(len(rec.get("level_basis") or "") > 10, "%s: no level_basis" % rid)
        for f in rec["gate"]["flags"]:
            rep.check(f in flags, "%s: gate flag %r is not declared in data/progression.json flags" % (rid, f))
        for other in rec["gate"].get("requires_met") or []:
            rep.check(any(r["id"] == other for r in doc["encounters"]),
                      "%s: requires_met names %r, which is not an encounter" % (rid, other))
        want = "quest.legendary_%s.met" % rid
        rep.check(want in fields, "%s: %s is not declared in data/progression.json quest_fields" % (rid, want))

    # ---- 4. geometry, recomputed, and the pack's writes tested against it ---
    checked_writes = 0
    checked_gates = 0
    for rec in sited:
        rid = rec["id"]
        g = L.geometry(rec, doc, ground)
        lake = rec["kind"] == "lake_grotto"
        env, sleeve = g["envelope"], g["sleeve"]

        # the roof: the envelope must stop clear of the lowest ground over its own footprint
        rep.check(env[4] + m + clear <= g["env_footprint_min_ground"],
                  "%s: envelope top y%d is not %d+%d below the lowest ground over its footprint (y%d)"
                  % (rid, env[4], m, clear, g["env_footprint_min_ground"]))
        # the sleeve: never raises the bed, and the unsleeved lip of the hole is short
        rep.check(sleeve[4] >= env[4] + 1, "%s: the sleeve does not reach above the envelope" % rid)
        lip = g["mouth_y"] - g["sleeve_top"] - 1
        rep.check(0 <= lip <= int(d["sleeve_flatness"]),
                  "%s: %d blocks of the shaft stand above the sleeve (limit %s): the ground under the mouth is "
                  "not flat enough" % (rid, lip, d["sleeve_flatness"]))
        # the seal: every void at least shell_margin inside the solid envelope
        voids = {"chamber": g["chamber"], "passage": g["passage"]}
        if lake:
            voids["pool"] = g["pool"]
        for name, v in voids.items():
            rep.check(_margin_ok(v, env, m),
                      "%s: the %s is not %d blocks inside the envelope on every face" % (rid, name, m))
        # the shaft is the ONE connection out, and it stays inside the sleeve's footprint horizontally
        sx0, sz0, sx1, sz1 = g["sleeve_footprint"]
        sh = g["shaft"]
        rep.check(sh[0] - sx0 >= m and sh[2] - sz0 >= m and sx1 - sh[3] >= m and sz1 - sh[5] >= m,
                  "%s: the shaft is not %d blocks inside its sleeve" % (rid, m))

        # the room itself
        outer = g["zone"]
        area = (outer[3] - outer[0] + 1) * (outer[5] - outer[2] + 1)
        pool_area = ((g["pool"][3] - g["pool"][0] + 1) * (g["pool"][5] - g["pool"][2] + 1)) if lake else 0
        rep.check(area - pool_area >= MIN_BATTLE_AREA,
                  "%s: %d walkable columns in the outer chamber, under %d" % (rid, area - pool_area, MIN_BATTLE_AREA))
        rep.check(outer[4] - outer[1] + 1 >= MIN_HEADROOM,
                  "%s: %d blocks of headroom, under %d" % (rid, outer[4] - outer[1] + 1, MIN_HEADROOM))
        if lake:
            rep.check(int(rec["approach"]["passage"]) <= MAX_LAKE_PASSAGE,
                      "%s: a %d-block passage, over the %d WATER_BUILD_PLAN 3.3 allows"
                      % (rid, rec["approach"]["passage"], MAX_LAKE_PASSAGE))
            # the flooded passage must meet the pool BELOW the pool's surface, or the player cannot swim in
            rep.check(g["passage"][4] < g["pool"][4],
                      "%s: the passage's roof (y%d) is not below the pool's surface (y%d)"
                      % (rid, g["passage"][4], g["pool"][4]))
            # and the air chamber must sit entirely above that surface, or it is not an air chamber
            rep.check(g["chamber"][1] > g["pool"][4],
                      "%s: the chamber floor (y%d) is not above the pool's surface (y%d)"
                      % (rid, g["chamber"][1], g["pool"][4]))
            rep.check("door" in g, "%s: a lake grotto needs its barrier partition (chamber.alcove > 0)" % rid)
        else:
            rep.check("plug" in g and int(rec.get("plug_depth") or 0) >= 4,
                      "%s: a sealed chamber needs a plug at least 4 deep" % rid)

        # ---- the generated carve, as text, against that geometry -----------
        carve = fn_dir / rid / "carve.mcfunction"
        rep.check(carve.is_file(), "%s: no carve function in the pack" % rid)
        if not carve.is_file():
            continue
        allowed = L._hull([env, sleeve, g["shaft"]])
        writes = 0
        air = []           # every cell the carve opens, for the independent dimension check below
        for line in carve.read_text(encoding="utf-8").splitlines():
            mm = FILL.match(line.strip())
            if mm:
                b = L._box(*(int(v) for v in mm.groups()[:6]))
            else:
                mm = SETBLOCK.match(line.strip())
                if not mm:
                    continue
                x, y, z = (int(v) for v in mm.groups()[:3])
                b = (x, y, z, x, y, z)
            writes += 1
            if "minecraft:air" in line:
                air.append(b)
            rep.check(_inside(b, allowed),
                      "%s: carve writes %s, outside the envelope and sleeve %s" % (rid, b, allowed))
            rep.check(L.volume(b) <= FILL_LIMIT,
                      "%s: a write of %d blocks, over Minecraft's %d" % (rid, L.volume(b), FILL_LIMIT))
        rep.check(writes >= 6, "%s: only %d writes in the carve; that is not a chamber" % (rid, writes))
        checked_writes += writes

        # ---- the chamber's SIZE, against the record's own declared numbers ---------------------------
        # Added 2026-09-30 after the F7 sweep. Everything else in this loop measures the emitted text
        # against `L.geometry(...)` - the BUILDER'S OWN FUNCTION. That catches an emission bug and cannot
        # catch a bug in geometry() itself: the writer would place the chamber wrongly, the audit would
        # expect it wrongly, and the two would agree. That is exactly the shape of F7, where portals.py
        # and portals_audit.py both read a landmark's `extent` as "where water is" and so agreed with
        # each other about a hole 219,737 columns wide.
        #
        # So this one check derives its expectation from the RECORD, in this file's own arithmetic, and
        # never calls into L: the record says `chamber: {width, length, height}`, and the air the carve
        # opens must measure that, give or take the alcove it also declares. A geometry() that scaled,
        # transposed or offset the chamber now shows up here.
        ch = rec.get("chamber") or {}
        ap = rec.get("approach") or {}
        if air and all(k in ch for k in ("width", "length", "height")):
            x0 = min(b[0] for b in air); x1 = max(b[3] for b in air)
            y0 = min(b[1] for b in air); y1 = max(b[4] for b in air)
            z0 = min(b[2] for b in air); z1 = max(b[5] for b in air)
            # per axis, not sorted together: the passage and the shaft extend ONE axis - whichever the
            # approach bears along - and the alcove widens the other. Conflating them hides a transpose.
            got = sorted(((x1 - x0 + 1), (z1 - z0 + 1)))
            decl = sorted((int(ch["width"]), int(ch["length"])))
            alc = int(ch.get("alcove") or 0)
            # the long axis carries the chamber, the passage and the bore of the shaft at its head, each a
            # number the DATA declares (approach.passage, defaults.bore). Measured once against regirock to
            # be sure the accounting is complete, not tuned until it passed: bore 3 + passage 12 + chamber
            # 17 = 32, which is exactly what the carve opens.
            run = int(ap.get("passage") or 0) + int((doc.get("defaults") or {}).get("bore") or 0)
            rep.check(got[0] >= decl[0] and got[1] >= decl[1],
                      "%s: the carve's air measures %dx%d, smaller than the chamber the record declares "
                      "(%dx%d)" % (rid, got[0], got[1], decl[0], decl[1]))
            rep.check(got[0] <= decl[0] + alc,
                      "%s: the carve's air is %d across its short axis; the record declares %d plus an "
                      "alcove of %d" % (rid, got[0], decl[0], alc))
            rep.check(got[1] <= decl[1] + run,
                      "%s: the carve's air is %d along its long axis; the record declares a chamber of %d "
                      "plus a passage of %d and a bore of %d" % (rid, got[1], decl[1],
                                                                 int(ap.get("passage") or 0),
                                                                 int((doc.get("defaults") or {}).get("bore") or 0)))
            rep.check(y1 - y0 + 1 >= int(ch["height"]),
                      "%s: the carve's air is %d tall, under the %d the record declares"
                      % (rid, y1 - y0 + 1, int(ch["height"])))
            rep.check(y1 - y0 + 1 <= int(ch["height"]) + int(ap.get("drop") or 0),
                      "%s: the carve's air is %d tall, over the chamber's %d plus the approach's declared "
                      "drop of %d" % (rid, y1 - y0 + 1, int(ch["height"]), int(ap.get("drop") or 0)))

        # ---- the gate, parsed out of the generated near ---------------------
        near = fn_dir / rid / "near.mcfunction"
        rep.check(near.is_file(), "%s: no near function in the pack" % rid)
        if near.is_file():
            need = ["%s:flag/%s=true" % (doc["namespace"], f) for f in rec["gate"]["flags"]]
            need += ["%s:legendary/%s/met=true" % (doc["namespace"], o)
                     for o in rec["gate"].get("requires_met") or []]
            opens = [l for l in near.read_text(encoding="utf-8").splitlines()
                     if "legendary/%s/open" % rid in l]
            rep.check(bool(opens), "%s: nothing in near can open the chamber" % rid)
            for line in opens:
                for key in need:
                    rep.check(key in line,
                              "%s: a line opens the chamber without %s in its predicate: %s" % (rid, key, line))
                checked_gates += 1

        # ---- the spawn-free zone -------------------------------------------
        zone = rec.get("spawn_free_zone")
        ok = isinstance(zone, list) and len(zone) == 4
        rep.check(ok, "%s: a sited encounter declares a spawn_free_zone [x0, z0, x1, z1]" % rid)
        if ok:
            rep.check(all(v % GRID == 0 for v in zone),
                      "%s: the spawn-free zone %s is not snapped to the %d-block grid" % (rid, zone, GRID))
            ch = g["chamber"]
            rep.check(zone[0] <= ch[0] and zone[1] <= ch[2] and zone[2] >= ch[3] and zone[3] >= ch[5],
                      "%s: the spawn-free zone %s does not cover the chamber footprint (%d, %d)-(%d, %d)"
                      % (rid, zone, ch[0], ch[2], ch[3], ch[5]))

        # ---- the water export, and the lake the mouth is supposed to be in ---
        if lake:
            rep.check(_export_provenance(rec, g, doc, water, landmarks, ground, world, rep),
                      "%s: the mouth is neither protected from the water export nor measured after it" % rid)
            rep.check(_in_the_lake(rec, g, landmarks, rep),
                      "%s: the mouth is not in deep water inside its own lake" % rid)

        # ---- a gate nobody can ever satisfy ---------------------------------
        rep.check(_met_is_reachable(rec, doc, rep),
                  "%s: a sited chamber whose gate can never open, unadmitted" % rid)

    rep.check(checked_writes > 0, "NOTHING TO CHECK: no block write was tested")
    rep.check(checked_gates > 0, "NOTHING TO CHECK: no gate line was tested")

    # ---- 4b. a retired chamber site: put back, and nothing of it left in the pack's writes ----------------------
    _retired_sites(doc, ground, pack, fn_dir, rep)

    # ---- 5. the gate-only records ------------------------------------------
    for rec in gate_only:
        rid = rec["id"]
        f = fn_dir / rid / "open.mcfunction"
        rep.check(f.is_file(), "%s: a gate_only record still needs its gate function" % rid)
        if f.is_file():
            body = f.read_text(encoding="utf-8")
            for fl in rec["gate"]["flags"]:
                rep.check("%s:flag/%s=true" % (doc["namespace"], fl) in body,
                          "%s: its open function does not check %s" % (rid, fl))
            rep.check("return 0" in body,
                      "%s: its open function does not refuse a player who fails the gate" % rid)
        tick = fn_dir / "tick.mcfunction"
        rep.check(tick.is_file(), "no tick function in the pack: nothing drives any gate")
        if tick.is_file():
            # a COMMAND, not a comment: the tick names it in a comment on purpose, so reapply.py's
            # uncovered() check sees that nothing driving it is a decision rather than a loss
            live = [l for l in tick.read_text(encoding="utf-8").splitlines()
                    if l.strip() and not l.strip().startswith("#")]
            rep.check(not any("legendary/%s/" % rid in l for l in live),
                      "%s: a gate_only record must not be driven; its trigger is an open question" % rid)

    return rep


# ------------------------------------------------------------------ a retired chamber site (2026-10-12)
#
# A record that MOVES keeps its old chamber in `retired_sites`; tools/legendaries.py emits a cleanup for it. This
# section judges that cleanup the way section 4 judges a carve, and with the same independence rule: the old
# chamber is derived HERE, from the record's declared numbers and the heightmap, in this file's own arithmetic. It
# never calls L.geometry(), so a geometry() that scales, shifts or transposes the chamber (the generator being
# mutated, the data untouched) is caught by the restore failing to cover what this derivation says was carved.
#
# What it proves, offline: the restore writes (a) every cell the old carve opened (chamber, passage, shaft, ladder,
# lanterns, pedestal) back to rock, (b) every sleeve and plug cell whose terrain is not the carve's own stone back
# to the terrain the heightmap says it is (surface at the ground, air above it), (c) nothing outside the old hull
# and nothing over the plug's top, and (d) nothing else in the pack writes, loads, tp's to or selects into that hull.
# The cleanup's guard, probe, kill selector and step order are read as TEXT.
#
# It does NOT prove: that the surface block is what the world had (terrain.surface_verified says it is a guess),
# that nothing OUTSIDE this pack (another pack, a later structure) touches the hull, or anything about a running
# server. Those are the staging read-back (the pedestal probe, the held count) and the owner's eyes.

AXES = {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}
HELD = "cobblers_leg_retire_held"
VOL = re.compile(r"x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(-?\d+),dy=(-?\d+),dz=(-?\d+)")


def own_old_site(site, ground):
    """The retired chamber, from the record's numbers and the heightmap alone: boxes as inclusive
    (x0, y0, z0, x1, y1, z1). Written separately from tools/legendaries.py geometry() on purpose."""
    px, pz = (int(v) for v in site["portal"])
    my = int(ground(px, pz))
    ap, ch = site["approach"], site["chamber"]
    dx, dz = AXES[int(ap["bearing_deg"])]
    bore, m = int(site["bore"]), int(site["shell_margin"])
    r = bore // 2
    width, length, height = int(ch["width"]), int(ch["length"]), int(ch["height"])
    drop, passage, plug = int(ap["drop"]), int(ap["passage"]), int(site["plug_depth"])
    floor = my - drop

    def box(s0, s1, a0, a1, y0, y1):
        xs = (px + dx * s0 - dz * a0, px + dx * s1 - dz * a1)
        zs = (pz + dz * s0 + dx * a0, pz + dz * s1 + dx * a1)
        return (min(xs), y0, min(zs), max(xs), y1, max(zs))

    s0 = r + passage + 1
    s1 = s0 + length - 1
    out = {"my": my, "floor": floor}
    out["chamber"] = box(s0, s1, -(width // 2), width // 2, floor + 1, floor + height)
    out["passage"] = box(r + 1, r + passage, -r, r, floor + 1, floor + bore)
    out["shaft"] = box(-r, r, -r, r, floor + 1, my - plug)
    out["plug"] = box(-r, r, -r, r, my - plug + 1, my)
    out["ladder"] = box(-r, -r, 0, 0, floor + 1, my - plug)
    out["pedestal"] = box(s1 - 2, s1 - 2, 0, 0, floor, floor)
    out["legendary"] = (out["pedestal"][0], floor + 1, out["pedestal"][2])
    voids = (out["chamber"], out["passage"], out["shaft"])
    top = floor + height + m
    out["envelope"] = (min(b[0] for b in voids) - m, floor + 1 - m, min(b[2] for b in voids) - m,
                       max(b[3] for b in voids) + m, top, max(b[5] for b in voids) + m)
    sx0, sz0, sx1, sz1 = px - r - m, pz - r - m, px + r + m, pz + r + m
    out["sleeve"] = (sx0, top + 1, sz0, sx1, int(ground.box(sx0, sz0, sx1, sz1).min()) - 1, sz1)
    parts = [out["envelope"], out["sleeve"], out["plug"]]
    out["hull"] = (min(b[0] for b in parts), min(b[1] for b in parts), min(b[2] for b in parts),
                   max(b[3] for b in parts), max(b[4] for b in parts), max(b[5] for b in parts))
    return out


def _vol_box(m):
    x, y, z, dx, dy, dz = (int(v) for v in m.groups())
    return (x, y, z, x + dx, y + dy, z + dz)


def _meets(a, b):
    return a[0] <= b[3] and b[0] <= a[3] and a[1] <= b[4] and b[1] <= a[4] and a[2] <= b[5] and b[2] <= a[5]


def _reaches(hull, line):
    """True when a coordinate-bearing command of `line` reaches the hull: fill, setblock, forceload, positioned,
    tp, a selector volume. (Not covered: a command that reaches it by ~ offset or a distance from a far point.)"""
    s = line.strip()
    if not s or s.startswith("#"):
        return False
    for rx in (FILL, SETBLOCK):
        mm = rx.match(s)
        if mm:
            vals = [int(v) for v in mm.groups()[:6 if rx is FILL else 3]]
            b = L._box(*vals) if rx is FILL else (vals[0], vals[1], vals[2], vals[0], vals[1], vals[2])
            if _meets(b, hull):
                return True
    for mm in re.finditer(r"forceload (?:add|remove) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+))?", s):
        a, b, c, d = mm.groups()
        x0, z0 = int(a), int(b)
        x1, z1 = (int(c), int(d)) if c is not None else (x0, z0)
        if _meets((min(x0, x1), hull[1], min(z0, z1), max(x0, x1), hull[4], max(z0, z1)), hull):
            return True
    for mm in re.finditer(r"(?:positioned|tp @s) (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)", s):
        x, y, z = (int(float(v) // 1) for v in mm.groups())
        if _meets((x, y, z, x, y, z), hull):
            return True
    for mm in VOL.finditer(s):
        if _meets(_vol_box(mm), hull):
            return True
    return False


def _retired_sites(doc, ground, pack, fn_dir, rep):
    import numpy as np
    sites = L.retired(doc)
    ns = doc["namespace"]
    files = sorted(p.relative_to(fn_dir).as_posix() for p in fn_dir.rglob("*.mcfunction")) if fn_dir.is_dir() else []
    # every retire_* function in the pack belongs to a declared site, and every declared site has all five
    declared = set()
    for rec, site in sites:
        for suf in ("", "_look", "_act", "_done", "_restore"):
            declared.add("%s/retire_%s%s.mcfunction" % (rec["id"], site["id"], suf))
    stray = [f for f in files if "/retire_" in f and f not in declared]
    rep.check(not stray, "the pack carries retire functions no record declares: %s" % stray)
    steps = None
    for rec, site in sites:
        rid, sid = rec["id"], site["id"]
        where = "%s retired site %s" % (rid, sid)
        for f in sorted(d for d in declared if d.startswith(rid + "/retire_%s" % sid)):
            rep.check(f in files, "%s: the pack has no %s" % (where, f))
        restore_f = fn_dir / rid / ("retire_%s_restore.mcfunction" % sid)
        act_f = fn_dir / rid / ("retire_%s_act.mcfunction" % sid)
        done_f = fn_dir / rid / ("retire_%s_done.mcfunction" % sid)
        if not (restore_f.is_file() and act_f.is_file() and done_f.is_file()):
            continue
        if int((site["chamber"] or {}).get("alcove") or 0):
            rep.errors.append("%s: an alcove chamber's door is not modelled by this audit" % where)
            continue
        o = own_old_site(site, ground)
        hull = o["hull"]
        t = site["terrain"]
        carve_block = doc["defaults"]["envelope_block"]

        # ---- the restore, applied as text to a grid of the hull ---------------------------------------------
        X0, Y0, Z0, X1, Y1, Z1 = hull
        ids = {}
        for b in ("minecraft:air", t["surface"], t["under"], t["deep"], carve_block):
            ids.setdefault(b, len(ids) + 1)
        written = np.zeros((X1 - X0 + 1, Y1 - Y0 + 1, Z1 - Z0 + 1), np.int16)
        outside = 0
        nwrites = 0
        for line in restore_f.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            mm = FILL.match(s)
            if mm:
                b, blk = L._box(*(int(v) for v in mm.groups()[:6])), mm.group(7)
            else:
                mm = SETBLOCK.match(s)
                if not mm:
                    continue
                x, y, z = (int(v) for v in mm.groups()[:3])
                b, blk = (x, y, z, x, y, z), mm.group(4)
            nwrites += 1
            if not _inside(b, hull):
                outside += 1
                continue
            ids.setdefault(blk, len(ids) + 1)
            written[b[0] - X0:b[3] - X0 + 1, b[1] - Y0:b[4] - Y0 + 1, b[2] - Z0:b[5] - Z0 + 1] = ids[blk]
        rep.check(nwrites >= 3, "%s: only %d writes in the restore; that is not a chamber put back" % (where, nwrites))
        rep.check(outside == 0, "%s: %d restore write(s) outside the old hull %s" % (where, outside, hull))

        # what the terrain is at every cell: the heightmap's ground, the site's three blocks
        gcol = ground.box(X0, Z0, X1, Z1).T
        rel = np.arange(Y0, Y1 + 1)[None, :, None] - gcol[:, None, :]
        expect = np.where(rel > 0, ids["minecraft:air"],
                          np.where(rel == 0, ids[t["surface"]],
                                   np.where(rel >= -2, ids[t["under"]], ids[t["deep"]]))).astype(np.int16)

        def mask(*boxes):
            m_ = np.zeros(written.shape, bool)
            for b in boxes:
                m_[b[0] - X0:b[3] - X0 + 1, b[1] - Y0:b[4] - Y0 + 1, b[2] - Z0:b[5] - Z0 + 1] = True
            return m_

        opened = mask(o["chamber"], o["passage"], o["shaft"], o["ladder"], o["pedestal"])
        stone = mask(o["envelope"], o["sleeve"], o["plug"]) & ~opened
        need = opened | (stone & (expect != ids[carve_block]))
        missing = need & (written == 0)
        wrong = (written != 0) & (written != expect)
        rep.check(int(need.sum()) > 0, "%s: NOTHING TO CHECK: no cell needs restoring" % where)
        rep.check(int(missing.sum()) == 0,
                  "%s: %d cell(s) the old carve changed are not put back (first %s)"
                  % (where, int(missing.sum()), [tuple(int(v) + o_ for v, o_ in zip(c, (X0, Y0, Z0)))
                                                 for c in np.argwhere(missing)[:3]]))
        rep.check(int(wrong.sum()) == 0,
                  "%s: %d cell(s) written with a block that is not the terrain there (first %s)"
                  % (where, int(wrong.sum()), [tuple(int(v) + o_ for v, o_ in zip(c, (X0, Y0, Z0)))
                                               for c in np.argwhere(wrong)[:3]]))
        px, py, pz = o["pedestal"][0], o["pedestal"][1], o["pedestal"][2]
        rep.check(int(written[px - X0, py - Y0, pz - Z0]) == ids[t["deep"]],
                  "%s: the pedestal (%d, %d, %d) is not put back to %s" % (where, px, py, pz, t["deep"]))
        restore_text = restore_f.read_text(encoding="utf-8")
        rep.check(restore_text.count("scoreboard players set #%s %s 0" % (rid, doc["objective"])) == 1,
                  "%s: the restore must clear the retired chamber's open score exactly once" % where)
        body = [l.strip() for l in restore_text.splitlines() if l.strip() and not l.strip().startswith("#")]
        rep.check(bool(body) and body[-1].startswith("setblock %d %d %d " % (px, py, pz)),
                  "%s: the pedestal must be the LAST write, so an interrupted restore is run again" % where)

        # ---- the act: guard, probe, kill, as text ------------------------------------------------------------
        base = "%s:legendary/%s/retire_%s" % (ns, rid, sid)
        guard = "@a[tag=%s]" % HELD
        tagged = []
        probe_ok = kill_ok = False
        stray_lines = []
        for line in act_f.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            mm = re.match(r"^tag @a\[(%s)\] add %s$" % (VOL.pattern, HELD), s)
            if mm:
                tagged.append(_vol_box(VOL.search(mm.group(1))))
                continue
            if s == "tag @a remove %s" % HELD or s.startswith("scoreboard players set #") or s.startswith("schedule function"):
                continue
            mm = re.match(r"^execute unless entity %s if block (-?\d+) (-?\d+) (-?\d+) (\S+) run function (\S+)$"
                          % re.escape(guard), s)
            if mm:
                probe_ok = ((int(mm.group(1)), int(mm.group(2)), int(mm.group(3))) == (px, py, pz)
                            and mm.group(4) == site["pedestal_block"] and mm.group(5) == base + "_restore")
                continue
            mm = re.match(r"^execute unless entity %s run kill @e\[(.*)\]$" % re.escape(guard), s)
            if mm:
                sel = mm.group(1)
                vm = VOL.search(sel)
                kb = _vol_box(vm) if vm else None
                tag = "tag=%s" % (doc["tag_prefix"] + rid)
                lx, ly, lz = o["legendary"]
                live = None
                if rec.get("status") == "sited":
                    live = L.geometry(rec, doc, ground)["legendary"]
                kill_ok = bool(kb and "type=cobblemon:pokemon" in sel and tag in sel.split(",")
                               and _inside(kb, o["envelope"])
                               and kb[0] <= lx <= kb[3] and kb[1] <= ly <= kb[4] and kb[2] <= lz <= kb[5]
                               and not (live and kb[0] <= live[0] <= kb[3] and kb[1] <= live[1] <= kb[4]
                                        and kb[2] <= live[2] <= kb[5]))
                continue
            stray_lines.append(s)
        rep.check(not stray_lines, "%s: the act holds lines this audit does not recognise: %s" % (where, stray_lines[:3]))
        rep.check(probe_ok, "%s: the restore is not called only while the held count is 0 and the old pedestal "
                            "(%s at %d %d %d) stands" % (where, site["pedestal_block"], px, py, pz))
        rep.check(kill_ok, "%s: the kill is not held to the record's own tag, the pokemon type and a box inside the old "
                           "chamber that holds the old legendary and not the live one" % where)
        for name in ("chamber", "passage"):
            rep.check(any(_inside(o[name], tb) for tb in tagged),
                      "%s: no held-player box covers the old %s %s" % (where, name, o[name]))
        shaft_to_top = (o["shaft"][0], o["shaft"][1], o["shaft"][2], o["shaft"][3], o["my"], o["shaft"][5])
        rep.check(any(_inside(shaft_to_top, tb) for tb in tagged),
                  "%s: no held-player box covers the old shaft up to the plug's top %s" % (where, shaft_to_top))
        rep.check("if entity @e[tag=%s]" % HELD in done_f.read_text(encoding="utf-8"),
                  "%s: the chain does not count the held players, so a refused restore would read as done" % where)
        callers = [f for f in files if "/retire_" not in f
                   and ("retire_%s_restore" % sid) in (fn_dir / f).read_text(encoding="utf-8")]
        rep.check(not callers, "%s: functions outside the cleanup call its restore: %s" % (where, callers))

        # ---- nothing else in the pack reaches the old hull ---------------------------------------------------
        for f in files:
            if "/retire_%s" % sid in f and f.startswith(rid + "/"):
                continue
            hit = [l.strip()[:100] for l in (fn_dir / f).read_text(encoding="utf-8").splitlines() if _reaches(hull, l)]
            rep.check(not hit, "%s: %s still reaches the old hull %s: %s" % (where, f, hull, hit[:2]))

        # ---- it is run first, read back as 0 held, and the live chamber is elsewhere --------------------------
        if steps is None:
            steps = L.placement_steps(doc, ground)
        want_fn = ("fn", base)
        rep.check(want_fn in steps, "%s: R14L's steps do not run the cleanup" % where)
        if want_fn in steps:
            i = steps.index(want_fn)
            chk = steps[i + 2] if i + 2 < len(steps) else None
            rep.check(steps[i + 1][0] == "wait" and chk and chk[0] == "check" and chk[1][0] == "chunk_look"
                      and chk[1][2] == 0 and chk[1][1] == "legret_%s_%s" % (rid, sid),
                      "%s: the cleanup is not followed by its wait and a read-back of 0 held" % where)
            firsts = [j for j, s_ in enumerate(steps) if s_[0] == "cmd" and s_[1].startswith("forceload add")
                      or s_[0] == "fn" and s_[1].endswith("/place")]
            rep.check(not firsts or i < min(firsts), "%s: the cleanup does not run before the first chamber step" % where)
        if rec.get("status") == "sited":
            live_hull = L.geometry(rec, doc, ground)["bbox"]
            rep.check(not _meets(live_hull, hull), "%s: the live chamber's hull %s meets the retired hull %s"
                      % (where, live_hull, hull))


def _keep_covers(rec, g, doc, water, landmarks, ground, rep):
    """The declared water-export keep zone, resolved in data/water_shape.json and tested on the heightmap.

    Unresolvable is a failure, never a skip.
    """
    ref = (rec.get("water_export") or {}).get("keep_zone")
    if not isinstance(ref, str) or ":" not in ref:
        rep.errors.append("%s: no water_export.keep_zone '<lake>:<keep id>'" % rec["id"])
        return False
    lake_id, keep_id = ref.split(":", 1)
    body = next((b for b in ((water or {}).get("lakes") or {}).get("bodies") or [] if b.get("id") == lake_id), None)
    if body is None:
        rep.errors.append("%s: data/water_shape.json has no lake %r" % (rec["id"], lake_id))
        return False
    keep = next((k for k in body.get("keep") or [] if k.get("id") == keep_id), None)
    if keep is None:
        rep.errors.append("%s: lake %s has no keep zone %r (its keeps: %s)"
                          % (rec["id"], lake_id, keep_id, [k.get("id") for k in body.get("keep") or []]))
        return False
    lm = next((l for l in (landmarks or {}).get("landmarks") or [] if l.get("id") == lake_id), None)
    if lm is None or not lm.get("anchor"):
        rep.errors.append("%s: data/landmarks.json has no anchor for %r" % (rec["id"], lake_id))
        return False
    ax, az = int(lm["anchor"]["x"]), int(lm["anchor"]["z"])
    sx0, sz0, sx1, sz1 = g["sleeve_footprint"]
    if keep.get("around") != "anchor":
        rep.errors.append("%s: keep zone %s is not anchored, so it cannot be resolved here" % (rec["id"], keep_id))
        return False
    if "radius" in keep:
        r = int(keep["radius"])
        worst = max(((x - ax) ** 2 + (z - az) ** 2) ** 0.5 for x in (sx0, sx1) for z in (sz0, sz1))
        if worst > r:
            rep.errors.append("%s: the sleeve reaches %.1f blocks from the anchor, past the keep's radius %d"
                              % (rec["id"], worst, r))
            return False
        return True
    if "core_depth" in keep:
        level = int(((lm.get("water_body") or {}).get("level_y")) or 0)
        if not level:
            rep.errors.append("%s: %s has no water level to measure depth against" % (rec["id"], lake_id))
            return False
        shallow = int((level - ground.box(sx0, sz0, sx1, sz1)).min())
        if shallow < int(keep["core_depth"]):
            rep.errors.append("%s: the shallowest column under the sleeve is %d deep, under the keep's core_depth %d"
                              % (rec["id"], shallow, keep["core_depth"]))
            return False
        return True
    rep.errors.append("%s: keep zone %s is neither a radius nor a core_depth" % (rec["id"], keep_id))
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    doc = L.load()
    water = json.loads((ROOT / "data" / "water_shape.json").read_text(encoding="utf-8"))
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    lms = json.loads((ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    rep = audit(doc, G.load(a.source_root), Path(a.pack), water, prog, lms, world)
    for e in rep.errors:
        print("FAIL %s" % e)
    print("legendaries audit: %d checks, %d failures" % (rep.checks, len(rep.errors)))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
