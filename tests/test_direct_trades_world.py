"""The barterer's world write (tools/direct_trades.py, step R18DT), audited by an agent that did not build it.

Every expectation here is computed from the data (data/direct_trades.json's site and booth, data/placements.json's
authored rects), the heightmap (tools/ground.py) and vanilla geometry stated below -- never from the generator's own
booth() or shell_cells(). The generator is CALLED only for its output: the place function's commands and the step.

What this does NOT cover: that the commands run (EXP-055), what the world holds at the booth today (a cellar, a
cave, a player's pit: the place function's breach check reads that at run time), the town's house lots
(derived/towns/gym8_town_plan.json is a derived plan, absent in a fresh worktree), and lightning that strikes below
the heightmap (a pit dug next to the booth).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

pytest.importorskip("numpy")
import direct_trades as D  # noqa: E402

DATA = json.loads((ROOT / "data" / "direct_trades.json").read_text(encoding="utf-8"))
PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
COORD = r"(-?\d+)"


def _ground():
    try:
        import ground as G
        return G.load()
    except Exception as exc:  # the canonical heightmap is outside the repo
        pytest.skip("no heightmap: %s" % exc)


@pytest.fixture(scope="module")
def place():
    out, _res = D.files(D.load(), _ground())
    return [ln for ln in out["data/cobblers/function/direct_trades/place.mcfunction"].splitlines()
            if ln.strip() and not ln.startswith("#")]


def _fill(place):
    (m,) = [re.match(r"fill %s %s %s %s %s %s (\S+) hollow$" % ((COORD,) * 6), ln) for ln in place
            if ln.startswith("fill ")]
    v = [int(m.group(i)) for i in range(1, 7)]
    return (min(v[0], v[3]), min(v[1], v[4]), min(v[2], v[5])), (max(v[0], v[3]), max(v[1], v[4]), max(v[2], v[5]))


def _checked(place):
    return [tuple(int(g) for g in re.match(r"execute if block %s %s %s " % ((COORD,) * 3), ln).groups())
            for ln in place if ln.startswith("execute if block ")]


def _written(place):
    """Every block position a command in the place function reads or writes."""
    pts = list(_checked(place))
    (x0, y0, z0), (x1, y1, z1) = _fill(place)
    pts += [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    for ln in place:
        m = re.match(r"setblock %s %s %s " % ((COORD,) * 3), ln)
        if m:
            pts.append(tuple(int(g) for g in m.groups()))
        m = re.match(r"summon \S+ (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) ", ln)
        if m:
            pts.append(tuple(int(float(g) // 1) for g in m.groups()))
    return pts


def _forceload_chunks(cmds, verb):
    out = set()
    for c in cmds:
        m = re.fullmatch(r"forceload %s %s %s(?: %s %s)?" % (verb, COORD, COORD, COORD, COORD), c)
        if not m:
            continue
        x0, z0 = int(m.group(1)), int(m.group(2))
        x1, z1 = (int(m.group(3)), int(m.group(4))) if m.group(3) else (x0, z0)
        out |= {(cx, cz) for cx in range(min(x0, x1) // 16, max(x0, x1) // 16 + 1)
                for cz in range(min(z0, z1) // 16, max(z0, z1) // 16 + 1)}
    return out


# Without it the step could hold one chunk while the booth spans two: `execute if block` and `fill` refuse a position
# that is not loaded, so in an unheld chunk the breach check silently skips its cells and the fill is refused while
# the setblock and the summon after it still run -- a villager summoned into uncarved rock. The booth's box comes from
# the emitted fill; the chunks are floor(coordinate / 16).
def test_the_forceload_holds_every_chunk_the_booth_touches(place):
    cmds = [v for kind, v in D.steps() if kind == "cmd"]
    need = {(x // 16, z // 16) for x, _y, z in _written(place)}
    held = _forceload_chunks(cmds, "add")
    assert need <= held, "R18DT holds chunks %s; the booth touches %s (unheld: %s)" % (
        sorted(held), sorted(need), sorted(need - held))
    assert _forceload_chunks(cmds, "remove") == held, "every chunk held is released"


# Without it the place function could write outside its booth: every setblock and the summon fall inside the fill's
# box, and the box is the data's interior plus a one-block shell, centred on the data's site.
def test_the_booth_writes_only_inside_its_box(place):
    (x0, y0, z0), (x1, y1, z1) = _fill(place)
    ix, iy, iz = DATA["site"]["booth"]["interior"]
    assert (x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1) == (ix + 2, iy + 2, iz + 2)
    assert ((x0 + x1) // 2, (z0 + z1) // 2) == (DATA["site"]["x"], DATA["site"]["z"])
    for x, y, z in _written(place):
        assert x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1, (x, y, z)


# Without it the breach check could guard fewer cells than the fill replaces: the cells checked are exactly the box
# minus its one-block-inset interior (5^3 - 3^3 = 98 for a 3x3x3 room), every check precedes the fill, and a refusal
# (`return fail` on the breach score) sits between them.
def test_the_breach_check_covers_every_shell_cell_before_the_fill(place):
    (x0, y0, z0), (x1, y1, z1) = _fill(place)
    shell = {(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)
             if not (x0 < x < x1 and y0 < y < y1 and z0 < z < z1)}
    checked = _checked(place)
    assert len(checked) == len(set(checked)) == len(shell) == (x1 - x0 + 1) * (y1 - y0 + 1) * (z1 - z0 + 1) - \
        (x1 - x0 - 1) * (y1 - y0 - 1) * (z1 - z0 - 1)
    assert set(checked) == shell
    last_check = max(i for i, ln in enumerate(place) if ln.startswith("execute if block "))
    fill_at = next(i for i, ln in enumerate(place) if ln.startswith("fill "))
    fail_at = [i for i, ln in enumerate(place) if ln.endswith("run return fail")]
    assert fail_at and last_check < fail_at[0] < fill_at


# Without it the booth could rise into reach of lightning or into the street: its top is under the heightmap's lowest
# ground over the footprint, and the villager's head is out of a bolt's box. Vanilla's bolt hits entities in a box 3
# blocks below its strike point and 3 to each side (a villager is 0.6 wide and 1.95 tall, centred on its block); the
# strike point is the air above the top block (tools/ground.py's y), so the feet must be at least 4 under the lowest
# ground within 3 blocks of the villager's column.
def test_the_booth_is_buried_out_of_lightning_reach(place):
    g = _ground()
    (x0, y0, z0), (x1, y1, z1) = _fill(place)
    foot_min = min(int(round(g(x, z))) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
    assert y1 < foot_min, "the booth's ceiling y%d is not under ground y%d" % (y1, foot_min)
    (vx, vy, vz), = [tuple(int(float(c) // 1) for c in re.match(r"summon \S+ (\S+) (\S+) (\S+) ", ln).groups())
                     for ln in place if ln.startswith("summon ")]
    reach_min = min(int(round(g(x, z))) for x in range(vx - 3, vx + 4) for z in range(vz - 3, vz + 4))
    assert vy <= reach_min - 4, "feet y%d, lowest ground within 3 blocks y%d" % (vy, reach_min)


def _overlap(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


# Without it the booth could be carved under an authored building: no anchor rect or plaza of any settlement in
# data/placements.json overlaps the booth's footprint. (House lots are placed from derived/towns, not checked here.)
def test_the_booth_meets_no_authored_rect(place):
    (x0, _y0, z0), (x1, _y1, z1) = _fill(place)
    booth = (x0, z0, x1, z1)
    hits = []
    for sid, s in (PLACEMENTS.get("settlements") or {}).items():
        plan = s.get("plan") or {}
        rects = [("plaza", (plan.get("plaza") or {}).get("rect"))] + [
            (a.get("id"), a.get("rect")) for a in plan.get("anchors") or []]
        for rid, r in rects:
            if r and _overlap(booth, r):
                hits.append("%s/%s %s" % (sid, rid, r))
    assert not hits, hits
