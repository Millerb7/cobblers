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


def run(spec, ground, basin, lairs, with_order=False):
    import gulch_mine as GM
    fns, cb = gulch_fns(spec)
    names = src = None
    if with_order:
        import reapply
        names = [n for n, _f in reapply.prepare_jobs(types.SimpleNamespace(source_root="", server_dir=""))]
        src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    return A.audit(spec, ground, basin, fns, cb, REC, lairs[0], GM.retire_steps(spec), lairs[1], src, names)


FLOOR = "basin column(s) of the field's floor are outside mega_field.polygon"


def left_out(rep):
    m = [re.search(r"area: (\d+) " + re.escape(FLOOR), e) for e in rep.errors]
    return max([int(x.group(1)) for x in m if x] or [0])


# Without it the field, keeper, retirement, lairs and step order would be unaudited: every check but the floor's
# coverage is clean on the committed data and the generators' output.
def test_the_committed_field_passes_every_check_but_the_floor_coverage(ground, basin, lairs):
    rep = run(SPEC, ground, basin, lairs, with_order=True)
    assert [e for e in rep.errors if FLOOR not in e] == []


# The finding this audit raised (2026-10-03): 14 basin columns at three corners, (4185, 4931), (4040, 5359) and
# (4146, 5378), lay outside mega_field.polygon although mega_field.trace.why says no basin column at the cliff's foot is
# left out. Closed in mega_field.py trace (lip vertices kept, and set square to the ring where the normal slid along it).
def test_the_committed_field_holds_its_whole_floor(ground, basin, lairs):
    rep = run(SPEC, ground, basin, lairs)
    assert left_out(rep) == 0


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
def test_trace_reading_rim_outset_as_zero_is_caught(ground, basin, lairs, monkeypatch):
    import mega_field as MF
    base = left_out(run(SPEC, ground, basin, lairs))
    _reading(monkeypatch, "trace", ["mega_field", "trace", "rim_outset"], 0)
    spec = copy.deepcopy(SPEC)
    spec["mega_field"]["polygon"] = MF.trace(SPEC)["polygon"]
    assert left_out(run(spec, ground, basin, lairs)) > max(base, 100)


# Without it a den sited off the field passes: sites' polygon test reading the field 40 blocks west of where it is
# seats one den (of 12) off the polygon and off the basin. (Answering "inside" everywhere seats more dens than the
# roster has species, which sites itself refuses.)
def test_sites_misreading_the_polygon_is_caught(ground, basin, lairs, monkeypatch):
    import mega_field as MF
    orig = MF.point_in
    monkeypatch.setattr(MF, "point_in", lambda poly, x, z: orig(poly, np.asarray(x) + 40, z))
    spec = copy.deepcopy(SPEC)
    spec["farms"] = [f for f in spec["farms"] if not f["id"].startswith("field_")] + MF.sites(SPEC)["farms"]
    rep = run(spec, ground, basin, lairs)
    assert any(e.startswith("den: ") and ("outside mega_field.polygon" in e or "not on the basin floor" in e)
               for e in rep.errors), rep.errors


# Without it a Mega spawned a block in the air (or in the ground) passes: anchor y off round(ground) + 1.
def test_sites_with_the_anchor_a_block_high_is_caught(ground, basin, lairs, monkeypatch):
    def up(r):
        for f in r["farms"]:
            for d in f["dens"]:
                d["anchor"][1] += 1
    spec = _sites_with(monkeypatch, up)
    rep = run(spec, ground, basin, lairs)
    assert any(e.startswith("den: ") and "is not round(ground) + 1" in e for e in rep.errors)


# Without it Megas could be seated by the critical path: sites reading road_clear as 100 seats two dens 99 and 108 from
# it. (As 0 it seats more dens than the roster has species, which sites itself refuses.)
def test_sites_reading_road_clear_as_100_is_caught(ground, basin, lairs, monkeypatch):
    import mega_field as MF
    _reading(monkeypatch, "sites", ["mega_field", "layout", "road_clear"], 100)
    spec = copy.deepcopy(SPEC)
    spec["farms"] = [f for f in spec["farms"] if not f["id"].startswith("field_")] + MF.sites(SPEC)["farms"]
    rep = run(spec, ground, basin, lairs)
    assert any(e.startswith("den: ") and "from the critical path" in e for e in rep.errors), rep.errors


# Without it two dens of one species pass, and their lairs would write one file.
def test_sites_dealing_one_species_twice_is_caught(ground, basin, lairs, monkeypatch):
    def same(r):
        for f in r["farms"]:
            for d in f["dens"]:
                if d["tier"] == "field_outer":
                    d["species"] = "houndoom"
    spec = _sites_with(monkeypatch, same)
    rep = run(spec, ground, basin, lairs)
    assert any("one den per species" in e for e in rep.errors)


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
    assert any(e.startswith("lairs: houndoom's lair writes ['minecraft:sand']") for e in rep.errors), rep.errors


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
