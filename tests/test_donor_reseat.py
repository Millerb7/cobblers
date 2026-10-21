"""Re-seated donors (tools/donor_reseat.py, reapply R9DR): Newmoon Island raised to the build limit, 2026-10-20.

Written by the builder of the re-seat (one session did both; see the report), so these are the builder's checks. The
expectations are NOT taken from tools/donor_reseat.py or tools/place_donor.py geometry: the boxes are this file's own
arithmetic on the record's corner and the template size stated here as read from the NBT, the probes are the
template-relative cells stated here as read from the NBT, and the generated functions are parsed as text. Independence
is shown by MUTATING THE GENERATOR (its box, its slabs, its probe turn), never the record: each must turn a check red.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import donor_reseat as D  # noqa: E402

DOC = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
REC = next(q for q in DOC["placements"] if q["id"] == "legendary_newmoon_island")

# read from data/lumymon/structure/newmoon_island.nbt in LumyMon-0.6.6.jar, 2026-10-20 (tools/nbt.py), not the record
SIZE = (101, 58, 100)
PROBES_IN_TEMPLATE = [(50, 0, 50, "minecraft:obsidian"), (50, 10, 50, "minecraft:obsidian"),
                      (50, 19, 50, "minecraft:obsidian"), (59, 37, 24, "lumymon:summon_anchor"),
                      (49, 46, 33, "lumymon:darkrai_shrine")]
TEMPLATE_ENTITY_TYPES = {"minecraft:armor_stand", "minecraft:painting", "handcrafted:fancy_painting"}
OLD_CORNER = (24, 141, 5582)        # the 2026-10-06 paste (commit fbeb7ffc)


def own_box(corner):
    x, y, z = corner
    return (x, y, z), (x + SIZE[0] - 1, y + SIZE[1] - 1, z + SIZE[2] - 1)


def new_corner():
    return tuple(REC["position"][k] for k in "xyz")


class FakeGround:
    """The heightmap is not needed to test the text the generator writes; the ground proof has its own test below."""

    def __init__(self, h=117):
        self.h = h

    def box(self, x0, z0, x1, z1):
        import numpy as np
        return np.full((z1 - z0 + 1, x1 - x0 + 1), self.h, dtype=int)

    def __call__(self, x, z):
        return self.h


def generated(g=None):
    fs = D.files(DOC, g or FakeGround())
    return {Path(k).stem: v.splitlines() for k, v in fs.items()}


def fills(lines):
    out = []
    for ln in lines:
        m = re.fullmatch(r"fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) minecraft:air", ln)
        if m:
            out.append(tuple(int(v) for v in m.groups()))
    return out


def test_the_records_old_seat_is_the_2026_10_06_paste():
    (s,) = REC["superseded_seats"]
    assert tuple(s["position"][k] for k in "xyz") == OLD_CORNER
    assert tuple(s["size"]) == tuple(REC["size"]) == SIZE
    assert [tuple(p) for p in REC["seat_probes"]] == PROBES_IN_TEMPLATE


def test_the_takedown_fills_exactly_the_old_box_with_air():
    # Without it a slab could be missed (part of the island left hanging) or the fill could reach past the box into
    # the new paste or the isle below
    fn = generated()["reseat_legendary_newmoon_island_0_do"]
    (lo, hi) = own_box(OLD_CORNER)
    fs = fills(fn)
    assert fs, fn[:5]
    covered = set()
    for x0, y0, z0, x1, y1, z1 in fs:
        assert (x0, z0, x1, z1) == (lo[0], lo[2], hi[0], hi[2])
        assert (x1 - x0 + 1) * (y1 - y0 + 1) * (z1 - z0 + 1) <= 32768
        layers = set(range(y0, y1 + 1))
        assert not covered & layers
        covered |= layers
    assert covered == set(range(lo[1], hi[1] + 1))


def test_the_template_entities_are_killed_in_the_old_box_before_any_block_goes():
    fn = generated()["reseat_legendary_newmoon_island_0_do"]
    (lo, hi) = own_box(OLD_CORNER)
    sel = "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (lo[0], lo[1], lo[2], hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])
    kills = [ln for ln in fn if ln.startswith("kill ")]
    killed = {re.search(r"type=([^,\]]+)", ln).group(1) for ln in kills}
    assert TEMPLATE_ENTITY_TYPES <= killed
    assert all(sel in ln for ln in kills), kills
    assert not {"minecraft:player", "cobblemon:pokemon"} & killed
    first_fill = next(i for i, ln in enumerate(fn) if ln.startswith("fill "))
    assert all(fn.index(k) < first_fill for k in kills)


def test_the_takedown_runs_only_with_nobody_on_the_island_and_only_while_the_old_paste_stands():
    # Without it a player standing on the old island would fall 24+ blocks when it goes, and a second run would empty
    # the box again (anything built there since included)
    entry = generated()["reseat_legendary_newmoon_island_0"]
    x, y, z = OLD_CORNER
    want = {(x + tx, y + ty, z + tz, b) for tx, ty, tz, b in PROBES_IN_TEMPLATE}
    acts = [ln for ln in entry if ln.endswith("run function cobblers:structures/reseat_legendary_newmoon_island_0_do")]
    got = set()
    for ln in acts:
        m = re.fullmatch(r"execute if score #(\S+) cobblers_chunk_look matches 0 if block (-?\d+) (-?\d+) (-?\d+) (\S+) run .*", ln)
        assert m, ln
        assert m.group(1) == "rs_legendary_newmoon_island_0_held"
        got.add((int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5)))
    assert got == want
    # every old probe is inside the box the act empties, so after one act no probe matches: a second run is a no-op
    (lo, hi) = own_box(OLD_CORNER)
    assert all(lo[0] <= px <= hi[0] and lo[1] <= py <= hi[1] and lo[2] <= pz <= hi[2] for px, py, pz, _b in want)
    held = [ln for ln in entry if ln.startswith("tag @a[") and "add cobblers_reseat_held" in ln]
    assert len(held) == 1
    m = re.search(r"x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(\d+),dy=(\d+),dz=(\d+)", held[0])
    hx, hy, hz, dx, dy, dz = (int(v) for v in m.groups())
    assert (hx, hy, hz) == lo and (hx + dx, hz + dz) == (hi[0], hi[2]) and hy + dy >= hi[1] + 1


def test_the_new_paste_is_guarded_by_every_new_probe():
    # Without it a second run would paste the island again and refill the containers a player has looted
    (line,) = [ln for ln in generated()["reseat_legendary_newmoon_island_0_place"] if not ln.startswith("#")]
    x, y, z = new_corner()
    want = ["unless block %d %d %d %s" % (x + tx, y + ty, z + tz, b) for tx, ty, tz, b in PROBES_IN_TEMPLATE]
    assert line == "execute %s run function cobblers:structures/place_legendary_newmoon_island" % " ".join(want)


def test_the_read_back_counts_old_and_new_probes_only_when_every_chunk_is_loaded():
    ver = generated()["reseat_legendary_newmoon_island_0_verify"]
    x, y, z = new_corner()
    ox, oy, oz = OLD_CORNER
    for tag, (cx, cy, cz) in (("old", OLD_CORNER), ("new", (x, y, z))):
        adds = [ln for ln in ver if "add #rs_legendary_newmoon_island_0_%s " % tag in ln]
        cells = {tuple(re.search(r"if block (-?\d+) (-?\d+) (-?\d+) (\S+) run", ln).groups()) for ln in adds}
        assert cells == {(str(cx + tx), str(cy + ty), str(cz + tz), b) for tx, ty, tz, b in PROBES_IN_TEMPLATE}
        assert "scoreboard players set #rs_legendary_newmoon_island_0_%s cobblers_chunk_look -1" % tag in ver
    zero = [ln for ln in ver if ln.endswith(" 0") and "if loaded" in ln]
    assert len(zero) == 2 and all(ln.count("if loaded") == 2 * len(PROBES_IN_TEMPLATE) for ln in zero)


def test_r9dr_runs_before_r9_with_its_three_read_backs():
    # Without it the old island would stay in the world (nothing runs the takedown) or the run would report success
    # without reading the world
    # reapply.steps() itself needs a prepared build/ (the Rift's index), so the order is read from its source, as
    # tests/test_hub_waystones.py does, and the actions from the step's own source of truth
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert '("R9DR"' in src and 'donor_reseat.steps(doc)' in src
    assert src.index('("R9DR"') < src.index('out.append(("R9", "pack donors')
    acts = D.steps(DOC)
    fns = [v for k, v in acts if k == "fn"]
    assert fns == ["cobblers:structures/reseat_legendary_newmoon_island_0",
                   "cobblers:structures/reseat_legendary_newmoon_island_0_place",
                   "cobblers:structures/reseat_legendary_newmoon_island_0_verify"]
    checks = [v[1:3] for k, v in acts if k == "check"]
    assert checks == [("rs_legendary_newmoon_island_0_held", 0), ("rs_legendary_newmoon_island_0_old", 0),
                      ("rs_legendary_newmoon_island_0_new", len(PROBES_IN_TEMPLATE))]
    x0, z0 = OLD_CORNER[0], OLD_CORNER[2]
    assert ("cmd", "forceload add %d %d %d %d" % (x0, z0, x0 + SIZE[0] - 1, z0 + SIZE[2] - 1)) == acts[0]
    assert acts[-1][0] == "cmd" and acts[-1][1].startswith("forceload remove")


def test_ground_at_the_old_bottom_refuses_the_whole_takedown():
    with pytest.raises(SystemExit) as e:
        D.files(DOC, FakeGround(h=OLD_CORNER[1]))
    assert "air is not the restore" in str(e.value)


def test_the_new_seat_over_the_build_limit_is_refused(monkeypatch):
    monkeypatch.setattr(D, "runtime_top", lambda: new_corner()[1] + SIZE[1] - 2)
    assert any("over the build limit" in p for p in D.problems(DOC, FakeGround()))


# ------------------------------------------------------------------ mutate the GENERATOR, never the record


def test_a_generator_whose_box_is_one_block_high_is_caught(monkeypatch):
    # every box one high: the new seat runs over the limit (refused) or the fill misses the old bottom (assertion)
    real = D.box

    def high(rec):
        (x0, y0, z0), (x1, y1, z1) = real(rec)
        return (x0, y0 + 1, z0), (x1, y1 + 1, z1)
    monkeypatch.setattr(D, "box", high)
    with pytest.raises((AssertionError, SystemExit)):
        test_the_takedown_fills_exactly_the_old_box_with_air()


def test_a_generator_that_reads_the_old_seat_one_block_high_is_caught(monkeypatch):
    real = D.seat_record

    def high(q, s):
        old = real(q, s)
        old["position"] = dict(old["position"], y=old["position"]["y"] + 1)
        return old
    monkeypatch.setattr(D, "seat_record", high)
    with pytest.raises(AssertionError):
        test_the_takedown_fills_exactly_the_old_box_with_air()


def test_a_generator_that_drops_its_last_slab_is_caught(monkeypatch):
    real = D.slabs
    monkeypatch.setattr(D, "slabs", lambda lo, hi: list(real(lo, hi))[:-1])
    with pytest.raises(AssertionError):
        test_the_takedown_fills_exactly_the_old_box_with_air()


def test_a_generator_that_turns_its_probes_wrong_is_caught(monkeypatch):
    import place_donor
    monkeypatch.setattr(place_donor, "transform", lambda x, z, rot, mirror="none": (z, x))
    with pytest.raises(AssertionError):
        test_the_new_paste_is_guarded_by_every_new_probe()


def test_a_generator_that_skips_the_held_gate_is_caught(monkeypatch):
    real = D.functions

    def open_gate(q, i, s):
        out = real(q, i, s)
        for k, lines in out.items():
            out[k] = [ln.replace(" matches 0 if block", " matches 0.. if block") for ln in lines]
        return out
    monkeypatch.setattr(D, "functions", open_gate)
    with pytest.raises(AssertionError):
        test_the_takedown_runs_only_with_nobody_on_the_island_and_only_while_the_old_paste_stands()
