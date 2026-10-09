#!/usr/bin/env python
"""rip_art.py - draw the dungeon rip's animated oval, from code, so the art is reproducible from the repo.

  python tools/rip_art.py --preview OUT.png     a contact sheet of eight frames (for a human look; writes nothing else)

The look (the owner, 2026-10-09): an upright OVAL standing in the open; a soft, puffy PINK cloud ring round a LAVENDER
band round a pale BLUE glowing centre. It was asked for "in the style of" the Cobblemon Ultra Beasts mod's wormhole.
That mod is not installed and its art was never fetched, read or copied; this is drawn from the owner's description
alone, with its own noise, its own colours and its own proportions.

How it is drawn (original; nothing here comes from any texture):

  * Polar coordinates on the frame: u, v in -1..1 across the frame, r = sqrt(u*u + v*v) (so the oval is the unit
    ellipse of a W x H frame, and a 3 x 4 block quad shows it undistorted when W:H is 3:4), theta = atan2(v, u).
  * A base disc: pale blue at the centre, lavender in the band, fading to pink at the rim, with three rotating
    spiral arms (integer arm count) and a core that pulses twice a loop.
  * A pink cloud ring over it: periodic value noise in (theta, r), three octaves, thresholded by a ring profile so
    its outer edge is lumpy ("puffy") and its inner edge melts into the band. Each octave turns a whole number of
    times per loop, some one way and some the other, so the clouds boil instead of sliding.
  * Everything is periodic in time: frame N is frame 0, so the animation loops without a seam. tests/test_rip_pack.py
    measures that on the output.

Output is straight-alpha RGBA, frames stacked top to bottom (the vanilla animated-texture layout).
"""
from __future__ import annotations

import argparse
import io
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# the palette, each an (r, g, b) of this drawing's own choosing
CORE_WHITE = (240, 250, 255)
CORE_BLUE = (190, 226, 255)       # the pale blue centre
BAND_BLUE = (170, 196, 255)       # where the blue turns
LAVENDER = (190, 164, 238)        # the band
RIM_PINK = (238, 168, 226)        # the disc's rim, under the clouds
CLOUD_LIGHT = (255, 214, 238)     # a puff's lit side
CLOUD_MID = (248, 166, 212)
CLOUD_DEEP = (222, 118, 188)      # the shaded side

# (lattice cells round the ring, lattice cells across the radius, whole turns per loop, weight, seed)
OCTAVES = ((7, 4, 1, 0.50, 11), (14, 8, -1, 0.32, 23), (28, 16, 2, 0.18, 37))
ARMS = 3                          # spiral arms on the disc; an integer, or the loop would not close


def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def _step(lo, hi, x):
    t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return _smooth(t)


def _hash(i, j, seed):
    """Integer lattice hash -> [0, 1). Pure uint32 arithmetic, so the same everywhere (no RNG stream to drift)."""
    h = (i.astype(np.uint64) * np.uint64(374761393) + j.astype(np.uint64) * np.uint64(668265263)
         + np.uint64(seed) * np.uint64(2246822519)) & np.uint64(0xFFFFFFFF)
    h = ((h ^ (h >> np.uint64(13))) * np.uint64(1274126177)) & np.uint64(0xFFFFFFFF)
    h = h ^ (h >> np.uint64(16))
    return (h & np.uint64(0xFFFFFF)).astype(np.float64) / float(0x1000000)


def _noise(theta_cells, r_cells, k, seed):
    """Value noise, periodic round the ring with period k cells (theta_cells in cells, any real)."""
    i0 = np.floor(theta_cells)
    fi = _smooth(theta_cells - i0)
    j0 = np.floor(r_cells)
    fj = _smooth(r_cells - j0)
    ia, ib = np.mod(i0, k), np.mod(i0 + 1, k)
    ja, jb = j0, j0 + 1
    v00, v10 = _hash(ia, ja, seed), _hash(ib, ja, seed)
    v01, v11 = _hash(ia, jb, seed), _hash(ib, jb, seed)
    return (v00 * (1 - fi) + v10 * fi) * (1 - fj) + (v01 * (1 - fi) + v11 * fi) * fj


def _mix(a, b, t):
    a, b = np.array(a, np.float64), np.array(b, np.float64)
    return a + (b - a) * t[..., None]


def frame(w, h, t, n):
    """One frame, t in 0..n-1 of an n-frame loop, as an h x w x 4 uint8 array (straight alpha)."""
    ph = t / float(n)                                   # 0..1 round the loop
    ys, xs = np.mgrid[0:h, 0:w]
    u = (xs + 0.5 - w / 2.0) / (w / 2.0)
    v = (ys + 0.5 - h / 2.0) / (h / 2.0)
    r = np.sqrt(u * u + v * v)
    th = np.arctan2(v, u)
    turn = (th + math.pi) / (2 * math.pi)               # 0..1 once round

    # --- the disc: blue centre, lavender band, pink rim, spiral arms turning once a loop
    arm = 0.5 + 0.5 * np.sin(2 * math.pi * (ARMS * turn + 1.6 * r - ph))
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * 2 * ph)  # two beats a loop
    col = _mix(CORE_BLUE, BAND_BLUE, _step(0.10, 0.40, r))
    col = _mix(col, LAVENDER, _step(0.28, 0.52, r))
    col = _mix(col, RIM_PINK, _step(0.66, 0.90, r))
    core = (1.0 - _step(0.0, 0.42, r)) * (0.30 + 0.30 * pulse)
    col = col + (np.array(CORE_WHITE, np.float64) - col) * core[..., None]
    lit = (0.10 * arm * _step(0.08, 0.30, r) * (1.0 - _step(0.62, 0.85, r)))
    col = col + (255.0 - col) * lit[..., None]
    a_disc = (1.0 - _step(0.80, 0.96, r)) * 0.95

    # --- the cloud ring: periodic noise thresholded by a ring profile, puffy at the outer edge
    nz = np.zeros_like(r)
    for k, kr, turns, wgt, seed in OCTAVES:
        nz += wgt * _noise(turn * k + turns * k * ph, r * kr, k, seed)
    nz = np.clip((nz - 0.2) / 0.6, 0.0, 1.0)            # roughly 0..1 with the mean near the middle
    rr = r + 0.30 * (nz - 0.5)                          # the puffs: the ring's edges ride on the noise
    inner = _step(0.58, 0.74, rr)                       # melts into the lavender band
    outer = 1.0 - _step(0.86, 0.93, rr)                 # a lumpy outer edge
    wisp = np.clip(0.55 + 1.1 * (nz - 0.35), 0.0, 1.0)  # thin places, so the ring is not one solid band
    a_cloud = inner * outer * wisp
    lightdir = np.clip(0.5 - 0.35 * v - 0.2 * u, 0.0, 1.0)      # lit from the upper left
    shade = np.clip(0.80 * nz + 0.40 * lightdir - 0.15 * (rr - 0.7), 0.0, 1.0)
    ccol = _mix(CLOUD_DEEP, CLOUD_MID, _step(0.20, 0.55, shade))
    ccol = _mix(ccol, CLOUD_LIGHT, _step(0.55, 0.90, shade))

    # --- composite the clouds over the disc, then soften the oval's rim
    a = a_cloud + a_disc * (1.0 - a_cloud)
    rgb = (ccol * a_cloud[..., None] + col * (a_disc * (1.0 - a_cloud))[..., None]) / np.maximum(a, 1e-6)[..., None]
    a = a * (1.0 - _step(0.90, 1.0, r))
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = np.clip(rgb + 0.5, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(a * 255.0 + 0.5, 0, 255).astype(np.uint8)
    # a fully clear pixel keeps a pink colour so the atlas's mipmaps never fringe the rim with black
    clear = out[..., 3] == 0
    out[clear, 0], out[clear, 1], out[clear, 2] = CLOUD_MID
    return out


def frames(w, h, n):
    return [frame(w, h, t, n) for t in range(n)]


def strip_png(w, h, n):
    """The animated texture: n frames stacked vertically, as PNG bytes."""
    arr = np.concatenate(frames(w, h, n), axis=0)
    buf = io.BytesIO()
    Image.fromarray(arr, "RGBA").save(buf, "PNG", optimize=True)
    return buf.getvalue()


def preview(w, h, n, picks, out):
    """A contact sheet: the picked frames side by side over a dark ground (as the rip's black backdrop shows them)."""
    sheet = Image.new("RGBA", (w * len(picks), h), (20, 18, 24, 255))
    for k, t in enumerate(picks):
        im = Image.fromarray(frame(w, h, t, n), "RGBA")
        sheet.alpha_composite(im, (k * w, 0))
    sheet = sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST)
    sheet.save(out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--preview", type=Path, required=True)
    p.add_argument("--size", default="96x128")
    p.add_argument("--frames", type=int, default=48)
    a = p.parse_args(argv)
    w, h = (int(x) for x in a.size.split("x"))
    picks = [round(i * a.frames / 6) for i in range(6)]
    preview(w, h, a.frames, picks, a.preview)
    print("wrote %s (%d frames of %dx%d at %s)" % (a.preview, len(picks), w, h, picks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
