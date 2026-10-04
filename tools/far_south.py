#!/usr/bin/env python
"""The far south's places of data/far_south.json: five places in the emptiest cells of rows F-H.

The owner, 2026-10-04: "the southern map, still the thinnest." Measured first (tools/south_density.py,
docs/world-building/SOUTH_DENSITY.md): rows F-H hold 14.9 things a player meets per km2 of land against 24.4 in rows
A-E. These five stand in the emptiest cells with land, each in the dress of its sub-region (docs/story/ENCOUNTERS.md's
species lists, data/regions.json's paint): a drovers' kraal on the Arrow Creeks savanna (F3), a stand of hoodoos on
the Scorched Plateau's eroded south (F6), a lightning-glassed dune top (G6), a ring of glyph stones on the south-east
dunes (G7) and a ruined garden folly on Sunset East (H3).

Nothing here is new machinery. The block primitives (a structure on a levelled floor, surface work, blocks on their
own column's ground, a ring, a line of posts, a clearing), the record checks and the residents' keeper are
tools/southern_residents.py's and tools/northern_residents.py's own functions, CALLED, not copied, and through them
tools/resident_encounters.py's keeper. Every Y is the canonical heightmap's rounded ground (tools/ground.py), never a
world's. No NPC: three named Pokemon (each dormant until a player comes within its trigger, leashed, respawned on the
keeper's clock) and three caches (data/rewards.json, given by tools/rewards_pack.py's advancement; the barrels are
scenery).

The siting rules fail the build (data/far_south.json rules): every written column, clear, anchor and cache in rows F-H
(z >= rules.south_of_z) and at least rules.authored_clearance from every x/z authored in any OTHER data/*.json (this
file's own cache rewards skipped by id) and from every route corridor box; outside every town footprint (+ the same
clearance), every Rift zone box and the keep-out box over the Rift's southern arms and the Mega field; every site
centre, anchor and cache at least rules.path_clearance from a route path (data/encounter_design.json
rules.hearts.clear_of_path_blocks); a resident's leash clear of every activated Habitat Block's spawn_range; its level
within its sub-region's tier ceiling; no block a spawn condition names. These are the builder's guards, not an audit:
the independent audit is another agent's (data/far_south.json audit_checklist).

  python tools/far_south.py [--source-root R] [--out DIR]    write build/datapacks/cobblers_far_south
  python tools/far_south.py --report                          the sites as measured, the checks, the steps

The re-application (tools/reapply.py): placement_steps() is R9FS, BEFORE R9E with the other block passes (after R9NR);
entity_steps() is R18FS, after R18NR: the ungated residents summoned and bound (all three are gated, so none today).
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
import northern_residents as NR  # noqa: E402
import southern_residents as SR  # noqa: E402

DATA = ROOT / "data" / "far_south.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_far_south"
SCHEMA = "cobblers.far-south/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
KINDS = NR.KINDS
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class FarSouthError(SystemExit):
    pass


jload = SR.jload
base = SR.base


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise FarSouthError("%s: schema must be %s" % (path, SCHEMA))
    ids = [r["id"] for r in doc["residents"]]
    if len(ids) != len(set(ids)):
        raise FarSouthError("site ids must be unique")
    for r in doc["residents"]:
        if r.get("npc"):
            raise FarSouthError("%s: this file seats no NPC (no dialogue records are built for it)" % r["id"])
        for p in r["pieces"]:
            if p["kind"] not in KINDS:
                raise FarSouthError("%s: unknown piece kind %s" % (r["id"], p["kind"]))
        pk = r.get("pokemon")
        if pk and not (0 < pk["trigger"] < pk["leash"]):
            raise FarSouthError("%s: the trigger must be inside the leash" % r["id"])
        caches = r.get("caches") or []
        if len(caches) > 1:
            raise FarSouthError("%s: one cache a site (records.reward names it, so the clearance scan skips it)" % r["id"])
        for c in caches:
            if (r.get("records") or {}).get("reward") != c["reward"]:
                raise FarSouthError("%s: records.reward must name the cache %s" % (r["id"], c["reward"]))
            if not isinstance(c.get("items_hook"), dict):
                raise FarSouthError("%s: the cache %s carries no items_hook" % (r["id"], c["reward"]))
    return doc


def sites(doc, g, wet=None):
    """tools/northern_residents.py sites(): the same pieces (its `clearing` among them), the same standing checks."""
    return NR.sites(doc, g, wet)


# ------------------------------------------------------------------ the siting rules (the builder's guards)


def authored_points(doc):
    return SR.authored_points(doc, own_file=DATA)


def _cols(s, extra):
    cols = set(s.cols) | {(e[0], e[2]) for e in extra}
    for c in s.clears:
        cols |= {(x, z) for x in range(c[0], c[3] + 1) for z in (c[2], c[5])}
        cols |= {(x, z) for z in range(c[2], c[5] + 1) for x in (c[0], c[3])}
    return cols


def siting(doc, r, s, extra, pts):
    """Problems, as strings, for one planned site. `extra` are the anchors and cache spots (x, y, z)."""
    import numpy as np
    rules = doc["rules"]
    probs = []
    P = np.array([(a, b) for a, b, _f in pts], float)
    F = [f for _a, _b, f in pts]
    cols = _cols(s, extra)
    C = np.array(sorted(cols), float)
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
                     % (r["id"], best[1][0], best[1][1], best[0], best[2], m))
    cprobs, cbest = SR.corridor_check(r["id"], cols, m)
    probs += cprobs
    for t in jload("towns.json")["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        if any(f["min_x"] - m <= x <= f["max_x"] + m and f["min_z"] - m <= z <= f["max_z"] + m for x, z in cols):
            probs.append("%s: within %d of town %s's footprint" % (r["id"], m, t["id"]))
    for k, zone in jload("rift_zones.json")["zones"].items():
        for bx in zone.get("boxes") or []:
            if any(bx[0] <= x <= bx[2] and bx[1] <= z <= bx[3] for x, z in cols):
                probs.append("%s: inside Rift zone %s" % (r["id"], k))
                break
    kx0, kz0, kx1, kz1 = rules["keep_out_box"]["box"]
    if any(kx0 <= x <= kx1 and kz0 <= z <= kz1 for x, z in cols):
        probs.append("%s: writes inside the keep-out box %s" % (r["id"], rules["keep_out_box"]["box"]))
    if any(z < rules["south_of_z"] for _x, z in cols):
        probs.append("%s: writes north of z %d (rows F-H only)" % (r["id"], rules["south_of_z"]))
    paths = np.array([p for pl in jload("route_paths.json")["paths"].values() for p in pl], float)
    cx, cz = r["site"]["centre"]
    dp = float(np.min(np.hypot(paths[:, 0] - cx, paths[:, 1] - cz)))
    if dp < rules["path_clearance"]:
        probs.append("%s: %.0f blocks from a route path (needs %d)" % (r["id"], dp, rules["path_clearance"]))
    for e in extra:
        de = float(np.min(np.hypot(paths[:, 0] - e[0], paths[:, 1] - e[2])))
        if de < rules["path_clearance"]:
            probs.append("%s: the anchor or cache %s is %.0f blocks from a route path (needs %d)"
                         % (r["id"], list(e), de, rules["path_clearance"]))
    pk = r.get("pokemon")
    if pk:
        ax, az = s.cx + pk["at"][0], s.cz + pk["at"][1]
        for b in jload("habitat_blocks.json")["blocks"]:
            if b.get("style") != "activated":
                continue
            d = math.hypot(b["position"]["x"] - ax, b["position"]["z"] - az)
            if d < b["activated"]["spawn_range"] + pk["leash"]:
                probs.append("%s: its leash overlaps Habitat Block %s (%.0f, needs %d)"
                             % (r["id"], b["id"], d, b["activated"]["spawn_range"] + pk["leash"]))
        sub, tier, ceiling = SR._sub_of(ax, az)
        if sub is None:
            probs.append("%s: the resident stands in no sub-region with a table" % r["id"])
        else:
            if pk["level"] > ceiling:
                probs.append("%s: L%d over %s's tier-%s ceiling %d" % (r["id"], pk["level"], sub, tier, ceiling))
            if sub != r["subregion"]:
                probs.append("%s: the resident stands in %s, the record says %s" % (r["id"], sub, r["subregion"]))
    sub = SR._sub_of(cx, cz)[0]
    if sub != r["subregion"]:
        probs.append("%s: the centre is in %s, the record says %s" % (r["id"], sub, r["subregion"]))
    cell = _cell(cx, cz)
    if cell != r["cell"]:
        probs.append("%s: the centre is in cell %s, the record says %s" % (r["id"], cell, r["cell"]))
    return probs, {"nearest_authored": best, "path": dp, "corridor": cbest}


def _cell(x, z):
    grid = jload("world.json")["grid"]
    s = grid["cell_size"]
    return grid["row_labels"][int(z - grid["origin_z"]) // s] + grid["column_labels"][int(x - grid["origin_x"]) // s]


def check_all(doc, built):
    pts = authored_points(doc)
    probs = []
    for r, s, extra, box in built:
        probs += siting(doc, r, s, extra, pts)[0]
    probs += SR.check_records(doc, built)
    spawn = set(jload("spawn_blocks.json")["blocks"])
    for r, s, extra, box in built:
        bad = sorted({base(v) for v in list(s.solid.values()) + list(s.hung.values())} & spawn)
        if bad:
            probs.append("%s: writes spawn-condition blocks %s (data/spawn_blocks.json)" % (r["id"], bad))
    rw = {x["id"]: x for x in jload("rewards.json")["rewards"]}
    for r, s, extra, box in built:
        for c in r.get("caches") or []:
            w = rw.get(c["reward"]) or {}
            if not w.get("contents"):
                probs.append("%s: data/rewards.json %s gives nothing" % (r["id"], c["reward"]))
    return probs


# ------------------------------------------------------------------ the pack


def files(doc, g, wet=None, check=True):
    import resident_encounters as RE
    built = sites(doc, g, wet)
    if check:
        probs = check_all(doc, built)
        if probs:
            raise FarSouthError("far_south: %d problem(s):\n  %s" % (len(probs), "\n  ".join(probs)))
    b = doc["build"]
    ns, F, obj = b["namespace"], b["folder"], b["objective"]
    fn = {}
    sh = SR.shim(doc)
    load_ = ["# the far south's keeper state (tools/far_south.py, on tools/resident_encounters.py's keeper).",
             "# A clock that has never been set starts READY (respawn ticks already elapsed), so a fresh world fills at once",
             "scoreboard objectives add %s dummy" % obj,
             "scoreboard players set #resp %s %d" % (obj, int(b["respawn_ticks"])),
             "execute store result score #ready %s run time query gametime" % obj,
             "scoreboard players operation #ready %s -= #resp %s" % (obj, obj)]
    keeper = ["execute store result score #now %s run time query gametime" % obj]
    for r, s, extra, box in built:
        lines = SR.build_lines(doc, r, s, box)
        lines[0] = "# Generated by tools/far_south.py from data/far_south.json: %s" % r["name"]
        lines[1] = lines[1].replace("R9SR", b["steps"]["blocks"])
        bad = function_limits.check_lines(lines, "%s/build" % r["id"])
        if bad:
            raise FarSouthError("%s/build: %d command(s) the server would refuse: %s" % (r["id"], len(bad), bad[:3]))
        fn["%s/build" % r["id"]] = lines
        if r.get("pokemon"):
            e = SR.resident_record(r)
            a = SR.anchor(s, r)
            i = e["id"]
            rf = RE.resident_files(sh, e, a, [], [], box)
            rf.pop("%s/dress" % i, None)
            fn.update(rf)
            load_ += ["execute unless score #%s.gone %s matches -2147483648.. run scoreboard players operation #%s.gone %s = #ready %s"
                      % (i, obj, i, obj, obj),
                      "execute unless score #%s.abs %s matches -2147483648.. run scoreboard players set #%s.abs %s 0" % (i, obj, i, obj)]
            keeper.append("execute if loaded %d %d %d run function %s:%s/%s/keep" % (a[0], a[1], a[2], ns, F, i))
    if any(r.get("pokemon") for r, _s, _e, _b in built):
        fn["spawn_at"] = ["# a macro, so the mod's command is parsed when it runs (EXP-046, .claude/rules/datapacks.md)",
                          "$spawnpokemonat $(x) $(y) $(z) $(species) $(props)"]
        load_.append("schedule function %s:%s/keeper %dt replace" % (ns, F, b["keeper"]["period_ticks"]))
        keeper.append("schedule function %s:%s/keeper %dt replace" % (ns, F, b["keeper"]["period_ticks"]))
        fn["load"] = load_
        fn["keeper"] = keeper
    out = {"data/%s/function/%s/%s.mcfunction" % (ns, F, n): "\n".join(v) + "\n" for n, v in fn.items()}
    if "load" in fn:
        out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:%s/load" % (ns, F)]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                              "Cobblers: the far south's places (tools/far_south.py)"}}, indent=2) + "\n"
    return out, built


# ------------------------------------------------------------------ the re-application


def _built(doc=None, g=None):
    import ground as G
    doc = doc or load()
    g = g or G.load()
    return doc, g, sites(doc, g)


def placement_steps(doc=None, g=None):
    """R9FS, BEFORE R9E: per site, hold its box, build, release (R9SR's shape)."""
    doc, g, built = _built(doc, g)
    b = doc["build"]
    steps = []
    for r, s, extra, box in built:
        hold = "%d %d %d %d" % tuple(box)
        steps += [("cmd", "forceload add " + hold), ("wait", 3),
                  ("fn", "%s:%s/%s/build" % (b["namespace"], b["folder"], r["id"])), ("cmd", "forceload remove " + hold)]
    return steps


def entity_steps(doc=None, g=None):
    """R18FS, after R18NR: each UNGATED resident summoned over RCON (guarded on tag AND species: THE SUMMON GUARD) and
    bound, inside a forceload of its site's box. A gated one (appears_after) is left to the keeper, which brings it in
    the first time a player holding the gate comes near. All three are gated today, so this is empty: said here so an
    empty step is read as the design, not as a fault."""
    import resident_encounters as RE
    doc, g, built = _built(doc, g)
    b = doc["build"]
    sh = SR.shim(doc)
    steps = []
    for r, s, extra, box in built:
        if not r.get("pokemon") or r["pokemon"].get("appears_after"):
            continue
        e = SR.resident_record(r)
        a = SR.anchor(s, r)
        hold = "%d %d %d %d" % tuple(box)
        steps += [("cmd", "forceload add " + hold), ("wait", 3), ("cmd", RE.summon_command(sh, e, a)), ("wait", 1),
                  ("fn", "%s:%s/%s/bind_new" % (b["namespace"], b["folder"], e["id"])), ("cmd", "forceload remove " + hold)]
    return steps


# ------------------------------------------------------------------ CLI


def report(doc, g):
    built = sites(doc, g)
    pts = authored_points(doc)
    lines = []
    for r, s, extra, box in built:
        probs, m = siting(doc, r, s, extra, pts)
        na = m["nearest_authored"]
        sub = SR._sub_of(*r["site"]["centre"])
        lines.append("%-16s %-28s %s centre %s ground y%d sub %s tier %s; %d blocks, bbox %s; nearest authored %.0f "
                     "(our column %s to data/%s); corridor box %.0f; path %.0f"
                     % (r["id"], r["name"], r["cell"], r["site"]["centre"], g(*r["site"]["centre"]), sub[0], sub[1],
                        len(s.solid) + len(s.hung), box, na[0], tuple(int(v) for v in na[1]), na[2],
                        m["corridor"][0], m["path"]))
        for k, v in s.floors.items():
            lines.append("    floor %s: %s" % (k, v if not isinstance(v, list) else "%d posts" % len(v)))
        if r.get("pokemon"):
            lines.append("    resident %s L%d anchor %s" % (r["pokemon"]["name"], r["pokemon"]["level"], list(SR.anchor(s, r))))
        for c in r.get("caches") or []:
            xyz = list(SR.spot(s, c["at"]))
            lines.append("    cache %s spot %s container %s" % (c["reward"], xyz, [xyz[0], xyz[1] - 1, xyz[2]]))
        for p in probs:
            lines.append("    PROBLEM %s" % p)
    for p in SR.check_records(doc, built):
        lines.append("PROBLEM %s" % p)
    lines.append("steps %s: %d actions; %s: %d actions" % (doc["build"]["steps"]["blocks"], len(placement_steps(doc, g)),
                                                        doc["build"]["steps"]["entities"], len(entity_steps(doc, g))))
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
    print("far_south: %d files -> %s (%d sites, build: %d commands)" % (len(written), out, len(built), n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
