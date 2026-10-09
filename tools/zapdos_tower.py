#!/usr/bin/env python
"""The one-off STAGING cleanup of the Zapdos tower at its superseded north-west coast site.

The owner, 2026-10-03: "move zapdos tower to mooshroom island i think or its own off in the sea". The tower moved to
the Fungal Isle's east coast (data/placements.json legendary_zapdos_tower, placed by tools/place_donor.py like every
other pack donor). The 2026-10-02 donor pass had already pasted it at the old site in the disposable staging world,
and nothing removes a paste: this pack does, once.

Everything here is read from data/adopted_legendary_sites.json `adopted_zapdos_tower`: `superseded_coast_site.placement`
is the old box, and the live seat is resolved through tools/adopted_sites.py (the placements record). Ground comes from
tools/ground.py (the canonical heightmap, rounded), never from a world. This file follows tools/articuno_tower.py's
cleanup of the Articuno shoulder copy.

  the cleanup   `cobblers:zapdos_cleanup/coast`, in its own pack written OUTSIDE build/datapacks (default
                build/staging/cobblers_zapdos_cleanup) so that tools/reapply.py's coverage check, which wants every pack
                in build/datapacks run by a step, never sees it, and no fresh build's apply runs it. STAGING ONLY: the
                live world never had the coast paste, and running this there would rewrite untouched cliff.
                Per column of the old box x562..592, z2614..2642, y74..139, with g the heightmap ground:
                  - air from max(g + 1, 74) to y139: everything the paste wrote above the ground (the paste never wrote
                    below its bottom layer y74, so nothing under it is touched);
                  - where g >= 74 (the paste's bottom layer took the ground's place): SUBSURFACE from y74 to g - 1 and
                    SURFACE at g.
                SURFACE and SUBSURFACE are ASSUMED (data/regions.json paint_presets.coast_scrub: terrain GRASS, with
                15% SAND patches, so grass_block over dirt); compare with the untouched ring round the box in staging
                and re-run with --surface / --subsurface if it is sand or stone there.
                Entities a template can carry (item frames, armour stands, paintings, dropped items) are killed in the
                box by tools/chunk_look.py's kill sweep (`coast_entities`, N155: every 20 ticks from tick 40 to 300,
                because a chunk's saved entities arrive after the forceload), which also releases the box: a fill
                does not remove entities. Wait 16 s before reading #zapdos_cleanup.

  python tools/zapdos_tower.py plan                     the box, the per-column rule's counts and the in-world probes
  python tools/zapdos_tower.py build [--out DIR] [--surface B] [--subsurface B] [--source-root R]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

SITES = ROOT / "data" / "adopted_legendary_sites.json"
SITE_ID = "adopted_zapdos_tower"
DEFAULT_OUT = ROOT / "build" / "staging" / "cobblers_zapdos_cleanup"
NS = "cobblers"
FN = "zapdos_cleanup"
SURFACE = "minecraft:grass_block"
SUBSURFACE = "minecraft:dirt"
# Where the template's altar sits relative to its corner, rotation none: lumymon:zapdos_altar at template [14,2,14],
# read 2026-10-02 from COBBLEVERSE-DP-v31.zip legendary/zapdos.nbt (adopted_zapdos_tower.carries_into_the_world).
ALTAR_OFFSET = (14, 2, 14)
ENTITY_TYPES = ("minecraft:item_frame", "minecraft:glow_item_frame", "minecraft:armor_stand", "minecraft:painting",
                "minecraft:item")
WORLD_READS: set = set()


class TowerError(SystemExit):
    pass


def record():
    doc = json.loads(SITES.read_text(encoding="utf-8"))
    rec = next((s for s in doc["sites"] if s.get("id") == SITE_ID), None)
    if rec is None:
        raise TowerError("data/adopted_legendary_sites.json has no %s" % SITE_ID)
    return rec


def _box(corner, y, rotation, mirror, size):
    if rotation != "none" or mirror != "none":
        raise TowerError("rotation %r / mirror %r: this tool knows only the unrotated box" % (rotation, mirror))
    (x0, z0), (sx, sy, sz) = corner, size
    return x0, y, z0, x0 + sx - 1, y + sy - 1, z0 + sz - 1


def old_box(rec=None):
    """(x0, y0, z0, x1, y1, z1), inclusive: the superseded coast paste."""
    rec = rec or record()
    old = rec.get("superseded_coast_site")
    if not old:
        raise TowerError("%s has no superseded_coast_site: nothing to clean up" % SITE_ID)
    p = old["placement"]
    return _box(p["corner"], p["y"], p.get("rotation", "none"), p.get("mirror", "none"), rec["size"])


def live_box(rec=None):
    """The tower's scheduled seat, through tools/adopted_sites.py (data/placements.json legendary_zapdos_tower)."""
    import adopted_sites
    rec = rec or record()
    w = adopted_sites.where(rec)
    return _box(w["corner"], w["y"], w["rotation"], w["mirror"], w["size"])


def _runs(values):
    """[(start index, end index, value)] for maximal runs of equal values."""
    out, start = [], 0
    for i in range(1, len(values) + 1):
        if i == len(values) or values[i] != values[start]:
            out.append((start, i - 1, values[start]))
            start = i
    return out


def cleanup_commands(g, rec=None, surface=SURFACE, subsurface=SUBSURFACE):
    rec = rec or record()
    x0, seat, z0, x1, top, z1 = old_box(rec)
    lx0, _ly0, lz0, lx1, _ly1, lz1 = live_box(rec)
    if not (x1 < lx0 or lx1 < x0 or z1 < lz0 or lz1 < z0):
        raise TowerError("the old box overlaps the live tower's footprint: the cleanup would erase the live tower")
    cmds = ["# Generated by tools/zapdos_tower.py from data/adopted_legendary_sites.json. Re-run to rebuild; do not edit.",
            "# STAGING ONLY. Removes the Zapdos tower pasted at the superseded north-west coast site (2026-10-02 donor pass),",
            "# box x%d..%d y%d..%d z%d..%d, and puts heightmap ground back. The live world never had this paste." % (
                x0, x1, seat, top, z0, z1),
            "forceload add %d %d %d %d" % (x0, z0, x1, z1)]
    grid = g.box(x0, z0, x1, z1)
    for iz in range(grid.shape[0]):
        z = z0 + iz
        row = [int(v) for v in grid[iz].tolist()]
        for a, b, gy in _runs(row):
            xa, xb = x0 + a, x0 + b
            lo = max(gy + 1, seat)
            if lo <= top:
                cmds.append("fill %d %d %d %d %d %d minecraft:air" % (xa, lo, z, xb, top, z))
            if gy >= seat:
                if gy - 1 >= seat:
                    cmds.append("fill %d %d %d %d %d %d %s" % (xa, seat, z, xb, gy - 1, z, subsurface))
                cmds.append("fill %d %d %d %d %d %d %s" % (xa, gy, z, xb, gy, z, surface))
    # the entities go through the kill sweep, which holds this box and releases it when it ends: a forceload is per
    # chunk, not counted, so this function must not release it under the sweep (N155)
    cmds.append("function %s" % ENTITIES_FN)
    bad = function_limits.check_lines(cmds, "%s/coast" % FN)
    if bad:
        raise TowerError("the cleanup has %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    return cmds


ENTITIES_FN = "%s:%s/coast_entities" % (NS, FN)
ENTITIES_HOLDER = "zapdos_cleanup"        # scoreboard players get #zapdos_cleanup cobblers_chunk_look: what went


def cleanup_entity_functions(rec=None):
    """{function id: lines}: the entities a template can carry, killed in the old box by tools/chunk_look.py's kill
    sweep (N155): every 20 ticks from tick 40 to 300, since the old one-tick kill came before a chunk's saved entities
    had arrived (tools/articuno_tower.py's shape)."""
    import chunk_look as CL
    rec = rec or record()
    x0, seat, z0, x1, top, z1 = old_box(rec)
    kills = ["type=%s,x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (t, x0, seat, z0, x1 - x0, top - seat, z1 - z0)
             for t in ENTITY_TYPES]
    return CL.sweep(ENTITIES_FN, (x0, z0, x1, z1), kills, ENTITIES_HOLDER, note="tools/zapdos_tower.py, STAGING ONLY")


def summary(g, rec=None):
    """Counts of what the per-column rule does, from the heightmap: for the plan and the report."""
    rec = rec or record()
    x0, seat, z0, x1, top, z1 = old_box(rec)
    cols = [int(v) for v in g.box(x0, z0, x1, z1).ravel().tolist()]
    restored = [gy for gy in cols if gy >= seat]
    return {"box": [x0, seat, z0, x1, top, z1], "columns": len(cols),
            "air_blocks": sum(top - max(gy + 1, seat) + 1 for gy in cols if max(gy + 1, seat) <= top),
            "ground_restored_columns": len(restored),
            "surface_blocks": len(restored), "subsurface_blocks": sum(gy - seat for gy in restored),
            "untouched_below_seat_columns": len(cols) - len(restored)}


def probes(g, rec=None):
    """In-world checks for the integrating session, each an `execute if|unless block` that should succeed."""
    rec = rec or record()
    lx0, ly0, lz0 = live_box(rec)[:3]
    ox0, oy0, oz0 = old_box(rec)[:3]
    dx, dy, dz = ALTAR_OFFSET
    ax, az = ox0 + dx, oz0 + dz
    return [
        {"what": "the Fungal Isle tower's altar, after the donor step", "check":
            "execute if block %d %d %d lumymon:zapdos_altar" % (lx0 + dx, ly0 + dy, lz0 + dz)},
        {"what": "the coast altar gone, after the cleanup (staging)", "check":
            "execute unless block %d %d %d lumymon:zapdos_altar" % (ax, oy0 + dy, az)},
        {"what": "air above the coast's ground at the altar column, after the cleanup", "check":
            "execute if block %d %d %d minecraft:air" % (ax, max(g(ax, az) + 1, oy0), az)},
    ]


def build(g, surface=SURFACE, subsurface=SUBSURFACE):
    import chunk_look as CL
    rec = record()
    out = {"pack.mcmeta": {"pack": {"pack_format": 48, "description":
                                    "Cobblers: STAGING ONLY one-off removal of the superseded Zapdos coast paste "
                                    "(generated by tools/zapdos_tower.py)"}},
           "data/%s/function/%s/coast.mcfunction" % (NS, FN): cleanup_commands(g, rec, surface, subsurface)}
    out.update(CL.files(cleanup_entity_functions(rec)))
    return out


def write(files, out):
    out = Path(out)
    if out.resolve().parent == (ROOT / "build" / "datapacks").resolve():
        raise TowerError("refusing to write into build/datapacks: tools/reapply.py would demand a step for a "
                         "staging-only cleanup")
    if out.exists():
        shutil.rmtree(out)
    for rel, content in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(content) + "\n" if isinstance(content, list) else json.dumps(content, indent=2) + "\n"
        f.write_text(body, encoding="utf-8", newline="\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("build", "plan"))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--surface", default=SURFACE)
    ap.add_argument("--subsurface", default=SUBSURFACE)
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    g = G.Ground(a.source_root)
    if a.action == "plan":
        print(json.dumps({"cleanup": summary(g), "probes": probes(g)}, indent=1))
        return 0
    files = build(g, a.surface, a.subsurface)
    write(files, a.out)
    n = len(files["data/%s/function/%s/coast.mcfunction" % (NS, FN)])
    print("wrote %s (%d lines in %s:%s/coast)" % (a.out, n, NS, FN))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
