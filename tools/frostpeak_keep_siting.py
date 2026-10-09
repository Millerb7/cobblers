#!/usr/bin/env python
"""Where on Frostpeak Strand can a castle be SEEN from Highwire? The measurement that sited Wardenhold.

The owner, 2026-10-09: "Measure the sightline before siting it -- Distant Horizons renders far, but terrain between them
may block it." This tool does that from the canonical heightmap (tools/ground.py rounding), never a world.

THE MODEL. Minecraft is flat: no curvature and no refraction, so a point is visible from an eye when the straight
segment between them clears the top of every ground column in between (a ground column's top surface is round(h) + 1).
Terrain only: no trees, no fog, no castle self-occlusion (a castle does not hide its own outline against the sky).
The castle raises the ground under its base rectangle to the courtyard floor (pad), so a site is evaluated with that
raised ground. The silhouette is every solid voxel of tools/frostpeak_keep.py building() above the courtyard floor,
projected onto the plane across the line of sight (1-block bins); a (bin, y) cell is visible when some voxel in it has a
clear segment to the eye. The fraction is visible cells over all cells.

OBSERVERS (each eye 1.62 above its feet):
  streets   ten points on Highwire's shelf (data/towns.json gym3_town footprint x 1660-1715, z 1382-1437, ground y174):
            the belvedere at the array path's lip (1700, 1382) and the nine of a 3 x 3 grid x 1664/1688/1712, z 1386/1410/1434
  gym roof  three points x 1740, z 1396/1410/1424 on the Relay Works' roofline: data/placements.json gym3_gym_building
            stands from y173, size 17 high, so its roof surface is y190 (a viewing height; the roof is not a walkway)

DISTANT HORIZONS. modpack/config/DistantHorizons.toml lodChunkRenderDistanceRadius = 256 chunks = 4,096 blocks, the figure
docs/world-building/SIGHTLINES.md also quotes; the sites here are 750-820 blocks from Highwire. That is the configured
radius, "a best effort number" in DH's own comment; what a thin spire looks like as an LOD at 800 blocks is NOT measured.

  python tools/frostpeak_keep_siting.py scan  Z0 Z1 X0 X1 STEP    candidates whose base rectangle lies in the Strand
  python tools/frostpeak_keep_siting.py site  X Z                  the chosen site's table: every observer, every feature
  python tools/frostpeak_keep_siting.py alternatives               the comparison table of other Strand sites
  python tools/frostpeak_keep_siting.py coverage [STEP]            how tall a tower must be, per land cell, to show from Highwire
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import frostpeak_keep as K  # noqa: E402  (the building's geometry; the siting scan IS about that shape)
import ground as G  # noqa: E402

EYE = 1.62
STREETS = {"belvedere (1700,1382)": (1700, 175 + EYE, 1382)}
for _x in (1664, 1688, 1712):
    for _z in (1386, 1410, 1434):
        STREETS["street (%d,%d)" % (_x, _z)] = (_x, 175 + EYE, _z)
GYM = {"gym roof (1740,%d)" % z: (1740, 190 + EYE, z) for z in (1396, 1410, 1424)}


class Siting:
    def __init__(self, g=None, doc=None):
        self.g = g or G.Ground()
        self.doc = doc or K.load()
        self.H0 = np.round(self.g.heights).astype(float) + 1.0          # the top surface of each ground column
        self.ox, self.oz = self.g.ox, self.g.oz
        V, self.notes = K.building(self.doc)
        self.solid = np.array([k for k, v in V.b.items() if v != K.AIR and k[1] >= 1], int)     # (u, ry, v)
        self.cols = np.unique(self.solid[:, [0, 2]], axis=0)
        self.poly = K.strand_polygon()

    def rect(self, cx, cz):
        d = self.doc["dims"]
        return cx - d["base_hu"], cz - d["base_hv"], cx + d["base_hu"], cz + d["base_hv"]

    def rect_in_polygon(self, cx, cz):
        x0, z0, x1, z1 = self.rect(cx, cz)
        pts = [(x, z) for x in range(x0, x1 + 1, 2) for z in (z0, z1)] + [(x, z) for z in range(z0, z1 + 1, 2) for x in (x0, x1)]
        return all(K.in_polygon(x, z, self.poly) for x, z in pts)

    def raised(self, cx, cz):
        """(pad, heights with the base rectangle raised to the courtyard floor)."""
        x0, z0, x1, z1 = self.rect(cx, cz)
        blk = self.H0[z0 - self.oz:z1 + 1 - self.oz, x0 - self.ox:x1 + 1 - self.ox]
        pad = int(blk.max() - 1)
        H = self.H0.copy()
        H[z0 - self.oz:z1 + 1 - self.oz, x0 - self.ox:x1 + 1 - self.ox] = np.maximum(blk, pad + 1)
        return pad, H

    def min_visible_y(self, H, eye, X, Z):
        """For each column, the lowest y a segment from the eye to that column clears every ground column in between."""
        x0, y0, z0 = eye
        D = np.hypot(X - x0, Z - z0)
        n = int(D.max())
        t = np.arange(1, n)[None, :] / D[:, None]
        ok = t < 1.0
        tt = np.minimum(t, 1.0)
        xs = np.rint(x0 + (X - x0)[:, None] * tt).astype(int) - self.ox
        zs = np.rint(z0 + (Z - z0)[:, None] * tt).astype(int) - self.oz
        slope = np.where(ok, (H[zs, xs] - y0) / (t * D[:, None]), -9.0)
        return y0 + D * slope.max(axis=1)

    def silhouette(self, cx, cz, eye, H, pad, sub=2):
        sel = (self.cols[:, 0] % sub == 0) & (self.cols[:, 1] % sub == 0)
        c = self.cols[sel]
        X, Z = cx + c[:, 0].astype(float), cz + c[:, 1].astype(float)
        mv = self.min_visible_y(H, eye, X, Z)
        dx, dz = cx - eye[0], cz - eye[2]
        dn = np.hypot(dx, dz)
        px, pz = -dz / dn, dx / dn
        lat = np.rint((X - cx) * px + (Z - cz) * pz).astype(int)
        m = (self.solid[:, 0] % sub == 0) & (self.solid[:, 2] % sub == 0)
        sv = self.solid[m]
        idx = {(a, b): i for i, (a, b) in enumerate(map(tuple, c))}
        ci = np.array([idx[(a, b)] for a, b in sv[:, [0, 2]]])
        y = pad + sv[:, 1]
        vis = (y + 0.5) >= mv[ci]
        allc = set(zip(lat[ci].tolist(), y.tolist()))
        visc = set(zip(lat[ci][vis].tolist(), y[vis].tolist()))
        return len(visc) / len(allc)

    def fractions(self, cx, cz):
        pad, H = self.raised(cx, cz)
        st = [self.silhouette(cx, cz, e, H, pad) for e in STREETS.values()]
        gy = [self.silhouette(cx, cz, e, H, pad) for e in GYM.values()]
        return pad, st, gy

    def features(self, cx, cz):
        """{observer: {feature: blocks of the feature visible above its lowest visible y}} (negative: hidden by that much)."""
        pad, H = self.raised(cx, cz)
        d = self.doc["dims"]
        kc = d["keep_cv"]
        feat = {"spire top (ry %d)" % self.notes["spire_top_ry"]: (0, kc, pad + self.notes["spire_top_ry"]),
                "beacon chamber floor (ry %d)" % d["spire_floor"]: (0, kc, pad + d["spire_floor"] + 1),
                "keep roof (ry %d)" % d["keep_roof"]: (0, kc, pad + d["keep_roof"]),
                "keep turret tip (ry %d)" % self.notes["turret_tip_ry"]: (d["keep_half"] - d["turret_half"], kc + d["keep_half"] - d["turret_half"], pad + self.notes["turret_tip_ry"]),
                "corner tower cone tip (ry %d)" % self.notes["corner_tip_ry"]: (d["wall_hu"] - 1, d["wall_hv"] - 1, pad + self.notes["corner_tip_ry"]),
                "south wall top (ry 13)": (0, d["wall_hv"], pad + 13)}
        out = {}
        for name, eye in list(STREETS.items()) + list(GYM.items()):
            row = {}
            for fn, (u, v, y) in feat.items():
                mv = self.min_visible_y(H, eye, np.array([cx + u], float), np.array([cz + v], float))[0]
                row[fn] = y - mv
            out[name] = (float(np.hypot(cx - eye[0], cz - eye[2])), row)
        return pad, out


def cmd_scan(s, a):
    z0, z1, x0, x1, step = a
    rows = []
    for cz in range(z0, z1 + 1, step):
        for cx in range(x0, x1 + 1, step):
            if not s.rect_in_polygon(cx, cz):
                continue
            pad, st, gy = s.fractions(cx, cz)
            rows.append((sum(st) / len(st), min(st), sum(gy) / len(gy), cx, cz, pad))
    rows.sort(reverse=True)
    print("%d candidates whose base rectangle lies wholly in the Strand's polygon" % len(rows))
    for r in rows[:12]:
        print("street mean %.2f min %.2f | gym roof mean %.2f | centre (%d, %d) pad y%d" % r)


def cmd_site(s, a):
    cx, cz = a
    pad, out = s.features(cx, cz)
    print("site (%d, %d) pad y%d; base rectangle in the Strand polygon: %s" % (cx, cz, pad, s.rect_in_polygon(cx, cz)))
    print("blocks of each feature visible above the lowest visible height at its column (negative = hidden by that much):")
    for name, (dist, row) in out.items():
        print("  %-24s %4.0f away  " % (name, dist) + "  ".join("%s %+.0f" % (k.split(" (")[0], v) for k, v in row.items()))
    _, st, gy = s.fractions(cx, cz)
    print("silhouette fraction visible: streets mean %.2f (min %.2f, max %.2f); gym roof mean %.2f (min %.2f, max %.2f)"
          % (sum(st) / len(st), min(st), max(st), sum(gy) / len(gy), min(gy), max(gy)))


def cmd_coverage(s, a):
    """How tall must a tower be, on each land cell of the Strand, to show above the terrain from Highwire's streets?"""
    step = a[0] if a else 32
    cells = [(x, z) for z in range(0, 760, step) for x in range(900, 2960, step)
             if K.in_polygon(x, z, s.poly) and s.H0[z - s.oz, x - s.ox] - 1 > 70]
    X, Z = np.array([c[0] for c in cells], float), np.array([c[1] for c in cells], float)
    ground_top = np.array([s.H0[z - s.oz, x - s.ox] for x, z in cells])
    need = np.full(len(cells), 1e9)
    for eye in list(STREETS.values()) + list(GYM.values()):
        need = np.minimum(need, s.min_visible_y(s.H0, eye, X, Z) - ground_top)
    print("%d land cells (ground over y70) of frostpeak_strand at %d-block spacing; the least height above the ground at which a point shows from ANY "
          "street or roofline observer:" % (len(cells), step))
    for h in (0, 10, 20, 40, 70, 100):
        n = int((need <= h).sum())
        print("  a point %3d blocks above the ground shows on %3d cells (%.0f%%)" % (h, n, 100.0 * n / len(cells)))
    order = np.argsort(need)[:6]
    print("  the six easiest cells (x, z, height needed): " + "; ".join("(%d,%d) %+.0f" % (cells[i][0], cells[i][1], need[i]) for i in order))


ALTERNATIVES = [("A  the chosen lip (Wardenhold)", (1548, 636)), ("B  east of the lip, same shelf", (1590, 624)),
                ("C  west end of the lip", (1340, 628)), ("D  mid Strand, south of the heart", (1330, 330)),
                ("E  the heart (data/encounter_design.json)", (1296, 208)), ("F  the north-west Strand", (1300, 120)),
                ("G  the east arm", (2300, 470)), ("H  the far east arm", (2700, 560))]


def cmd_alternatives(s, a):
    print("%-40s %-12s %-6s %-14s %s" % ("site", "centre", "pad", "base in polygon", "street mean/max, gym mean/max"))
    for name, (cx, cz) in ALTERNATIVES:
        try:
            pad, st, gy = s.fractions(cx, cz)
        except Exception as e:                       # a site whose rectangle leaves the heightmap
            print("%-40s (%d,%d) unavailable: %s" % (name, cx, cz, str(e)[:40]))
            continue
        print("%-40s %-12s y%-5d %-14s %.2f/%.2f, %.2f/%.2f" % (name, "(%d,%d)" % (cx, cz), pad, s.rect_in_polygon(cx, cz),
                                                             sum(st) / len(st), max(st), sum(gy) / len(gy), max(gy)))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("scan", "site", "alternatives", "coverage"):
        print(__doc__)
        return 2
    s = Siting()
    {"scan": cmd_scan, "site": cmd_site, "alternatives": cmd_alternatives, "coverage": cmd_coverage}[argv[0]](s, [int(v) for v in argv[1:]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
