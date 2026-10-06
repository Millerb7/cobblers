"""tools/fossil_dig_audit.py: an independent audit of the Scorchbone Dig's built pack.

Written by an agent that built none of the place (CLAUDE.md principle 16). Every mutation below changes the CODE of
tools/fossil_dig.py (its source is edited and re-executed for one test) and leaves data/fossil_dig.json alone
(CLAUDE.md, "How to prove an audit is independent"): a record-side mutation moves the expectation with the output and
proves nothing. A mutation counts as caught only by a problem the unmutated build does not already have.

The fixture is a synthetic ground whose numbers can be checked by hand:

    g(x, z) = 142 + (x >= 4190) - (z >= 5630)

The upper rect (x 4171..4195, z 5615..5631) has its lowest ground 141 at z 5630..5631, so the floors are 140, 138
and 136; the foreman's column (4168, 5621) reads 142, so his seat at y143 is on it; the rim stair's top is
g(4170, 5623) + 0 = 142. Siting reads the real data files, so the synthetic build carries the real siting finding.

Not covered here (needs a running server): that a suspicious block keeps its LootTable from setblock and brushes out
the fossil, that the restore fires on approach and never under a player, that the foreman appears and talks.
"""
import hashlib
import inspect
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import fossil_dig as FD          # noqa: E402  (the generator: mutated, never used to derive an expectation)
import fossil_dig_audit as A     # noqa: E402

RECORD = ROOT / "data" / "fossil_dig.json"
RECORD_SHA = hashlib.sha256(RECORD.read_bytes()).hexdigest()


def SYNTH(x, z):
    return 142 + (1 if x >= 4190 else 0) - (1 if z >= 5630 else 0)


def _jar():
    jp = A.find_jar(os.environ.get("COBBLERS_JAR_DIR") or str(A.LOCAL_JARS))
    return A.Jar(jp) if jp else None


JAR = _jar()

# the real build's only problem, a FINDING awaiting the owner: data/far_south.json:26 declares a keep-out box
# [3244, 3460, 4923, 5707] (the Rift's southern arms widened by 300, "another builder is expanding the Mega field
# there") and the dig (x 4156..4200, z 5609..5637) is inside it. The builder checked only data/southern_residents.json's
# keep-out. If this set changes, either the finding was resolved or a new one appeared: both must be looked at.
KNOWN_SITING = set()  # 2026-10-06: the far-south keep-out box ends at z5560 (data/far_south.json box_changed_why); the dig clears it


def build(ground=SYNTH):
    out, _pl = FD.files(FD.load(), ground)
    assert hashlib.sha256(RECORD.read_bytes()).hexdigest() == RECORD_SHA, "a test touched data/fossil_dig.json"
    return out


def run(ground=SYNTH):
    return A.audit(build(ground), ground, jar=JAR)


def mutate(monkeypatch, fn, old, new):
    """Replace `old` (exactly once) in the generator function `fn`'s source and install the result for this test."""
    src = inspect.getsource(getattr(FD, fn))
    assert src.count(old) == 1, "the mutation's anchor is not in %s exactly once: %r" % (fn, old)
    ns = dict(FD.__dict__)
    exec(compile(src.replace(old, new), FD.__file__, "exec"), ns)
    monkeypatch.setattr(FD, fn, ns[fn])


@pytest.fixture(scope="module")
def baseline():
    return set(run().problems)


def caught(rep, baseline, kind):
    new = [p for p in rep.problems if p not in baseline]
    return any(k == kind for k, _m in new), new[:3]


# ------------------------------------------------------------------------------------------------- the fixture
def test_on_synthetic_ground_the_audit_derives_the_hand_computed_floors_and_seams():
    # protects the audit's own derivation: if removed, an audit that computed the wrong floors would grade nothing
    rep = run()
    assert rep.facts["floors"] == {"upper": 140, "middle": 138, "bed": 136}
    assert rep.facts["seams"] == 12
    assert rep.facts["clear_box"][0] <= 4159 and rep.facts["clear_box"][3] >= 4197


def test_on_synthetic_ground_the_unmutated_build_has_only_the_known_siting_finding(baseline):
    # protects against a noisy audit: if removed, a baseline full of false problems would hide every mutation
    expected = set(KNOWN_SITING)
    if JAR is None:
        expected = {p for p in baseline if p[0] == "loot"} | expected
    assert baseline == expected, sorted(baseline - expected)[:5]


def test_every_pit_floor_cell_is_reached_by_the_walk():
    # protects the walk check: if removed, an unreachable level would pass as long as its blocks exist
    rep = run()
    w = rep.facts["walk"]
    assert w["floor_cells"] > 300 and w["reached"] == w["floor_cells"]


def test_an_empty_pack_fails_closed():
    # protects fail-closed: if removed, a pack whose build never ran would pass with nothing checked
    rep = A.audit({}, SYNTH, jar=JAR)
    assert rep.problems and rep.problems[0][0] == "pack"


# ------------------------------------------------------------------------------------------------- generator mutations
def test_a_check_without_the_player_guard_is_caught(monkeypatch, baseline):
    # protects restore safety: if removed, a wall could be rebuilt inside a player standing at the seam
    mutate(monkeypatch, "driver_files", '"execute if entity @a[%s] run return 0" % vol,', "")
    ok, new = caught(run(), baseline, "restore")
    assert ok, new


def test_a_check_without_the_pokemon_guard_is_caught(monkeypatch, baseline):
    # protects restore safety: if removed, a restore could entomb a Pokemon in the face
    mutate(monkeypatch, "driver_files", '"execute if entity @e[type=cobblemon:pokemon,%s] run return 0" % vol,', "")
    ok, new = caught(run(), baseline, "restore")
    assert ok, new


def test_a_pit_two_blocks_deeper_than_the_heightmap_says_is_caught(monkeypatch, baseline):
    # protects the ground rule: if removed, floors not derived from the rounded heightmap would pass
    mutate(monkeypatch, "plan", 'floors = {"upper": low - lv["upper"]["depth_below_lowest_ground"]}',
           'floors = {"upper": low - lv["upper"]["depth_below_lowest_ground"] - 2}')
    ok, new = caught(run(), baseline, "pit")
    assert ok, new


@pytest.mark.skipif(JAR is None, reason="NOT_EXECUTED: no Cobblemon 1.8 jar (set COBBLERS_JAR_DIR)")
def test_an_uncommon_loot_table_is_caught(monkeypatch, baseline):
    # protects the rare-only rule: if removed, a seam could hand out evolution items other systems price
    mutate(monkeypatch, "seam_state", '["seam_block"], loot_table)', '["seam_block"], loot_table.replace('
           '"rare/helix_fossil", "uncommon/prehistoric_sunscorched_den"))')
    ok, new = caught(run(), baseline, "loot")
    assert ok, new


def test_a_restore_fill_without_replace_is_caught(monkeypatch, baseline):
    # protects players' blocks: if removed, the restore would overwrite whatever stands in the wall
    mutate(monkeypatch, "driver_files", '"fill %d %d %d %d %d %d %s replace %s" % (x, y, z, x, y, z, st, tag)',
           '"fill %d %d %d %d %d %d %s" % (x, y, z, x, y, z, st)')
    ok, new = caught(run(), baseline, "restore")
    assert ok, new


def test_a_seam_function_without_its_guard_is_caught(monkeypatch, baseline):
    # protects unbrushed seams and players' blocks: if removed, every restore would re-roll a seam that still holds
    mutate(monkeypatch, "driver_files", '"execute unless block %d %d %d %s run return 0" % (x, y, z, tag),', "")
    ok, new = caught(run(), baseline, "restore")
    assert ok, new


def test_air_written_bottom_up_is_caught(monkeypatch, baseline):
    # protects the cut: if removed, the mesa's sand could fall into the pit while it is dug
    mutate(monkeypatch, "build_lines", "if s == AIR}, top_down=True)", "if s == AIR}, top_down=False)")
    ok, new = caught(run(), baseline, "gravity")
    assert ok, new


def test_a_guard_box_not_grown_by_one_is_caught(monkeypatch, baseline):
    # protects restore safety: if removed, a player pressed against the face would not stop the restore
    mutate(monkeypatch, "driver_files", '_vol(f["bounds"], 1)', '_vol(f["bounds"], 0)')
    ok, new = caught(run(), baseline, "restore")
    assert ok, new


def test_a_period_shorter_than_a_day_is_caught(monkeypatch, baseline):
    # protects the supply rate: if removed, the dig could hand out fossils four times as fast
    mutate(monkeypatch, "driver_files", '"scoreboard players set #period fd.t %d" % rs["period_ticks"]',
           '"scoreboard players set #period fd.t %d" % (rs["period_ticks"] // 4)')
    ok, new = caught(run(), baseline, "restore")
    assert ok, new


def test_a_rearm_tag_holding_suspicious_gravel_is_caught(monkeypatch, baseline):
    # protects armed seams: if removed, the restore could replace an unbrushed fossil
    mutate(monkeypatch, "files", 'json.dumps({"values": doc["restore"]["rearm"]}, indent=2)',
           'json.dumps({"values": doc["restore"]["rearm"] + ["minecraft:suspicious_gravel"]}, indent=2)')
    ok, new = caught(run(), baseline, "restore")
    assert ok, new


def test_a_restore_band_that_differs_from_the_build_is_caught(monkeypatch, baseline):
    # protects the look of the wall: if removed, every restore would repaint the strata in the wrong colour
    mutate(monkeypatch, "plan", "            wall[c] = st_", '            wall[c] = "minecraft:terracotta"')
    ok, new = caught(run(), baseline, "restore")
    assert ok, new


def test_a_lantern_on_a_post_one_high_is_caught(monkeypatch, baseline):
    # protects lantern support: if removed, a lantern over air would pass (it pops off in game)
    mutate(monkeypatch, "plan", "for y in (base + 1, base + 2):", "for y in (base + 1,):")
    ok, new = caught(run(), baseline, "support")
    assert ok, new


def test_a_tent_ridge_lifted_off_the_canvas_is_caught(monkeypatch, baseline):
    # protects "nothing floating": if removed, a block touching nothing would pass
    mutate(monkeypatch, "plan", "p.put(cx + mid, Gt + 3, z, cv)", "p.put(cx + mid, Gt + 4, z, cv)")
    ok, new = caught(run(), baseline, "support")
    assert ok, new


def test_a_pit_without_its_stairs_is_caught(monkeypatch, baseline):
    # protects access: if removed, levels two blocks down with no way in would pass
    mutate(monkeypatch, "plan", "for j in range(1, h + 1):", "for j in range(1, 1):")
    ok, new = caught(run(), baseline, "walk")
    assert ok, new


def test_a_waterlogged_block_is_caught(monkeypatch, baseline):
    # protects "no water": if removed, a waterlogged sieve would pass
    mutate(monkeypatch, "plan", '"minecraft:scaffolding[bottom=false,distance=0,waterlogged=false]"',
           '"minecraft:scaffolding[bottom=false,distance=0,waterlogged=true]"')
    ok, new = caught(run(), baseline, "palette")
    assert ok, new


def test_built_set_before_the_build_writes_is_caught(monkeypatch, baseline):
    # protects the driver: if removed, a restore could run on a half-built dig
    mutate(monkeypatch, "build_lines", 'out.append("scoreboard players set #built fd.t 1")',
           'out.insert(3, "scoreboard players set #built fd.t 1")')
    ok, new = caught(run(), baseline, "driver")
    assert ok, new


def test_a_drive_without_the_built_gate_is_caught(monkeypatch, baseline):
    # protects the driver: if removed, the restore could write into a world the build never reached
    mutate(monkeypatch, "driver_files", '"execute unless score #built fd.t matches 1 run return 0",', "")
    ok, new = caught(run(), baseline, "driver")
    assert ok, new


def test_a_write_outside_the_footprint_is_caught(monkeypatch, baseline):
    # protects the footprint: if removed, a stray block outside the cleared, force-loaded box would pass
    mutate(monkeypatch, "build_lines", 'out.append("scoreboard players set #built fd.t 1")',
           'out += ["setblock %d 150 %d minecraft:terracotta" % (x1 + 20, z0), "scoreboard players set #built fd.t 1"]')
    ok, new = caught(run(), baseline, "footprint")
    assert ok, new


def test_a_dig_moved_toward_hornwall_is_caught(monkeypatch, baseline):
    # protects siting: if removed, a generator that built 150 blocks south, inside the clearance of Hornwall, would pass
    mutate(monkeypatch, "plan", 'cx, cz = doc["site"]["centre"]',
           'cx, cz = doc["site"]["centre"][0], doc["site"]["centre"][1] + 150')
    ok, new = caught(run(), baseline, "siting")
    assert ok, new


# ------------------------------------------------------------------------------------------------- the real build
def test_the_real_build_has_only_the_known_findings():
    # protects the content: the dig as built on the canonical heightmap. If removed, nothing grades the real place
    import ground as G
    try:
        g = G.load()
    except (SystemExit, OSError, FileNotFoundError) as e:
        pytest.skip("NOT_EXECUTED: no canonical heightmap (%s)" % e)
    if JAR is None:
        pytest.skip("NOT_EXECUTED: no Cobblemon 1.8 jar (set COBBLERS_JAR_DIR)")
    rep = A.audit(build(g), g, jar=JAR)
    assert set(rep.problems) == KNOWN_SITING, sorted(set(rep.problems) ^ KNOWN_SITING)[:5]
    assert rep.facts["floors"] == {"upper": 140, "middle": 138, "bed": 136}
