"""Boats as shallows craft: the cobblers_blackout pack's boat/* functions (the owner's water decision 2, option C).

Written by the test author, not by the session that wrote the rule (d910046, tools/blackout_pack.py and
data/blackout.json "boats"). It runs the generated functions on tests/test_surface_exhaustion.py's swim simulator (the
command simulator of tests/test_blackout_pack.py, given a vehicle, a position and a water column).

Independent sources:
  - the owner, 2026-09-27 (docs/mechanics/WATER_BUILD_PLAN.md:791): "Boats: option C, shallows only. A boat should not
    defeat swimming, exhaustion and the ferry from day one"; WATER_PROPOSAL.md 4.4 option C: past 96 blocks from land a
    boat is swamped, its rider dismounted and swimming; sheltered water is an authored exception; coasts, lakes and
    rivers stay boat water;
  - data/blackout.json "boats": rough_blocks, deep_blocks, the sheltered boxes and the message;
  - tools/open_water.py's band map (the rule names it), called here at the data's distances on a small synthetic
    ground, and a brute-force distance from land written here for the points the scenarios use;
  - vanilla 1.21.1: minecraft:boat and minecraft:chest_boat are the boat entity types (a bamboo raft is a
    minecraft:boat); `ride @s dismount` leaves the vehicle at once; a `dx` volume selects an entity whose 0.6-wide
    hitbox meets [x, x + dx + 1); `data get ... Pos` floors; scoreboard `/=` floors.

With the canonical heightmap (slow; skipped without COBBLERS_SOURCE_ROOT): every cell row the check can compute has
its row function, and the sheltered box holds the Sound's rough pocket the data measured.

Not covered, and it needs a running server (EXP-044): that `on vehicle` finds a boat and a Cobblemon ride; that a
dismounted rider stays in the water rather than on the boat's hitbox; whether a player can re-place a boat at once
(carrying one is not prevented: see the ferry contract C11 in tests/test_system_contracts.py); boats entering rough
water from a lake connected to the sea through a river (the band map calls such water sea).
"""
from __future__ import annotations

import copy
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import blackout_pack as BP  # noqa: E402
import ground as GROUND  # noqa: E402
import open_water as OW  # noqa: E402
import test_blackout_pack as TB  # noqa: E402
import test_surface_exhaustion as TSE  # noqa: E402

CFG = TB.CFG
BOATS_CFG = CFG["boats"]
NS = TB.NS
CELL = 16
WORLD_MIN = -1024                      # the playable world's west/north edge inside the 10,240 border (STATE "World facts")
SEA_LEVEL = 62
ROW = re.compile(r"execute if score #cx bo\.tmp matches (\d+)\.\.(\d+) run return run scoreboard players set @s bo\.zone (\d)")
SHELTER = re.compile(r"execute if entity @s\[x=(-?\d+),y=-64,z=(-?\d+),dx=(\d+),dy=640,dz=(\d+)\] run return 0")


# ------------------------------------------------------------------------------------------------ a synthetic ground

class Synthetic:
    """A heightmap over x, z 2048..3071: sea floor at y40 everywhere, an island (land at y70) over x, z 2300..2399, and
    a ring of land x, z 2600..2999, 48 wide, round a lake whose floor is y40 (below sea level, ringed by land: not sea).
    Everything outside is sea by construction (tools/open_water.py)."""
    ox = oz = 2048

    def __init__(self):
        h = np.full((1024, 1024), 40.0)
        def land(x0, z0, x1, z1):
            h[z0 - self.oz:z1 - self.oz + 1, x0 - self.ox:x1 - self.ox + 1] = 70.0
        land(2300, 2300, 2399, 2399)
        land(2600, 2600, 2999, 2647)
        land(2600, 2952, 2999, 2999)
        land(2600, 2600, 2647, 2999)
        land(2952, 2600, 2999, 2999)
        self.heights = h

    def land_cells(self):
        """The 16-block cells holding any column at or above sea level (the band map's own definition of land)."""
        out = set()
        zs, xs = np.nonzero(self.heights >= SEA_LEVEL)
        for z, x in zip(zs, xs):
            out.add(((x + self.ox - WORLD_MIN) // CELL, (z + self.oz - WORLD_MIN) // CELL))
        return out


SYN = Synthetic()
LAND_CELLS = SYN.land_cells()


def cell_of(x, z):
    return (math.floor(x) - WORLD_MIN) // CELL, (math.floor(z) - WORLD_MIN) // CELL


def expected_band(x, z):
    """0 shallows or not sea, 1 open, 2 deep, by brute force: the Chebyshev distance in cells to the nearest land cell;
    rough from rough_blocks / 16 + 1 cells out (the band map's dilation), deep past deep_blocks / 16. The lake inside
    the ring is not sea."""
    cx, cz = cell_of(x, z)
    if (cx, cz) in LAND_CELLS:
        return 0
    lake = cell_of(2648, 2648), cell_of(2951, 2951)
    if lake[0][0] <= cx <= lake[1][0] and lake[0][1] <= cz <= lake[1][1]:
        return 0
    d = min(max(abs(cx - a), abs(cz - b)) for a, b in LAND_CELLS)
    if d <= BOATS_CFG["rough_blocks"] // CELL:
        return 0
    return 1 if d <= BOATS_CFG["deep_blocks"] // CELL else 2


@pytest.fixture(scope="module")
def boated(tmp_path_factory):
    """The pack tools/blackout_pack.py main() writes over the synthetic ground: ({path: text}, {name: lines})."""
    mp = pytest.MonkeyPatch()
    mp.setattr(GROUND, "load", lambda *a, **k: SYN)
    out = tmp_path_factory.mktemp("boats") / "cobblers_blackout"
    try:
        assert BP.main(["--out", str(out)]) == 0
    finally:
        mp.undo()
    files = {p.relative_to(out).as_posix(): p.read_text(encoding="utf-8") for p in out.rglob("*") if p.is_file()}
    return files, TB.functions(files)


def rows_of(fns):
    """{(cell row, cell x): band} from the written boat/r/<z> functions."""
    out = {}
    for name, lines in fns.items():
        m = re.fullmatch(r"boat/r/(\d+)", name)
        if not m:
            continue
        for l in lines:
            r = ROW.fullmatch(l)
            assert r, (name, l)
            a, b, v = (int(g) for g in r.groups())
            for cx in range(a, b + 1):
                assert (int(m.group(1)), cx) not in out, (name, cx)
                out[(int(m.group(1)), cx)] = v
    return out


# ------------------------------------------------------------------------------------------------ the band rows

# Without it the boat rows drift from the band map the rule names (a row shifted by a cell, open and deep swapped, the
# distances read from somewhere other than the data), or main() stops writing them and every boat check calls a
# function that does not exist. The rows main() writes are exactly tools/open_water.py's bands at the data's
# rough_blocks and deep_blocks, run-length encoded by cell row; and nothing else in the pack depends on the ground.
def test_the_boat_rows_are_the_band_map_at_the_datas_distances(boated):
    files, fns = boated
    got = rows_of(fns)
    b = OW.bands(BOATS_CFG["rough_blocks"], BOATS_CFG["deep_blocks"], ground=SYN)
    want = {}
    for code, key in ((1, "open"), (2, "deep")):
        for cz, cx in zip(*np.nonzero(b[key])):
            want[(int(cz), int(cx))] = code
    assert got and got == want, (len(got), len(want), sorted(set(got.items()) ^ set(want.items()))[:5])
    assert {k: v for k, v in files.items() if "/boat/r/" not in k} == TB.PACK, "the rest of the pack changed with the ground"


# Without it the band map (or a row) calls shallows, a lake or open sea by the wrong name at the places a boater meets
# them: 40 blocks off the island is shallows, 126 blocks north of it open, far out deep, and the lake inside the ring
# (below sea level, ringed by land) not sea at all, however far from its shore.
@pytest.mark.parametrize("x,z,want", [(2440.5, 2350.5, 0), (2350.5, 2174.5, 1), (1000.5, 1000.5, 2), (2800.5, 2800.5, 0),
                                      (-500.5, -300.5, 2), (2350.5, 2350.5, 0)],
                         ids=["shallows by the island", "open water north of it", "the deep", "the ringed lake",
                              "west of the origin", "on the island"])
def test_the_rows_name_the_places_a_boater_meets(boated, x, z, want):
    assert expected_band(x, z) == want, (x, z, expected_band(x, z))
    cx, cz = cell_of(x, z)
    assert rows_of(boated[1]).get((cz, cx), 0) == want


# ------------------------------------------------------------------------------------------------ the check, run

def ride(fns, files, x, z, vehicle="minecraft:boat", water=TSE.DEEP, fat=500):
    """One swim sample (surface/tick) as a player riding `vehicle` at x, z over `water`."""
    s = TSE._swim(water=water, x=x, z=z, vehicle=vehicle, fat=fat, samples=0, fns=fns, pack=files)
    s.call("surface/tick")
    assert not s.missing, s.missing
    return s


def tipped(s):
    return "ride @s dismount" in s.log


def sheltered(x, z):
    """In a sheltered box of the data: the 0.6-wide hitbox meets the box's blocks [x0, x1 + 1) (vanilla volume)."""
    return any(b["box"][0] - 0.3 < x < b["box"][2] + 1 + 0.3 and b["box"][1] - 0.3 < z < b["box"][3] + 1 + 0.3
               for b in BOATS_CFG["sheltered"])


POINTS = {"shallows by the island": (2440.5, 2350.5), "open water north of the island": (2350.5, 2174.5),
          "the deep": (1000.5, 1000.5), "the ringed lake": (2800.5, 2800.5), "west of the origin": (-500.5, -300.5)}


# Without it a boat crosses rough sea (the owner: "A boat should not defeat swimming, exhaustion and the ferry"), or is
# swamped in the shallows, on a lake or on a river, where WATER_PROPOSAL option C keeps boats. A rider is put out of a
# boat or a chest boat exactly where the band map says rough water (open or deep) and no sheltered box says otherwise,
# and is told why.
@pytest.mark.parametrize("vehicle", ["minecraft:boat", "minecraft:chest_boat"])
@pytest.mark.parametrize("where", sorted(POINTS))
def test_rough_water_tips_a_boat_rider_out_and_shallows_and_lakes_do_not(boated, where, vehicle):
    files, fns = boated
    x, z = POINTS[where]
    s = ride(fns, files, x, z, vehicle)
    rough = expected_band(x, z) > 0 and not sheltered(x, z)
    assert tipped(s) == rough, (where, s.log)
    msg = [l for l in s.log if l.startswith("title @s actionbar ")]
    if rough:
        assert msg and json.loads(msg[0][len("title @s actionbar "):])["text"] == BOATS_CFG["message"], msg
        assert not s.state["riding"]
    else:
        assert not msg and s.state["riding"]
        assert s.get("@s", "bo.fat") == 500 - TSE.REC, "a boat rider on boat water recovers"


# Without it the rule reaches a player riding a water Pokemon (the ride that ends fatigue, WATER_BUILD_PLAN 11.2 item 3):
# only a boat's rider is tipped out; a ridden Pokemon over the deep is never dismounted and its rider recovers.
@pytest.mark.parametrize("where", sorted(POINTS))
def test_a_ridden_pokemon_is_not_a_boat(boated, where):
    files, fns = boated
    s = ride(fns, files, *POINTS[where], vehicle="cobblemon:pokemon")
    assert not tipped(s) and s.state["riding"], s.log
    assert s.get("@s", "bo.fat") == 500 - TSE.REC
    assert not [c for c in s.calls if c[0].startswith("boat/")], s.calls


# Without it a boat rider on rough water is never tipped out: a rider sits with the feet above the water, so a check
# placed after the "feet not in water" return would never run for them (data/blackout.json boats; surface/tick runs the
# boat check first).
def test_the_boat_check_runs_for_a_rider_whose_feet_are_dry(boated):
    files, fns = boated
    s = ride(fns, files, *POINTS["the deep"], water=TSE.LAND)
    assert tipped(s), s.log


# Without it the rider tipped out of a boat recovers for that sample instead of swimming (the rule: "is put out of it
# with the message ... then the swim rule applies"): after the dismount surface/tick re-stores `on vehicle`, which
# with no vehicle stores nothing (the simulator's reading of vanilla), so #ride must be reset first or it keeps the 1
# the boat set and the sample recovers. Found by this suite at 361c9cf; fixed in 0f190dd.
def test_a_rider_tipped_out_swims_in_the_same_sample(boated):
    files, fns = boated
    s = ride(fns, files, *POINTS["the deep"])
    assert tipped(s)
    assert s.get("@s", "bo.fat") > 500, s.get("@s", "bo.fat")


# ------------------------------------------------------------------------------------------------ the sheltered water

# Without it the sheltered water is not the data's (a box shifted or grown, or a data box the pack forgot): the check's
# selector volumes are exactly the data's sheltered boxes, in the data's order, each over the full height.
def test_the_sheltered_volumes_are_exactly_the_datas_boxes():
    got = [tuple(int(v) for v in m.groups()) for l in TB.FNS["boat/check"] for m in [SHELTER.fullmatch(l)] if m]
    want = [(b["box"][0], b["box"][1], b["box"][2] - b["box"][0], b["box"][3] - b["box"][1]) for b in BOATS_CFG["sheltered"]]
    assert got == want, (got, want)
    body = [l for l in TB.FNS["boat/check"] if not l.startswith("#")]
    first_shelter = next(i for i, l in enumerate(body) if SHELTER.fullmatch(l))
    assert body.index("ride @s dismount") > first_shelter, "a rider is dismounted before the sheltered boxes are tested"


def _edges():
    out = []
    for b in BOATS_CFG["sheltered"]:
        x0, z0, x1, z1 = b["box"]
        mx, mz = (x0 + x1) // 2 + 0.5, (z0 + z1) // 2 + 0.5
        out += [(b["id"] + " inside, west edge", x0 + 0.5, mz, False), (b["id"] + " inside, east edge", x1 + 0.5, mz, False),
                (b["id"] + " inside, north edge", mx, z0 + 0.5, False), (b["id"] + " inside, south edge", mx, z1 + 0.5, False),
                (b["id"] + " one block west", x0 - 0.5, mz, True), (b["id"] + " one block east", x1 + 1.5, mz, True),
                (b["id"] + " one block north", mx, z0 - 0.5, True), (b["id"] + " one block south", mx, z1 + 1.5, True)]
    return out


# Without it a boat is swamped inside the Sound's bay (Pacifidlog's boat culture, the jetty's rack; WATER_PROPOSAL 4.3:
# "the Sound is sheltered water"), or the shelter leaks past the box into the open sea south of it ("The open sea south
# of z6992 stays rough"). The synthetic ground puts the box far out at sea, so only the box decides: every block of
# its edge keeps the boat, the block beyond each edge tips it.
@pytest.mark.parametrize("what,x,z,tips", _edges(), ids=[e[0] for e in _edges()])
def test_a_sheltered_box_keeps_its_boats_to_its_edge(boated, what, x, z, tips):
    files, fns = boated
    assert expected_band(x, z) > 0, "the synthetic ground must make the box rough water"
    assert tipped(ride(fns, files, x, z)) == tips, what


# Without it the row lookup reads the wrong cell: the check turns the feet into a cell as floor((x + 1024) / 16), the
# band map's own indexing (cell 0 at the world's west edge), so the first and last block of every run of rough cells in
# a row is rough and the block before the run (a shallows cell) is not.
def test_the_check_finds_the_cell_the_band_map_indexes(boated):
    files, fns = boated
    rows = rows_of(fns)
    runs = []
    for (cz, cx), v in sorted(rows.items()):
        if (cz, cx - 1) not in rows and cz in (cell_of(0, 2174)[1], cell_of(0, 2560)[1]):
            runs.append((cz, cx, v))
    assert runs
    for cz, cx, v in runs:
        z = WORLD_MIN + cz * CELL + 7.5
        for x, want in ((WORLD_MIN + cx * CELL + 0.01, v), (WORLD_MIN + (cx + 1) * CELL - 0.01, rows.get((cz, cx), 0)),
                        (WORLD_MIN + cx * CELL - 0.01, 0)):
            if sheltered(x, z):
                continue
            s = TSE._sim(fns=fns, pack=files)
            s.state.update(x=x, z=z, riding=True, vehicle="minecraft:boat")
            s.call("boat/check")
            assert s.get("@s", "bo.zone") == want, (x, z, want, s.get("@s", "bo.zone"))


# Without it a boat in a pack whose boats tag lists something else (a raft type from a later version, a Pokemon) is
# judged wrongly: the tag the check tests is the pack's own, holding exactly vanilla 1.21.1's two boat entity types.
def test_the_boats_tag_is_vanillas_two_boat_types():
    tag = json.loads(TB.PACK["data/%s/tags/entity_type/boats.json" % NS])
    assert tag == {"values": ["minecraft:boat", "minecraft:chest_boat"]}, tag
    tick = [l for l in TB.FNS["surface/tick"] if not l.startswith("#")]
    assert "execute store success score #boat bo.tmp on vehicle if entity @s[type=#%s:boats]" % NS in tick


# ------------------------------------------------------------------------------------------------ the real band map

@pytest.fixture(scope="module")
def real_bands():
    import terrain as T
    try:
        g = GROUND.Ground()
    except (T.TerrainUnavailable, FileNotFoundError, OSError) as e:
        pytest.skip("NOT_EXECUTED: the canonical heightmap is unavailable (%s); set COBBLERS_SOURCE_ROOT" % e)
    return OW.bands(BOATS_CFG["rough_blocks"], BOATS_CFG["deep_blocks"], ground=g)


# Without it a boat on a row with no rough cell calls boat/r/<z> for a row the pack never wrote (an unknown function:
# the check fails with an error instead of passing): on the real band map every cell row of the playable world holds
# rough water (the 1024-block sea margin), so main() writes every row.
@pytest.mark.slow
def test_every_cell_row_of_the_world_has_a_boat_row(real_bands):
    rough = real_bands["open"] | real_bands["deep"]
    n = (9215 - WORLD_MIN + 1) // CELL
    assert rough.shape == (n, n)
    assert all(rough[z].any() for z in range(n)), [z for z in range(n) if not rough[z].any()][:5]


# Without it the sheltered box misses the pocket it exists for, or shelters water the data says stays rough: the data
# measured the Sound bay's rough pocket at cells x6976-7151 z6880-6976 on the band map; every rough cell there lies in
# the box, and every rough cell the box's rows touch outside the box is south of it (the open sea, which stays rough).
@pytest.mark.slow
def test_the_sheltered_box_holds_the_sounds_rough_pocket(real_bands):
    rough = real_bands["open"] | real_bands["deep"]
    (box,) = [b["box"] for b in BOATS_CFG["sheltered"] if b["id"] == "pacifidlog_bay"]
    cx0, cz0 = cell_of(6976, 6880)
    cx1, cz1 = cell_of(7151, 6976)
    pocket = {(cz, cx) for cz in range(cz0, cz1 + 1) for cx in range(cx0, cx1 + 1) if rough[cz, cx]}
    assert len(pocket) >= 10, "the measured pocket holds no rough water any more: re-measure"
    for cz, cx in pocket:
        x, z = WORLD_MIN + cx * CELL, WORLD_MIN + cz * CELL
        assert box[0] <= x and x + CELL - 1 <= box[2] and box[1] <= z and z + CELL - 1 <= box[3], (cx, cz)
    bx0, bz0 = cell_of(box[0], box[1])
    bx1, bz1 = cell_of(box[2], box[3])
    for cz in range(bz0 - 1, bz1 + 1):
        for cx in range(bx0 - 3, bx1 + 4):
            inside = bx0 <= cx <= bx1 and bz0 <= cz <= bz1
            if rough[cz, cx] and not inside:
                raise AssertionError("rough cell (%d, %d) beside the bay, outside the box" % (cx, cz))
