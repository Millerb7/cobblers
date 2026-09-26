#!/usr/bin/env python
"""Level the apex oval for the League.

Two pieces of one journey, so they share a tool and an audit:

  - the LOT: the apex oval levelled to y88 for `cobbleverse:kanto_league`, which tools/place_donor.py then stamps
    from data/placements.json. The lot is cut where the ground is high and filled where it is low, with a skirt
    so the platform meets the terrain instead of ending in a cliff.
  - the TUNNEL: from the Deep's floor, through its sheer north face, climbing to the entrance shelf. Nine trainer
    stands are marked and left unstaffed; Codex writes them.

Ground comes from the canonical heightmap, never from a world; `verify` reads a world only to check.

    python tools/rift_league_tunnel.py build  --source-root <root> [--server-dir <server>]
    python tools/rift_league_tunnel.py verify --world <stopped world copy>
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

import function_limits as FL

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "rift_league_tunnel.json"
PLACEMENTS = ROOT / "data" / "placements.json"
REGIONS = ROOT / "data" / "rift_regions.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_league_tunnel"
PLAN = ROOT / "derived" / "rift_league_tunnel" / "plan.json"
TILE = 64
PART = 3500

WORLD_READS = {"verify", "main"}


class LeagueError(Exception):
    pass


def h3(x, y, z, salt):
    a = (np.asarray(x, np.int64) * 73856093) ^ (np.asarray(y, np.int64) * 19349663) \
        ^ (np.asarray(z, np.int64) * 83492791) ^ np.int64(salt * 2654435761)
    a &= np.int64(0x7FFFFFFF)
    a = (a ^ (a >> 15)) * np.int64(2246822519)
    a &= np.int64(0x7FFFFFFF)
    a = (a ^ (a >> 13)) * np.int64(3266489917)
    return a & np.int64(0x7FFFFFFF)


def unit(x, y, z, salt):
    return h3(x, y, z, salt) / float(0x7FFFFFFF)


def installed_blocks(server_dir):
    import glob
    import re
    import zipfile
    if not server_dir:
        return None
    import runtime_guard
    runtime_guard.require_lock("read the server's mod jars")
    mods = runtime_guard.check(Path(server_dir) / "mods", "read the mod jars in")
    ids = set()
    for jar in glob.glob(str(mods / "*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except (zipfile.BadZipFile, OSError):  # not a readable jar
            continue
        for n in z.namelist():
            m = re.match(r"assets/([^/]+)/blockstates/([^/]+)\.json$", n)
            if m:
                ids.add("%s:%s" % m.groups())
    return ids


def pick(block, fallback, have):
    return block if block.startswith("minecraft:") or have is None or block in have else fallback


def town_owned(lot, doc):
    """[(anchor id, rect)] the lot's skirt leaves alone: the anchors of `leave_to_the_town` (data/placements.json), which
    the town step (R8) lays and the town audit checks. Fails when the spec names anchors the placements do not have."""
    own = lot.get("leave_to_the_town")
    if not own:
        return []
    plan = ((doc["settlements"].get(own["settlement"]) or {}).get("plan")) or {}
    roles = set(own.get("roles") or [])
    out = [(a["id"], a["rect"]) for a in plan.get("anchors") or [] if a.get("role") in roles and a.get("rect")]
    if not out:
        raise LeagueError("leave_to_the_town names %s anchors of %s, and data/placements.json has none"
                          % (sorted(roles), own["settlement"]))
    return out


def donor_volume(lot, doc):
    """The inclusive box ((x0, y0, z0), (x1, y1, z1)) the lot's donor is stamped over, from its placement record."""
    import place_donor
    rec = next((q for q in doc["placements"] if q.get("id") == lot.get("donor")), None)
    if rec is None:
        raise LeagueError("the lot's donor %r is not in data/placements.json" % lot.get("donor"))
    return place_donor.box(rec)


def build(source_root, server_dir=None):
    import ground as G
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    doc = json.loads(PLACEMENTS.read_text(encoding="utf-8"))
    have = installed_blocks(server_dir)
    g = G.load(source_root)
    lines, checks, counts = [], [], {}

    def count(k, v=1):
        counts[k] = counts.get(k, 0) + v

    # ---------------------------------------------------------------- the lot
    lot = spec["lot"]
    x0, z0, x1, z1 = lot["box"]
    Y = lot["y"]
    fill_b = pick(lot["fill"], lot["fill_fallback"], have)
    top_b = pick(lot["surface"], lot["surface_fallback"], have)
    skirt = lot["skirt"]
    # the town's cells inside the skirt, and the donor's volume (it is stamped whole over the lot, after it)
    towns = town_owned(lot, doc)
    (dx0, dy0, dz0), (dx1, dy1, dz1) = donor_volume(lot, doc)
    H = g.box(x0 - skirt, z0 - skirt, x1 + skirt, z1 + skirt)
    cut = fill = 0
    for iz in range(H.shape[0]):
        for ix in range(H.shape[1]):
            x, z = x0 - skirt + ix, z0 - skirt + iz
            inside = x0 <= x <= x1 and z0 <= z <= z1
            if any(r[0] <= x <= r[2] and r[1] <= z <= r[3] for _, r in towns):
                count("skirt columns left to the town (%s)" % ", ".join(a for a, _ in towns))
                continue
            gy = int(H[iz, ix])
            if inside:
                want = Y
            else:
                # the skirt: ease from the platform out to the ground over `skirt` blocks
                d = max(x0 - x, x - x1, z0 - z, z - z1, 0)
                f = min(1.0, d / float(skirt))
                want = int(round(Y * (1 - f) + gy * f))
            if want < gy:
                lines.append("fill %d %d %d %d %d %d minecraft:air" % (x, want + 1, z, x, gy + 4, z))
                cut += gy - want
            if want > gy:
                lines.append("fill %d %d %d %d %d %d %s" % (x, gy + 1, z, x, want, z, fill_b))
                fill += want - gy
            lines.append("setblock %d %d %d %s" % (x, want, z, top_b))
            if inside and unit(x, want, z, 81) < 0.004:
                checks.append((x, want, z, [top_b], "lot surface"))
            # air only where the lot cut, and not inside the donor's volume: R9 stamps the building there whole, so
            # a sample inside it read the building's floor as a mismatch (EXP-026 run 4: 20 of 48, e.g. obsidian at
            # (3690, 89, 2390)). Sampled over the whole lot and skirt, so the skirt's cuts are checked too.
            in_donor = dx0 <= x <= dx1 and dy0 <= want + 1 <= dy1 and dz0 <= z <= dz1
            if want < gy and not in_donor and unit(x, want, z, 82) < 0.02:
                checks.append((x, want + 1, z, ["minecraft:air"], "lot clear"))
    count("lot columns", (x1 - x0 + 1) * (z1 - z0 + 1))
    count("blocks cut for the lot", cut)
    count("blocks filled for the lot", fill)

    # The tunnel used to be built here as a switchback road. It is Victory Road now, and it is a labyrinth:
    # tools/victory_road.py owns it. Both were built once and overlapped, which the audit caught as the
    # road's corridors overwriting this tool's stands and lights (2026-09-23).

    return {"lines": lines, "checks": checks, "counts": counts,
            "lot": lot["box"], "lot_y": Y, "skirt": skirt,
            "left_to_the_town": [[a, r] for a, r in towns],
            "donor_volume": [[dx0, dy0, dz0], [dx1, dy1, dz1]]}, spec


def write(plan):
    import shutil
    if OUT.exists():
        shutil.rmtree(OUT)
    fn = OUT / "data" / "cobblers" / "function" / "league_tunnel"
    fn.mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps(
        {"pack": {"pack_format": 48, "description": "Cobblers: the League's lot and Victory Road's tunnel"}},
        indent=2) + "\n", encoding="utf-8")
    tiles = {}
    for ln in plan["lines"]:
        t = ln.split()
        tiles.setdefault((int(t[1]) // TILE, int(t[3]) // TILE), []).append(ln)
    order = []
    for t in sorted(tiles):
        body = tiles[t]
        for k in range(0, len(body), PART):
            name = "lt_%d_%d%s" % (t[0], t[1], "" if k == 0 else "_%d" % (k // PART + 1))
            out = FL.ensure_loaded(["# Generated by tools/rift_league_tunnel.py: tile %d %d" % t] + body[k:k + PART])
            probs = FL.check_lines(out, name)
            if probs:
                raise LeagueError("function %s would be refused: %s" % (name, probs[:3]))
            (fn / (name + ".mcfunction")).write_text("\n".join(out) + "\n", encoding="utf-8")
            order.append(name)
    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps({k: v for k, v in plan.items() if k != "lines"}), encoding="utf-8")
    return order


def verify(world):
    import build_audit
    import runtime_guard
    runtime_guard.check(world, "read")
    if not PLAN.is_file():
        print("FAIL: no derived/rift_league_tunnel/plan.json: run the build first")
        return 1
    p = json.loads(PLAN.read_text(encoding="utf-8"))
    kinds = {c[4] for c in p["checks"]}
    need = {"lot surface", "lot clear"}
    if not need <= kinds:
        print("FAIL: the plan checks %s, missing %s" % (sorted(kinds), sorted(need - kinds)))
        return 1
    W = build_audit.World(world)
    by, bad = {}, {}
    for x, y, z, allowed, what in p["checks"]:
        got = W.block(x, y, z)
        ok = got in allowed
        by.setdefault(what, [0, 0])[0 if ok else 1] += 1
        if not ok:
            bad.setdefault(what, []).append((x, y, z, got))
    for k in sorted(by):
        good, wrong = by[k]
        print("%-16s %7d of %7d as planned%s" % (k, good, good + wrong, ("   e.g. %s" % bad[k][:2]) if wrong else ""))
    total = sum(b for _, b in by.values())
    print("the League's lot and the tunnel: %s" % ("clean" if total == 0 else "%d MISMATCHES" % total))
    return 0 if total == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build", "verify"))
    ap.add_argument("--source-root")
    ap.add_argument("--server-dir")
    ap.add_argument("--world")
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        if not a.world:
            ap.error("verify needs --world")
        return verify(a.world)
    plan, spec = build(a.source_root, a.server_dir)
    order = write(plan)
    for k, v in sorted(plan["counts"].items()):
        print("  %-40s %9d" % (k, v))
    print("the League's lot and the tunnel: %d functions, %d commands" % (len(order), len(plan["lines"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
