"""tools/northern_residents_audit.py against tools/northern_residents.py: the audit's derived spots and clearing boxes are
the hand-computed ones, and a broken GENERATOR fails a named check.

Written by an agent that built none of the six northern residents (CLAUDE.md principle 16). Every mutation below
changes the generator's CODE (a function of tools/northern_residents.py) and leaves data/northern_residents.json and
every other data file alone: a record-side mutation moves the expectation and the output together and proves nothing
(CLAUDE.md, "How to prove an audit is independent"). A mutation counts as caught only by an error the unmutated build
does not already have. The siting, badge and carving rules read no generator output, so they are tested on data the
test moves or on hand cases.

THE MUTATION RUN (2026-10-03, by hand, on the canonical heightmap): in tools/northern_residents.py piece_clearing,
`ox, oz = p.get("at") or (0, 0)` became `ox, oz = (p.get("at") or (0, 0))[0] + 1, (p.get("at") or (0, 0))[1]` -- every
clearing one block east, data untouched. The generator's own record check then refused to write (its bbox moved), so
the pack was written with files(check=False) and audited: unmutated, 3 problems (the three KNOWN siting faults below);
mutated, 43 -- among them "clearing: <id> <piece>: the box [...] is not cleared of [...]" (hide_and_seek_den's
thicket and both of hunters_hide's clearings in the lines read), "writes: ... a clear outside the bbox", and "steps:
... does not run inside a forceload of its bbox" for each of the six sites that has a clearing. Reverted (git checkout). The same mutation is
test_a_clearing_shifted_one_block_is_caught below, on synthetic ground.

Most tests run on a synthetic ground, dead flat at y100 and dry everywhere unless a test wets a column, so every feet
y is 101 and every clearing box runs from y101 to 100 + up, by hand. The committed build on the canonical heightmap
is tested last (skipped, and says so, when tools/terrain.env_source_root() finds no heightmap).

NOT covered, and it needs a running server: that the blocks land and the clearings leave no floating canopy, that the
keeper spawns, holds and wakes the three Pokemon, that the NPCs appear and their dialogue runs, that the rewards pay
once, that the function effect and the player_tag read work as a pair in game.
"""
import copy
import inspect
import json
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import northern_residents as NR  # noqa: E402
import northern_residents_audit as A  # noqa: E402

DOC = json.loads((ROOT / "data" / "northern_residents.json").read_text(encoding="utf-8"))
BY = {r["id"]: r for r in DOC["residents"]}
REAPPLY = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")

# Faults this audit found in the committed build on 2026-10-03, reported, not fixed (the data and generator are the
# builder's). Each is a site closer than rules.authored_clearance (96) to a box data/routes.json authors (a route's
# biome corridor, {"min_x", "max_x", "min_z", "max_z"}): tools/southern_residents.authored_points(), the builder's
# guard, reads only x/z dicts and coordinate lists, never a min/max box, so it never saw them;
# tools/southern_residents_audit.authored() reads such a box as a filled rectangle, the standard the southern six
# were held to. When one is fixed (or the owner rules corridors out of the rule) the heightmap test fails and says so.
# Resolved 2026-10-03 by the builder: the three sites (stubborn_tree 73, wandering_stone 76, hide_and_seek 93 from a
# data/routes.json corridor box) were re-sited (data/northern_residents.json superseded_site) and the generator's guard
# now counts the corridor boxes as filled rectangles (tools/southern_residents.py corridor_check). Entries removed.
KNOWN = []


class Ground:
    """Flat y100."""

    def __call__(self, x, z):
        return 100


class Water:
    """The water surface y, or None; truthy where wet, which is also what the generator's wet(x, z) means."""

    def __init__(self, extra=()):
        self.extra = set(extra)

    def __call__(self, x, z):
        return 101 if (x, z) in self.extra else None

    level = __call__


G = Ground()
W = Water()


def build(out, g=G, w=W):
    """The generator's pack on this ground, its own siting checks off (the audit is what must catch a fault)."""
    written, built = NR.files(NR.load(), g, w, check=False)
    for rel, text in written.items():
        f = Path(out) / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    return written, built


def steps_on(g, w):
    # the generator's own R9NR + R18NR, on this ground and water (its _built() reads the real water; this hands it ours)
    orig = NR.sites
    NR.sites = lambda d, gg, ww=None: orig(d, gg, w)
    try:
        doc = NR.load()
        return NR.placement_steps(doc, g) + NR.entity_steps(doc, g)
    finally:
        NR.sites = orig


def run(tmp, g=G, w=W, steps=None):
    build(tmp, g, w)
    if steps is None:
        steps = steps_on(g, w)
    return A.audit(DOC, g, w, Path(tmp), steps)


def mutate(monkeypatch, owner, name, old, new):
    """Replace `old` with `new` in the SOURCE of owner.name and install the result: a change to the generator's code,
    never to its data."""
    fn = getattr(owner, name)
    src = textwrap.dedent(inspect.getsource(fn))
    assert old in src, "the mutation's anchor text is not in %s any more: %r" % (name, old)
    ns = dict(fn.__globals__)
    exec(compile(src.replace(old, new, 1), fn.__code__.co_filename, "exec"), ns)
    monkeypatch.setattr(owner, name, ns[name])


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    return run(tmp_path_factory.mktemp("north_base"))


def caught(rep, baseline, check):
    return [e for e in rep.errors if e not in set(baseline.errors) and e.startswith(check + ":")]


def known(e):
    return any(e.startswith(c + ":") and t in e for c, t in KNOWN)


# ------------------------------------------------------------------ the audit's own derivations, by hand


# Without it the audit's feet could drift from the record's geometry and still agree with the generator.
def test_the_audits_feet_on_flat_ground_are_one_above_it_everywhere():
    want = {"stubborn_tree": {"anchor": (1616, 101, 3280), "npc": (1619, 101, 3283)},
            "agnes_carving": {"npc": (1694, 101, 2231)}, "pips_gym": {"npc": (4608, 101, 1718)},
            "wandering_stone": {"anchor": (5259, 101, 2704)}, "hide_and_seek": {"npc": (6696, 101, 3718)},
            # Lettie stands on the hollow's podzol floor, laid at max ground (y100) under its footprint
            "hide_and_seek_den": {"npc": (6752, 101, 3660)},
            "hunters_hide": {"anchor": (5532, 101, 3248), "npc": (5485, 101, 3201)}}
    for rid, w in want.items():
        s = A.spots_of(BY[rid], A.expect(BY[rid], G, W))
        for k, v in w.items():
            assert s[k] == v, (rid, k, s[k])


class Slope:
    """y = 100 + x mod 4: a square four or more wide has min 100 and max 103."""

    def __call__(self, x, z):
        return 100 + x % 4


# Without it a clearing seated on the centre's ground (not the square's lowest and highest) would pass.
def test_a_clearings_box_runs_from_min_ground_plus_one_to_max_ground_plus_up():
    E = A.expect(BY["stubborn_tree"], G, W)
    assert [c[1] for c in E.clearings] == [(1601, 101, 3265, 1631, 116, 3295)]
    E = A.expect(BY["agnes_carving"], Slope(), lambda x, z: None)
    # the wagon's clearing r9 round (1696, 2224), up 14; the oak's glade r4 round (1704, 2168), up 14
    assert [c[1] for c in E.clearings] == [(1687, 101, 2215, 1705, 117, 2233), (1700, 101, 2164, 1708, 117, 2172)]


# Without it a site's box clear over a stream (which #minecraft:replaceable would drain) would pass.
def test_a_clearing_over_a_wet_column_is_named():
    E = A.expect(BY["hide_and_seek"], G, Water(extra={(6699, 3713)}))
    assert E.clearings[0][2] == [(6699, 3713)]


# Without it the audit's carving reading could accept any text near the sign's.
def test_the_carving_reading_is_word_for_word_and_ignores_the_carvers_mark():
    assert A._sign_text(["SHE SAID YES", "I STILL CANT", "BELIEVE IT", "- E."]) == "she said yes i still cant believe it"
    assert A._said("It says 'She said yes. I still can't believe it.'") == "she said yes i still cant believe it"
    assert A._sign_text(["A.M. + E.M.", "", "1st of May", ""]) == A._said("It says 'A.M. + E.M., 1st of May.'")
    assert A._said("It says 'She said no.'") != A._sign_text(["SHE SAID YES"])


# Without it Pip's windows could overlap (two speeches at once) or leave a badge count with none.
def test_the_badge_evaluator_counts_a_flag_as_held_from_its_gym_on():
    c = {"kind": "all", "conditions": [{"kind": "flag", "flag": "gym5_cleared"},
                                       {"kind": "not", "condition": {"kind": "flag", "flag": "gym6_cleared"}}]}
    assert [n for n in range(9) if A._visible(c, n)] == [5]
    assert A._visible({"kind": "progression_equals", "field": "x", "value": False}, 0)


# ------------------------------------------------------------------ the unmutated generator


# Without it every mutation test below could be catching the audit's own false positives.
def test_the_unmutated_build_on_synthetic_ground_fails_only_its_recorded_ys_and_the_known_faults(baseline):
    other = [e for e in baseline.errors if not e.startswith("ys:") and not known(e)]
    assert not other, other[:5]
    # the records were measured on the real heightmap, so on flat y100 they disagree: the ys check does read them
    assert any(e.startswith("ys: stubborn_tree:") for e in baseline.errors)


# ------------------------------------------------------------------ generator mutations


# Without it a clearing a block off its site (a canopy left over the woodpile) would pass.
def test_a_clearing_shifted_one_block_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, NR, "piece_clearing", 'ox, oz = p.get("at") or (0, 0)',
           'ox, oz = (p.get("at") or (0, 0))[0] + 1, (p.get("at") or (0, 0))[1]')
    rep = run(tmp_path)
    assert any("stubborn_tree the felled wood: the box" in e for e in caught(rep, baseline, "clearing")), rep.errors[:5]


# Without it a clearing that starts at the ground (the box one lower) would pass.
def test_a_clearing_one_block_lower_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, NR, "piece_clearing", "min(gs) + 1, s.cz + oz - r", "min(gs), s.cz + oz - r")
    rep = run(tmp_path)
    assert any("hunters_hide the hollow: the box" in e for e in caught(rep, baseline, "clearing")), rep.errors[:5]


# Without it the generator's refusal to clear over water could be dropped unseen.
def test_the_clearings_wet_refusal_removed_is_caught(monkeypatch, tmp_path):
    w2 = Water(extra={(6699, 3713)})                          # inside Tam's home-base clearing, nothing built on it
    with pytest.raises(SystemExit):
        build(tmp_path / "guarded", G, w2)                    # the guard in place: the generator refuses
    mutate(monkeypatch, NR, "piece_clearing", "if wet:", "if False:")
    rep = run(tmp_path / "mutant", G, w2)
    errs = [e for e in rep.errors if e.startswith("clearing: hide_and_seek home base")]
    assert any("wet column" in e for e in errs), rep.errors[:6]
    assert any("reaches the water" in e for e in rep.errors if e.startswith("writes: hide_and_seek")), rep.errors[:6]


# Without it a clear run after the blocks (it would take the oak, the hollow's boughs, the woodpile) would pass.
def test_clears_moved_after_the_writes_are_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, NR, "files", "lines = SR.build_lines(doc, r, s, box)",
           "lines = SR.build_lines(doc, r, s, box); lines = lines[:3] + [l for l in lines[3:] if 'replace #' not in l]"
           " + [l for l in lines[3:] if 'replace #' in l]")
    rep = run(tmp_path)
    assert any("runs after the write" in e for e in caught(rep, baseline, "clearing")), rep.errors[:5]


# Without it the keeper could spawn and leash a resident a block over its spot.
def test_an_anchor_off_its_ground_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, NR, "files", "a = SR.anchor(s, r)", "a = SR.anchor(s, r); a = (a[0], a[1] + 1, a[2])")
    rep = run(tmp_path)
    assert any("old_knot" in e for e in caught(rep, baseline, "keeper")), rep.errors[:5]


# Without it an NPC the re-application stands a block off the spot its record and the heightmap give would pass.
def test_an_npc_step_shifted_one_block_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, NR, "npc_placements", 'SR.spot(s, n["at"])', '(lambda v: (v[0] + 1, v[1], v[2]))(SR.spot(s, n["at"]))')
    rep = run(tmp_path)
    errs = caught(rep, baseline, "steps")
    for rid in ("stubborn_tree", "hide_and_seek_den", "hunters_hide"):
        assert any("%s: the npc step" % rid in e for e in errs), (rid, rep.errors[:5])


# Without it a resident never summoned or never bound by R18NR would pass.
def test_a_summon_without_its_bind_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, NR, "entity_steps", '("fn", "%s:%s/%s/bind_new" % (b["namespace"], b["folder"], e["id"])), ', "")
    rep = run(tmp_path)
    assert any("heave: the summon is not bound" in e for e in caught(rep, baseline, "steps")), rep.errors[:5]


# Without it Lettie could be found and the tag Tam reads never set.
def test_the_player_tag_function_misspelt_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, NR, "files", '"tag @s add %s" % pt["tag"]', '"tag @s add %s_" % pt["tag"]')
    rep = run(tmp_path)
    assert any("found_lettie" in e for e in caught(rep, baseline, "dialogue")), rep.errors[:5]


# Without it a site's build run outside the forceload of its own box (the fills silently fail) would pass.
def test_a_build_outside_its_forceload_is_caught(tmp_path, baseline):
    steps = [s if not (s[0] == "cmd" and s[1].startswith("forceload add 1601 ")) else ("cmd", "forceload add 0 0 1 1")
             for s in steps_on(G, W)]
    rep = run(tmp_path, steps=steps)
    assert any("stubborn_tree: its build does not run inside a forceload" in e for e in caught(rep, baseline, "steps")), rep.errors[:5]


# Without it a re-application that never runs the builds or summons (an empty R9NR/R18NR) would audit clean.
def test_missing_steps_fail_closed(tmp_path):
    build(tmp_path)
    rep = A.audit(DOC, G, W, tmp_path, [])
    steps = [e for e in rep.errors if e.startswith("steps:")]
    assert len([e for e in steps if "its build does not run inside" in e]) == len(DOC["residents"])
    for pk in ("old_knot", "heave", "tilpey_hart"):
        assert any("%s: 0 summon steps" % pk in e for e in steps), pk
    assert any("hunters_hide: 0 R18NR npc steps" in e for e in steps)


# Without it a pack the generator never wrote (or wrote elsewhere) would audit clean.
def test_a_missing_pack_fails_closed(tmp_path):
    rep = A.audit(DOC, G, W, tmp_path / "absent", [])
    assert any(e.startswith("pack:") for e in rep.errors)


# ------------------------------------------------------------------ tools/reapply.py


# Without it R9NR/R18NR could be dropped from, or misplaced in, the re-application and nothing would say so.
def test_the_wiring_is_clean_and_bites_on_a_dropped_or_misplaced_step():
    ok = A.Report()
    A.check_wiring(DOC, ok, REAPPLY)
    assert not ok.errors, ok.errors
    for old, new, want in (('out.append(("R18NR"', 'out.append(("R18XX"', "appends step R18NR 0 times"),
                           ("northern_residents.placement_steps()))", "southern_residents.placement_steps()))", "not northern_residents.placement_steps"),
                           ('add("northern_residents_audit"', 'add("northern_residents_check"', "no prepare job northern_residents_audit"),
                           ('"cobblers_northern_residents")', '"cobblers_other")', "WORLD_LOCAL")):
        assert old in REAPPLY, old
        rep = A.Report()
        A.check_wiring(DOC, rep, REAPPLY.replace(old, new, 1))
        assert any(want in e for e in rep.errors), (old, rep.errors)
    # R9NR and R9E swapped in the order: the blocks would land after the Habitat Blocks' chunks reloaded
    swapped = REAPPLY.replace('out.append(("R9E"', 'out.append(("R9TMP"', 1).replace('out.append(("R9NR"', 'out.append(("R9E"', 1) \
        .replace('out.append(("R9TMP"', 'out.append(("R9NR"', 1)
    rep = A.Report()
    A.check_wiring(DOC, rep, swapped)
    assert any("R9NR runs after R9E" in e for e in rep.errors), rep.errors


# ------------------------------------------------------------------ rules that read only data


# Without it a site moved south of row D, onto a road, or into a town would pass.
def test_siting_rules_bite_on_a_moved_column():
    pts = A.authored(DOC, A.DATA)
    r = BY["hunters_hide"]
    spots = {"npc": (5485, 101, 3201)}
    ok = A.Report()
    A.check_siting(DOC, r, {(5480, 3196)}, spots, pts, ok, A.DATA)
    assert not ok.errors, ok.errors
    routes = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"]
    px, pz = routes["route_06_koga_to_sabrina"][0][:2]
    for col, want in (((px, pz), "authored"), ((5480, 4100), "south of z 4096")):
        rep = A.Report()
        A.check_siting(DOC, r, {(5480, 3196), col}, spots, pts, rep, A.DATA)
        assert any(want in e for e in rep.errors), (col, want, rep.errors)
    rep = A.Report()
    A.check_siting(DOC, r, {(5480, 3196)}, {"npc": (px, 101, pz)}, pts, rep, A.DATA)
    assert any("the npc" in e and "route path" in e for e in rep.errors), rep.errors


# Without it a resident above its place's ceiling, or catchable before its gate, would pass.
def test_resident_rules_bite_on_a_moved_level():
    r = copy.deepcopy(BY["wandering_stone"])
    anchor = tuple(r["pokemon"]["anchor"])
    rep = A.Report()
    A.SA.check_resident(DOC, r, anchor, rep, A.DATA)
    assert not rep.errors, rep.errors
    for level, want in ((46, "ceiling"), (40, "before gym5_cleared")):
        r["pokemon"]["level"] = level
        rep = A.Report()
        A.SA.check_resident(DOC, r, anchor, rep, A.DATA)
        assert any(want in e for e in rep.errors), (level, rep.errors)


# Without it the committed dialogue could drift from the carving, Pip's windows or the tag pair.
def test_the_committed_dialogue_keeps_the_places_promises():
    rep = A.Report()
    A.check_carving(DOC, BY["agnes_carving"], rep, A.DATA)
    A.check_badges(DOC, BY["pips_gym"], rep, A.DATA)
    assert not rep.errors, rep.errors


# Without it a second keeper reusing this pack's objective would reset these residents' clocks.
def test_the_objective_is_this_packs_alone():
    rep = A.Report()
    A.check_objective(DOC, rep, A.DATA)
    assert not rep.errors, rep.errors


# ------------------------------------------------------------------ the committed build, on the canonical heightmap


# Without it the committed records (feet, npc_at, bbox) could disagree with the real ground unseen.
def test_the_committed_build_on_the_heightmap_has_only_the_known_faults(tmp_path):
    import terrain
    if not terrain.env_source_root():
        pytest.skip("NOT_EXECUTED: no COBBLERS_SOURCE_ROOT (environment or .claude/settings.json): the heightmap is outside the repo")
    import ground
    g = ground.load()
    doc = NR.load()
    written, _built = NR.files(doc, g)                      # the generator's own checks ON: it must build
    for rel, text in written.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    water = A.SA.Water(g, [tuple(r["site"]["centre"]) for r in DOC["residents"]])
    rep = A.audit(DOC, g, water, tmp_path, NR.placement_steps(doc, g) + NR.entity_steps(doc, g))
    other = [e for e in rep.errors if not known(e)]
    assert not other, other[:5]
    for c, t in KNOWN:
        assert any(e.startswith(c + ":") and t in e for e in rep.errors), \
            "KNOWN fault no longer reported (fixed?): remove it from KNOWN: %s" % t
