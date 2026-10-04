"""tools/mega_field_audit.py: the Mega field's independent audit, and proof that each check bites a broken GENERATOR.

Written by an agent that did not build the field (tools/mega_field.py, the keeper in tools/gulch_mine.py, the lairs in
tools/mega_dens.py). Per CLAUDE.md "How to prove an audit is independent", every mutation below changes the
generator's CODE or how it reads a value (a function wrapped or replaced with monkeypatch) and leaves
data/gulch_mine.json and data/mega_dens.json untouched; the audit then sees the generator's output.

The synthetic tests at the top need nothing; the rest need the canonical heightmap (tools/ground.py) and
derived/rift_sculpt/ (basin.npy, plan.json); a skip names what is missing.

NOT covered (runtime, EXP-054): a Mega spawning and standing at its anchor, hostility, a roll after a real win, the
owner-only pickup, R9SX's forceload loading the retired Megas in its 5 s wait, megas/watch's tick cost.
"""
import copy
import json
import re
import sys
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import mega_field_audit as A  # noqa: E402

SPEC = json.loads((ROOT / "data" / "gulch_mine.json").read_text(encoding="utf-8"))
REC = json.loads((ROOT / "data" / "mega_dens.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------- synthetic fixtures
def _toy_area(field_x0):
    """A 40 x 20 basin (x 100..139, z 100..119); the gulch zone east of it from x 140; the field from field_x0 to 140."""
    B = np.zeros((60, 80), bool)                         # origin (80, 80)
    B[100 - 80:120 - 80, 100 - 80:140 - 80] = True
    zone = [[140, 95], [170, 95], [170, 125], [140, 125]]
    spec = {"zone": {"polygon": zone},
            "mega_field": {"polygon": [[field_x0, 97], [140, 97], [140, 123], [field_x0, 123]],
                           "trace": {"cut_near": [140, 95], "rim_outset": 3, "tolerance": 1.5}}}
    D = {"cursor": (110, 110), "sites": [(120, 105), (130, 115)]}
    return spec, (B, (80, 80)), D


# Without it the area check could pass a field that leaves floor out: a polygon 3 outside a toy basin is clean, and the
# same polygon pulled in to x 101 leaves exactly the basin's x 100 column (20 columns, z 100..119) outside.
def test_the_area_check_counts_the_floor_left_outside_on_a_toy_basin():
    spec, basin, D = _toy_area(97)
    R = A.Report()
    A.check_area(spec, basin, D, R)
    assert R.errors == []
    spec, basin, D = _toy_area(101)
    R = A.Report()
    A.check_area(spec, basin, D, R)
    assert any(e.startswith("area: 20 basin column(s) of the field's floor are outside") for e in R.errors), R.errors


# Without it a polygon that runs far past the floor (here 9 out, beyond rim_outset 3 + tolerance 1.5) passes.
def test_the_area_check_refuses_a_polygon_far_past_the_floor_on_a_toy_basin():
    spec, basin, D = _toy_area(91)
    R = A.Report()
    A.check_area(spec, basin, D, R)
    assert any("more than 4 (rim_outset + tolerance)" in e for e in R.errors), R.errors


# Without it the level check would use a cap that is not rctmod's: gyms topping at 10, 20 .. 80, four at 85 and a
# champion at 90 give a cap of 85 with 8 badges (the next trainer is the first of the four), 80 with 7, 100 after all.
def test_the_cap_is_rctmods_rule_on_a_toy_league(tmp_path):
    def t(cls, order, top):
        return {"id": "%s_%d" % (cls, order), "class": cls, "order": order, "team": [{"level": top - 1}, {"level": top}]}
    tr = [t("gym_leader", i, 10 * i) for i in range(1, 9)] + [t("elite_four", i, 85) for i in range(1, 5)]
    tr.append(t("champion", 1, 90))
    (tmp_path / "trainers.json").write_text(json.dumps({"trainers": tr}), encoding="utf-8")
    toml = tmp_path / "rct.toml"
    toml.write_text("initialLevelCap = 20\nrelativeLevelCap = 0\n", encoding="utf-8")
    caps = A.cap_table(tmp_path, toml)
    assert (caps[0], caps[1], caps[7], caps[8], caps[12], caps[13]) == (20, 20, 80, 85, 90, 100)


# Without it the audit would read its expectations from somewhere else than the owner's text: these are section 13's
# numbers as written (cap 50, outer 60 at 15% for 10 min, deeper 67 at 30% for 15 min, 2 raw stones).
def test_the_design_is_read_from_section_13():
    D = A.design()
    assert D["sites"] == [(4090, 5289), (3738, 5164)] and D["cursor"] == (3967, 5037)
    assert D["tiers"]["field_outer"] == {"offset": 10, "pct": 15, "ticks": 12000}
    assert D["tiers"]["field_deeper"] == {"offset": 17, "pct": 30, "ticks": 18000}
    assert (D["raw"], D["price"]) == ("mega_showdown:mega_stone", 2)
    assert {"aggron", "gengar", "swampert"} <= D["broken"]


def _toy_dens(*homes, leash=36):
    dens = [{"id": "d%d" % i, "species": "s%d" % i, "anchor": [x, 65, z], "leash": leash, "tier": "t"}
            for i, (x, z) in enumerate(homes)]
    return {"farms": [{"id": "field_toy", "dens": dens}]}


# Without it a den standing alone would pass as crowded, or two dens could share a home. Homes at x 0, 50 and 150 with
# ranges of 36: 0 and 50 overlap by 72 - 50 = 22; the den at 150 is 100 from its nearest and overlaps nothing. A fourth
# home at x -20 is inside the first den's range (20 <= 36) and 70 from the second.
def test_crowding_names_the_den_whose_range_overlaps_nothing_on_toy_homes():
    R = A.Report()
    pairs = A.check_crowding(_toy_dens((0, 0), (50, 0), (150, 0)), R)
    assert [(a["id"], b["id"], s, o) for a, b, s, o in pairs] == [("d0", "d1", 50.0, 22.0)]
    assert R.errors == ["crowding: d2: its range overlaps no other den's: the nearest, d1, is 100.0 away and the two "
                        "ranges reach 72"]
    R = A.Report()
    A.check_crowding(_toy_dens((0, 0), (50, 0), (-20, 0)), R)
    assert R.errors == ["crowding: d0 and d2 are 20.0 apart: one's range (36) reaches the other's home"]
    # the declared depth: d0 and d1 overlap 22, enough at layout.min_overlap 22 and a sliver for both at 23
    for need, errs in ((22, []), (23, ["crowding: d%d: its deepest overlap with another den's range is 22.0, under "
                                       "layout.min_overlap 23" % i for i in (0, 1)])):
        spec = _toy_dens((0, 0), (50, 0))
        spec["mega_field"] = {"layout": {"min_overlap": need}}
        R = A.Report()
        A.check_crowding(spec, R)
        assert R.errors == errs


class _ToyGround:
    """Ground y64 everywhere except one column at (5, 5), raised to y67."""

    def __call__(self, x, z):
        return 67 if (x, z) == (5, 5) else 64

    def box(self, x0, z0, x1, z1):
        H = np.full((z1 - z0 + 1, x1 - x0 + 1), 64)
        if x0 <= 5 <= x1 and z0 <= 5 <= z1:
            H[5 - z0, 5 - x0] = 67
        return H


# Without it the coverage would be counted on a floor that includes steps. The 10 x 10 polygon holds columns 0..9; the
# 3-block step at (5, 5) takes it and its four neighbours, so 95 are usable. A den at (2, 2) with range 3 covers the
# columns whose centres are within 3 of (2, 2): x and z 0..4 less (4, 4), at 2.5 and 2.5 (3.54), so 24.
def test_the_usable_floor_and_its_coverage_on_a_toy_field():
    spec = _toy_dens((2, 2), leash=3)
    spec["mega_field"] = {"polygon": [[0, 0], [10, 0], [10, 10], [0, 10]], "layout": {"roster": [["s0", "m"]]}}
    R = A.Report()
    (_x0, _z0), floor, cov = A.check_floor(spec, _ToyGround(), R)
    assert (int(floor.sum()), int(cov.sum())) == (95, 24)
    assert R.notes[0].startswith("floor: 95 usable columns (inside the polygon, dry, no step over one block); the 1 "
                                 "dens' ranges cover 24 of them (25.3%)"), R.notes


def _toy_borders(kill_min=22):
    """Two dens 50 apart on z 0 (ranges 36 overlap 22, the lens x 14..36), flat ground y64, one built border."""
    spec = _toy_dens((0, 0), (50, 0))
    spec["mega_field"] = {"polygon": [[-60, -60], [110, -60], [110, 60], [-60, 60]]}
    spec["zone"] = {"polygon": [[500, 500], [510, 500], [510, 510], [500, 510]]}
    spec["grid"] = {"x": [500, 510], "z": [500, 510]}
    bdoc = {"blocks": {"ids": ["minecraft:gravel", "minecraft:podzol", "minecraft:snow_block", "minecraft:stone",
                               "minecraft:skeleton_skull", "minecraft:bone_block"]},
            "scar": {"minecraft:gravel": 1}, "rubble": {"loose_blocks": ["minecraft:stone"]},
            "kill": {"min_overlap": kill_min}, "keep": {"anchor_clear": 9, "lair_clear": 2}, "coverage_cap": 0.5,
            "max_rise": 2}
    rec = {"dens": [{"den": "d0", "scrape": {"minecraft:podzol": 1}, "boulder": ["minecraft:stone"]},
                    {"den": "d1", "scrape": {"minecraft:snow_block": 1}, "boulder": ["minecraft:stone"]}]}
    lines = ["setblock 20 64 0 minecraft:podzol",            # a's side (20.5 from a, 29.5 from b), a's own scrape
             "setblock 30 64 0 minecraft:snow_block",         # b's side, b's own
             "setblock 25 64 1 minecraft:gravel",             # the shared scar
             "setblock 25 65 2 minecraft:stone",              # broken rock above the scar
             "setblock 26 65 0 minecraft:skeleton_skull"]     # the carcass: overlap 22 >= 22
    floor = ((0, 0), np.ones((1, 1), bool), np.ones((1, 100), bool))     # 100 usable columns in range
    marks = {"route": [], "built": [], "towns": [], "wet": lambda x, z: False, "spawn": {"minecraft:sand"},
             "white": set()}
    return spec, bdoc, {"d0__d1": lines}, rec, floor, marks


def _toy_check(spec, bdoc, fns, rec, floor, marks, lair_cols=()):
    R = A.Report()
    A.check_borders(spec, bdoc, fns, rec, set(lair_cols), _ToyGround(), floor, R, marks)
    return R.errors


# Without it the border checks could pass anything. The toy border is clean as built; each change below breaks one
# rule the owner's brief or data/mega_borders.json states, and the error names it: a scar column at x 12 is 37.5 from
# b's home (outside b's range of 36); snow (b's own scrape) at x 20 is on a's side; a carcass on a border overlapping
# 22 when the threshold is 23; sand, a spawn condition; a block 3 above ground (max_rise 2); a lair column 2 away.
def test_the_border_rules_on_a_toy_border():
    spec, bdoc, fns, rec, floor, marks = _toy_borders()
    assert _toy_check(spec, bdoc, fns, rec, floor, marks) == []
    f2 = {"d0__d1": fns["d0__d1"] + ["setblock 12 64 0 minecraft:gravel"]}
    assert _toy_check(spec, bdoc, f2, rec, floor, marks) == [
        "borders: d0__d1: 1 of its 6 columns lie outside the overlap of the two ranges (not inside both), e.g. (12, 0)"]
    f3 = {"d0__d1": [l.replace("setblock 20 64 0 minecraft:podzol", "setblock 20 64 0 minecraft:snow_block")
                     for l in fns["d0__d1"]]}
    errs = _toy_check(spec, bdoc, f3, rec, floor, marks)
    assert len(errs) == 2 and "take the OTHER den's own scrape block on this den's side, e.g. ((20, 0), " in errs[0]
    assert errs[1] == "borders: d0__d1: no scar column on d0's side is from its own scrape palette"
    _s, bdoc23, *_r = _toy_borders(kill_min=23)
    assert _toy_check(spec, bdoc23, fns, rec, floor, marks) == [
        "borders: d0__d1: ranges overlap only 22.0, under kill.min_overlap 23, and it carries a kill"]
    nokill = {"d0__d1": fns["d0__d1"][:-1]}
    assert _toy_check(spec, bdoc, nokill, rec, floor, marks) == [
        "borders: d0__d1: ranges overlap 22.0 (kill.min_overlap 22) and it carries 0 carcass skull(s), not one"]
    sand = dict(bdoc, blocks={"ids": bdoc["blocks"]["ids"] + ["minecraft:sand"]})
    f4 = {"d0__d1": fns["d0__d1"] + ["setblock 24 65 0 minecraft:sand"]}
    assert any("writes ['minecraft:sand'], a spawn condition" in e for e in _toy_check(spec, sand, f4, rec, floor, marks))
    f5 = {"d0__d1": fns["d0__d1"] + ["setblock 24 67 0 minecraft:stone"]}
    assert _toy_check(spec, bdoc, f5, rec, floor, marks) == [
        "borders: d0__d1: 1 block(s) off round(ground) .. +2, e.g. (24, 67, 0) (ground y64)"]
    assert _toy_check(spec, bdoc, fns, rec, floor, marks, lair_cols=[(27, 1)]) == [
        "borders: d0__d1 writes 2 column(s) within lair_clear 2 of a column a lair writes, e.g. (25, 1)"]
    # nothing built for an overlapping pair, and a border for a pair whose ranges do not meet
    assert _toy_check(spec, bdoc, {}, rec, floor, marks) == [
        "borders: d0 and d1 overlap 22.0 blocks and no border is built between them"]
    far = _toy_dens((0, 0), (80, 0))
    far.update({k: spec[k] for k in ("mega_field", "zone", "grid")})
    assert _toy_check(far, bdoc, fns, rec, floor, marks) == [
        "borders: border d0__d1 is built between two dens whose ranges do not overlap"]


# Without it the borders could swallow the field: 5 written columns against 100 usable in range is 5%; a cap of 4%
# refuses it, and the error carries both counts.
def test_the_border_coverage_cap_on_a_toy_border():
    spec, bdoc, fns, rec, floor, marks = _toy_borders()
    errs = _toy_check(spec, dict(bdoc, coverage_cap=0.04), fns, rec, floor, marks)
    assert errs == ["borders: the borders write 5 columns, 5.0% of the 100 usable columns inside a range: over "
                    "coverage_cap 4.0%"]


# Without it a border could write nothing where its overlap has ground to dress, and pass. Two dens at (0, 0) and
# (4, 0), ranges 3, overlap 2: the columns whose centres lie in both ranges are x 1..2, z -2..1 (8). anchor_clear 1.5
# takes (1, -1), (1, 0) and (1, 1), each within 1.5 of (0, 0), leaving 5, the first (1, -2): an empty border is a
# problem. With anchor_clear 9, or no usable floor under the lens, no column is free and an empty border is right.
def test_an_empty_border_is_right_only_where_its_lens_has_no_free_column():
    spec = _toy_dens((0, 0), (4, 0), leash=3)
    spec["mega_field"] = {"polygon": [[-60, -60], [110, -60], [110, 60], [-60, 60]]}
    spec["zone"] = {"polygon": [[500, 500], [510, 500], [510, 510], [500, 510]]}
    spec["grid"] = {"x": [500, 510], "z": [500, 510]}
    _s, bdoc, _f, _r, _fl, marks = _toy_borders()
    rec = {"dens": [{"den": "d0", "scrape": {}, "boulder": []}, {"den": "d1", "scrape": {}, "boulder": []}]}
    fns = {"d0__d1": ["# This lens has no ground to dress. It writes nothing."]}
    floor = ((-10, -10), np.ones((21, 21), bool), np.ones((21, 21), bool))
    tight = dict(bdoc, keep={"anchor_clear": 1.5, "lair_clear": 0})
    errs = _toy_check(spec, tight, fns, rec, floor, marks)
    assert errs == ["borders: d0__d1 writes nothing, but its lens (overlap 2.0) has 5 free dressing column(s), e.g. "
                    "(1, -2): in both ranges, on the usable floor, clear of every anchor, lair, other border and "
                    "footprint rule"]
    assert _toy_check(spec, dict(bdoc, keep={"anchor_clear": 9, "lair_clear": 0}), fns, rec, floor, marks) == []
    bare = ((-10, -10), np.zeros((21, 21), bool), np.ones((21, 21), bool))
    assert _toy_check(spec, tight, fns, rec, bare, marks) == []
    # and R9MB runs an empty border once, with nothing held
    R = A.Report()
    A.check_border_steps({"d0__d1": []}, [("fn", "cobblers:mega_borders/d0__d1")], R)
    assert R.errors == []


# Without it R9MB could skip a border, run one outside its hold, or leave a chunk loaded.
def test_the_r9mb_steps_on_toy_borders():
    cols = {"d0__d1": [(20, 0), (30, 0)]}
    good = [("cmd", "forceload add 20 0 30 0"), ("wait", 3), ("fn", "cobblers:mega_borders/d0__d1"),
            ("cmd", "forceload remove 20 0 30 0")]
    R = A.Report()
    A.check_border_steps(cols, good, R)
    assert R.errors == []
    R = A.Report()
    A.check_border_steps(cols, [("cmd", "forceload add 20 0 29 0")] + good[1:3] + [("cmd", "forceload remove 20 0 29 0")], R)
    assert R.errors == ["order: R9MB runs d0__d1 with no hold covering every column it writes"]
    R = A.Report()
    A.check_border_steps(cols, good[:3], R)
    assert R.errors == ["order: R9MB leaves 1 hold(s) of 1 unreleased"]
    R = A.Report()
    A.check_border_steps(cols, [], R)
    assert R.errors == ["order: R9MB runs border d0__d1 0 time(s), not once"]


# ------------------------------------------------------------------------------------------- the real inputs
@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.load()
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


@pytest.fixture(scope="module")
def basin():
    if not (A.SCULPT / "basin.npy").is_file() or not (A.SCULPT / "plan.json").is_file():
        pytest.skip("no derived/rift_sculpt/basin.npy and plan.json (tools/rift_heightmap.py --apply's outputs)")
    return A.load_basin()


def gulch_fns(spec):
    import gulch_mine as GM
    m = copy.deepcopy(spec)
    for s in m["megas"]["slots"]:                       # the mine's slots need a hall floor; the field's dens do not
        s["_anchor"] = [s["anchor"][0], 47, s["anchor"][1]]
    model = types.SimpleNamespace(spec=m)
    fns = dict(GM.cutter_files(model))
    fns.update(GM.keeper_files(model))
    cb = GM.callback_files(m)
    return fns, next(iter(cb.values()), "")


def lair_fns(ground):
    import mega_dens as M
    doc, dens = M.load()
    written, _ds = M.files(doc, dens, ground)
    lairs = {Path(k).stem: v.splitlines() for k, v in written.items() if k.endswith(".mcfunction")}
    return lairs, M.placement_steps(doc, dens, ground)


@pytest.fixture(scope="module")
def lairs(ground):
    return lair_fns(ground)


BDOC = json.loads((ROOT / "data" / "mega_borders.json").read_text(encoding="utf-8"))
_COMMITTED_BORDERS = {}   # the unmutated generator's borders for the committed data, built once


def border_fns(spec, ground):
    """tools/mega_borders.py's OUTPUT for `spec`: the built functions {"<a>__<b>": lines} and R9MB's steps."""
    import mega_borders as MB
    bds, _cov = MB.plan(gm=spec, g=ground)
    files = MB.files(bds)
    fns = {Path(k).stem: v.splitlines() for k, v in files.items() if k.endswith(".mcfunction")}
    return fns, MB.placement_steps(bds)


def committed_borders(ground):
    """The unmutated generator's borders for the committed data. A test whose subject is not the borders (the polygon's
    trace, a den's site) passes these, so it pays for one plan, not two; the borders it is then audited with do not
    match its mutated dens, which adds border errors its assertions do not look at. (Regenerating them is not just
    slower: with road_clear read as 100, tools/mega_borders.py's placement_steps crashes in Border.box on a border that
    found no column to write -- a generator defect, reported, not exercised by the committed layout.)"""
    if "b" not in _COMMITTED_BORDERS:
        _COMMITTED_BORDERS["b"] = border_fns(SPEC, ground)
    return _COMMITTED_BORDERS["b"]


def run(spec, ground, basin, lairs, with_order=False, borders=None):
    import gulch_mine as GM
    fns, cb = gulch_fns(spec)
    names = src = None
    if with_order:
        import reapply
        names = [n for n, _f in reapply.prepare_jobs(types.SimpleNamespace(source_root="", server_dir=""))]
        src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    if borders is None and spec is SPEC:
        borders = committed_borders(ground)
    bf, r9mb = borders or border_fns(spec, ground)
    return A.audit(spec, ground, basin, fns, cb, REC, lairs[0], GM.retire_steps(spec), lairs[1], src, names,
                   borders=(BDOC, bf, r9mb))


FLOOR = "basin column(s) of the field's floor are outside mega_field.polygon"

# The findings the audit raises on the committed layout that the builder owns (KNOWN, reported, not fixed here). Each
# gets a strict xfail that turns red when it is fixed, so this list is shortened rather than left to hide a new fault of
# the same shape. EMPTY since 2026-10-04's per-den field: the two findings of the species-keyed layout are closed --
# the lone steelix and charizard dens (now each den has a neighbour or is dropped) and the border tips 0.75 outside a
# range (tools/mega_borders.py Border.inside). tools/mega_field_audit.py main() carries the same list.
KNOWN = ()


def unknown(rep):
    return [e for e in rep.errors if FLOOR not in e and not any(k.search(e) for k in KNOWN)]


def left_out(rep):
    m = [re.search(r"area: (\d+) " + re.escape(FLOOR), e) for e in rep.errors]
    return max([int(x.group(1)) for x in m if x] or [0])


@pytest.fixture(scope="module")
def committed(ground, basin, lairs):
    return run(SPEC, ground, basin, lairs, with_order=True)


# Without it the field, keeper, retirement, lairs, borders and step order would be unaudited: every check but the
# KNOWN findings above is clean on the committed data and the generators' output.
def test_the_committed_field_passes_every_check_but_the_known_findings(committed):
    assert unknown(committed) == []


# Finding 1, FIXED 2026-10-04 (the per-den field gives a lone den a neighbour or drops it). Without it a den standing
# alone, with nothing pressing on its range, would pass as "crowded".
def test_every_dens_range_overlaps_another_dens(committed):
    assert not [e for e in committed.errors if "its range overlaps no other den's" in e]


# Finding 2, FIXED 2026-10-04 (tools/mega_borders.py Border.scar keeps a block inside both ranges). Without it a
# border could be dressed where only one Mega ranges, not where two meet.
def test_every_border_column_lies_inside_both_ranges(committed):
    assert not [e for e in committed.errors if "lie outside the overlap of the two ranges" in e]


# Without it the owner's "overlapping ranges" and the floor they cover would go unreported: the audit states the
# overlapping pairs and their overlaps, the usable floor and the fraction inside a range, and the borders, kills and
# their share of that floor (per-den field, 2026-10-04: 27 dens, 45 pairs 1.3..28.0, 18.4% of 449,577 usable columns,
# 45 borders, 19 kills, 5,563 columns = 6.7% of the floor in range against the 8% cap, none empty).
def test_the_committed_crowding_and_floor_are_reported(committed):
    notes = "\n".join(committed.notes)
    assert re.search(r"^crowding: \d+ dens, [1-9]\d* overlapping pairs, overlaps [\d.]+\.\.[\d.]+ blocks", notes, re.M)
    assert re.search(r"^floor: [1-9]\d* usable columns .* cover \d+ of them \([\d.]+%\)", notes, re.M)
    assert re.search(r"^borders: [1-9]\d* built, \d+ kills, \d+ columns written", notes, re.M)


# The finding this audit raised (2026-10-03): 14 basin columns at three corners, (4185, 4931), (4040, 5359) and
# (4146, 5378), lay outside mega_field.polygon although mega_field.trace.why says no basin column at the cliff's foot is
# left out. Closed in mega_field.py trace (lip vertices kept, and set square to the ring where the normal slid along it).
def test_the_committed_field_holds_its_whole_floor(committed):
    assert left_out(committed) == 0


# ------------------------------------------------------------------------------------------- generator mutations
def _sites_with(monkeypatch, change):
    """mega_field.sites wrapped: its output changed by `change`, data untouched; returns the spec the audit sees."""
    import mega_field as MF
    orig = MF.sites

    def wrapped(spec, source_root=None):
        r = orig(spec, source_root)
        change(r)
        return r
    monkeypatch.setattr(MF, "sites", wrapped)
    spec = copy.deepcopy(SPEC)
    spec["farms"] = [f for f in spec["farms"] if not f["id"].startswith("field_")] + MF.sites(SPEC)["farms"]
    return spec


def _reading(monkeypatch, fn_name, path, value):
    """mega_field.<fn_name> made to read one layout/trace value as `value` (the data file is never written)."""
    import mega_field as MF
    orig = getattr(MF, fn_name)

    def wrapped(spec, source_root=None):
        s = copy.deepcopy(spec)
        node = s
        for k in path[:-1]:
            node = node[k]
        node[path[-1]] = value
        return orig(s, source_root)
    monkeypatch.setattr(MF, fn_name, wrapped)


# Without it the area check would pass a field traced on the lip itself: trace reading rim_outset as 0 leaves far more
# of the floor outside than the committed polygon does.
def test_trace_reading_rim_outset_as_zero_is_caught(ground, basin, lairs, committed, monkeypatch):
    import mega_field as MF
    base = left_out(committed)
    _reading(monkeypatch, "trace", ["mega_field", "trace", "rim_outset"], 0)
    spec = copy.deepcopy(SPEC)
    spec["mega_field"]["polygon"] = MF.trace(SPEC)["polygon"]
    assert left_out(run(spec, ground, basin, lairs, borders=committed_borders(ground))) > max(base, 100)


# Without it a den sited off the field passes: sites' polygon test reading the field 60 blocks off where it is seats
# dens off the polygon and off the basin. (Answering "inside" everywhere would also make every lake ring "inside", since
# sites tests water with the same function.)
def test_sites_misreading_the_polygon_is_caught(ground, basin, lairs, monkeypatch):
    import mega_field as MF
    orig = MF.point_in
    # 2026-10-04: the per-den field's reach rounds keep every den on the field at the old 40-block misreading (a
    # column 40 out is cliff, which the pad refuses), and 150 seats fewer dens than the roster, which sites refuses; 60
    # the other way (point_in(x - 60)) seats 4 of 30 dens off the polygon and the basin
    monkeypatch.setattr(MF, "point_in", lambda poly, x, z: orig(poly, np.asarray(x) - 60, z))
    spec = copy.deepcopy(SPEC)
    spec["farms"] = [f for f in spec["farms"] if not f["id"].startswith("field_")] + MF.sites(SPEC)["farms"]
    rep = run(spec, ground, basin, lairs, borders=committed_borders(ground))
    assert any(e.startswith("den: ") and ("outside mega_field.polygon" in e or "not on the basin floor" in e)
               for e in rep.errors), rep.errors


# Without it a Mega spawned a block in the air (or in the ground) passes: anchor y off round(ground) + 1.
def test_sites_with_the_anchor_a_block_high_is_caught(ground, basin, lairs, monkeypatch):
    def up(r):
        for f in r["farms"]:
            for d in f["dens"]:
                d["anchor"][1] += 1
    spec = _sites_with(monkeypatch, up)
    rep = run(spec, ground, basin, lairs, borders=committed_borders(ground))
    assert any(e.startswith("den: ") and "is not round(ground) + 1" in e for e in rep.errors)


# Without it Megas could be seated by the critical path: sites reading road_clear as 100 seats dens under 128 from it.
def test_sites_reading_road_clear_as_100_is_caught(ground, basin, lairs, monkeypatch):
    import mega_field as MF
    _reading(monkeypatch, "sites", ["mega_field", "layout", "road_clear"], 100)
    spec = copy.deepcopy(SPEC)
    spec["farms"] = [f for f in spec["farms"] if not f["id"].startswith("field_")] + MF.sites(SPEC)["farms"]
    rep = run(spec, ground, basin, lairs, borders=committed_borders(ground))
    assert any(e.startswith("den: ") and "from the critical path" in e for e in rep.errors), rep.errors


# Inverted 2026-10-04: a species may hold several dens (the committed field gives lopunny, sableye, glalie and venusaur
# two each), so the property is now that a den's ID is its own. Without it the old species-keyed ids would pass, and two
# dens of one species would share one keeper tag, one clock, one lair file and one border name: sites emitting the
# pre-2026-10-04 ids (gm_mf_<species>) is named once per den that repeats a species, and never otherwise.
def test_sites_keying_dens_by_species_is_caught(ground, basin, monkeypatch):
    def by_species(r):
        for f in r["farms"]:
            for d in f["dens"]:
                d["id"] = "gm_mf_" + d["species"]
    spec = _sites_with(monkeypatch, by_species)
    fns, _cb = gulch_fns(SPEC)
    sold = re.findall(r'sell:\{id:"mega_showdown:([a-z_]+)"', "\n".join(fns.get("cutters_place") or []))
    R = A.Report()
    A.check_dens(spec, ground, basin, A.design(), R, sold)
    species = [d["species"] for _fa, d in A.field_dens(SPEC)]
    repeats = len(species) - len(set(species))
    assert repeats >= 1, "no species holds two dens: this mutation cannot bite on the committed field"
    dup = [e for e in R.errors if "is the id of two dens" in e]
    assert len(dup) == repeats, dup
    R = A.Report()
    A.check_dens(SPEC, ground, basin, A.design(), R, sold)
    assert not [e for e in R.errors if "is the id of two dens" in e]


# Without it the keeper could spawn a field Mega at a level that is not Z2's cap 60 plus the owner's offset.
def test_a_keeper_level_off_by_one_is_caught(ground, basin, lairs, monkeypatch):
    import gulch_mine as GM
    orig = GM.den_level
    monkeypatch.setattr(GM, "den_level", lambda spec, site, d: orig(spec, site, d) + 1)
    rep = run(SPEC, ground, basin, lairs)
    bad = [e for e in rep.errors if e.startswith("level: ")]
    assert len(bad) == sum(len(f["dens"]) for f in SPEC["farms"] if f["id"].startswith("field_"))


# Without it the drop chance or respawn could drift from section 13.1's per tier.
def test_a_keeper_reading_the_wrong_tier_for_drops_is_caught(ground, basin, lairs, monkeypatch):
    import gulch_mine as GM
    orig = GM.den_rules

    def every_den_outer(spec, site, d):
        if site.startswith("field_"):
            return orig(spec, site, dict(d, tier="field_outer"))
        return orig(spec, site, d)
    monkeypatch.setattr(GM, "den_rules", every_den_outer)
    rep = run(SPEC, ground, basin, lairs)
    assert any(e.startswith("drops: ") and "drop chance 15" in e for e in rep.errors)
    assert any(e.startswith("drops: ") and "respawn 12000" in e for e in rep.errors)


# Without it a farm Mega could fall in battle with no roll: the callback dropped from the pack.
def test_a_pack_without_the_battle_callback_is_caught(ground, basin, lairs, monkeypatch):
    import gulch_mine as GM
    monkeypatch.setattr(GM, "callback_files", lambda spec: {})
    rep = run(SPEC, ground, basin, lairs)
    assert any("battle_fainted callback" in e for e in rep.errors)


# Without it a retired den's Mega would be left on staging with nothing to leash or replace it.
def test_retire_forgetting_a_den_is_caught(ground, basin, lairs, monkeypatch):
    import gulch_mine as GM
    orig = GM.retired_dens
    monkeypatch.setattr(GM, "retired_dens", lambda spec: orig(spec)[:-1])
    rep = run(SPEC, ground, basin, lairs)
    assert any(e.startswith("retire: megas/retire kills") for e in rep.errors)
    assert any(e.startswith("retire: R9SX holds no box covering") for e in rep.errors)


# Without it R9SX could hold too little ground: a leashed Mega 32 out would be in an unloaded chunk and survive.
def test_r9sx_holding_less_than_the_leash_is_caught(ground, basin, lairs, monkeypatch):
    import gulch_mine as GM
    orig = GM.retired_dens
    monkeypatch.setattr(GM, "retired_dens", lambda spec: [(i, a, l - 24) for i, a, l in orig(spec)])
    rep = run(SPEC, ground, basin, lairs)
    assert any(e.startswith("retire: R9SX holds no box covering") for e in rep.errors)


# Without it a lair could make the Rift floor spawn something: one sand block in Houndoom's lair is a spawn condition.
def test_a_lair_writing_a_spawn_condition_is_caught(ground, basin, monkeypatch):
    import mega_dens as M
    orig = M.Den.build

    def sand(self):
        r = orig(self)
        if self.species == "houndoom":
            k = next(k for k, s in self.w.items() if s != "minecraft:air")
            self.w[k] = "minecraft:sand"
        return r
    monkeypatch.setattr(M.Den, "build", sand)
    rep = run(SPEC, ground, basin, lair_fns(ground))
    den = next(d["id"] for _fa, d in A.field_dens(SPEC) if d["species"] == "houndoom")
    assert any(e.startswith("lairs: %s's lair writes ['minecraft:sand']" % den) for e in rep.errors), rep.errors


# Without it the audit job could run before the packs it reads exist, or the drift check after the build it guards.
def test_prepare_out_of_order_is_caught(monkeypatch):
    import reapply
    names = [n for n, _f in reapply.prepare_jobs(types.SimpleNamespace(source_root="", server_dir=""))]
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    R = A.Report()
    A.check_order(src, names, R)
    assert R.errors == []
    moved = [n for n in names if n != "mega_field_audit"]
    moved.insert(moved.index("gulch_mine:build"), "mega_field_audit")
    R = A.Report()
    A.check_order(src, moved, R)
    assert any("mega_field_audit after" in e for e in R.errors)
    # the borders build after the lairs it keeps clear of, and the audit after the borders
    moved = [n for n in names if n != "mega_borders:build"]
    moved.insert(moved.index("mega_dens:build"), "mega_borders:build")
    R = A.Report()
    A.check_order(src, moved, R)
    assert any("mega_borders:build after mega_dens:build" in e for e in R.errors), R.errors
    # and R9MB runs between R9MD and R9E, from a pack the install carries
    R = A.Report()
    A.check_order(src.replace('"cobblers_mega_borders",', ""), names, R)
    assert R.errors == ["order: cobblers_mega_borders is not in reapply.SERVER_PACKS: the borders would never be "
                        "installed"]


# ------------------------------------------------------------------------------------------- border generator mutations
# Every mutation below changes tools/mega_borders.py's (or tools/mega_field.py's) CODE or how it reads a value, with
# data/mega_borders.json and data/gulch_mine.json untouched; the audit sees the generator's output.
def _borders_with(monkeypatch, ground, cls, name, wrap):
    """mega_borders.<cls>.<name> replaced by wrap(orig); returns (border functions, R9MB steps) built through it."""
    import mega_borders as MB
    owner = getattr(MB, cls) if cls else MB
    monkeypatch.setattr(owner, name, wrap(getattr(owner, name)))
    return border_fns(SPEC, ground)


def _border_errors(rep):
    return [e for e in unknown(rep) if e.startswith(("borders: ", "order: "))]


# Without it a border drawn beside the overlap rather than at it passes: the lens's centre moved 12 blocks toward the
# second den (inside Border.__init__) puts most of every scar inside one range only. Since 2026-10-04 the generator
# has its own guard (Border.inside), which would hide the shift from the audit; it is removed too, so what is tested is
# the audit, not the generator's guard.
def test_borders_shifted_off_the_overlap_are_caught(ground, basin, lairs, monkeypatch):
    import mega_borders as MB
    monkeypatch.setattr(MB.Border, "inside", lambda self, x, z: True)

    def wrap(orig):
        def init(self, *a, **k):
            orig(self, *a, **k)
            self.cx, self.cz = self.cx + 12 * self.ux, self.cz + 12 * self.uz
        return init
    rep = run(SPEC, ground, basin, lairs, borders=_borders_with(monkeypatch, ground, "Border", "__init__", wrap))
    bad = [e for e in rep.errors if "lie outside the overlap of the two ranges" in e]
    assert len(bad) >= 20, bad
    assert max(int(re.search(r": (\d+) of its", e).group(1)) for e in bad) > 20, bad


# Without it the 2026-10-04 finding could come back unseen: Border.inside (the builder's fix for scar tips up to 0.75
# outside one range, where the ragged edge outruns a lens already narrowed to nothing) answering True everywhere puts
# scar columns outside the overlap again, and the audit names them.
def test_borders_without_their_inside_guard_are_caught(ground, basin, lairs, monkeypatch):
    rep = run(SPEC, ground, basin, lairs,
              borders=_borders_with(monkeypatch, ground, "Border", "inside", lambda orig: lambda self, x, z: True))
    assert any("lie outside the overlap of the two ranges" in e for e in rep.errors), _border_errors(rep)


# Without it kills could be strewn on every border, not only where the ranges overlap most: Border.kill reading
# kill.min_overlap as 12 puts a carcass on the borders overlapping 12.5 to 21.9.
def test_borders_reading_the_kill_threshold_low_are_caught(ground, basin, lairs, monkeypatch):
    def wrap(orig):
        def kill(self):
            saved = self.doc
            self.doc = dict(saved, kill=dict(saved["kill"], min_overlap=12))
            try:
                orig(self)
            finally:
                self.doc = saved
        return kill
    rep = run(SPEC, ground, basin, lairs, borders=_borders_with(monkeypatch, ground, "Border", "kill", wrap))
    assert any("under kill.min_overlap 22, and it carries a kill" in e for e in rep.errors), _border_errors(rep)


# Without it a border could wear the wrong territory's colours: Border.side negated deals each side the other den's
# scrape palette.
def test_borders_with_the_sides_swapped_are_caught(ground, basin, lairs, monkeypatch):
    def wrap(orig):
        return lambda self, x, z: -orig(self, x, z)
    rep = run(SPEC, ground, basin, lairs, borders=_borders_with(monkeypatch, ground, "Border", "side", wrap))
    assert any("take the OTHER den's own scrape block on this den's side" in e for e in rep.errors), _border_errors(rep)


# Without it a border could make the Rift floor spawn something: Border.scar leaving one scar column as sand (past its
# own put() check, which refuses it).
def test_borders_writing_a_spawn_condition_are_caught(ground, basin, lairs, monkeypatch):
    def wrap(orig):
        def scar(self):
            orig(self)
            k = min(self.w)
            self.w[k] = "minecraft:sand"
        return scar
    rep = run(SPEC, ground, basin, lairs, borders=_borders_with(monkeypatch, ground, "Border", "scar", wrap))
    assert any("writes ['minecraft:sand'], a spawn condition" in e for e in rep.errors), _border_errors(rep)


# Without it the borders could rewrite the field: Border.scar reading half_width as 12 and cover as 1, with the
# generator's own coverage() answering 0 so its refusal never fires; the audit's own count is over coverage_cap.
def test_borders_over_the_coverage_cap_are_caught(ground, basin, lairs, monkeypatch):
    import mega_borders as MB
    monkeypatch.setattr(MB, "coverage", lambda ctx, gm, cols: {"range floor": 1, "written columns": 0, "fraction": 0.0})

    def wrap(orig):
        def scar(self):
            saved = self.doc
            self.doc = dict(saved, border=dict(saved["border"], half_width=12.0, cover=1.0))
            try:
                orig(self)
            finally:
                self.doc = saved
        return scar
    rep = run(SPEC, ground, basin, lairs, borders=_borders_with(monkeypatch, ground, "Border", "scar", wrap))
    assert any(e.startswith("borders: the borders write") and "over coverage_cap 8.0%" in e for e in rep.errors), \
        _border_errors(rep)


# Without it a border could write over a lair: Context forgetting the lairs' columns (self.lair emptied).
def test_borders_ignoring_the_lairs_are_caught(ground, basin, lairs, monkeypatch):
    def wrap(orig):
        def init(self, *a, **k):
            orig(self, *a, **k)
            self.lair = set()
        return init
    rep = run(SPEC, ground, basin, lairs, borders=_borders_with(monkeypatch, ground, "Context", "__init__", wrap))
    assert any("within lair_clear 2 of a column a lair writes" in e for e in rep.errors), _border_errors(rep)


# Without it R9MB could leave a border unbuilt on the world: placement_steps dropping the last border's four steps.
def test_r9mb_dropping_a_border_is_caught(ground, basin, lairs, monkeypatch):
    def wrap(orig):
        return lambda bds=None: orig(bds)[:-4]
    rep = run(SPEC, ground, basin, lairs, borders=_borders_with(monkeypatch, ground, None, "placement_steps", wrap))
    assert any(e.startswith("order: R9MB runs border") and "0 time(s), not once" in e for e in rep.errors), \
        _border_errors(rep)


# Without it the field could go back to dens standing apart: mega_field.sites emitting a leash of 21 on dens it seated
# for 36 gives ranges that touch nothing (homes lair_spacing 43 or more apart, ranges 42), and every den is named.
# (Repointed 2026-10-04: sites READING the leash as 21 now drops every den with no neighbour within 2 x 21 - 8 = 34,
# under the 43 spacing, and refuses the empty field itself, so the audit never sees it.)
def test_sites_emitting_the_leash_short_is_caught(ground, basin, lairs, monkeypatch):
    def short(r):
        for f in r["farms"]:
            for d in f["dens"]:
                d["leash"] = 21
    spec = _sites_with(monkeypatch, short)
    R = A.Report()
    A.check_crowding(spec, R)
    lonely = [e for e in R.errors if "its range overlaps no other den's" in e]
    assert len(lonely) == len(A.field_dens(spec)), lonely


# Without it the tiers could drift from the owner's "outer/deeper by distance from the town": sites reading
# deeper_from_town as 300 makes dens 300 to 399 from the square deeper than the declared 400 allows.
def test_sites_reading_the_tier_band_short_is_caught(ground, basin, lairs, monkeypatch):
    import mega_field as MF
    _reading(monkeypatch, "sites", ["mega_field", "layout", "deeper_from_town"], 300)
    spec = copy.deepcopy(SPEC)
    spec["farms"] = [f for f in spec["farms"] if not f["id"].startswith("field_")] + MF.sites(SPEC)["farms"]
    rep = run(spec, ground, basin, lairs)
    assert any(e.startswith("tiers: ") and "field_outer by deeper_from_town 400, but it is field_deeper" in e
               for e in rep.errors), [e for e in rep.errors if e.startswith("tiers")]


# Without it a den could touch its neighbours by a sliver the border cannot dress: mega_field.sites reading
# layout.min_overlap as 0 (the data still declaring 8) lets the reach rounds pull dens apart, and a den whose deepest
# overlap falls under the declared 8 is named.
def test_sites_reading_min_overlap_as_zero_is_caught(ground, basin, lairs, monkeypatch):
    import mega_field as MF
    _reading(monkeypatch, "sites", ["mega_field", "layout", "min_overlap"], 0)
    spec = copy.deepcopy(SPEC)
    spec["farms"] = [f for f in spec["farms"] if not f["id"].startswith("field_")] + MF.sites(SPEC)["farms"]
    R = A.Report()
    A.check_crowding(spec, R)
    assert any("under layout.min_overlap 8" in e for e in R.errors), R.errors


# ------------------------------------------------------------------------------------------- per-den keys (2026-10-04)
# Without it the borders could go back to being named by species, where two dens of one species collide on one name
# (or a venusaur__venusaur names one den twice): Border.__init__ naming each border by its dens' species is refused
# for every border, and every overlapping pair is then named as having none.
def test_borders_named_by_species_are_caught(ground, basin, lairs, monkeypatch):
    def wrap(orig):
        def init(self, ctx, a, b, *r, **k):
            orig(self, ctx, a, b, *r, **k)
            self.name = "%s__%s" % (a["species"], b["species"])
        return init
    rep = run(SPEC, ground, basin, lairs, borders=_borders_with(monkeypatch, ground, "Border", "__init__", wrap))
    pairs = len(A.overlaps(SPEC))
    assert pairs, "no overlapping pair: this mutation cannot bite on the committed field"
    assert sum(1 for e in rep.errors if e.endswith("and no border is built between them")) == pairs
    assert any(e.startswith("borders: border function ") and "names no two field dens" in e for e in rep.errors)


# Without it a border with ground to dress could write nothing and pass as "no ground": Border.build made to write
# nothing for the first pair's border (its lens untouched) is named, with the free columns this audit finds in it.
def test_a_border_writing_nothing_on_free_ground_is_caught(ground, basin, lairs, monkeypatch):
    import mega_borders as MB
    first = "%s__%s" % tuple(d["id"] for d in MB.borders(SPEC)[0][:2])

    def wrap(orig):
        def build(self):
            orig(self)
            if self.name == first:
                self.w, self.carcass = {}, None
            return self
        return build
    rep = run(SPEC, ground, basin, lairs, borders=_borders_with(monkeypatch, ground, "Border", "build", wrap))
    bad = [e for e in rep.errors if e.startswith("borders: %s writes nothing, but its lens" % first)]
    assert len(bad) == 1, _border_errors(rep)


# Without it a species holding several dens could be dressed once, its other dens bare or overwritten in one file:
# mega_dens.files naming each lair by its species, not its den, leaves every den without its own lair.
def test_lairs_named_by_species_are_caught(ground, basin, monkeypatch):
    import mega_dens as M
    orig = M.files
    sp_of = {r["den"]: r["species"] for r in REC["dens"]}

    def by_species(*a, **k):
        out, ds = orig(*a, **k)
        named = {}
        for path, body in out.items():
            stem = Path(path).stem
            named[path[:-len(stem) - len(".mcfunction")] + sp_of.get(stem, stem) + ".mcfunction"
                  if path.endswith(".mcfunction") else path] = body
        return named, ds
    monkeypatch.setattr(M, "files", by_species)
    rep = run(SPEC, ground, basin, lair_fns(ground))
    missing = [e for e in rep.errors if e.startswith("lairs: no built lair mega_dens/gm_mf_")]
    assert len(missing) == len(A.field_dens(SPEC)), missing
    assert any(e.startswith("lairs: built lairs for no field den: ") for e in rep.errors)
