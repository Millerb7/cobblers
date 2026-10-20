#!/usr/bin/env python
"""Re-seated pack donors: a data/placements.json donor moved to a new position, its OLD seat taken down first.

The owner, 2026-10-20: "raise darkrais island way into the air, where it touches the build limit". Newmoon Island
(legendary_newmoon_island) had been pasted at y141; moving the record's position moves the next paste (tools/place_donor.py,
reapply R9) but leaves the old paste standing in the world. A record that has moved keeps each seat it left under
`superseded_seats`, and this tool writes that seat's takedown and the step that runs it:

  {"position": {"x", "y", "z"}, "size": [x, y, z], "rotation", "mirror", "retired": <date>, "why": ...,
   "restore": "air", "remove_entities": [entity type, ...]}

and the record carries `seat_probes`: template-relative [x, y, z, block] cells read from the template's NBT, which say
whether a paste stands at a seat (the old one before its takedown, the new one after its paste).

"restore": "air" is the only restore this tool writes: a floating template's seat is restored by air alone, and only
when EVERY column under it has its ground (tools/ground.py, the canonical heightmap, rounded) below the box's bottom.
The paste wrote every cell of its box (the template lists all of them), so whatever stood there before is already gone;
air is what a fresh export has there. Any column at or above the bottom refuses the whole takedown: such a seat needs a
terrain restore, which this tool does not write.

What the step does (tools/reapply.py R9DR, before R9), per superseded seat, holding the footprint's chunks:
  1. counts the players standing in or on the old box into #<holder>_held cobblers_chunk_look (the step reads 0 back,
     so a player there fails the step and NOTHING is written while anyone is);
  2. only with none, and only while a probe still shows the old paste, kills the template's own entity types inside the
     old box (armour stands and paintings, so none falls or drops) and fills the box with air, in /fill-sized slabs;
  3. pastes the template at its new position (cobblers:structures/place_<id>) only while no probe shows it there yet;
  4. reads back: #<holder>_old (old probes still standing: want 0; -1 if a probe's chunk was not loaded) and
     #<holder>_new (new probes standing: want every probe).
A second run finds no old probe and the new paste standing, so it writes nothing.

  python tools/donor_reseat.py check        every re-seat against the heightmap and the other placements
  python tools/donor_reseat.py plan         the steps and functions it would write, one line each

What this does NOT cover (CLAUDE.md "Our list is not the world"): anything a player built inside an old box after the
paste (the probes gate the takedown on the paste still standing, not on the box being only the paste), and trees or
mod blocks no file in data/ authors.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

PLACEMENTS = ROOT / "data" / "placements.json"
DIMENSION = ROOT / "modpack" / "datapacks" / "cobblers_height" / "data" / "minecraft" / "dimension_type" / "overworld.json"
NS = "cobblers"
FOLDER = "structures"
OBJ = "cobblers_chunk_look"        # tools/chunk_look.py OBJ: tools/reapply.py's ("check", ("chunk_look", ...)) reads it
HELD = "cobblers_reseat_held"
FILL_MAX = 32768                   # /fill refuses more than this many blocks (tools/place_donor.py commands)
ON_TOP = 3                         # a player standing on the old box's top layer is held too: feet up to 3 above it
RESTORES = ("air",)


class ReseatError(SystemExit):
    pass


def load(path=PLACEMENTS):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def runtime_top():
    """The highest buildable layer, from the height pack the world loads: min_y + height - 1."""
    d = json.loads(DIMENSION.read_text(encoding="utf-8"))
    return int(d["min_y"]) + int(d["height"]) - 1


def reseated(doc=None):
    """[(record, seat index, seat)] for every placement that keeps a superseded seat."""
    doc = doc if doc is not None else load()
    out = []
    for q in doc.get("placements") or []:
        for i, s in enumerate(q.get("superseded_seats") or []):
            out.append((q, i, s))
    return out


def seat_record(q, s):
    """The record as it stood at the old seat: its old position, size, rotation and mirror."""
    old = dict(q)
    old["position"] = dict(s["position"])
    old["size"] = list(s.get("size") or q["size"])
    old["rotation"] = s.get("rotation", q.get("rotation", "none"))
    old["mirror"] = s.get("mirror", q.get("mirror", "none"))
    return old


def box(rec):
    """((x0, y0, z0), (x1, y1, z1)), the inclusive world box tools/place_donor.py pastes the record into."""
    import place_donor
    return place_donor.box(rec)


def probe_cells(rec):
    """[(x, y, z, block)] in the world: the record's `seat_probes`, turned with the template about its position."""
    import place_donor
    x, y, z = (int(rec["position"][k]) for k in "xyz")
    out = []
    for tx, ty, tz, blk in rec.get("seat_probes") or []:
        rx, rz = place_donor.transform(int(tx), int(tz), rec.get("rotation", "none"), rec.get("mirror", "none"))
        out.append((x + rx, y + int(ty), z + rz, blk))
    return out


def holder(q, i):
    return "rs_%s_%d" % (q["id"], i)


def names(q, i):
    base = "%s/reseat_%s_%d" % (FOLDER, q["id"], i)
    return {"entry": base, "act": base + "_do", "place": base + "_place", "verify": base + "_verify"}


def hold_box(q, s):
    """(x0, z0, x1, z1): the old box's and the new box's columns together, force-loaded while the step runs."""
    (a0, _, b0), (a1, _, b1) = box(seat_record(q, s))
    (c0, _, d0), (c1, _, d1) = box(q)
    return min(a0, c0), min(b0, d0), max(a1, c1), max(b1, d1)


def slabs(lo, hi):
    area = (hi[0] - lo[0] + 1) * (hi[2] - lo[2] + 1)
    per = max(1, FILL_MAX // area)
    y = lo[1]
    while y <= hi[1]:
        yield lo[0], y, lo[2], hi[0], min(hi[1], y + per - 1), hi[2]
        y += per


def ground_proof(lo, hi, g):
    """(highest rounded ground under the box, [problem]): every column's ground must be below the box's bottom."""
    h = g.box(lo[0], lo[2], hi[0], hi[2])
    top = int(h.max())
    bad = []
    if top >= lo[1]:
        n = int((h >= lo[1]).sum())
        bad.append("%d of %d columns have ground at or above the old box's bottom y%d (highest y%d): air is not the "
                   "restore there, and this tool writes no terrain" % (n, h.size, lo[1], top))
    sea = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))["vertical"]["sea_level"]
    if sea >= lo[1]:
        bad.append("sea level y%d is at or above the old box's bottom y%d" % (sea, lo[1]))
    return top, bad


def _overlap(a, b):
    (a0, a1), (b0, b1) = a, b
    return all(a0[k] <= b1[k] and b0[k] <= a1[k] for k in range(3))


def other_boxes(doc, q):
    """[(id, lo, hi)] of every other pack donor, with the box tools/place_donor.py pastes it into. Other records are
    not seated by a box this tool can compute; tools/legendary_sweep_audit.py holds them to the footprint."""
    out = []
    for o in doc.get("placements") or []:
        if o is q or not o.get("pack_template") or not o.get("size") or not o.get("position"):
            continue
        lo, hi = box(o)
        out.append((o["id"], lo, hi))
    return out


def seat_problems(q, i, s, g, doc=None):
    """[problem] for one superseded seat: the restore it asks for, the heightmap under it, the new seat clear of it and
    under the build limit, the probes, and no other donor inside the box the takedown empties."""
    doc = doc if doc is not None else load()
    tag = "%s superseded_seats[%d]" % (q["id"], i)
    bad = []
    if s.get("restore") not in RESTORES:
        bad.append("%s: restore %r; this tool writes only %s" % (tag, s.get("restore"), RESTORES))
    old = seat_record(q, s)
    lo, hi = box(old)
    nlo, nhi = box(q)
    _top, gb = ground_proof(lo, hi, g)
    bad += ["%s: %s" % (tag, b) for b in gb]
    if _overlap((lo, hi), (nlo, nhi)):
        bad.append("%s: the old box %s..%s overlaps the new one %s..%s; the takedown would empty part of the new paste"
                   % (tag, lo, hi, nlo, nhi))
    top = runtime_top()
    if nhi[1] > top:
        bad.append("%s: the new box's top layer y%d is over the build limit y%d" % (q["id"], nhi[1], top))
    if nlo[1] < -64:
        bad.append("%s: the new box's bottom y%d is under the world" % (q["id"], nlo[1]))
    probes = q.get("seat_probes") or []
    if not probes:
        bad.append("%s has no seat_probes: nothing tells the step whether a paste stands" % q["id"])
    sx, sy, sz = q["size"]
    for p in probes:
        if not (0 <= p[0] < sx and 0 <= p[1] < sy and 0 <= p[2] < sz) or not isinstance(p[3], str) or ":" not in p[3]:
            bad.append("%s seat_probe %s is not a [x, y, z, namespaced block] inside the template's %s" % (q["id"], p, q["size"]))
    if list(s.get("size") or q["size"]) != list(q["size"]):
        bad.append("%s: the old seat's size %s is not the template's %s" % (tag, s.get("size"), q["size"]))
    for oid, olo, ohi in other_boxes(doc, q):
        if _overlap((lo, hi), (olo, ohi)):
            bad.append("%s: the takedown would empty part of %s (%s..%s)" % (tag, oid, olo, ohi))
        if _overlap((nlo, nhi), (olo, ohi)):
            bad.append("%s: the new paste %s..%s overlaps %s (%s..%s)" % (q["id"], nlo, nhi, oid, olo, ohi))
    for e in s.get("remove_entities") or []:
        if ":" not in e or e in ("minecraft:player", "cobblemon:pokemon"):
            bad.append("%s: remove_entities %r is not an entity type this takedown may kill" % (tag, e))
    return bad


def problems(doc=None, g=None):
    doc = doc if doc is not None else load()
    if g is None:
        import ground as G
        g = G.load()
    out = []
    seen = set()
    for q, i, s in reseated(doc):
        if not q.get("pack_template"):
            out.append("%s keeps superseded_seats but is not a pack donor" % q["id"])
            continue
        out += seat_problems(q, i, s, g, doc)
        h = holder(q, i)
        if h in seen:
            out.append("%s: score holder %s repeated" % (q["id"], h))
        seen.add(h)
        if len("#%s_held" % h) > 40:
            out.append("%s: score holder #%s_held is over 40 characters" % (q["id"], h))
    return out


def _sel(lo, hi, extra=""):
    return "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d%s" % (lo[0], lo[1], lo[2], hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], extra)


def functions(q, i, s):
    """{function name (under data/cobblers/function/): lines} for one superseded seat."""
    n = names(q, i)
    h = holder(q, i)
    old = seat_record(q, s)
    lo, hi = box(old)
    old_probes = probe_cells(old)
    new_probes = probe_cells(q)
    loaded = "# chunks-loaded-by: tools/reapply.py R9DR (forceload add %d %d %d %d before this runs)" % hold_box(q, s)
    held_hi = (hi[0], hi[1] + ON_TOP, hi[2])
    entry = ["# Generated by tools/donor_reseat.py from data/placements.json %s superseded_seats[%d]: the old seat at "
             "(%d, %d, %d), retired %s, taken down to air" % (q["id"], i, lo[0], lo[1], lo[2], s.get("retired")),
             loaded,
             "# A player in or on the old box is held, counted into #%s_held %s (the step reads 0 back, so a refusal stops "
             "the run), and nothing is written while anyone is. The takedown runs only while a probe still shows the old "
             "paste, so a second run writes nothing." % (h, OBJ),
             "scoreboard objectives add %s dummy" % OBJ,
             "tag @a remove %s" % HELD,
             "tag @a[%s] add %s" % (_sel(lo, held_hi), HELD),
             "execute store result score #%s_held %s if entity @a[tag=%s]" % (h, OBJ, HELD)]
    for (x, y, z, blk) in old_probes:
        entry.append("execute if score #%s_held %s matches 0 if block %d %d %d %s run function %s:%s"
                     % (h, OBJ, x, y, z, blk, NS, n["act"]))
    entry.append("tag @a remove %s" % HELD)
    act = ["# Generated by tools/donor_reseat.py: the old seat of %s emptied to air (the heightmap's ground is below it "
           "in every column: tools/donor_reseat.py check)" % q["id"],
           "# chunks-loaded-by: %s:%s (its caller holds the box's chunks)" % (NS, n["entry"]),
           "# the template's own entities first, so none falls out of the box or drops when its wall goes"]
    for e in s.get("remove_entities") or []:
        act.append("kill @e[type=%s,%s]" % (e, _sel(lo, hi)))
    act += ["fill %d %d %d %d %d %d minecraft:air" % sl for sl in slabs(lo, hi)]
    cond = " ".join("unless block %d %d %d %s" % (x, y, z, blk) for (x, y, z, blk) in new_probes)
    place = ["# Generated by tools/donor_reseat.py: %s pasted at its new seat (%d, %d, %d) only while no probe shows it "
             "there, so a second run does not paste it again (a re-paste would refill its looted containers)"
             % (q["id"], q["position"]["x"], q["position"]["y"], q["position"]["z"]),
             loaded,
             "execute %s run function %s:%s/place_%s" % (cond, NS, FOLDER, q["id"])]
    ver = ["# Generated by tools/donor_reseat.py: the read-back. #%s_old counts the old seat's probes still standing (want "
           "0), #%s_new the new seat's (want %d); both stay -1 unless every probe's chunk is loaded" % (h, h, len(new_probes)),
           loaded,
           "scoreboard objectives add %s dummy" % OBJ,
           "scoreboard players set #%s_old %s -1" % (h, OBJ),
           "scoreboard players set #%s_new %s -1" % (h, OBJ)]
    every = " ".join("if loaded %d %d %d" % (x, y, z) for (x, y, z, _b) in old_probes + new_probes)
    ver += ["execute %s run scoreboard players set #%s_old %s 0" % (every, h, OBJ),
            "execute %s run scoreboard players set #%s_new %s 0" % (every, h, OBJ)]
    for (x, y, z, blk) in old_probes:
        ver.append("execute if score #%s_old %s matches 0.. if block %d %d %d %s run scoreboard players add #%s_old %s 1"
                   % (h, OBJ, x, y, z, blk, h, OBJ))
    for (x, y, z, blk) in new_probes:
        ver.append("execute if score #%s_new %s matches 0.. if block %d %d %d %s run scoreboard players add #%s_new %s 1"
                   % (h, OBJ, x, y, z, blk, h, OBJ))
    return {n["entry"]: entry, n["act"]: act, n["place"]: place, n["verify"]: ver}


def files(doc=None, g=None):
    """{path under the pack: text}, refused whole if any re-seat has a problem."""
    doc = doc if doc is not None else load()
    bad = problems(doc, g)
    if bad:
        raise ReseatError("tools/donor_reseat.py refuses to write the takedowns:\n  " + "\n  ".join(bad))
    import function_limits
    out = {}
    for q, i, s in reseated(doc):
        for name, lines in functions(q, i, s).items():
            refused = function_limits.check_lines(lines, name)
            if refused:
                raise ReseatError("%s: %d command(s) the server would refuse: %s" % (name, len(refused), refused[:2]))
            out["data/%s/function/%s.mcfunction" % (NS, name)] = "\n".join(lines) + "\n"
    return out


def write(out_dir, doc=None, g=None):
    fs = files(doc, g)
    for rel, text in fs.items():
        p = Path(out_dir) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    return sorted(fs)


def steps(doc=None):
    """tools/reapply.py R9DR's actions, from the committed data alone (no heightmap, no build/)."""
    doc = doc if doc is not None else load()
    out = []
    for q, i, s in reseated(doc):
        n = names(q, i)
        h = holder(q, i)
        hold = "%d %d %d %d" % hold_box(q, s)
        nprobe = len(q.get("seat_probes") or [])
        out += [("cmd", "forceload add " + hold), ("wait", 4),
                ("fn", "%s:%s" % (NS, n["entry"])),
                ("check", ("chunk_look", h + "_held", 0, "players on %s's old seat (its takedown refused)" % q["id"])),
                # place_<id> pastes 20 ticks after it is called and checks 20 after that (tools/place_donor.py SETTLE)
                ("fn", "%s:%s" % (NS, n["place"])), ("wait", 5),
                # place_<id>_check released its own forceload, and a forceload is per chunk, not counted: hold again
                ("cmd", "forceload add " + hold), ("wait", 3),
                ("fn", "%s:%s" % (NS, n["verify"])),
                ("check", ("chunk_look", h + "_old", 0, "%s's old seat: probes still standing" % q["id"])),
                ("check", ("chunk_look", h + "_new", nprobe, "%s's new seat: probes standing" % q["id"])),
                ("cmd", "forceload remove " + hold)]
    return out


def step_functions(doc=None):
    doc = doc if doc is not None else load()
    return ["%s:%s" % (NS, v) for q, i, _s in reseated(doc) for v in names(q, i).values()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("plan")
    a = ap.parse_args(argv)
    import ground as G
    g = G.load()
    doc = load()
    bad = problems(doc, g)
    for q, i, s in reseated(doc):
        lo, hi = box(seat_record(q, s))
        nlo, nhi = box(q)
        top, _ = ground_proof(lo, hi, g)
        print("%s seat %d: old box %s..%s (highest ground y%d, %d under its bottom); new box %s..%s (build limit y%d)"
              % (q["id"], i, lo, hi, top, lo[1] - top, nlo, nhi, runtime_top()))
        if a.cmd == "plan":
            for name, lines in functions(q, i, s).items():
                print("  %s: %d lines" % (name, len(lines)))
            print("  R9DR: %d actions" % len(steps(doc)))
    for b in bad:
        print("PROBLEM %s" % b)
    print("%d re-seat(s), %d problem(s)" % (len(reseated(doc)), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
