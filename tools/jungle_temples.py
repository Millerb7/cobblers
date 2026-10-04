#!/usr/bin/env python
"""The jungle's lost temples of data/jungle_temples.json: three overgrown ruins on the Long Isle's south.

The owner, 2026-10-04: "make sure the jungle has its lost temples." The jungle is the Long Isle's south
(data/regions.json long_isle_south) since the Jungle Isle went under the sea; the old jungle ruins' six drowned pieces
are superseded (data/placements.json superseded_placements), and docs/world-building/LONG_ISLE.md section 11.4 moves
their story here. Three temples, each with a cache (data/rewards.json, given by tools/rewards_pack.py's advancement;
the barrels are scenery): the Ring Court (west, a puzzle: the eye in a ring of carved stones is a trapdoor over an
undercroft), the Harbour Mark (middle, a sea-mark on the highest terrace, its arm pointing to Sunset West), the Green
Stair (north, a stepped pyramid whose top stair fell; the way up is the vines). No named Pokemon: the island's one
heart is Split-Bark (data/resident_encounters.json).

Nothing here is new machinery. The block primitives (a structure on a levelled floor, blocks on their own column's
ground, a ring) and the build-function writer are tools/southern_residents.py's, CALLED, not copied, as
tools/far_south.py calls them. Every Y is the canonical heightmap's rounded ground (tools/ground.py), never a world's.

The siting rules fail the build (data/jungle_temples.json rules): every written column and clear inside
long_isle_south, round(ground) above the sea and dry; a structure's foundation no taller than rules.max_foundation;
at least rules.authored_clearance from every x/z authored in any OTHER data/*.json (this file's own cache rewards
skipped by id) and from every route corridor box; at least rules.keep_clear.blocks from every keep_clear entry (the
Mew temple's footprint, the elders, the island's heart, a portal, the ferry stops); outside every town footprint (+ the
authored clearance) and every Rift zone box; no block a spawn condition names (data/spawn_blocks.json); every cache's
spot two blocks of standing room over its barrel. These are the builder's guards, not an audit: the independent audit
is another agent's (data/jungle_temples.json audit_checklist).

  python tools/jungle_temples.py [--source-root R] [--out DIR]    write build/datapacks/cobblers_jungle_temples
  python tools/jungle_temples.py --report                          the sites as measured, the checks, the steps

The re-application (tools/reapply.py): placement_steps() is R9JT, after R9FS and BEFORE R9E with the other block
passes. The pack is a server pack, not world-local: it has no load or tick function and does nothing unless called.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402
import southern_residents as SR  # noqa: E402

DATA = ROOT / "data" / "jungle_temples.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_jungle_temples"
SCHEMA = "cobblers.jungle-temples/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
KINDS = ("structure", "ground_blocks", "ring")
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()

jload = SR.jload
base = SR.base


class TempleError(SystemExit):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise TempleError("%s: schema must be %s" % (path, SCHEMA))
    ids = [t["id"] for t in doc["temples"]]
    if len(ids) != len(set(ids)):
        raise TempleError("temple ids must be unique")
    for t in doc["temples"]:
        if t.get("npc") or t.get("pokemon"):
            raise TempleError("%s: this file seats no NPC and no named Pokemon (the island's heart is Split-Bark)" % t["id"])
        for p in t["pieces"]:
            if p["kind"] not in KINDS:
                raise TempleError("%s: unknown piece kind %s" % (t["id"], p["kind"]))
        caches = t.get("caches") or []
        if len(caches) != 1:
            raise TempleError("%s: one cache a temple (records.reward names it, so the clearance scan skips it)" % t["id"])
        for c in caches:
            if (t.get("records") or {}).get("reward") != c["reward"]:
                raise TempleError("%s: records.reward must name the cache %s" % (t["id"], c["reward"]))
            if not isinstance(c.get("items_hook"), dict):
                raise TempleError("%s: the cache %s carries no items_hook" % (t["id"], c["reward"]))
            if not isinstance(c.get("feet_dy"), int):
                raise TempleError("%s: the cache %s needs an integer feet_dy (feet above the named floor)" % (t["id"], c["reward"]))
    # tools/southern_residents.py's helpers read a doc's "residents": the temples are those records here
    doc["residents"] = doc["temples"]
    return doc


# ------------------------------------------------------------------ the plan


def plan(doc, t, g, wet):
    s = SR.Site(doc, t, g, wet)
    for p in t["pieces"]:
        k = p["kind"]
        if k == "structure":
            SR.piece_structure(s, p)
        elif k == "ground_blocks":
            SR.piece_ground_blocks(s, p)
        elif k == "ring":
            SR.piece_ring(s, p)
    return s


def spot(s, c):
    """A cache's feet (x, y, z): [lx, lz, piece] and feet_dy above that piece's floor (below it for the undercroft)."""
    lx, lz, on = c["at"]
    return s.cx + lx, s.floors[on] + int(c["feet_dy"]), s.cz + lz


def sites(doc, g, wet=None):
    import resident_encounters as RE
    wet = wet or RE.Wet(g, [tuple(t["site"]["centre"]) for t in doc["temples"]])
    out = []
    for t in doc["temples"]:
        s = plan(doc, t, g, wet)
        extra = [spot(s, c) for c in t["caches"]]
        out.append((t, s, extra, SR.box_of(s, extra)))
    return out


# ------------------------------------------------------------------ the siting rules (the builder's guards)


def authored_points(doc):
    return SR.authored_points(doc, own_file=DATA)


def _cols(s, extra):
    cols = set(s.cols) | {(e[0], e[2]) for e in extra}
    for c in s.clears:
        cols |= {(x, z) for x in range(c[0], c[3] + 1) for z in range(c[2], c[5] + 1)}
    return cols


def _box_dist(x, z, b):
    return math.hypot(max(b[0] - x, 0, x - b[2]), max(b[1] - z, 0, z - b[3]))


def _coast(g, cx, cz, limit=600):
    """The distance from the centre to the nearest column at or below the sea, on a ring sweep every 4 blocks."""
    sea = jload("world.json")["vertical"]["sea_level"]
    for r in range(4, limit + 1, 4):
        n = max(16, int(2 * math.pi * r / 4))
        for k in range(n):
            a = 2 * math.pi * k / n
            if g(int(round(cx + r * math.sin(a))), int(round(cz - r * math.cos(a)))) <= sea:
                return r
    return None


def siting(doc, t, s, extra, pts):
    """(problems, measures) for one planned temple."""
    import numpy as np
    from subregion_boxes import point_in_polygon
    rules = doc["rules"]
    probs = []
    cols = _cols(s, extra)
    C = np.array(sorted(cols), float)
    # inside the sub-region, above the sea, dry
    sub = [x for x in jload("regions.json")["subregions"] if x["id"] == rules["subregion"]][0]
    polys = sub["polygons"]
    outside = [(x, z) for x, z in sorted(cols) if not any(point_in_polygon(x, z, p) for p in polys)]
    if outside:
        probs.append("%s: %d written column(s) outside %s, e.g. %s" % (t["id"], len(outside), rules["subregion"], outside[:3]))
    low = [(x, z, s.g(x, z)) for x, z in sorted(cols) if s.g(x, z) <= rules["dry_above"]]
    if low:
        probs.append("%s: %d column(s) at or below y%d, e.g. %s" % (t["id"], len(low), rules["dry_above"], low[:3]))
    wet = [(x, z) for x, z in sorted(cols) if s.wet(x, z)]
    if wet:
        probs.append("%s: %d wet column(s), e.g. %s" % (t["id"], len(wet), wet[:3]))
    # the foundation under each structure
    found = {}
    for p in t["pieces"]:
        if p["kind"] != "structure":
            continue
        x0, z0, x1, z1 = p["footprint"]
        gs = [s.g(s.cx + a, s.cz + b) for a in range(x0, x1 + 1) for b in range(z0, z1 + 1)]
        found[p["name"]] = max(gs) - min(gs)
        if found[p["name"]] > rules["max_foundation"]:
            probs.append("%s %s: a foundation %d tall (max %d)" % (t["id"], p["name"], found[p["name"]], rules["max_foundation"]))
    # every other data file's x/z
    P = np.array([(a, b) for a, b, _f in pts], float)
    F = [f for _a, _b, f in pts]
    best = (1e9, None, None)
    for i in range(0, len(C), 256):
        blk = C[i:i + 256]
        d = np.hypot(P[None, :, 0] - blk[:, None, 0], P[None, :, 1] - blk[:, None, 1])
        j = np.unravel_index(np.argmin(d), d.shape)
        if d[j] < best[0]:
            best = (float(d[j]), tuple(blk[j[0]]), F[j[1]])
    m = rules["authored_clearance"]
    if best[0] < m:
        probs.append("%s: (%d, %d) is %.0f blocks from an x/z authored in data/%s (needs %d)"
                     % (t["id"], best[1][0], best[1][1], best[0], best[2], m))
    cprobs, cbest = SR.corridor_check(t["id"], cols, m)
    probs += cprobs
    for tw in jload("towns.json")["towns"]:
        f = tw.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        if any(f["min_x"] - m <= x <= f["max_x"] + m and f["min_z"] - m <= z <= f["max_z"] + m for x, z in cols):
            probs.append("%s: within %d of town %s's footprint" % (t["id"], m, tw["id"]))
    for k, zone in jload("rift_zones.json")["zones"].items():
        for bx in zone.get("boxes") or []:
            if any(bx[0] <= x <= bx[2] and bx[1] <= z <= bx[3] for x, z in cols):
                probs.append("%s: inside Rift zone %s" % (t["id"], k))
                break
    # the keep-clear list
    kc = rules["keep_clear"]
    near = []
    for e in kc["entries"]:
        b = e["box"]
        d = min(_box_dist(x, z, b) for x, z in cols)
        near.append((d, e["id"]))
        if d < kc["blocks"]:
            probs.append("%s: %.0f blocks from %s (keep_clear needs %d)" % (t["id"], d, e["id"], kc["blocks"]))
    near.sort()
    cell = _cell(*t["site"]["centre"])
    if cell != t["cell"]:
        probs.append("%s: the centre is in cell %s, the record says %s" % (t["id"], cell, t["cell"]))
    return probs, {"nearest_authored": best, "corridor": cbest, "keep_clear": near[:3], "foundation": found}


def _cell(x, z):
    grid = jload("world.json")["grid"]
    n = grid["cell_size"]
    return grid["row_labels"][int(z - grid["origin_z"]) // n] + grid["column_labels"][int(x - grid["origin_x"]) // n]


def check_records(doc, built):
    """The cache container, trigger and bbox recorded in the data are the ones the heightmap gives; each cache's spot is
    two blocks of standing room over its barrel."""
    probs = []
    rw = {x["id"]: x for x in jload("rewards.json")["rewards"]}
    for t, s, extra, box in built:
        blocks = dict(s.solid)
        blocks.update(s.hung)
        for c in t["caches"]:
            xyz = list(spot(s, c))
            w = rw.get(c["reward"])
            if not w or w.get("kind") != "cache":
                probs.append("%s: data/rewards.json %s is not a cache" % (t["id"], c["reward"]))
                continue
            if not w.get("contents"):
                probs.append("%s: data/rewards.json %s gives nothing" % (t["id"], c["reward"]))
            cont = [xyz[0], xyz[1] - 1, xyz[2]]
            ct = w.get("container") or {}
            if ct.get("at") != cont:
                probs.append("%s: %s container at %s, the site gives %s" % (t["id"], c["reward"], ct.get("at"), cont))
            if s.solid.get(tuple(cont)) is None or base(s.solid[tuple(cont)]) != ct.get("block"):
                probs.append("%s: no %s written at %s" % (t["id"], ct.get("block"), cont))
            for dy in (0, 1):
                b = base(blocks.get((xyz[0], xyz[1] + dy, xyz[2]), "minecraft:air"))
                if b not in ("minecraft:air", "minecraft:moss_carpet"):
                    probs.append("%s: %s's spot %s has %s at feet+%d" % (t["id"], c["reward"], xyz, b, dy))
            tr = w.get("trigger") or {}
            lo, hi = tr.get("min"), tr.get("max")
            if not (lo and hi and all(lo[i] <= xyz[i] <= hi[i] for i in range(3))):
                probs.append("%s: %s trigger %s does not hold the spot %s" % (t["id"], c["reward"], tr, xyz))
        if list(box) != t.get("bbox"):
            probs.append("%s: the writes' box is %s, the record's bbox %s" % (t["id"], box, t.get("bbox")))
    return probs


def check_all(doc, built):
    pts = authored_points(doc)
    probs = []
    for t, s, extra, box in built:
        probs += siting(doc, t, s, extra, pts)[0]
    probs += check_records(doc, built)
    spawn = set(jload("spawn_blocks.json")["blocks"])
    for t, s, extra, box in built:
        written = {base(v) for v in list(s.solid.values()) + list(s.hung.values())}
        bad = sorted(written & spawn)
        if bad:
            probs.append("%s: writes spawn-condition blocks %s (data/spawn_blocks.json)" % (t["id"], bad))
        for no in ("minecraft:chest", "minecraft:trapped_chest"):
            if no in written:
                probs.append("%s: writes %s (a Gimmighoul condition)" % (t["id"], no))
        if any(b.endswith("_bed") for b in written):
            probs.append("%s: writes a bed (the blackout's checkpoints own respawn)" % t["id"])
    return probs


# ------------------------------------------------------------------ the pack


def files(doc, g, wet=None, check=True):
    built = sites(doc, g, wet)
    if check:
        probs = check_all(doc, built)
        if probs:
            raise TempleError("jungle_temples: %d problem(s):\n  %s" % (len(probs), "\n  ".join(probs)))
    b = doc["build"]
    ns, F = b["namespace"], b["folder"]
    out = {}
    for t, s, extra, box in built:
        lines = SR.build_lines(doc, t, s, box)
        lines[0] = "# Generated by tools/jungle_temples.py from data/jungle_temples.json: %s" % t["name"]
        lines[1] = lines[1].replace("R9SR", b["step"])
        bad = function_limits.check_lines(lines, "%s/build" % t["id"])
        if bad:
            raise TempleError("%s/build: %d command(s) the server would refuse: %s" % (t["id"], len(bad), bad[:3]))
        out["data/%s/function/%s/%s/build.mcfunction" % (ns, F, t["id"])] = "\n".join(lines) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                              "Cobblers: the jungle's lost temples (tools/jungle_temples.py)"}}, indent=2) + "\n"
    return out, built


# ------------------------------------------------------------------ the re-application


def _built(doc=None, g=None):
    import ground as G
    doc = doc or load()
    g = g or G.load()
    return doc, g, sites(doc, g)


def placement_steps(doc=None, g=None):
    """R9JT, after R9FS and BEFORE R9E: per temple, hold its box, build, release (R9FS's shape)."""
    doc, g, built = _built(doc, g)
    b = doc["build"]
    steps = []
    for t, s, extra, box in built:
        hold = "%d %d %d %d" % tuple(box)
        steps += [("cmd", "forceload add " + hold), ("wait", 3),
                  ("fn", "%s:%s/%s/build" % (b["namespace"], b["folder"], t["id"])), ("cmd", "forceload remove " + hold)]
    return steps


# ------------------------------------------------------------------ CLI


def report(doc, g):
    built = sites(doc, g)
    pts = authored_points(doc)
    lines = []
    for t, s, extra, box in built:
        probs, m = siting(doc, t, s, extra, pts)
        na = m["nearest_authored"]
        lines.append("%-13s %-17s %s centre %s ground y%d; %d blocks, bbox %s; nearest authored %.0f (our column %s to "
                     "data/%s); corridor box %.0f; coast %s"
                     % (t["id"], t["name"], t["cell"], t["site"]["centre"], g(*t["site"]["centre"]),
                        len(s.solid) + len(s.hung), box, na[0], tuple(int(v) for v in na[1]), na[2], m["corridor"][0],
                        _coast(g, *t["site"]["centre"])))
        lines.append("    nearest keep_clear: %s" % ", ".join("%s %.0f" % (i, d) for d, i in m["keep_clear"]))
        for k, v in s.floors.items():
            lines.append("    floor %s: y%s, foundation relief %s" % (k, v, m["foundation"].get(k)))
        for c in t["caches"]:
            xyz = list(spot(s, c))
            lines.append("    cache %s spot %s container %s" % (c["reward"], xyz, [xyz[0], xyz[1] - 1, xyz[2]]))
        for p in probs:
            lines.append("    PROBLEM %s" % p)
    for p in check_records(doc, built):
        lines.append("PROBLEM %s" % p)
    lines.append("steps %s: %d actions" % (doc["build"]["step"], len(placement_steps(doc, g))))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--report", action="store_true", help="print the sites, the checks and the steps; write nothing")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    if a.report:
        print("\n".join(report(doc, g)))
        return 0
    written, built = files(doc, g)
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in written.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    n = sum(1 for rel, t in written.items() if rel.endswith("/build.mcfunction")
            for l in t.splitlines() if l and not l.startswith("#"))
    print("jungle_temples: %d files -> %s (%d temples, build: %d commands)" % (len(written), out, len(built), n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
