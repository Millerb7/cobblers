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


def audit(doc, ground, pack, water=None, progression=None, landmarks=None):
    rep = Report()
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
        rep.check(isinstance(rec.get("cap_at_gate"), int) and int(rec["level"]) <= rec["cap_at_gate"],
                  "%s: level %s is above cap_at_gate %s, so data/level_cap.json makes it uncatchable"
                  % (rid, rec.get("level"), rec.get("cap_at_gate")))
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
            rep.check(_inside(b, allowed),
                      "%s: carve writes %s, outside the envelope and sleeve %s" % (rid, b, allowed))
            rep.check(L.volume(b) <= FILL_LIMIT,
                      "%s: a write of %d blocks, over Minecraft's %d" % (rid, L.volume(b), FILL_LIMIT))
        rep.check(writes >= 6, "%s: only %d writes in the carve; that is not a chamber" % (rid, writes))
        checked_writes += writes

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

        # ---- the pending water export ---------------------------------------
        if lake:
            rep.check(_keep_covers(rec, g, doc, water, landmarks, ground, rep),
                      "%s: its declared keep zone does not actually protect the mouth" % rid)

    rep.check(checked_writes > 0, "NOTHING TO CHECK: no block write was tested")
    rep.check(checked_gates > 0, "NOTHING TO CHECK: no gate line was tested")

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
    rep = audit(doc, G.load(a.source_root), Path(a.pack), water, prog, lms)
    for e in rep.errors:
        print("FAIL %s" % e)
    print("legendaries audit: %d checks, %d failures" % (rep.checks, len(rep.errors)))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
