"""The Displaced City cavern's shell (tools/cavern_plan.py 02_shell) and its place in the re-application.

Written in the same session as the shell. The generated-output tests skip when the cavern has not been generated in
this checkout (derived/ and build/ are not committed; generating needs the heightmap).
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

FN = ROOT / "build" / "datapacks" / "cobblers_cavern" / "data" / "cobblers" / "function" / "cavern"
NPZ = ROOT / "derived" / "cavern" / "plan.npz"
FILL = re.compile(r"fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) minecraft:stone replace #cobblers:cavern_void$")


def test_the_shell_runs_after_the_seal_and_before_anything_is_dug():
    # After the tunnel it would fill the tunnel; after the excavation it would be pointless over the roof and fill the
    # arrival. It must come straight after 00_seal.
    import reapply
    c = reapply.CAVERN
    assert c.index("02_shell") == c.index("00_seal") + 1
    assert c.index("02_shell") < c.index("10_excavate") < c.index("50_tunnel")


def _generated():
    if not (FN / "02_shell.mcfunction").is_file() or not NPZ.is_file():
        pytest.skip("the cavern is not generated in this checkout (python tools/cavern_plan.py --source-root <root>)")
    return (FN / "02_shell.mcfunction").read_text(encoding="utf-8").splitlines(), np.load(NPZ)


def test_the_shell_only_turns_voids_to_rock_and_never_reaches_the_ground():
    # A fill that replaced anything would bury the cavern's own rock features; one that reached the ground would put
    # stone on the surface of the Glacial Tear.
    lines, arr = _generated()
    plan = json.loads((ROOT / "derived" / "cavern" / "plan.json").read_text(encoding="utf-8"))
    x0, z0 = plan["cavern"][0], plan["cavern"][1]
    top, ceil = arr["top"], arr["ceiling"]
    fills = [l for l in lines if l.startswith("fill")]
    assert fills and all(FILL.match(l) for l in fills), [l for l in fills if not FILL.match(l)][:3]
    n = top.shape[0]
    for l in fills:
        xa, ya, za, xb, yb, zb = map(int, FILL.match(l).groups())
        for x in range(xa, xb + 1):
            i, j = x - x0, za - z0
            if 0 <= i < n and 0 <= j < n:
                assert yb <= top[j, i] - 1, l
                assert ya == ceil[j, i], l                   # over the roof it starts at the ceiling, not in the chamber


def test_the_shell_is_24_blocks_over_the_roof_where_the_ground_allows():
    lines, arr = _generated()
    lo, hi = arr["shell_lo"], arr["shell_hi"]
    m = (lo.shape[0] - arr["ceiling"].shape[0]) // 2
    inner_hi = hi[m:-m, m:-m]
    ceil, top = arr["ceiling"], arr["top"]
    assert (inner_hi == np.minimum(ceil + 23, top - 1)).all()
    # and the ring round the walls exists, 24 wide
    assert m == 24 and (hi[:m] > lo[:m]).any()


def test_the_cavern_tag_names_every_void():
    if not (ROOT / "build" / "datapacks" / "cobblers_cavern").is_dir():
        pytest.skip("the cavern is not generated in this checkout")
    tag = json.loads((ROOT / "build" / "datapacks" / "cobblers_cavern" / "data" / "cobblers" / "tags" / "block"
                      / "cavern_void.json").read_text(encoding="utf-8"))
    for b in ("minecraft:air", "minecraft:cave_air", "minecraft:water", "minecraft:lava", "minecraft:gravel"):
        assert b in tag["values"]
