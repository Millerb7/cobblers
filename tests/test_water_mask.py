"""The water a thing claims to stand in must be water that is PAINTED. F7, closed.

THE BUG. `tools/portals.py`'s `water_check` tested a dive portal's centre column against its
landmark's `extent.polygons`. `tools/paint_maps.py` paints a lake only inside that landmark's
`water_body.basin_polygons`, on the columns where the heightmap is below its `level_y`, and
`tools/worldpainter/paint.js` raises the water there and nowhere else. The two polygon sets are not
the same set, so a portal sited inside `extent` and outside `basin` passed the audit and stood in
open air on a hillside. `tools/portals_audit.py` read the same wrong polygons, so the independent
audit agreed with the builder about the wrong thing.

WHAT THESE TESTS ARE FOR. A fix to a fail-open check is worth nothing without a case the old code
passes and the new code refuses, so the pre-F7 rule is written out below as `old_rule` and every
central test asserts BOTH halves: old accepts, new refuses. Two of them do it with the repository's
real polygons, through the real tools, because a fix proven only against a hand-made fixture is a
fix proven against the fixture.

WHAT THEY DO NOT COVER. Nothing here proves water reached the world. These tests read
`data/landmarks.json` and the canonical heightmap and check what the export was TOLD to paint; a
column can satisfy every assertion here and still be dry in the save if the export never ran, ran
against another heightmap, or a later carve raised the floor (F5's lake bed is the standing proof
that a world can disagree with its own paint). That needs eyes in the game or a world read, and it
is an experiment, not a pytest. Nor do they test the PIL rasteriser itself: `claim()` uses an
even-odd ray cast and can differ from PIL's polygon fill by a pixel on a boundary, which is why
`python tools/water_mask.py gap` cross-checks every sited claim column against the real raster (0
disagreements, 2026-09-30) and why a claim must have every column of its footprint inside the basin.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import water_mask as W  # noqa: E402
import portals as P  # noqa: E402
import portals_audit as PA  # noqa: E402

LANDMARKS = json.loads((ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))["landmarks"]
BODIES = W.bodies()
DEEP = 40          # a flat stand-in ground, far below every authored lake level (77 to 127)


class Flat:
    """tools/ground.py's stand-in: flat ground at y40, so no test here needs the heightmap.

    It is deliberately deep: every depth rule passes everywhere on it, which isolates the thing
    under test to the POLYGON rule -- the only positional gate the old check had."""

    def __init__(self, *a, **k):
        pass

    def __call__(self, x, z):
        return DEEP


def old_rule(body, x, z, ground=None):
    """The pre-F7 check, copied out: inside the landmark's `extent.polygons`, at depth. True = accepted.

    This is `tools/portals.py` water_check as it stood at dd81da1, reduced to its positional gate:

        level, polys = bodies[body]                 # bodies came from extent.polygons
        if not any(in_polygon(p, x, z) for p in polys):
            out.append("... is outside %s's outline")
    """
    g = ground or Flat()
    b = BODIES.get(body)
    if b is None:
        return False
    return W.in_polygons(b["extent"], x, z) and g(x, z) <= b["level_y"] - 6


def gap_column(body, stride=7):
    """A real (x, z) inside `body`'s extent polygons and outside its basin polygons, or None."""
    b = BODIES[body]
    pts = [q for ring in b["extent"] for q in ring]
    x0, x1 = min(q[0] for q in pts), max(q[0] for q in pts)
    z0, z1 = min(q[1] for q in pts), max(q[1] for q in pts)
    for z in range(z0, z1 + 1, stride):
        for x in range(x0, x1 + 1, stride):
            if W.in_polygons(b["extent"], x, z) and not W.in_polygons(b["basin"], x, z):
                return (x, z)
    return None


# Without it every other test here could pass on polygon sets that happen to be identical, and the
# whole fix would be untested while looking tested: the premise is that extent and basin DISAGREE.
def test_extent_and_basin_polygons_of_the_real_water_bodies_disagree():
    gaps = {bid: gap_column(bid) for bid in BODIES}
    assert any(v for v in gaps.values()), \
        "no landmark has a column inside extent and outside basin: this suite no longer tests anything"
    assert gaps.get("lake_tilpey"), "Lake Tilpey's 219,737-column gap is gone; re-measure before trusting this"


# THE TEST THAT DISTINGUISHES OLD FROM NEW, on real polygons. Without it the fix is unproven: the old
# rule accepted this column, the new one must refuse it, and if that ever stops being true the check
# has gone back to passing dry ground.
@pytest.mark.parametrize("body", sorted(bid for bid in W.bodies() if gap_column(bid)))
def test_the_old_extent_rule_accepts_a_real_column_the_new_basin_rule_refuses(body):
    x, z = gap_column(body)
    assert old_rule(body, x, z), \
        "(%d, %d) is not in %s's extent: the fixture does not exercise the gap" % (x, z, body)
    problems = W.claim(body, [(x, z)], Flat(), 0, bodies_=BODIES, label="fixture")
    assert problems, "%s: (%d, %d) is outside the basin and claim() accepted it" % (body, x, z)
    assert "basin_polygons" in problems[0], problems


# Without it a footprint could straddle the basin edge -- centre in the lake, corners on the bank --
# and pass, which is how a 5 by 5 apron ends up half dry. The old check only ever looked at one column.
def test_claim_refuses_a_footprint_whose_centre_is_wet_and_whose_corner_is_not():
    bid = "lake_tilpey"
    x, z = gap_column(bid)
    centre = _any_basin_column(bid)
    assert W.claim(bid, [centre], Flat(), 0, bodies_=BODIES) == []
    assert W.claim(bid, [centre, (x, z)], Flat(), 0, bodies_=BODIES), \
        "a footprint with one column outside the basin was accepted"


def _any_basin_column(bid, stride=11):
    b = BODIES[bid]
    pts = [q for ring in b["basin"] for q in ring]
    x0, x1 = min(q[0] for q in pts), max(q[0] for q in pts)
    z0, z1 = min(q[1] for q in pts), max(q[1] for q in pts)
    for z in range(z0, z1 + 1, stride):
        for x in range(x0, x1 + 1, stride):
            if W.in_polygons(b["basin"], x, z):
                return (x, z)
    raise AssertionError("%s: no column inside its own basin polygons" % bid)


# Without it a landmark that loses its basin_polygons (or never had them) silently becomes a body
# nothing is painted in, and everything claiming to be in it passes while standing in air.
def test_claim_refuses_a_body_that_has_a_level_but_no_basin_polygons():
    fake = {"pool": {"level_y": 90, "basin": [], "extent": [[(0, 0), (99, 0), (99, 99), (0, 99)]]}}
    out = W.claim("pool", [(50, 50)], Flat(), 0, bodies_=fake)
    assert out and "no basin_polygons" in out[0], out


# Without it an unnamed or misspelled body reads as "no rule to apply" and the claim passes by default.
def test_claim_refuses_a_body_that_is_not_in_the_landmarks():
    out = W.claim("lake_that_does_not_exist", [(10, 10)], Flat(), 0, bodies_=BODIES)
    assert out and "no water body" in out[0], out


# Without it a claim with an empty footprint passes vacuously, which is the fail-open shape F7 was.
def test_claim_refuses_a_claim_with_no_columns():
    assert W.claim("lake_tilpey", [], Flat(), 0, bodies_=BODIES)


# Without it the shoreline passes: ground exactly AT the surface holds no water, and paint's float
# comparison (h < level) marks h=76.6 wet while the export's rounded ground block sits at y77, level
# with the water. tools/ground.py is rounded, and the rule here must refuse equality.
@pytest.mark.parametrize("gy, wet", [(70, True), (89, True), (90, False), (91, False)])
def test_claim_refuses_ground_at_or_above_the_surface(gy, wet):
    fake = {"pool": {"level_y": 90, "basin": [[(0, 0), (99, 0), (99, 99), (0, 99)]], "extent": []}}
    out = W.claim("pool", [(50, 50)], lambda x, z: gy, 0, bodies_=fake)
    assert (out == []) is wet, out


# Without it a structure can sit in one block of water and call itself drowned: min_submersion is the
# difference between a lake floor and a shelf, and the margin must be enforced per column.
def test_claim_enforces_the_submersion_margin():
    fake = {"pool": {"level_y": 90, "basin": [[(0, 0), (99, 0), (99, 99), (0, 99)]], "extent": []}}
    assert W.claim("pool", [(50, 50)], lambda x, z: 85, 6, bodies_=fake)
    assert W.claim("pool", [(50, 50)], lambda x, z: 84, 6, bodies_=fake) == []


# Without it a sea claim is checked against a level the export does not paint: paint.js floods from
# the import's water_level, and a disagreement between the two numbers would be read as "fine".
def test_sea_level_refuses_to_answer_when_the_two_world_numbers_disagree(tmp_path):
    w = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    assert W.sea_level() == int(w["vertical"]["sea_level"]) == int(w["import"]["water_level"])
    w["import"]["water_level"] = int(w["vertical"]["sea_level"]) + 3
    p = tmp_path / "world.json"
    p.write_text(json.dumps(w), encoding="utf-8")
    with pytest.raises(W.WaterError):
        W.sea_level(p)


# ---------------------------------------------------------------- the same proof, through the tools


def _doc_with_portal_in_the_gap():
    """data/portals.json with one dive portal moved into its own lake's extent-but-not-basin gap."""
    doc = json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))
    moved = None
    for s in doc["portals"]:
        if s["gate"] == "dive" and gap_column(s["water_body"]):
            s["at"] = list(gap_column(s["water_body"]))
            moved = s["id"]
            break
    assert moved, "no dive portal's body has an extent gap to move it into"
    return doc, moved


def _pre_f7_water_check(doc, spec, site, bodies):
    """tools/portals.py water_check as it stood at dd81da1, so the old builder can be run again.

    Verbatim except for reading `extent` out of the new bodies dict, which is the same list of
    polygons the old `water_bodies()` returned: the CENTRE column inside the extent outline, the
    lintel under the level, the apron columns deep enough. Nothing about the basin."""
    body = spec["water_body"]
    b = BODIES.get(body)
    if b is None:
        return ["%s: no water body %r" % (spec["id"], body)]
    level, polys, out = b["level_y"], b["extent"], []
    x, z = spec["at"]
    if not W.in_polygons(polys, x, z):
        out.append("%s: (%d, %d) is outside %s's outline" % (spec["id"], x, z, body))
    top = site["apron_y"] + P.ARCH_HEIGHT
    if top > level - doc["rules"]["min_water_above"]:
        out.append("%s: its lintel tops out at y%d" % (spec["id"], top))
    for c, gy in site["ground"].items():
        if gy > level - doc["rules"]["min_submersion"]:
            out.append("%s: the apron column %s is at y%d" % (spec["id"], c, gy))
            break
    site["level_y"] = level
    return out


def _old_builder(monkeypatch):
    """Run tools/portals.py with its pre-F7 water rule, and with the clearances stood down.

    The clearances are patched out because a gap column is chosen for being dry, not for being far
    from a town, and a clearance failure would mask the thing under test. Everything else -- the
    geometry, the apron, the emitter -- is the real tool."""
    monkeypatch.setattr(P, "water_check", _pre_f7_water_check)
    monkeypatch.setattr(P, "clearances", lambda doc, sites: [])


# THE TOOL-LEVEL OLD-vs-NEW PROOF. Without it tools/portals.py could keep its own loose rule while
# water_mask is strict: the builder must REFUSE a portal the pre-F7 builder would have emitted.
def test_portals_sites_refuses_a_dive_portal_standing_in_the_extent_gap(monkeypatch):
    doc, moved = _doc_with_portal_in_the_gap()

    _old_builder(monkeypatch)
    P.sites(doc, Flat())          # no raise: the pre-F7 bug, reproduced

    monkeypatch.undo()
    monkeypatch.setattr(P, "clearances", lambda doc, sites: [])
    with pytest.raises(P.PortalError) as e:
        P.sites(doc, Flat())
    assert moved in str(e.value) and "basin_polygons" in str(e.value), str(e.value)


# Without it the independent audit still reads extent polygons and signs off on a pack the pre-F7
# builder could have written: two tools agreeing about the wrong water is what F7 actually was.
def test_portals_audit_refuses_a_pack_whose_portal_stands_in_the_extent_gap(tmp_path, monkeypatch):
    doc, moved = _doc_with_portal_in_the_gap()
    _old_builder(monkeypatch)
    S = P.sites(doc, Flat())
    files = P.files(doc, S)
    monkeypatch.undo()

    pack = tmp_path / "datapacks" / "cobblers_portals"
    for rel, body in files.items():
        f = pack / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body, encoding="utf-8")
    data = tmp_path / "portals.json"
    data.write_text(json.dumps(doc), encoding="utf-8")

    monkeypatch.setattr(PA, "PACK", pack)
    monkeypatch.setattr(PA, "DATA", data)
    import ground as G
    monkeypatch.setattr(G, "Ground", Flat)

    class A:
        source_root = None
        packs = str(tmp_path / "datapacks")

    bad = PA.audit(A())
    hits = [b for b in bad if moved in b and "basin_polygons" in b]
    assert hits, "the audit passed a portal standing outside the basin: %s" % bad[:4]


# ------------------------------------------------------------------- the repository as it stands today


# Without it the fix is a rule nobody has run against the real map: this is the check that every
# thing sited TODAY -- the six dive portals' aprons, the ferry docks' decks and heads -- stands in
# water the paint actually lays. It needs the canonical heightmap, so it is slow and skips without it.
@pytest.mark.slow
def test_every_water_claim_sited_in_the_repository_is_in_painted_water():
    import terrain as T
    import ground as G
    try:
        g = G.Ground()
    except (T.TerrainUnavailable, FileNotFoundError, OSError) as e:
        pytest.skip("NOT_EXECUTED: the canonical heightmap is unavailable (%s); set COBBLERS_SOURCE_ROOT" % e)
    bad = []
    claims = W.sited_claims()
    assert len(claims) >= 6, "the claim list has shrunk to %d: a tool stopped being covered" % len(claims)
    for label, body, cols, sub in claims:
        bad += W.claim(body, cols, g, sub, bodies_=BODIES, label=label)
    assert bad == [], bad


# ------------------------------------------------------------- the cheap gate in tools/validate.py


def _validate_water_issues(monkeypatch, claims=None):
    import validate as V
    if claims is not None:
        import water_mask
        monkeypatch.setattr(water_mask, "sited_claims", lambda: claims)
    ctx = V.Context(ROOT, False)
    V.check_water_claims(ctx)
    return [i for i in ctx.issues if i.level == "error"]


# Without it the repository's cheapest gate is silent about the F7 class of defect, and a portal or a
# dock sited outside its basin is caught only by an audit that needs the heightmap (so not in CI, and
# not in an agent's worktree -- F8). The claims sited today must pass it.
def test_validate_water_claims_passes_the_repository_as_it_stands(monkeypatch):
    assert _validate_water_issues(monkeypatch) == []


# Without it the gate could be registered and do nothing: a claim in the extent gap must make it fail.
def test_validate_water_claims_fails_on_a_claim_in_the_extent_gap(monkeypatch):
    x, z = gap_column("lake_tilpey")
    bad = _validate_water_issues(monkeypatch, [("fixture claim", "lake_tilpey", [(x, z)], 6)])
    assert bad and "basin_polygons" in bad[0].message, bad


# Without it a body that lost its basin polygons passes the gate: there is then no painted water at
# all, and every claim on it is a claim on dry ground.
def test_validate_water_claims_fails_on_a_body_with_no_basin(monkeypatch):
    import water_mask
    monkeypatch.setattr(water_mask, "bodies", lambda path=None: {
        "pool": {"level_y": 90, "basin": [], "extent": [[(0, 0), (9, 0), (9, 9), (0, 9)]]}})
    bad = _validate_water_issues(monkeypatch, [])
    assert bad and "no basin_polygons" in bad[0].message, bad
