"""Every authored `ground_y` is still the ground the heightmap has at that column.

Written by the test author, not by the session that authored any of the files it reads.

WHAT BREAKS WITHOUT IT. `data/elder_trees.json` is a PINNED file: `tools/elder_trees.py` stopped
re-siting the elders on 2026-09-26 (so a repaint could not silently drop or move a tree out from under
its bird) and now takes each trunk's `ground_y` straight out of the file -- `sites.append({... "ground_y":
p["ground_y"] ...})` -- without ever comparing it to the heightmap, and WITHOUT the `wet = heights <=
sea_level` guard that the siting path applies, because the pinned branch sets `included = []` and skips
it entirely.

Then the water pass drowned the Jungle Isle. Every column inside the isle's polygon now lies at or below
sea level (`regions.json`'s own measured block says max 61 against a sea of 62), and the four pinned
jungle elders kept their pre-water heights: recorded 70, 126, 81 and 77 where the heightmap has 53, 58,
53 and 54. The owner flew out there on 2026-10-01 and found four full-size world trees hanging in open
air over the ocean, 8 to 64 blocks above the sea, with their 16 bird Habitat Blocks inside the trunks.

The reason nothing caught it is the one CLAUDE.md names: an audit that shares the builder's derivation is
not independent. `tests/test_elder_birds.py` checks the doc table, `data/elder_trees.json` and the site
file against EACH OTHER, and all three carry the same stale number, so three sources agreed and the
world disagreed. This test is the only one that asks the terrain.

The same sweep found the one other record in `data/` with a real divergence, and it is not a fault:
`relic_island`'s centre says 68.0 where the heightmap says 35, because `tools/islet.py` BUILDS that
island out of the seabed. It declares that itself, in `heightmap_seabed_y` -- which is what makes it
exemptible by a rule rather than by a name.

NOT SWEPT, and by measurement rather than by fiat: `data/rivers.json`. Its seven heads carry fractional
heights that match neither `round(h)` nor the raw float -- (2504, 1444) records 170.9 where the raw
heightmap is 176.35 -- so they come off a coarser analysis grid and mean something else. Widening this
test's tolerance to 5.5 to admit them would make it prove nothing about the 8-to-68-block errors it
exists to catch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# `ground_y` here means "the Y of the ground block a fresh export has at this column" (tools/ground.py).
# A LIVE FAULT, strict xfail until decision B13 is answered: the four drowned jungle elders. The remedy is
# the owner's ("in the ocean with the roots extended, or somewhere else entirely"), so the data is not
# guessed at here -- answering B13 removes the mark and this test turns green on its own.
DROWNED_ELDERS = (
    "data/elder_trees.json's four jungle elders carry their pre-water heights (70, 126, 81, 77) where the "
    "heightmap now has 53, 58, 53 and 54: the water pass drowned the Jungle Isle and tools/elder_trees.py's "
    "pinned path neither re-reads the ground nor applies the siting path's `wet` guard. Four world trees "
    "stand in open air over the ocean with 16 bird Habitat Blocks in their trunks. Decision B13.")

SWEPT = (
    pytest.param("data/elder_trees.json", marks=pytest.mark.xfail(strict=True, reason=DROWNED_ELDERS)),
    "data/towns.json",
    "data/themed_saplings.json",
)

# A footprint centre may sit on a half-block midpoint of its corners, so a record is allowed to be half a
# block off the column it names. Nothing larger: the smallest real fault this test exists for is 17.
TOLERANCE = 0.5

# A record that declares the seabed it was built up from is ground a tool MAKES, not ground the terrain
# has. relic_island is the only one today; the rule, not the id, is what exempts it.
BUILT_GROUND_KEY = "heightmap_seabed_y"


@pytest.fixture(scope="module")
def ground():
    import ground as G
    from terrain import TerrainUnavailable
    try:
        return G.load()
    except TerrainUnavailable as e:
        # The one error that means "this machine has no heightmap". Never a bare except: a bug inside
        # G.load() must fail this suite, not silently skip every column in it.
        pytest.skip("the canonical heightmap is not available here (%s)" % (str(e) or type(e).__name__)[:80])


def _columns(obj, path=""):
    """Every (path, x, z, ground_y, declares_built_ground) record anywhere in a document."""
    if isinstance(obj, dict):
        x, z, gy = obj.get("x"), obj.get("z"), obj.get("ground_y")
        if isinstance(x, int) and isinstance(z, int) and isinstance(gy, (int, float)):
            yield path, x, z, float(gy), BUILT_GROUND_KEY in obj
        for k, v in obj.items():
            yield from _columns(v, "%s/%s" % (path, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _columns(v, "%s[%d]" % (path, i))


@pytest.mark.parametrize("rel", SWEPT)
def test_every_authored_ground_is_the_heightmaps_ground(rel, ground):
    doc = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    wrong = []
    for path, x, z, gy, built in _columns(doc):
        if built:
            continue
        real = ground(x, z)
        if abs(gy - real) > TOLERANCE:
            wrong.append("%s (%d, %d): records %g, the heightmap has %d (%+g)" % (path, x, z, gy, real, gy - real))
    assert not wrong, (
        "%s carries ground that the terrain does not have. A tree, building or site placed on one of these "
        "stands in mid-air or buried:\n  %s" % (rel, "\n  ".join(wrong)))


@pytest.mark.xfail(strict=True, reason=DROWNED_ELDERS)
def test_no_pinned_elder_is_planted_on_a_drowned_column(ground):
    """A tree needs soil. tools/elder_trees.py's siting path refuses a wet cell (`wet = heights <=
    sea_level`); its pinned path never looks, which is how four elders came to stand over open ocean."""
    import terrain as T
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    sea = T.sea_level(world)
    elders = json.loads((ROOT / "data" / "elder_trees.json").read_text(encoding="utf-8"))["elders"]
    drowned = ["%s (%d, %d): ground %d, sea %d" % (e["id"], e["x"], e["z"], ground(e["x"], e["z"]), sea)
               for e in elders if ground(e["x"], e["z"]) <= sea]
    assert not drowned, (
        "pinned elders stand on columns at or below sea level, so there is no ground to plant them in:\n  %s"
        % "\n  ".join(drowned))
