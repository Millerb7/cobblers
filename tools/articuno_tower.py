#!/usr/bin/env python
"""Articuno's tower on Frostpeak's summit: the re-apply step that pastes it, and the one-off staging cleanup of the
shoulder copy it replaces.

The owner, 2026-10-02: "Paste the real Cobbleverse Articuno tower on the summit; its crown shows over the crest from
the research camp, so the camp's telescope sees what the researchers study. The shoulder copy is removed."

Everything here is read from data/adopted_legendary_sites.json `adopted_articuno_shrine`: `placement` is the summit
site, `superseded_shoulder_site.placement` the shoulder one. Ground comes from tools/ground.py (the canonical
heightmap, rounded), never from a world.

  placement_steps()   the step for tools/reapply.py, in its (kind, value) tuple shape: hold the footprint's chunks,
                      wait for them, `place template` over RCON (the command EXP-048 proved from the console), release.
                      NOT wired into tools/reapply.py: the adopted sites have no apply step yet and this is the first.
                      Re-running it re-stamps the same blocks; whether the template carries entities that a second
                      paste would double has not been read (no .nbt is read anywhere in the repository).

  the cleanup         `cobblers:articuno_cleanup/shoulder`, in its own pack written OUTSIDE build/datapacks (default
                      build/staging/cobblers_articuno_cleanup) so that tools/reapply.py's coverage check, which wants
                      every pack in build/datapacks run by a step, never sees it. STAGING ONLY: the shoulder copy was
                      pasted once by hand into the disposable staging world during EXP-048 and is in no apply step; the
                      live world never had it, and running this there would write snow over untouched mountain.
                      Per column of the shoulder box: air from ground + 1 to the old top + 1 (a snow layer can settle
                      on the tower's roof), the surface block put back at ground ONLY where the paste's bottom layer
                      replaced it (ground == the old seat y), and a snow cover on top. The surface and cover are
                      ASSUMED (data/regions.json snowy_peak: terrain SNOW below y165, frost true) and can be changed
                      with --surface / --cover after comparing with the untouched ring round the box.

  python tools/articuno_tower.py plan                      the step tuples and the in-world probes; writes nothing
  python tools/articuno_tower.py build [--out DIR] [--surface B] [--cover B|none] [--source-root R]
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
SITE_ID = "adopted_articuno_shrine"
DEFAULT_OUT = ROOT / "build" / "staging" / "cobblers_articuno_cleanup"
NS = "cobblers"
FN = "articuno_cleanup"
SURFACE = "minecraft:snow_block"
COVER = "minecraft:snow[layers=1]"
ROOF_PAD = 1            # clear this many layers above the old top: snow settles on a roof in a snowy biome
# Where the template's altar sits relative to its corner, rotation none: EXP-048 pasted the shoulder copy at corner
# (904, 151, 320) and found `lumymon:articuno_altar` at (914, 153, 331) (experiments/EXP-048-legendary-altar/README.md).
ALTAR_OFFSET = (10, 2, 11)
# vanilla decorative entities a template can carry; a fill does not remove entities
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


def box(placement, size):
    """(x0, y0, z0, x1, y1, z1), inclusive, of a paste: corner, seat y, template size, rotation none."""
    if placement["rotation"] != "none" or placement["mirror"] != "none":
        raise TowerError("rotation %r / mirror %r: this tool knows only the unrotated box"
                         % (placement["rotation"], placement["mirror"]))
    (x0, z0), y0 = placement["corner"], placement["y"]
    sx, sy, sz = size
    return x0, y0, z0, x0 + sx - 1, y0 + sy - 1, z0 + sz - 1


def summit_box(rec=None):
    rec = rec or record()
    return box(rec["placement"], rec["size"])


def shoulder_box(rec=None):
    rec = rec or record()
    old = rec.get("superseded_shoulder_site")
    if not old:
        raise TowerError("%s has no superseded_shoulder_site: nothing to clean up" % SITE_ID)
    return box(old["placement"], rec["size"])


def placement_steps(rec=None):
    """[(kind, value)] for tools/reapply.py: hold the footprint's chunks, paste, release."""
    rec = rec or record()
    x0, _y0, z0, x1, _y1, z1 = summit_box(rec)
    hold = "%d %d %d %d" % (x0, z0, x1, z1)
    command = rec["placement"]["command"].lstrip("/")
    import place_donor
    pl = rec["placement"]
    clear = place_donor.remove_item_commands((pl["corner"][0], pl["y"], pl["corner"][1]), pl["rotation"],
                                             pl.get("remove_items"))
    return ([("cmd", "forceload add " + hold), ("wait", 3), ("cmd", command)] + [("cmd", c) for c in clear]
            + [("cmd", "forceload remove " + hold)])


def _runs(values):
    """[(start index, end index, value)] for maximal runs of equal values."""
    out, start = [], 0
    for i in range(1, len(values) + 1):
        if i == len(values) or values[i] != values[start]:
            out.append((start, i - 1, values[start]))
            start = i
    return out


def cleanup_commands(g, rec=None, surface=SURFACE, cover=COVER):
    rec = rec or record()
    x0, seat, z0, x1, top, z1 = shoulder_box(rec)
    sx0, _sy0, sz0, sx1, _sy1, sz1 = summit_box(rec)
    if not (x1 < sx0 or sx1 < x0 or z1 < sz0 or sz1 < z0):
        raise TowerError("the shoulder box overlaps the summit footprint: the cleanup would erase the live tower")
    cmds = ["# Generated by tools/articuno_tower.py from data/adopted_legendary_sites.json. Re-run to rebuild; do not edit.",
            "# STAGING ONLY. Removes the Articuno tower pasted by hand at the superseded shoulder site (EXP-048),",
            "# box x%d..%d y%d..%d z%d..%d, and puts heightmap ground back. The live world never had this paste." % (
                x0, x1, seat, top, z0, z1),
            "forceload add %d %d %d %d" % (x0, z0, x1, z1)]
    for t in ENTITY_TYPES:
        cmds.append("kill @e[type=%s,x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d]" % (t, x0, seat, z0, x1 - x0, top + ROOF_PAD - seat, z1 - z0))
    grid = g.box(x0, z0, x1, z1)
    for iz in range(grid.shape[0]):
        z = z0 + iz
        row = [int(v) for v in grid[iz].tolist()]
        for a, b, gy in _runs(row):
            xa, xb = x0 + a, x0 + b
            if gy + 1 <= top + ROOF_PAD:
                cmds.append("fill %d %d %d %d %d %d minecraft:air" % (xa, gy + 1, z, xb, top + ROOF_PAD, z))
            if gy >= seat:
                # the paste's bottom layer is at the seat: where the ground reached it, the ground block was replaced
                cmds.append("fill %d %d %d %d %d %d %s" % (xa, gy, z, xb, gy, z, surface))
            if cover:
                cmds.append("fill %d %d %d %d %d %d %s" % (xa, gy + 1, z, xb, gy + 1, z, cover))
    cmds.append("forceload remove %d %d %d %d" % (x0, z0, x1, z1))
    bad = function_limits.check_lines(cmds, "%s/shoulder" % FN)
    if bad:
        raise TowerError("the cleanup has %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    return cmds


def probes(g, rec=None):
    """In-world checks for the integrating session, each an `execute if|unless block` that should succeed."""
    rec = rec or record()
    sx0, sy0, sz0 = rec["placement"]["corner"][0], rec["placement"]["y"], rec["placement"]["corner"][1]
    ox0, oy0, oz0 = shoulder_box(rec)[0], shoulder_box(rec)[1], shoulder_box(rec)[2]
    dx, dy, dz = ALTAR_OFFSET
    ax, az = ox0 + dx, oz0 + dz
    return [
        {"what": "the summit tower's altar, after the step", "check":
            "execute if block %d %d %d lumymon:articuno_altar" % (sx0 + dx, sy0 + dy, sz0 + dz)},
        {"what": "the shoulder altar gone, after the cleanup (staging)", "check":
            "execute unless block %d %d %d lumymon:articuno_altar" % (ax, oy0 + dy, az)},
        {"what": "air above the shoulder's ground at the altar column, after the cleanup", "check":
            "execute if block %d %d %d minecraft:air" % (ax, g(ax, az) + 2, az)},
    ]


def build(g, surface=SURFACE, cover=COVER):
    rec = record()
    return {"pack.mcmeta": {"pack": {"pack_format": 48, "description":
                                     "Cobblers: STAGING ONLY one-off removal of the superseded Articuno shoulder paste "
                                     "(generated by tools/articuno_tower.py)"}},
            "data/%s/function/%s/shoulder.mcfunction" % (NS, FN): cleanup_commands(g, rec, surface, cover)}


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
    ap.add_argument("--cover", default=COVER, help="the block laid on the restored ground, or 'none'")
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    g = G.Ground(a.source_root)
    cover = None if a.cover == "none" else a.cover
    if a.action == "plan":
        print(json.dumps({"steps": placement_steps(), "probes": probes(g)}, indent=1))
        return 0
    files = build(g, a.surface, cover)
    write(files, a.out)
    n = len(files["data/%s/function/%s/shoulder.mcfunction" % (NS, FN)])
    print("wrote %s (%d lines in %s:%s/shoulder)" % (a.out, n, NS, FN))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
