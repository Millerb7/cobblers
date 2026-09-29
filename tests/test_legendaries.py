"""tools/legendaries_audit.py: the legendary chambers' offline audit, and the five ways it must fail.

Written by the test author, not by the session that wrote data/legendaries.json, tools/legendaries.py or the audit.

The audit is only worth running if it REJECTS a broken chamber, and an audit is easy to write so that it passes
on anything. So the suite is half positive and half tamper: the committed data and a pack freshly emitted from it
must pass, and five hand-made faults -- each one found or feared on 2026-09-29 -- must each produce a named
failure. If a tamper case ever passes, the audit has gone fail-open and the positive test below means nothing.

Expectations come from data/legendaries.json, data/landmarks.json, data/world.json and tools/ground.py, never from
the emitted pack (CLAUDE.md, "Any expectation derived from the artifact being checked is not an expectation"). The
pack each test audits is emitted in a tmp dir from the doc under test, so a tampered record is audited against the
pack that record would really produce, not against a stale clean one.

NOT COVERED, and it needs a staging world or a running server: that the carve writes the blocks it says it does,
that a keeper actually keeps the plug, that the gate opens for a qualified player and refuses an unqualified one,
that the summoned legendary is where the chamber is, and anything a player sees. Validity is not runtime
behaviour (.claude/rules/testing.md): every proof here is arithmetic over the heightmap and text over generated
functions.
"""
import copy
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import legendaries as L  # noqa: E402
import legendaries_audit as A  # noqa: E402

DATA = ROOT / "data"
WORLD = json.loads((DATA / "world.json").read_text(encoding="utf-8"))
LANDMARKS = json.loads((DATA / "landmarks.json").read_text(encoding="utf-8"))
WATER = json.loads((DATA / "water_shape.json").read_text(encoding="utf-8"))
PROGRESSION = json.loads((DATA / "progression.json").read_text(encoding="utf-8"))
LM = {l["id"]: l for l in LANDMARKS["landmarks"]}


@pytest.fixture(scope="session")
def ground():
    """The canonical heightmap, once. A skip is not a pass: it names what is missing."""
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


@pytest.fixture
def doc():
    """A fresh, mutable copy of data/legendaries.json for each test to tamper with."""
    return copy.deepcopy(L.load())


def emit(doc, ground, out: Path) -> Path:
    """The pack tools/legendaries.py would write for this doc, in a tmp dir."""
    for rel, text in L.files(doc, ground).items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    return out


def run(doc, ground, out, world=WORLD, landmarks=LANDMARKS):
    return A.audit(doc, ground, emit(doc, ground, out), WATER, PROGRESSION, landmarks, world)


def rec_of(doc, rid):
    return next(r for r in doc["encounters"] if r["id"] == rid)


def failing(rep, needle):
    return [e for e in rep.errors if needle in e]


def depth_at(ground, lake_id, x, z):
    """Blocks of water over a column, from data/landmarks.json's surveyed level and the heightmap. Test-side."""
    return int(LM[lake_id]["water_body"]["level_y"]) - int(ground(x, z))


def inside_basin(lake_id, x, z):
    """Even-odd ray cast, written here rather than imported, so a bug in the audit's own point-in-polygon does
    not silently agree with this test's preconditions."""
    for ring in LM[lake_id]["water_body"]["basin_polygons"]:
        crossings = 0
        for i in range(len(ring)):
            (xi, zi), (xj, zj) = ring[i], ring[i - 1]
            if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / float(zj - zi) + xi:
                crossings += 1
        if crossings % 2:
            return True
    return False


# ---------------------------------------------------------------- positive --

@pytest.mark.slow
def test_committed_legendaries_pass_their_own_audit(doc, ground, tmp_path):
    # If removed: a chamber whose roof, seal, gate or mouth drifts ships with nobody noticing.
    rep = run(doc, ground, tmp_path / "pack")
    assert rep.errors == [], "\n".join(rep.errors)
    assert rep.checks > 100, "only %d checks: the audit has stopped looking at most of the data" % rep.checks


@pytest.mark.slow
def test_audit_fails_on_an_empty_pack(doc, ground, tmp_path):
    # If removed: the audit could pass when the generator emitted nothing -- the fail-open shape that shipped
    # four broken audits (docs/STATE.md "Re-export readiness").
    empty = tmp_path / "empty"
    empty.mkdir()
    rep = A.audit(doc, ground, empty, WATER, PROGRESSION, LANDMARKS, WORLD)
    assert rep.errors, "an audit of an empty pack reported no failures"
    assert failing(rep, "no carve function") or failing(rep, "NOTHING TO CHECK"), rep.errors


@pytest.mark.slow
def test_every_sited_lake_mouth_is_deep_water_inside_its_own_lake(ground):
    # If removed: a grotto mouth could sit on a bank or an island and only the audit would know. Computed here
    # from data/landmarks.json and the heightmap, independently of tools/legendaries_audit.py.
    doc = L.load()
    grottos = [r for r in L.emitted(doc) if r["kind"] == "lake_grotto"]
    assert grottos, "no sited lake grotto: this test would pass vacuously"
    for rec in grottos:
        x, z = rec["mouth"]
        assert inside_basin(rec["site"], x, z), "%s's mouth (%d, %d) is outside %s's basin outline" % (
            rec["id"], x, z, rec["site"])
        d = depth_at(ground, rec["site"], x, z)
        assert d >= A.MIN_GROTTO_DEPTH, "%s's mouth stands %d under %s's water level, not %d" % (
            rec["id"], d, rec["site"], A.MIN_GROTTO_DEPTH)


# ------------------------------------------------------------ the tampering --

@pytest.mark.slow
def test_a_mouth_moved_onto_the_island_is_rejected(doc, ground, tmp_path):
    # Case 1. If removed: a grotto could be carved under the island the player walks on instead of under the
    # apron's deep water, and the chamber's own arithmetic would still be perfect.
    foliage = json.loads((DATA / "foliage.json").read_text(encoding="utf-8"))
    elder = next(o for o in foliage["landmark_trees"] if o["id"] == "weeping_elder_tilpey")
    x, z = elder["site"]                      # the island's centre, the landmark Uxie's mouth is sited FROM
    assert depth_at(ground, "lake_tilpey", x, z) < 0, "the fixture column is under water; it is not the island"
    rec_of(doc, "uxie")["mouth"] = [x, z]
    rep = run(doc, ground, tmp_path / "pack")
    assert failing(rep, "uxie: the mouth stands"), "the island mouth was accepted: %s" % rep.errors


@pytest.mark.slow
def test_a_mouth_moved_off_the_basin_onto_a_shelf_is_rejected(doc, ground, tmp_path):
    # Case 2. If removed: a mouth could drift out of the surveyed lake onto a shallow shelf beside it, where the
    # water the grotto is reached through is not the lake it belongs to.
    x, z = 2910, 4846
    d = depth_at(ground, "arrow_lake", x, z)
    assert 0 < d < A.MIN_GROTTO_DEPTH, "the fixture column reads %d deep: it is not a shallow shelf" % d
    assert not inside_basin("arrow_lake", x, z), "the fixture column is inside the basin; it tests nothing"
    rec_of(doc, "mesprit")["mouth"] = [x, z]
    rep = run(doc, ground, tmp_path / "pack")
    assert failing(rep, "outside arrow_lake's basin outline"), "the off-basin mouth was accepted: %s" % rep.errors


@pytest.mark.slow
def test_a_moved_heightmap_invalidates_a_mouth_measured_after_the_export(doc, ground, tmp_path):
    # Case 3. If removed: Uxie's mouth, which carries no keep zone because it was measured on the applied water
    # export, would keep its "applied" claim after the bed under it was rewritten by a later export.
    uxie = rec_of(doc, "uxie")
    assert uxie["water_export"]["measured_on_sha256"] == WORLD["heightmap"]["sha256"], \
        "the committed record is already stale; this test cannot tell tampering from the real state"
    world = copy.deepcopy(WORLD)
    world["heightmap"]["sha256"] = "0" * 64
    rep = run(doc, ground, tmp_path / "pack", world=world)
    assert failing(rep, "uxie: measured on heightmap"), "a moved heightmap was accepted: %s" % rep.errors


@pytest.mark.slow
def test_a_mouth_with_no_export_provenance_is_rejected(doc, ground, tmp_path):
    # Case 4. If removed: a lake grotto could claim neither a keep zone (measured before the export) nor
    # applied + measured_on_sha256 (measured after it), and nothing would say which bed it was sited on.
    rec_of(doc, "uxie")["water_export"] = {"clear": True}
    rep = run(doc, ground, tmp_path / "pack")
    assert failing(rep, "uxie: water_export declares neither"), "a mouth with no provenance was accepted: %s" % rep.errors


@pytest.mark.slow
def test_an_unadmitted_unsatisfiable_gate_is_rejected(doc, ground, tmp_path):
    # Case 5, the live fault. Regigigas is built and needs registeel's `met`, which only a SITED record's function
    # grants; registeel is not sited. If removed: that dead end, and every future one, becomes invisible again.
    gigas = rec_of(doc, "regigigas")
    assert "registeel" in gigas["gate"]["requires_met"], "regigigas no longer depends on registeel"
    assert rec_of(doc, "registeel")["status"] != "sited", "registeel is sited now: this test no longer tests it"
    gigas["gate"].pop("unsatisfiable_until")
    rep = run(doc, ground, tmp_path / "pack")
    assert failing(rep, "regigigas: its gate cannot be satisfied until registeel"), \
        "an unreachable chamber was accepted: %s" % rep.errors


@pytest.mark.slow
def test_a_new_unsatisfiable_dependency_must_be_admitted(doc, ground, tmp_path):
    # The property case 5 exists for, on a record that has no admission today: a sited chamber that acquires a
    # dependency on an unsited one must fail until it says so. If removed: the next dead gate ships silently.
    groudon = rec_of(doc, "groudon")
    assert not groudon["gate"].get("unsatisfiable_until"), "groudon already admits something"
    groudon["gate"]["requires_met"] = ["registeel"]
    rep = run(doc, ground, tmp_path / "pack")
    assert failing(rep, "groudon: its gate cannot be satisfied until registeel"), \
        "a newly unreachable chamber was accepted: %s" % rep.errors


@pytest.mark.slow
def test_a_stale_admission_is_rejected(doc, ground, tmp_path):
    # If removed: unsatisfiable_until could name records that are sited or are not prerequisites at all, and the
    # admission would stop meaning "this is still unreachable".
    rec_of(doc, "groudon")["gate"]["unsatisfiable_until"] = ["regirock"]
    rep = run(doc, ground, tmp_path / "pack")
    assert failing(rep, "groudon: its gate cannot be satisfied"), \
        "a stale admission was accepted: %s" % rep.errors
