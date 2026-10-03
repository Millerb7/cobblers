"""tools/southern_residents_audit.py against tools/southern_residents.py: the audit's derived spots and floors are the
hand-computed ones, and a broken GENERATOR fails a named check.

Written by an agent that built none of the six residents (CLAUDE.md principle 16). Every mutation below changes the
generator's CODE (a function of tools/southern_residents.py, of tools/resident_encounters.py whose keeper it calls, or
of tools/compile_dialogue.py which compiles its NPCs) and leaves data/southern_residents.json and every other data file
alone: a record-side mutation moves the expectation and the output together and proves nothing (CLAUDE.md, "How to
prove an audit is independent"). A mutation counts as caught only by an error the unmutated build does not already
have. The siting and resident rules read no generator output, so they are tested on records the test moves.

Most tests run on a synthetic ground: dead flat at y100, with a sea at y62 over a y58 bed for 1760 <= x <= 1900, 6600 <= z <= 6765, so
Corran Vey's ranging poles (from (1740, 6800), bearing 30, every 8 from the 8th block) are hand-computable: the k-th at
(1740 + round(0.5 d), 6800 - round(0.866 d)), d = 8 (k + 1); k = 0..3 dry, k = 4..13 wet. Every feet y is 101. The
committed build on the canonical heightmap is tested last (skipped, and says so, without COBBLERS_SOURCE_ROOT).

NOT covered, and it needs a running server: that the blocks land, that the keeper spawns and holds the two Pokemon,
that the NPCs appear and their dialogue runs, that the cache pays once (the audit's NOT-checked list).
"""
import copy
import inspect
import json
import os
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_dialogue as CD  # noqa: E402
import resident_encounters as RE  # noqa: E402
import southern_residents as SR  # noqa: E402
import southern_residents_audit as A  # noqa: E402

DOC = json.loads((ROOT / "data" / "southern_residents.json").read_text(encoding="utf-8"))
BY = {r["id"]: r for r in DOC["residents"]}

# The fault this audit found in the committed build on 2026-10-03 (reported, not fixed: compile_dialogue is shared
# tooling and the builder's caveat names it). When it is fixed the real-heightmap test below fails and says so.
KNOWN = [("hand-in", "surveyor_line: option r_give takes the WHOLE main-hand stack of minecraft:compass")]


def SEA(x, z):
    return 1760 <= x <= 1900 and 6600 <= z <= 6765


class Ground:
    """Flat y100, a y58 sea bed under the strait north-east of Corran's camp."""

    def __call__(self, x, z):
        return 58 if SEA(x, z) else 100


class Water:
    """The water surface y, or None; truthy where wet, which is also what the generator's wet(x, z) means."""

    def __init__(self, extra=()):
        self.extra = set(extra)

    def __call__(self, x, z):
        if (x, z) in self.extra:
            return 101
        return 62 if SEA(x, z) else None

    level = __call__


G = Ground()
W = Water()


def build(out, g=G, w=W):
    """The generator's pack and steps on this ground, its own checks off (they would refuse the synthetic ground's
    records): the audit is what must catch a fault."""
    doc = SR.load()
    written, built = SR.files(doc, g, w, check=False)
    for rel, text in written.items():
        f = Path(out) / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    return written, built


def run(tmp, g=G, w=W, steps=None):
    build(tmp, g, w)
    doc = SR.load()
    if steps is None:
        steps = placement_steps(doc, g, w) + entity_steps(doc, g, w)
    return A.audit(DOC, g, w, Path(tmp), steps)


def placement_steps(doc, g, w):
    # the generator's own R9SR, on this ground and water (its _built() reads the real water; this hands it ours)
    orig = SR.sites
    SR.sites = lambda d, gg, ww=None: orig(d, gg, w)
    try:
        return SR.placement_steps(doc, g)
    finally:
        SR.sites = orig


def entity_steps(doc, g, w):
    orig = SR.sites
    SR.sites = lambda d, gg, ww=None: orig(d, gg, w)
    try:
        return SR.entity_steps(doc, g)
    finally:
        SR.sites = orig


def mutate(monkeypatch, owner, name, old, new):
    """Replace `old` with `new` in the SOURCE of owner.name (a module's function or a class's method) and install the
    result: a change to the generator's code, never to its data."""
    fn = getattr(owner, name)
    src = textwrap.dedent(inspect.getsource(fn))
    assert old in src, "the mutation's anchor text is not in %s any more: %r" % (name, old)
    ns = dict(fn.__globals__)
    exec(compile(src.replace(old, new, 1), fn.__code__.co_filename, "exec"), ns)
    monkeypatch.setattr(owner, name, ns[name])


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    return run(tmp_path_factory.mktemp("south_base"))


def caught(rep, baseline, check):
    return [e for e in rep.errors if e not in set(baseline.errors) and e.startswith(check + ":")]


# ------------------------------------------------------------------ the audit's own derivations, by hand


# Without it the audit's feet could drift from the record's geometry and still agree with the generator.
def test_the_audits_feet_on_flat_ground_are_one_above_it_everywhere():
    want = {"fairy_ring": {"anchor": (608, 101, 5888)}, "post_fourteen": {"anchor": (7861, 101, 4704)},
            "half_house": {"npc": (2526, 101, 7470)}, "surveyor_line": {"npc": (1741, 101, 6799)},
            "prospector_camp": {"npc": (2433, 101, 5698), "cache": (2252, 101, 5640)},
            "gate_watcher": {"npc": (4135, 101, 6336)}}
    for rid, w in want.items():
        r = BY[rid]
        E = A.expect(r, G, W)
        if "anchor" in w:
            assert A.spot(E, r["pokemon"]["at"]) == w["anchor"], rid
        if "npc" in w:
            assert A.spot(E, r["npc"]["at"]) == w["npc"], rid
        if "cache" in w:
            assert A.spot(E, r["caches"][0]["at"]) == w["cache"], rid
            # the barrel set in the ground at the cairn's east foot is the cache's container, one under the spot
            assert E.final((2252, 100, 5640)) == frozenset({"minecraft:barrel"})


class Slope:
    """y = 100 + x mod 4: a footprint four or more wide has min 100 and max 103."""

    def __call__(self, x, z):
        return 100 + x % 4


# Without it a structure seated on min (or mean) ground, half buried, would pass.
def test_a_structure_floor_is_the_max_ground_under_its_footprint():
    s = Slope()
    no_water = Water()
    E = A.expect(BY["post_fourteen"], s, lambda x, z: None)
    assert E.floors["the hut"][0] == 103                    # x 7853..7861 covers every x mod 4
    assert E.floors["the watchtower"][0] == 102             # x 7848..7850: 100, 101, 102
    E = A.expect(BY["gate_watcher"], s, lambda x, z: None)
    assert E.floors["the board"][0] == 102                  # x 4138 only: 4138 mod 4 = 2
    # the foundation fills the hut's low columns up to the floor: x 7856 (mod 4 = 0) from 101 to 102
    E = A.expect(BY["post_fourteen"], s, lambda x, z: None)
    assert E.final((7856, 101, 4701)) == frozenset({"minecraft:cobblestone"})
    assert E.final((7856, 102, 4701)) == frozenset({"minecraft:cobblestone"})
    assert no_water(0, 0) is None


# Without it the poles' wet/dry split, the one place the build is allowed on water, would go unchecked.
def test_the_ranging_poles_walk_into_the_synthetic_sea_as_computed_by_hand():
    E = A.expect(BY["surveyor_line"], G, W)
    assert [p[2] for p in E.posts] == ["dry"] * 4 + ["wet"] * 10
    assert E.posts[4][:2] == (1760, 6765) and E.posts[-1][:2] == (1796, 6703)
    # a wet pole: shaft from the bed + 1 (59) to the surface (62), red/white/red above it (63..65)
    assert {y for (x, y, z), k in E.wet_posts.items() if (x, z) == (1760, 6765) and k[0] == "shaft"} == {59, 60, 61, 62}
    assert {y for (x, y, z), k in E.wet_posts.items() if (x, z) == (1760, 6765) and k[0] == "top"} == {63, 64, 65}


# ------------------------------------------------------------------ the unmutated generator


# Without it every mutation test below could be catching the audit's own false positives.
def test_the_unmutated_build_on_synthetic_ground_fails_only_its_recorded_ys_and_the_compass(baseline):
    other = [e for e in baseline.errors if not e.startswith(("ys:", "hand-in:"))]
    assert not other, other[:5]
    # the records were measured on the real heightmap, so on flat y100 they disagree: the ys check does read them
    assert any(e.startswith("ys: fairy_ring:") for e in baseline.errors)
    assert any(e.startswith(KNOWN[0][0] + ":") and KNOWN[0][1] in e for e in baseline.errors)


# ------------------------------------------------------------------ generator mutations


# Without it a floor seated a block above its footprint's highest ground (a step up into every door) would pass.
def test_a_structure_floor_raised_one_block_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, SR, "piece_structure", "B = max(s.g(x, z) for x, z in cols)",
           "B = max(s.g(x, z) for x, z in cols) + 1")
    monkeypatch.setattr(SR, "check_standing", lambda *a: None)   # the builder's own guard would refuse Ash's spot
    rep = run(tmp_path)
    assert caught(rep, baseline, "seat"), rep.errors[:5]


# Without it a pole built as if on land (dry fence and wool standing in the sea) would pass.
def test_posts_built_dry_on_wet_columns_are_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, SR, "piece_posts", "lv = s.wet.level(x, z)", "lv = None")
    rep = run(tmp_path)
    assert any("not waterlogged" in e for e in caught(rep, baseline, "writes")), rep.errors[:5]
    assert any("reaches the water" in e for e in caught(rep, baseline, "writes")), rep.errors[:5]


# Without it a camp block written on water, the guard the generator holds over ground_blocks, could be dropped.
def test_the_ground_blocks_wet_guard_removed_is_caught(monkeypatch, tmp_path):
    w2 = Water(extra={(1736, 6802)})                          # under the surveyor's tent
    with pytest.raises(SystemExit):
        build(tmp_path / "guarded", G, w2)                    # the guard in place: the generator refuses
    mutate(monkeypatch, SR, "piece_ground_blocks", "if not s.dry(x, z):", "if False:")
    rep = run(tmp_path / "mutant", G, w2)
    assert any("on a wet column" in e and "(1736, 101, 6802)" in e for e in rep.errors if e.startswith("writes:")), rep.errors[:6]


# Without it a resident turned to the wrong way on its spot (Ash faces the porch, yaw -90) would pass.
def test_a_residents_yaw_dropped_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, SR, "resident_record", '"yaw": pk["yaw"]', '"yaw": 0.0')
    rep = run(tmp_path)
    assert any("ash" in e and "home" in e for e in caught(rep, baseline, "keeper")), rep.errors[:5]


# Without it the keeper could spawn and leash a resident a block off its spot.
def test_an_anchor_off_its_ground_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, SR, "anchor", "return x, s.g(x, z) + 1, z", "return x, s.g(x, z) + 2, z")
    monkeypatch.setattr(SR, "check_standing", lambda *a: None)   # the builder's own guard would refuse it
    rep = run(tmp_path)
    assert caught(rep, baseline, "keeper") and caught(rep, baseline, "steps"), rep.errors[:5]


# Without it Ash could appear before gym 7 for anyone who walks past.
def test_the_presence_gate_dropped_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, SR, "resident_record", '"appears_after": pk.get("appears_after")', '"appears_after": None')
    rep = run(tmp_path)
    assert any("ash: the spawn is not gated on gym7_cleared" in e for e in caught(rep, baseline, "keeper")), rep.errors[:5]


# Without it a resident spawned above its place's ceiling or below its catch gate would pass.
def test_a_residents_spawn_level_changed_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, SR, "resident_record", '"level": pk["level"]', '"level": pk["level"] + 2')
    rep = run(tmp_path)
    errs = caught(rep, baseline, "keeper") + caught(rep, baseline, "steps")
    assert any("level=34" in e for e in errs) and any("level=53" in e for e in errs), rep.errors[:5]


# Without it a toadstool ring of the wrong radius (the sign's warning no longer the rule) would pass.
def test_a_ring_of_the_wrong_radius_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, SR, "piece_ring", 'n, r = int(p["count"]), float(p["r"])', 'n, r = int(p["count"]), float(p["r"]) + 1')
    rep = run(tmp_path)
    assert any("fairy_ring" in e and "off-plan" in e for e in caught(rep, baseline, "writes")), rep.errors[:5]


# Without it surface work spilling a block wider than the record (the half-house's line) would pass.
def test_a_surface_wider_than_the_record_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, SR, "_segment_cols", "r = half + 0.5", "r = half + 1.5")
    rep = run(tmp_path)
    assert any("half_house" in e and "off-plan" in e for e in caught(rep, baseline, "writes")), rep.errors[:5]


# Without it a duplicate-cull kill that can reach the blackout's guardian would pass.
def test_a_kill_that_can_reach_a_guardian_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, RE, "resident_files", "tag=%s,tag=!%s,%s,limit=1,sort=furthest", "tag=%s,tag=%s,%s,limit=1,sort=furthest")
    rep = run(tmp_path)
    assert any("could reach a guardian" in e for e in caught(rep, baseline, "keeper")), rep.errors[:5]


# Without it a summon guarded on a bare distance (R14C's failure: any Pokemon nearby blocks it) would pass.
def test_a_summon_guard_on_bare_distance_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, RE, "summon_command", "distance=..4,%s] run spawnpokemonat", "distance=..4%.0s] run spawnpokemonat")
    rep = run(tmp_path)
    assert any("without the species" in e for e in caught(rep, baseline, "steps")), rep.errors[:5]


# Without it a build run outside the forceload of its own box (chunks not loaded: the fills silently fail) would pass.
def test_a_build_outside_its_forceload_is_caught(tmp_path, baseline):
    doc = SR.load()
    steps = [s if not (s[0] == "cmd" and s[1].startswith("forceload add 598 ")) else ("cmd", "forceload add 0 0 1 1")
             for s in placement_steps(doc, G, W)] + entity_steps(doc, G, W)
    rep = run(tmp_path, steps=steps)
    assert any("fairy_ring: its build does not run inside a forceload" in e for e in caught(rep, baseline, "steps")), rep.errors[:5]


# Without it an NPC placed facing the wrong way, or twice, would pass.
def test_an_npc_step_with_the_wrong_yaw_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, SR, "npc_placements", 'n["yaw"]))', 'n["yaw"] + 180))')
    rep = run(tmp_path)
    assert any("half_house: the npc step" in e for e in caught(rep, baseline, "steps")), rep.errors[:5]


# Without it the hand-in check could be a constant failure: a compiler that takes ONE compass must pass it.
def test_a_hand_in_that_takes_one_item_passes(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, CD.Compiler, "effect", "run item replace entity @s weapon.mainhand with minecraft:air",
           "run item modify entity @s weapon.mainhand cobblers:take_one")
    rep = run(tmp_path)
    assert not [e for e in rep.errors if e.startswith("hand-in:")], rep.errors[:5]
    assert set(rep.errors) < set(baseline.errors)


# Without it Hale's Leftovers option could compile with no gym8_cleared probe and show to anyone.
def test_a_compiled_flag_option_without_its_probe_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, CD.Compiler, "cond", 'sel = "@s[advancements={%s:flag/%s=true}]" % (NS, ident(c["flag"]))',
           'sel = "@s[tag=%s_%s]" % (NS, ident(c["flag"]))')
    rep = run(tmp_path)
    assert any("never probes advancements={cobblers:flag/gym8_cleared=true}" in e
               for e in caught(rep, baseline, "dialogue")), rep.errors[:5]


# ------------------------------------------------------------------ rules that read only data


def _cols(*pts):
    return set(pts)


# Without it a site moved onto a road, a nest, the Mega farm or north of the line would pass.
def test_siting_rules_bite_on_a_moved_column():
    pts = A.authored(DOC, A.DATA)
    r = BY["gate_watcher"]
    ok = A.Report()
    A.check_siting(DOC, r, _cols((4136, 6336)), pts, ok, A.DATA)
    assert not ok.errors, ok.errors
    routes = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"]
    px, pz = next(iter(routes.values()))[0][:2]
    hb = next(b for b in json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]
              if b.get("position"))
    for col, want in (((px, pz), "route path"), ((hb["position"]["x"], hb["position"]["z"]), "authored"),
                      ((3500, 4800), "keep-out"), ((4136, 4000), "north of z")):
        rep = A.Report()
        A.check_siting(DOC, r, _cols((4136, 6336), col), pts, rep, A.DATA)
        assert any(want in e for e in rep.errors), (col, want, rep.errors)


# Without it a resident above its place's ceiling, or catchable before its gate, would pass.
def test_resident_rules_bite_on_a_moved_level():
    r = copy.deepcopy(BY["fairy_ring"])
    anchor = tuple(r["pokemon"]["anchor"])
    rep = A.Report()
    A.check_resident(DOC, r, anchor, rep, A.DATA)
    assert not rep.errors, rep.errors
    for level, want in ((36, "ceiling"), (30, "before gym3_cleared")):
        r["pokemon"]["level"] = level
        rep = A.Report()
        A.check_resident(DOC, r, anchor, rep, A.DATA)
        assert any(want in e for e in rep.errors), (level, rep.errors)


# ------------------------------------------------------------------ the committed build, on the canonical heightmap


# Without it the committed records (feet, npc_at, cache, bbox) could disagree with the real ground unseen.
def test_the_committed_build_on_the_heightmap_has_only_the_known_fault(tmp_path):
    if not os.environ.get("COBBLERS_SOURCE_ROOT"):
        pytest.skip("NOT_EXECUTED: COBBLERS_SOURCE_ROOT is not set: the canonical heightmap is outside the repo")
    import ground
    g = ground.load()
    doc = SR.load()
    written, _built = SR.files(doc, g)                      # the generator's own checks ON: it must build
    for rel, text in written.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    water = A.Water(g, [tuple(r["site"]["centre"]) for r in DOC["residents"]])
    rep = A.audit(DOC, g, water, tmp_path, SR.placement_steps(doc, g) + SR.entity_steps(doc, g))
    other = [e for e in rep.errors if not any(e.startswith(c + ":") and t in e for c, t in KNOWN)]
    assert not other, other[:5]
    for c, t in KNOWN:
        assert any(e.startswith(c + ":") and t in e for e in rep.errors), \
            "KNOWN fault no longer reported (fixed?): remove it from KNOWN: %s" % t


# Without it a pack the generator never wrote (or wrote elsewhere) would audit clean.
def test_a_missing_pack_fails_closed(tmp_path):
    rep = A.audit(DOC, G, W, tmp_path / "absent", [])
    assert rep.errors and rep.errors[0].startswith("pack:")


# Without it a re-application that never runs the builds or summons (an empty R9SR/R18SR) would audit clean.
def test_missing_steps_fail_closed(tmp_path):
    build(tmp_path)
    rep = A.audit(DOC, G, W, tmp_path, [])
    steps = [e for e in rep.errors if e.startswith("steps:")]
    assert len([e for e in steps if "its build does not run inside" in e]) == 6
    assert any("grandmother_cap: 0 summon steps" in e for e in steps)
    assert any("half_house: 0 R18SR npc steps" in e for e in steps)
