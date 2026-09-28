"""tools/open_water.py: the open sea by distance from land, on the canonical heightmap.

Written by the test author, not by the session that wrote the tool (commits 476c4e5..5bcecec). Moved here from
tests/test_surface_exhaustion.py when the owner changed the swim rule (2262aa3): the cobblers_blackout pack no longer
reads these bands (data/blackout.json "surface" "superseded"), so nothing here says anything about swim fatigue. The
tool is kept as an analysis tool, and these tests keep it honest to its own docstring.

Independent sources: tools/open_water.py's docstring rule (a 16-block cell is land if any column in it is at or above sea
level 62; the sea is the below-sea cells connected to the world border, so an inland basin is not sea; shallows, open
and deep by Chebyshev distance from land, 96 and 256 blocks by default) with the distances recomputed here by brute
force; the owner's places: Lake Tilpey at (5964, 4135) is a lake, and the far west margin (-900, 4000) is 1,024 blocks
of open ocean outside the heightmap (docs/STATE.md 'World facts').

The band thresholds, as the tool applies them: a sea cell whose Chebyshev distance d (in cells) from the nearest land
cell is at most shallow_blocks/16 is shallows; at most deep_blocks/16 is open; beyond is deep.

The real-heightmap test needs the canonical heightmap (outside the repository): without it it SKIPS, and a skip is not
a pass.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import open_water as OW  # noqa: E402

N_CELLS = (OW.WORLD_MAX - OW.WORLD_MIN + 1) // OW.CELL        # 640
SHALLOW, DEEP = 96, 256                                        # the docstring's defaults


def cell_of(x, z):
    return (z - OW.WORLD_MIN) // OW.CELL, (x - OW.WORLD_MIN) // OW.CELL


class FakeGround:
    """What open_water reads from tools/ground.py: the heights (z, x) and their origin."""

    def __init__(self, heights, ox=0, oz=0):
        self.heights, self.ox, self.oz = heights, ox, oz


def _synthetic():
    """A 1024-block heightmap at the origin, all under sea level, with: an island (x, z 512..575); a walled basin
    (cells 70..83 square, walls land, inside at y 50) with no way out; a second walled basin (cells 104..117) whose west
    wall has a one-cell gap at cell row 110."""
    h = np.full((1024, 1024), 40.0)
    h[512:576, 512:576] = 70

    def basin(c0, c1, gap=None):
        b0, b1 = c0 * 16 + OW.WORLD_MIN, (c1 + 1) * 16 + OW.WORLD_MIN
        h[b0:b1, b0:b1] = 70
        h[b0 + 16:b1 - 16, b0 + 16:b1 - 16] = 50
        if gap is not None:
            g = gap * 16 + OW.WORLD_MIN
            h[g:g + 16, b0:b0 + 16] = 40

    basin(70, 83)
    basin(104, 117, gap=110)
    return FakeGround(h)


SYN = _synthetic()


@pytest.fixture(scope="module")
def syn_cells():
    return OW.cells(SYN)


# Without it a lake (a basin under sea level, ringed by land) is treated as open sea, or the flood fill stops at the
# first wall and misses a basin the sea reaches through a gap.
def test_an_enclosed_basin_below_sea_level_is_not_sea_and_one_open_to_the_sea_is(syn_cells):
    land, sea = syn_cells
    assert land.shape == sea.shape == (N_CELLS, N_CELLS)
    assert land[cell_of(520, 520)] and not sea[cell_of(520, 520)]
    closed = (76, 76)                                   # inside the closed basin
    assert not land[closed] and not sea[closed], "an enclosed basin is not sea"
    opened = (110, 110)                                 # inside the basin whose wall has a gap
    assert not land[opened] and sea[opened], "a basin the sea reaches is sea"
    assert sea[0, 0] and sea[N_CELLS - 1, N_CELLS - 1], "the margin outside the heightmap is sea"
    assert not (land & sea).any()


def _chebyshev_from(land):
    """Brute-force Chebyshev distance (in cells) of every cell from the nearest land cell."""
    zz, xx = np.indices(land.shape)
    d = np.full(land.shape, 10 ** 6)
    for z, x in zip(*np.nonzero(land)):
        d = np.minimum(d, np.maximum(abs(zz - z), abs(xx - x)))
    return d


# Without it the bands drift from the tool's stated rule: the shallows reach too far out or not far enough, or the deep
# band starts too near the shore.
@pytest.mark.parametrize("shallow,deep", [(SHALLOW, DEEP), (64, 160)])
def test_the_band_thresholds_follow_the_distance_from_land(syn_cells, shallow, deep):
    land, sea = syn_cells
    b = OW.bands(shallow, deep, SYN)
    d = _chebyshev_from(land)
    s, m = shallow // OW.CELL, deep // OW.CELL
    want_open = sea & (d > s) & (d <= m)
    want_deep = sea & (d > m)
    assert (b["open"] == want_open).all(), int((b["open"] != want_open).sum())
    assert (b["deep"] == want_deep).all(), int((b["deep"] != want_deep).sum())
    assert not (b["open"] & b["deep"]).any()
    # not vacuous: the synthetic world has shallows, open water and deep water, and the closed basin is in none
    assert (sea & (d <= s)).any() and want_open.any() and want_deep.any()
    assert b["open"][97, 96 - s - 1] and not b["open"][97, 96 - s] and not b["deep"][97, 96 - s]   # west of the island
    assert not b["open"][76, 76] and not b["deep"][76, 76]


def _raster(boxes):
    m = np.zeros((N_CELLS, N_CELLS), dtype=int)
    for x0, z0, x1, z1 in boxes:
        assert (x0 - OW.WORLD_MIN) % 16 == 0 and (x1 + 1 - OW.WORLD_MIN) % 16 == 0, (x0, x1)
        m[(z0 - OW.WORLD_MIN) // 16:(z1 - OW.WORLD_MIN) // 16 + 1, (x0 - OW.WORLD_MIN) // 16:(x1 - OW.WORLD_MIN) // 16 + 1] += 1
    return m


# Without it a box leaks past its band or leaves a hole in it, or two boxes overlap and a cell is counted twice.
def test_the_rectangles_cover_the_mask_exactly():
    rng = np.random.default_rng(44)
    masks = [rng.random((N_CELLS, N_CELLS)) < 0.3, np.zeros((N_CELLS, N_CELLS), dtype=bool),
             np.ones((N_CELLS, N_CELLS), dtype=bool)]
    b = OW.bands(SHALLOW, DEEP, SYN)
    masks += [b["open"], b["deep"]]
    for i, mask in enumerate(masks):
        r = _raster(OW.rectangles(mask))
        assert r.max() <= 1, (i, "overlap")
        assert (r.astype(bool) == mask).all(), (i, int((r.astype(bool) != mask).sum()))


@pytest.fixture(scope="module")
def real_ground():
    import ground as G
    import terrain as T
    try:
        return G.load()
    except (T.TerrainUnavailable, FileNotFoundError) as e:
        pytest.skip("the canonical heightmap is unavailable: %s" % e)


# Without it the tool calls the owner's lake sea, or the open ocean off the map's west edge something other than deep.
def test_lake_tilpey_is_no_sea_band_and_the_far_west_margin_is_deep(real_ground):
    b, (land, sea) = OW.bands(SHALLOW, DEEP, real_ground), OW.cells(real_ground)
    tilpey = cell_of(5964, 4135)
    assert not land[tilpey] and not sea[tilpey], "Lake Tilpey's basin is below sea level and not sea"
    assert not b["open"][tilpey] and not b["deep"][tilpey]
    west = cell_of(-900, 4000)
    assert b["deep"][west] and not b["open"][west]
    assert int(b["open"].sum()) > 1000 and int(b["deep"].sum()) > 10000
