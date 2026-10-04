"""tools/far_south_audit.py against tools/far_south.py (and tools/rewards_pack.py, which pays the caches): the audit's
derived spots are the hand-computed ones, and a broken GENERATOR fails a named check.

Written by an agent that built none of the five far-south places (CLAUDE.md principle 16). Every mutation below
changes a generator's CODE (a function of tools/far_south.py or tools/rewards_pack.py) and leaves data/far_south.json,
data/rewards.json and every other data file alone: a record-side mutation moves the expectation and the output
together and proves nothing (CLAUDE.md, "How to prove an audit is independent"). A mutation counts as caught only by an
error the unmutated build does not already have. The siting, keep-out, species and wiring rules read no generator
output, so they are tested on data the test moves, on hand cases, or on a synthetic jar.

THE MUTATION RUN (2026-10-04, by hand, on the canonical heightmap and the Cobblemon 1.8 jar): in tools/far_south.py
files(), `a = SR.anchor(s, r)` was followed by `a = (a[0] + 1, a[1], a[2])` (every summon and keep one block east), and
sites() handed tools/northern_residents.py a copy of the record with glyph_ring's centre moved 2 east (the site built
two blocks off its record); data untouched. The generator's own record check then refused to write, so the pack was
written with files(check=False) and audited: unmutated, 0 problems and the 3 KNOWN catch-window defects; mutated, 44
problems -- "writes: glyph_ring: ... outside the bbox", "45 block(s) off-plan", "steps: glyph_ring: its build does not
run inside a forceload of its bbox", and for each of the three residents "keeper: ... the spawn is zebstrika at
('2809.5', ...), expected ... 2808.5". Reverted (git checkout). The same two mutations are tests below, on synthetic
ground.

Most tests run on a synthetic ground, dead flat at y100 and dry everywhere unless a test wets a column, so every
standing spot is y101 and every cache container y100, by hand. The committed build on the canonical heightmap is tested
last (skipped, and says so, when tools/terrain.env_source_root() finds no heightmap).

NOT covered, and it needs a running server: that the blocks land, that the keeper spawns and wakes the three Pokemon
only for a gym7_cleared player, that the caches' advancements fire and pay once, that the level cap refuses a catch.
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

import far_south as FS  # noqa: E402
import far_south_audit as A  # noqa: E402
import rewards_pack as RP  # noqa: E402

DOC = json.loads((ROOT / "data" / "far_south.json").read_text(encoding="utf-8"))
BY = {r["id"]: r for r in DOC["residents"]}
REWARDS = json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))
REAPPLY = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")


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


class Jar:
    """A synthetic Cobblemon jar: three species native to arid country, and the six cache items' models."""

    def __init__(self, natives=None, items=None):
        self.natives = natives or {"zebstrika": {"arid"}, "crustle": {"arid"}, "sigilyph": {"arid"}}
        self.species = {k: {} for k in self.natives}
        items = items if items is not None else ["smooth_rock", "dusk_ball", "thunder_stone", "soft_sand", "leaf_stone",
                                                 "miracle_seed"]
        self.names = {"assets/cobblemon/models/item/%s.json" % i for i in items}

    def info(self, key):
        return self.natives[key[0]], set(), False, "synthetic"


G = Ground()
W = Water()


def build(out, g=G, w=W):
    """The generator's pack on this ground, its own siting checks off (the audit is what must catch a fault)."""
    written, built = FS.files(FS.load(), g, w, check=False)
    for rel, text in written.items():
        f = Path(out) / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    return written, built


def steps_on(g, w):
    # the generator's own R9FS + R18FS, on this ground and water (its _built() reads the real water; this hands it ours)
    orig = FS.sites
    FS.sites = lambda d, gg, ww=None: orig(d, gg, w)
    try:
        doc = FS.load()
        return FS.placement_steps(doc, g) + FS.entity_steps(doc, g)
    finally:
        FS.sites = orig


def rewards(out):
    RP.write(REWARDS, Path(out))
    return Path(out)


def run(tmp, g=G, w=W, steps=None, jar=None):
    tmp = Path(tmp)
    build(tmp / "pack", g, w)
    rp = rewards(tmp / "rewards")
    if steps is None:
        steps = steps_on(g, w)
    return A.audit(DOC, g, w, tmp / "pack", steps, rpack=rp, jar=jar or Jar())


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
    return run(tmp_path_factory.mktemp("far_south_base"))


def caught(rep, baseline, check):
    return [e for e in rep.errors if e not in set(baseline.errors) and e.startswith(check + ":")]


# ------------------------------------------------------------------ the audit's own derivations, by hand


# Without it the audit's spots could drift from the record's geometry and still agree with the generator.
def test_the_audits_spots_on_flat_ground_are_one_above_it():
    # centre + at, by hand: kraal (2808, 5760) + (0, -3); chimneys (5176, 5968) + (4, 4) and cache (1, -10);
    # glyph ring (7056, 6200) + (0, 0); glass garden (5976, 6544) + (12, -11); folly (2904, 7632) + (-2, -2)
    want = {"stallion_kraal": {"anchor": (2808, 101, 5757), "caches": []},
            "four_chimneys": {"anchor": (5180, 101, 5972), "caches": [(5177, 101, 5958)]},
            "glyph_ring": {"anchor": (7056, 101, 6200), "caches": []},
            "glass_garden": {"caches": [(5988, 101, 6533)]},
            "garden_folly": {"caches": [(2902, 101, 7630)]}}
    for rid, w in want.items():
        s = A.NA.spots_of(BY[rid], A.NA.expect(BY[rid], G, W))
        for k, v in w.items():
            assert s[k] == v, (rid, k, s[k])


# Without it rows F-H could be read from a constant that drifts from data/world.json's grid.
def test_rows_f_to_h_are_the_grids_sixth_to_eighth_rows():
    assert A.row_f_line(A.DATA) == 5 * 1024
    assert A.grid_south_edge(A.DATA) == 8 * 1024


# Without it the keep-out box could be narrowed off the Rift arms it claims to cover.
def test_the_keep_out_box_is_the_rift_arms_widened_by_300():
    # rift_south_west_arm x3544-4263 z3880-5407, rift_south_east_arm x3992-4623 z3760-5375 (data/regions.json)
    assert A.keep_out_derived(A.DATA) == [3544 - 300, 3760 - 300, 4623 + 300, 5407 + 300]
    ok = A.Report()
    A.check_keep_out(DOC, ok, A.DATA)
    assert not ok.errors, ok.errors
    narrow = copy.deepcopy(DOC)
    narrow["rules"]["keep_out_box"]["box"] = [3544, 3760, 4623, 5407]
    rep = A.Report()
    A.check_keep_out(narrow, rep, A.DATA)
    assert any("does not hold the Rift arms" in e for e in rep.errors), rep.errors


# Without it the audit's polygon reading could call a column inside the Mega field outside it.
def test_the_polygon_test_and_distance_are_hand_checkable():
    import numpy as np
    sq = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert A._in_poly(5, 5, sq) and not A._in_poly(15, 5, sq)
    d = A._poly_distance(np.array([[15.0, 5.0], [13.0, 14.0]]), sq)
    assert list(np.round(d, 6)) == [5.0, 5.0]


# ------------------------------------------------------------------ the unmutated generator


# Without it every mutation test below could be catching the audit's own false positives.
def test_the_unmutated_build_on_synthetic_ground_fails_only_its_recorded_ys_and_the_known_faults(baseline):
    real, hits, stale = A.classify(baseline.errors)
    other = [e for e in real if not e.startswith("ys:")]
    assert not other, other[:5]
    assert not stale, stale
    # the records were measured on the real heightmap, so on flat y100 they disagree: the ys check does read them
    assert any(e.startswith("ys: stallion_kraal: site.measured says y107") for e in baseline.errors), baseline.errors[:5]


# ------------------------------------------------------------------ generator mutations


# Without it the keeper could spawn, leash and wake a resident a block off its spot.
def test_a_summon_shifted_one_block_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, FS, "files", "a = SR.anchor(s, r)", "a = SR.anchor(s, r); a = (a[0] + 1, a[1], a[2])")
    rep = run(tmp_path)
    errs = caught(rep, baseline, "keeper")
    for pk in ("greymane", "fifth_chimney", "old_watcher"):
        assert any(e.startswith("keeper: %s: the spawn is" % pk) for e in errs), (pk, rep.errors[:5])


# Without it a site the generator builds off its record (into another place's ground) would pass.
def test_a_site_shifted_two_blocks_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, FS, "sites", "return NR.sites(doc, g, wet)",
           "d2 = json.loads(json.dumps(doc)); d2['residents'][3]['site']['centre'][0] += 2; return NR.sites(d2, g, wet)")
    rep = run(tmp_path)
    assert any("glyph_ring" in e and "outside the bbox" in e for e in caught(rep, baseline, "writes")), rep.errors[:5]
    assert any("glyph_ring" in e and "off-plan" in e for e in caught(rep, baseline, "writes")), rep.errors[:5]


# Without it a site the generator moves out of rows F-H (into row E) would pass.
def test_a_site_moved_into_row_e_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, FS, "sites", "return NR.sites(doc, g, wet)",
           "d2 = json.loads(json.dumps(doc)); d2['residents'][3]['site']['centre'][1] -= 1200; return NR.sites(d2, g, wet)")
    rep = run(tmp_path)
    assert any("glyph_ring" in e and "outside rows F-H" in e for e in caught(rep, baseline, "siting")), rep.errors[:5]


# Without it a gated resident the re-application summons anyway (before gym 7) would pass.
def test_the_gate_dropped_from_the_steps_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, FS, "entity_steps", 'if not r.get("pokemon") or r["pokemon"].get("appears_after"):',
           'if not r.get("pokemon"):')
    rep = run(tmp_path, steps=None)
    # entity_steps is read by steps_on, which runs after the mutation is installed
    errs = caught(rep, baseline, "steps")
    assert any("greymane is presence-gated on gym7_cleared but the re-application summons it" in e for e in errs), rep.errors[:5]


# Without it a keeper that spawns the resident for a player without gym 7 would pass.
def test_the_gate_dropped_from_the_keeper_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, FS, "files", "e = SR.resident_record(r)\n",
           "e = SR.resident_record(r); e['build']['appears_after'] = None\n")
    rep = run(tmp_path)
    errs = caught(rep, baseline, "keeper")
    for pk in ("greymane", "fifth_chimney", "old_watcher"):
        assert any("%s: the spawn is not gated on gym7_cleared" % pk in e for e in errs), (pk, rep.errors[:5])


# Without it a build that lays a spawn-condition block (sand calls a species in) would pass.
def test_a_spawn_condition_block_written_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, FS, "files", 'fn["%s/build" % r["id"]] = lines',
           'fn["%s/build" % r["id"]] = lines + ["setblock %d 101 %d minecraft:sand" % (s.cx + 2, s.cz + 2)]')
    rep = run(tmp_path)
    # sand is outside blocks.ids too (the record keeps every spawn condition out of its list), and the replay names the
    # first rule a write breaks; either way the write is refused and named
    errs = caught(rep, baseline, "writes")
    assert any("minecraft:sand" in e and ("a spawn condition" in e or "not in blocks.ids" in e) for e in errs), rep.errors[:5]
    assert any("off-plan" in e for e in errs), errs[:5]


# Without it a build function the re-application runs outside the forceload of its box would pass.
def test_a_build_held_off_its_box_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, FS, "placement_steps", 'hold = "%d %d %d %d" % tuple(box)',
           'hold = "%d %d %d %d" % (box[0] + 1, box[1], box[2] + 1, box[3])')
    rep = run(tmp_path)
    errs = caught(rep, baseline, "steps")
    assert len([e for e in errs if "its build does not run inside a forceload" in e]) == len(DOC["residents"]), errs


# Without it a cache that pays one item too many (or one too few) would pass.
def test_a_cache_function_paying_the_wrong_count_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, RP, "function", 'c["count"]))', 'c["count"] + 1))')
    rep = run(tmp_path)
    errs = caught(rep, baseline, "caches")
    for rid in ("far_south_hoodoo_tin", "far_south_glass_cutters_box", "far_south_folly_cellar"):
        assert any("%s's function gives" % rid in e for e in errs), (rid, rep.errors[:5])


# Without it a cache whose advancement fires on a box other than its trigger (wrong place, or never) would pass.
def test_a_cache_advancement_on_the_wrong_box_is_caught(monkeypatch, tmp_path, baseline):
    mutate(monkeypatch, RP, "advancement", '"x": {"min": x0, "max": x1 + 1}', '"x": {"min": x0 + 1, "max": x1 + 2}')
    rep = run(tmp_path)
    assert any("far_south_hoodoo_tin's advancement box" in e for e in caught(rep, baseline, "caches")), rep.errors[:5]


# Without it a re-application that never runs the builds (an empty R9FS) would audit clean.
def test_missing_steps_fail_closed(tmp_path):
    build(tmp_path / "pack")
    rep = A.audit(DOC, G, W, tmp_path / "pack", [], rpack=rewards(tmp_path / "rewards"), jar=Jar())
    steps = [e for e in rep.errors if e.startswith("steps:")]
    assert len([e for e in steps if "its build does not run inside" in e]) == len(DOC["residents"])


# Without it a pack the generator never wrote (or a rewards pack nobody wrote) would audit clean.
def test_a_missing_pack_or_rewards_pack_fails_closed(tmp_path):
    rep = A.audit(DOC, G, W, tmp_path / "absent", [])
    assert any(e.startswith("pack:") for e in rep.errors)
    build(tmp_path / "pack")
    rep = A.audit(DOC, G, W, tmp_path / "pack", steps_on(G, W), rpack=None, jar=Jar())
    assert any("no rewards pack" in e for e in rep.errors), rep.errors[:5]


# ------------------------------------------------------------------ rules that read only data


# Without it a column moved into the keep-out box, the Mega field, a route corridor or onto a path would pass.
def test_siting_rules_bite_on_a_moved_column():
    pts = A.SA.authored(DOC, A.DATA, record=A.RECORD)
    r = BY["four_chimneys"]
    spots = {"anchor": (5180, 159, 5972), "caches": [(5177, 159, 5958)]}
    ok = A.Report()
    A.check_siting(DOC, r, {(5176, 5968)}, spots, pts, ok, A.DATA)
    assert not ok.errors, ok.errors
    mega = json.loads((ROOT / "data" / "gulch_mine.json").read_text(encoding="utf-8"))["mega_field"]["polygon"]
    mx = round(sum(p[0] for p in mega) / len(mega))
    mz = round(sum(p[1] for p in mega) / len(mega))
    routes = json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))["routes"]
    b = routes[0]["spawn_scope"]["boxes"][0]
    for col, want in (((4000, 5500), "keep-out box"), ((5176, 5000), "outside rows F-H"),
                      ((b["min_x"] + 1, b["min_z"] + 1), "authored")):
        rep = A.Report()
        A.check_siting(DOC, r, {(5176, 5968), col}, spots, pts, rep, A.DATA)
        assert any(want in e for e in rep.errors), (col, want, rep.errors)
    # the Mega field: a column at its vertex mean is inside or within the clearance of it
    rep = A.Report()
    A.check_siting(DOC, r, {(5176, 5968), (mx, mz)}, spots, pts, rep, A.DATA)
    assert any("the Mega field" in e for e in rep.errors), rep.errors
    paths = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"]
    px, pz = next(iter(paths.values()))[0][:2]
    rep = A.Report()
    A.check_siting(DOC, r, {(5176, 5968)}, {"anchor": spots["anchor"], "caches": [(px, 159, pz)]}, pts, rep, A.DATA)
    assert any("the cache" in e and "route path" in e for e in rep.errors), rep.errors


# Without it a resident above its place's ceiling, or gated on anything but gym 7, would pass.
def test_resident_rules_bite_on_a_moved_level_and_gate():
    r = copy.deepcopy(BY["stallion_kraal"])
    anchor = tuple(r["pokemon"]["anchor"])
    rep = A.Report()
    A.SA.check_resident(DOC, r, anchor, rep, A.DATA)
    assert all("above the cap 55" in e for e in rep.errors), rep.errors      # the KNOWN catch-window defect only
    r["pokemon"]["level"] = 61
    rep = A.Report()
    A.SA.check_resident(DOC, r, anchor, rep, A.DATA)
    assert any("ceiling 60" in e for e in rep.errors), rep.errors
    r["pokemon"]["gate"] = "gym6_cleared"
    rep = A.Report()
    A.check_gate(r, rep)
    assert any("gate is gym6_cleared" in e for e in rep.errors), rep.errors


# Without it a species placed out of its country (a cold-native on the savanna) or not in the jar would pass.
def test_the_species_climate_and_presence_bite():
    r = BY["stallion_kraal"]
    rep = A.Report()
    A.check_species(r, Jar(), rep, A.DATA)
    assert not rep.errors, rep.errors
    rep = A.Report()
    A.check_species(r, Jar(natives={"zebstrika": {"cold"}}), rep, A.DATA)
    assert any("2 steps" in e or "3 steps" in e for e in rep.errors), rep.errors
    rep = A.Report()
    A.check_species(r, Jar(natives={"crustle": {"arid"}}), rep, A.DATA)
    assert any("not a species in the Cobblemon jar" in e for e in rep.errors), rep.errors


# Without it a cache that gives an item the jar does not have would pass.
def test_a_cache_item_missing_from_the_jar_is_caught(tmp_path, baseline):
    rep = run(tmp_path, jar=Jar(items=["dusk_ball"]))
    errs = caught(rep, baseline, "caches")
    assert any("cobblemon:smooth_rock, which is not an item" in e for e in errs), rep.errors[:5]


# Without it a KNOWN defect that has been fixed would keep its entry, and a new fault matching nothing would hide.
def test_known_faults_go_stale_when_they_stop_firing():
    known = [("residents", "x: L1 is above", "w")]
    real, hits, stale = A.classify(["residents: x: L1 is above the cap", "siting: y"], known)
    assert real == ["siting: y"] and hits == ["residents: x: L1 is above the cap"] and not stale
    assert A.classify([], known)[2] == known


# ------------------------------------------------------------------ tools/reapply.py


# Without it R9FS/R18FS or the audit job could be dropped from, or misplaced in, the re-application unseen.
def test_the_wiring_is_clean_and_bites_on_a_dropped_or_misplaced_step():
    ok = A.Report()
    A.check_wiring(DOC, ok, REAPPLY)
    assert not ok.errors, ok.errors
    for old, new, want in (('out.append(("R18FS"', 'out.append(("R18XX"', "appends step R18FS 0 times"),
                           ("far_south.placement_steps()))", "northern_residents.placement_steps()))", "not far_south.placement_steps"),
                           ('add("far_south_audit"', 'add("far_south_check"', "no prepare job far_south_audit"),
                           ('far south\'s keeper spawns its three Pokemon the same way\n               "cobblers_far_south",',
                            'far south\'s keeper spawns its three Pokemon the same way\n               "cobblers_other",',
                            "WORLD_LOCAL")):
        assert old in REAPPLY, old
        rep = A.Report()
        A.check_wiring(DOC, rep, REAPPLY.replace(old, new, 1))
        assert any(want in e for e in rep.errors), (old, rep.errors)
    swapped = REAPPLY.replace('out.append(("R9E"', 'out.append(("R9TMP"', 1).replace('out.append(("R9FS"', 'out.append(("R9E"', 1) \
        .replace('out.append(("R9TMP"', 'out.append(("R9FS"', 1)
    rep = A.Report()
    A.check_wiring(DOC, rep, swapped)
    assert any("R9FS runs after R9E" in e for e in rep.errors), rep.errors


# Without it a second keeper reusing this pack's objective would reset these residents' clocks.
def test_the_objective_is_this_packs_alone():
    rep = A.Report()
    A.check_objective(DOC, rep, A.DATA)
    assert not rep.errors, rep.errors


# ------------------------------------------------------------------ the committed build, on the canonical heightmap


# Without it the committed records (anchors, triggers, containers, bboxes) could disagree with the real ground unseen.
def test_the_committed_build_on_the_heightmap_has_only_the_known_faults(tmp_path):
    import terrain
    if not terrain.env_source_root():
        pytest.skip("NOT_EXECUTED: no COBBLERS_SOURCE_ROOT (environment or .claude/settings.json): the heightmap is outside the repo")
    import ground
    g = ground.load()
    doc = FS.load()
    written, _built = FS.files(doc, g)                      # the generator's own checks ON: it must build
    for rel, text in written.items():
        f = tmp_path / "pack" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    water = A.SA.Water(g, [tuple(r["site"]["centre"]) for r in DOC["residents"]])
    rep = A.audit(DOC, g, water, tmp_path / "pack", FS.placement_steps(doc, g) + FS.entity_steps(doc, g),
                  rpack=rewards(tmp_path / "rewards"), jar=Jar())
    real, hits, stale = A.classify(rep.errors)
    assert not real, real[:5]
    assert not stale, "KNOWN fault no longer reported (fixed?): remove it from KNOWN: %s" % stale
