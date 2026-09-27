"""Surface exhaustion (EXP-044): tools/open_water.py's sea bands and the cobblers_blackout pack's surface/* functions.

Written by the test author, not by the session that wrote either (commits 476c4e5..5d522d7).

Independent sources: data/blackout.json "surface" (the rule and every number); tools/open_water.py's docstring rule (a
16-block cell is land if any column in it is at or above sea level 62; the sea is the below-sea cells connected to the
world border, so an inland basin is not sea; shallows, open and deep by Chebyshev distance from land) with the
distances recomputed here by brute force; the owner's places: Lake Tilpey at (5964, 4135) is a lake, and the far west
margin (-900, 4000) is 1,024 blocks of open ocean outside the heightmap (docs/STATE.md 'World facts'); vanilla command
semantics as tests/test_blackout_pack.py's simulator runs them.

The band thresholds, as the tool applies them: a sea cell whose Chebyshev distance d (in cells) from the nearest land
cell is at most shallow_blocks/16 is shallows (the gap between the two cells' facing edges, (d - 1) * 16 blocks, is under
shallow_blocks); at most deep_blocks/16 is open; beyond is deep.

The real-heightmap tests need the canonical heightmap (outside the repository): without it they SKIP, and a skip is not
a pass.

Not covered, and it needs a running server (EXP-044): that `on vehicle` sees a Cobblemon ride or a boat; that the
slowness and hunger feel as the data says; the measured swim speeds the "feel" note rests on; whether the #ride
fake-player score carries from one player to the next in the same tick when the second rides nothing (vanilla: an
`execute store` whose chain forks to no executor stores nothing; unverified here).
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import blackout_pack as BP  # noqa: E402
import open_water as OW  # noqa: E402
import test_blackout_pack as TB  # noqa: E402

CFG = TB.CFG
SURF = CFG["surface"]
N_CELLS = (OW.WORLD_MAX - OW.WORLD_MIN + 1) // OW.CELL        # 640


def cell_of(x, z):
    return (z - OW.WORLD_MIN) // OW.CELL, (x - OW.WORLD_MIN) // OW.CELL


class FakeGround:
    """What open_water reads from tools/ground.py: the heights (z, x) and their origin."""

    def __init__(self, heights, ox=0, oz=0):
        self.heights, self.ox, self.oz = heights, ox, oz


# ------------------------------------------------------------------------------------------------ open_water, synthetic

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


# Without it a lake (a basin under sea level, ringed by land) is treated as open sea, and a swimmer in Lake Tilpey is
# exhausted; or the flood fill stops at the first wall and misses a basin the sea reaches through a gap.
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


# Without it the bands drift from the data: free swimming reaches too far out or not far enough, or the deep band (twice
# the strain) starts too near the shore.
@pytest.mark.parametrize("shallow,deep", [(SURF["shallow_blocks"], SURF["deep_blocks"]), (64, 160)])
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


# Without it a box leaks past its band (a swimmer in the shallows is tested as open water) or leaves a hole in it, or two
# boxes overlap and a cell is counted twice.
def test_the_rectangles_cover_the_mask_exactly():
    rng = np.random.default_rng(44)
    masks = [rng.random((N_CELLS, N_CELLS)) < 0.3, np.zeros((N_CELLS, N_CELLS), dtype=bool),
             np.ones((N_CELLS, N_CELLS), dtype=bool)]
    b = OW.bands(SURF["shallow_blocks"], SURF["deep_blocks"], SYN)
    masks += [b["open"], b["deep"]]
    for i, mask in enumerate(masks):
        r = _raster(OW.rectangles(mask))
        assert r.max() <= 1, (i, "overlap")
        assert (r.astype(bool) == mask).all(), (i, int((r.astype(bool) != mask).sum()))


# ------------------------------------------------------------------------------------------------ open_water, real

@pytest.fixture(scope="module")
def real_ground():
    import ground as G
    import terrain as T
    try:
        return G.load()
    except (T.TerrainUnavailable, FileNotFoundError) as e:
        pytest.skip("the canonical heightmap is unavailable: %s" % e)


@pytest.fixture(scope="module")
def real_bands(real_ground):
    return OW.bands(SURF["shallow_blocks"], SURF["deep_blocks"], real_ground), OW.cells(real_ground)


# Without it the owner's lake is exhausting to swim in, or the open ocean off the map's west edge is free.
def test_lake_tilpey_is_no_sea_zone_and_the_far_west_margin_is_deep(real_bands):
    b, (land, sea) = real_bands
    tilpey = cell_of(5964, 4135)
    assert not land[tilpey] and not sea[tilpey], "Lake Tilpey's basin is below sea level and not sea"
    assert not b["open"][tilpey] and not b["deep"][tilpey]
    west = cell_of(-900, 4000)
    assert b["deep"][west] and not b["open"][west]
    assert int(b["open"].sum()) > 1000 and int(b["deep"].sum()) > 10000


@pytest.fixture(scope="module")
def real_pack(real_ground, tmp_path_factory):
    """The pack as `python tools/blackout_pack.py` writes it, heightmap rows included."""
    out = tmp_path_factory.mktemp("cobblers_blackout")
    assert BP.main(["--out", str(out)]) == 0
    return {p.relative_to(out).as_posix(): p.read_text(encoding="utf-8") for p in out.rglob("*") if p.is_file()}


# Without it a swimmer in a row with no row function sends the macro to a function that does not exist (an error every
# 10 ticks, and no zone), or the rows the pack carries differ from the bands open_water computes.
def test_the_real_pack_has_a_row_for_every_world_row_and_its_rows_are_the_bands(real_pack, real_bands):
    b, _ = real_bands
    fns = TB.functions(real_pack)
    rows = {int(n.rsplit("/", 1)[1]): lines for n, lines in fns.items() if re.fullmatch(r"surface/r/-?\d+", n)}
    assert set(rows) == set(range(N_CELLS)), sorted(set(range(N_CELLS)) ^ set(rows))[:10]
    got = {1: np.zeros((N_CELLS, N_CELLS), dtype=bool), 2: np.zeros((N_CELLS, N_CELLS), dtype=bool)}
    for z, lines in rows.items():
        for l in lines:
            m = re.fullmatch(r"execute if score #cx bo\.tmp matches (\d+)\.\.(\d+) run return run scoreboard players "
                             r"set @s bo\.zone ([12])", l)
            assert m, (z, l)
            a, c, v = map(int, m.groups())
            assert not got[v][z, a:c + 1].any(), (z, a, c, "overlapping runs")
            got[v][z, a:c + 1] = True
    assert (got[1] == b["open"]).all() and (got[2] == b["deep"]).all()
    # and the reference check, with the macro-built names resolved against the rows that exist
    refs = TB._references(real_pack)
    assert not [r for r in refs if r[1] != TB.NS]
    assert not [(w, f) for w, _, f, _ in refs if "$(" not in f and f not in fns and f != "blackout/battle_loss_"]


def _zone(fns, x, z):
    s = TB.Sim(fns=fns, query=lambda cmd: {"data get entity @s Pos[0]": x, "data get entity @s Pos[2]": z}.get(cmd, 0),
               cond=lambda kind, toks: kind == "block")
    for f in TB.load_functions():
        s.call(f)
    s.set("@s", "bo.zone", 9)
    s.call("surface/tick")
    assert not s.missing, s.missing
    return s.get("@s", "bo.zone")


# Without it the pack's own lookup (the cell arithmetic, the macro, the row) disagrees with the bands at the places
# the owner named.
def test_the_real_pack_puts_tilpey_in_no_zone_and_the_far_west_in_the_deep(real_pack):
    fns = TB.functions(real_pack)
    assert _zone(fns, 5964, 4135) == 0
    assert _zone(fns, -900, 4000) == 2


# ------------------------------------------------------------------------------------------------ the surface tick

FNS = TB.FNS                       # built with TB.ROWS: row 330 (z 4256..4271), open cells 10-19, deep cells 20-29
Z = 4260
OPEN_X, DEEP_X, NONE_X = -860, -700, -384


def _swim(x=OPEN_X, z=Z, water=True, sub=0, riding=False, qual=0, fat=0, samples=1, health=20, fns=None):
    """Run surface/tick `samples` times; returns the simulator."""
    q = {"data get entity @s Pos[0]": x, "data get entity @s Pos[2]": z,
         "attribute @s minecraft:generic.max_health get 1": 20, "data get entity @s Health 1": health}

    def cond(kind, toks):
        if kind == "block":
            return water
        if kind == "on":
            return riding
        if kind == "entity":
            return True
        return False

    s = TB.Sim(fns=fns or FNS, query=lambda cmd: q.get(cmd, 0), cond=cond)
    for f in TB.load_functions():
        s.call(f)
    s.set("@s", "bo.sub", sub)
    s.set("@s", "bo.qual", qual)
    s.set("@s", "bo.fat", fat)
    for _ in range(samples):
        s.call("surface/tick")
    return s


PER = SURF["sample_ticks"]
GAIN_OPEN = SURF["gain_open_per_tick"] * PER
GAIN_DEEP = SURF["gain_deep_per_tick"] * PER
REC = SURF["recover_per_tick"] * PER


# Without it a swimmer who reaches land, the shallows or a lake, or who rides a water Pokemon or a boat, stays tired
# (or tires further), and a ride across the open sea exhausts its rider.
@pytest.mark.parametrize("where", ["land", "riding in the deep", "shallows or lake", "feet on land, eyes in water"])
def test_land_riding_and_the_shallows_recover(where):
    kw = {"land": dict(water=False, sub=0), "riding in the deep": dict(x=DEEP_X, riding=True),
          "shallows or lake": dict(x=NONE_X), "feet on land, eyes in water": dict(water=False, sub=1)}[where]
    s = _swim(fat=500, **kw)
    if where == "feet on land, eyes in water":
        assert s.get("@s", "bo.fat") == 500 + GAIN_OPEN, "eyes under water in the open sea is swimming"
        return
    assert s.get("@s", "bo.fat") == 500 - REC, (where, s.get("@s", "bo.fat"))
    assert _swim(fat=REC // 2, **kw).get("@s", "bo.fat") == 0, "recovery stops at zero"


# Without it the deep band tires no faster than open water, or a trained partner does not halve the strain.
@pytest.mark.parametrize("x,qual,gain", [(OPEN_X, 0, GAIN_OPEN), (DEEP_X, 0, GAIN_DEEP),
                                         (OPEN_X, 1, GAIN_OPEN // 2), (DEEP_X, 2, GAIN_DEEP // 2)])
def test_the_deep_band_doubles_and_a_qualified_player_halves(x, qual, gain):
    assert GAIN_DEEP == 2 * GAIN_OPEN
    s = _swim(x=x, qual=qual, samples=7)
    assert s.get("@s", "bo.fat") == 7 * gain, (x, qual, s.get("@s", "bo.fat"))
    assert s.get("@s", "bo.zone") == (2 if x == DEEP_X else 1)


# Without it the warnings repeat every sample or never come, the slowness starts at the wrong fatigue, or fatigue grows
# without bound (a swimmer then needs hours on land to recover).
def test_warnings_come_once_effects_follow_the_thresholds_and_fatigue_is_capped():
    s = _swim(samples=SURF["exhausted_ticks"] // GAIN_OPEN + 2)
    tellraws = [l for l in s.log if l.startswith("tellraw")]
    assert len([l for l in tellraws if CFG["messages"]["surface_tiring"] in l]) == 1, tellraws
    assert len([l for l in tellraws if CFG["messages"]["surface_exhausted"] in l]) == 1, tellraws
    slow = _swim(fat=SURF["slow_ticks"] - GAIN_OPEN - 1)
    assert "effect give @s minecraft:slowness 2 0 true" not in slow.log
    slow = _swim(fat=SURF["slow_ticks"] - GAIN_OPEN)
    assert "effect give @s minecraft:slowness 2 0 true" in slow.log
    exh = _swim(fat=SURF["exhausted_ticks"] - GAIN_OPEN)
    assert {"effect give @s minecraft:slowness 2 1 true", "effect give @s minecraft:hunger 2 0 true"} <= set(exh.log)
    cap = _swim(x=DEEP_X, fat=SURF["cap_ticks"] - 1, samples=3)
    assert cap.get("@s", "bo.fat") == SURF["cap_ticks"]


# Without it a collapse deals some other damage than drowning's half-health hit (the ladder's lethal-from-half rule and
# its message would not apply), or never hits at all.
def test_a_collapse_pulse_reuses_the_drowning_hit():
    assert "function %s:water/pulse" % TB.NS in TB.FNS["surface/collapse"]
    s = _swim(fat=SURF["collapse_ticks"] - GAIN_OPEN)
    assert [c[0] for c in s.calls if c[0].startswith("water/")] == ["water/pulse", "water/pulse_apply"], s.calls
    assert "damage @s 10 minecraft:drown" in s.log, s.log
    s = _swim(fat=SURF["collapse_ticks"] - GAIN_OPEN, health=10 + CFG["water"]["pulse_regen_margin"])
    assert "damage @s 1000 minecraft:drown" in s.log, s.log
    assert not [c for c in _swim(fat=SURF["collapse_ticks"] - GAIN_OPEN - 1).calls if c[0] == "water/pulse"]


def _pulses(x, qual, f0, samples=40):
    """[(fatigue before, after, pulsed)] per sample from fatigue f0."""
    s = _swim(x=x, qual=qual, fat=f0, samples=0)
    out = []
    for _ in range(samples):
        before = s.get("@s", "bo.fat")
        s.calls.clear()
        s.call("surface/tick")
        out.append((before, s.get("@s", "bo.fat"), any(c[0] == "water/pulse" for c in s.calls)))
    return out


CADENCE_BUG = ("tools/blackout_pack.py:715 surface/collapse pulses when (fatigue - collapse) mod pulse_ticks < "
               "sample_ticks, which assumes a sample adds exactly sample_ticks of fatigue (10). A trained swimmer in "
               "open water adds 5: two pulses 10 ticks apart every 120 (the second lethal from half health). In the "
               "deep band a sample adds 20: a count that is not a multiple of 20 past collapse (an untrained swimmer "
               "who tired in open water, at gain 10, and crossed into the deep at 1190) steps 1210, 1230, 1250, ... "
               "and never lands in the window: a collapsed swimmer is never hurt")


# Without it a collapsed swimmer is hit twice in half a second (and dies on the second) or never at all, depending on
# the band, the partner and where the count started: past collapse a pulse must land each time fatigue passes another
# pulse_ticks of fatigue, once, for every gain the pack uses.
@pytest.mark.parametrize("x,qual", [
    (OPEN_X, 0),
    pytest.param(DEEP_X, 0, marks=pytest.mark.xfail(strict=True, reason=CADENCE_BUG)),
    pytest.param(OPEN_X, 1, marks=pytest.mark.xfail(strict=True, reason=CADENCE_BUG)),
    (DEEP_X, 1),
])
def test_past_collapse_a_pulse_lands_once_per_pulse_ticks_of_fatigue(x, qual):
    fcol, fp = SURF["collapse_ticks"], SURF["pulse_ticks"]
    bad = []
    for f0 in range(fcol - 60, fcol, 5):
        for before, after, pulsed in _pulses(x, qual, f0):
            due = any(before < fcol + k * fp <= after for k in range(0, (after - fcol) // fp + 2))
            if due != pulsed:
                bad.append((f0, before, after, pulsed))
    assert not bad, bad[:6]


# Without it sample_ticks is half honoured: the gains and the collapse window scale with it, but the tick that runs
# surface/tick stays every 10 ticks, so a sample_ticks of 20 would double every rate.
@pytest.mark.xfail(strict=True, reason=(
    "tools/blackout_pack.py:178 runs surface/tick when gametime mod 10 is 0 (#m10, the constant #10), whatever "
    "data/blackout.json surface.sample_ticks says; the gains (line 663) and the collapse window use sample_ticks. No "
    "effect at today's value, 10"))
def test_the_surface_tick_runs_every_sample_ticks():
    cfg = copy.deepcopy(CFG)
    cfg["surface"]["sample_ticks"] = 20
    fns = TB.functions(TB.build(cfg))
    tick = [l for l in fns["blackout/tick"] if not l.startswith("#")]
    i = next(i for i, l in enumerate(tick) if l.endswith("run function %s:surface/tick" % TB.NS))
    holder = re.match(r"execute if score (#\w+) bo\.tmp matches 0 ", tick[i]).group(1)
    mod = [l for l in tick[:i] if l.startswith("scoreboard players operation %s bo.tmp %%= " % holder)][-1].split()[6]
    consts = {l.split()[3]: int(l.split()[5]) for f in ("blackout/load", "surface/load") for l in fns[f]
              if l.startswith("scoreboard players set #")}
    assert consts[mod] == 20, (mod, consts[mod])
