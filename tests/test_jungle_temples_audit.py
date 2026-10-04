"""tools/jungle_temples_audit.py against tools/jungle_temples.py: the audit's parser, walker and checks on hand-built
fixtures, and a broken GENERATOR fails a named check.

Written by an agent that built none of the three temples (CLAUDE.md principle 16). Every mutation below changes the
generator's CODE (tools/jungle_temples.py plan(), monkeypatched to alter the Site it returns) and leaves
data/jungle_temples.json, data/rewards.json and every other data file alone: a record-side mutation moves the
expectation and the output together and proves nothing (CLAUDE.md, "How to prove an audit is independent"). The
generator's own guards are switched off (files(check=False)) so a broken plan is written and the AUDIT has to catch
it. A mutation counts as caught only by an error the unmutated build does not already have.

The mutations run on a synthetic ground, flat at y100 (the y60 mutation adds a y60 patch), with no water, so every
floor is y100 by hand. The committed build on the canonical heightmap is tested last (skipped, and says so, when
tools/terrain.env_source_root() finds no heightmap).

THE MUTATION RUN (2026-10-04, these tests, synthetic ground): drop the ladder (rungs made air) -> reach + eye; the Ring
Court moved 500 east onto y60 ground -> ground "at or below y62"; the north-face vines moved a block off their wall ->
hold + reach; the summit barrel made a chest -> writes + caches; the fallen stair rebuilt -> reach "without climbing";
the trapdoor made stone -> reach; the arm turned east -> mark; a cobweb -> writes "spawn condition"; the Harbour Mark
raised 3 -> ground "does not rest"; a block 5 past the bbox -> writes (the generator widens its own forceload to
follow, so the steps stay consistent: the step check is proved on the hand case instead).

And by hand on the canonical heightmap (2026-10-04): tools/jungle_temples.py plan() edited to turn every ladder into
air before `return s`; the generator's own guards PASSED it and wrote the pack (847 commands); this audit on that pack:
4 problems -- "eye: ring_court: a ladder of 0 under the trapdoor, the design says 5", "reach: ... cannot be reached
from outside", "no way back out", "not reached by the ladder on the pillar's south face". Reverted (git checkout).

NOT covered, and it needs a running server: that the blocks land and stay put after block updates, that a player can
break the moss carpet and open the trapdoor (survival assumed), that the advancement fires once, that signs read.
"""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import jungle_temples_audit as A  # noqa: E402

DOC = json.loads((ROOT / "data" / "jungle_temples.json").read_text(encoding="utf-8"))
BY = {t["id"]: t for t in DOC["temples"]}
REAPPLY = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")


def flat(y):
    return lambda x, z: y


def dry(x, z):
    return None


# ------------------------------------------------------------------ the parser


# Without it a fill's extent or a clear's filter could be misread and every later check would reason on a wrong world.
def test_replay_expands_fills_and_keeps_clears_apart():
    R = A.Replay("# c\nfill 0 64 0 1 65 2 minecraft:stone\nsetblock 0 64 0 minecraft:vine[north=true]\n"
                 "fill 0 66 0 3 70 3 minecraft:air replace #minecraft:leaves\n")
    assert len(R.blocks) == 2 * 2 * 3                         # 12 cells, one overwritten
    assert A.base(R.blocks[(0, 64, 0)]) == "minecraft:vine"
    assert R.clears == [(0, 66, 0, 3, 70, 3, "#minecraft:leaves")]
    assert len(R.columns()) == 16 and not R.bad


# Without it a summon, a function call or a destroy-mode fill would pass as a block write.
def test_replay_refuses_anything_but_plain_block_writes():
    R = A.Replay("summon minecraft:pig 0 64 0\nfill 0 0 0 1 1 1 minecraft:stone destroy\n"
                 "fill 0 0 0 1 1 1 minecraft:stone replace minecraft:dirt\nfunction a:b\n")
    assert len(R.bad) == 4 and not R.blocks


# ------------------------------------------------------------------ the walker, on flat y64


def shaft(ladder=True, trapdoor=False):
    """A 5-deep shaft at (0, 60..64, 0) in flat y64 ground; its floor is the terrain at y59. Feet at the bottom: y60."""
    lines = []
    for y in range(60, 65):
        if trapdoor and y == 64:
            lines.append("setblock 0 64 0 minecraft:jungle_trapdoor[facing=north,half=top,open=false]")
        elif ladder:
            lines.append("setblock 0 %d 0 minecraft:ladder[facing=south]" % y)
        else:
            lines.append("setblock 0 %d 0 minecraft:air" % y)
    return A.Replay("\n".join(lines))


# Without it a pit you can fall into and never climb out of would read as a reachable cache.
def test_walker_cannot_get_in_or_out_of_a_five_deep_pit_without_a_ladder():
    R = shaft(ladder=False)
    i, o, _p = A.reach(A.World(R, flat(64)), (-3, -3, 3, 3), R, (0, 60, 0))
    assert not i and not o


# Without it the ladder, the one way into the Ring Court's undercroft, would never be credited.
def test_walker_climbs_a_ladder_both_ways():
    R = shaft(ladder=True)
    i, o, path = A.reach(A.World(R, flat(64)), (-3, -3, 3, 3), R, (0, 60, 0))
    assert i and o and path[-1] == (0, 60, 0)


# Without it the "only through the eye" check could not tell an open trapdoor from a shut one.
def test_walker_passes_a_trapdoor_only_when_it_may_open():
    R = shaft(ladder=True, trapdoor=True)
    W = A.World(R, flat(64))
    assert A.reach(W, (-3, -3, 3, 3), R, (0, 60, 0))[0]
    shut = A.World(R, flat(64), blocked=[(0, 64, 0)])
    assert not A.reach(shut, (-3, -3, 3, 3), R, (0, 60, 0))[0]


# Without it a three-high wall would read as a step and a summit as reachable on foot.
def test_walker_jumps_one_block_not_two():
    one = A.Replay("setblock 2 65 0 minecraft:stone")
    two = A.Replay("setblock 2 65 0 minecraft:stone\nsetblock 2 66 0 minecraft:stone")
    assert A.reach(A.World(one, flat(64)), (-3, -3, 3, 3), one, (2, 66, 0))[0]
    assert not A.reach(A.World(two, flat(64)), (-3, -3, 3, 3), two, (2, 67, 0))[0]


# ------------------------------------------------------------------ hold, ground, bbox


def tdoc(fp=(-2, -2, 2, 2)):
    t = {"id": "t", "site": {"centre": [0, 0], "measured": "y64 at the centre"}, "bbox": [-5, -5, 5, 5],
         "pieces": [{"kind": "structure", "name": "s", "footprint": list(fp)}]}
    return {"rules": {"dry_above": 62, "max_foundation": 6}, "temples": [t]}, t


# Without it a vine, ladder or sign with nothing behind it would pass, and pop off on the first block update.
def test_hold_names_an_unbacked_vine_and_ladder():
    R = A.Replay("setblock 0 66 0 minecraft:vine[north=true,south=false]\nsetblock 3 66 3 minecraft:ladder[facing=south]\n"
                 "setblock 5 66 5 minecraft:stone\nsetblock 5 66 6 minecraft:vine[north=true]")
    _d, t = tdoc()
    rep = A.Report()
    A.check_hold(t, R, A.World(R, flat(64)), rep)
    assert len(rep.errors) == 2 and all(e.startswith("hold:") for e in rep.errors), rep.errors


# Without it a ruin could be dug into the ground, float above it, or stand on the sea.
def test_ground_names_digging_floating_and_low_columns():
    doc, t = tdoc()
    R = A.Replay("setblock 0 65 0 minecraft:stone\nsetblock 0 70 1 minecraft:stone\nsetblock 4 60 4 minecraft:stone")
    rep = A.Report()
    A.check_ground(doc, t, R, flat(64), dry, A.floors(t, flat(64)), rep, A.DATA)
    assert any("under the ground outside the undercroft" in e for e in rep.errors)
    assert any("does not rest on the ground" in e for e in rep.errors)
    rep2 = A.Report()
    A.check_ground(doc, t, A.Replay("setblock 0 63 0 minecraft:stone"), flat(62), dry, A.floors(t, flat(62)), rep2, A.DATA)
    assert any("at or below y62" in e for e in rep2.errors), rep2.errors


# Without it a write past the record's bbox would sit outside the forceload that lets it land.
def test_bbox_and_steps_name_a_write_outside_the_box():
    _d, t = tdoc()
    R = A.Replay("setblock 9 65 0 minecraft:stone")
    rep = A.Report()
    A.check_bbox(t, R, [], rep)
    assert rep.has("writes", "outside the bbox")
    doc = {"build": {"namespace": "cobblers", "folder": "jungle_temples"}, "temples": [t]}
    rep = A.Report()
    A.check_steps(doc, [("cmd", "forceload add -5 -5 5 5"), ("fn", "cobblers:jungle_temples/t/build"),
                        ("cmd", "forceload remove -5 -5 5 5")], {"t": R}, rep)
    assert rep.has("steps", "outside its forceload")
    rep = A.Report()
    A.check_steps(doc, [("fn", "cobblers:jungle_temples/t/build")], {"t": A.Replay("")}, rep)
    assert rep.has("steps", "nothing force-loaded")


# ------------------------------------------------------------------ the data-side checks


# Without it the record's keep-clear list could drop the island's heart and the generator would stop guarding it.
def test_keep_clear_list_must_hold_every_derived_neighbour():
    kc = A.derive_keep_clear(DOC)
    ids = {i for i, _b, _s in kc}
    assert {"split_bark", "legendary_mew_temple", "sky_far_reach", "elder_long_isle_south_3"} <= ids, ids
    mew = [b for i, b, _s in kc if i == "legendary_mew_temple"][0]
    assert mew == (7604, 7082, 7640, 7120)                    # the corner (7604, 7082) plus 37 x 39, by hand
    rep = A.Report()
    A.check_keep_clear_list(DOC, kc, rep)
    assert not rep.errors, rep.errors
    short = copy.deepcopy(DOC)
    short["rules"]["keep_clear"]["entries"] = [e for e in short["rules"]["keep_clear"]["entries"] if e["id"] != "split_bark"]
    rep = A.Report()
    A.check_keep_clear_list(short, kc, rep)
    assert rep.has("keep_clear", "lacks split_bark")


# Without it the sea-mark's arm could point anywhere and the quest's "west by the arm" would lie.
def test_the_arm_must_point_toward_sunset_west():
    west = A.Replay("setblock 7559 155 7328 minecraft:stone_brick_slab[type=top]\n"
                    "setblock 7559 152 7328 minecraft:jungle_wall_sign[facing=west]{front_text:{messages:['\"HARBOUR\"']}}")
    east = A.Replay("setblock 7561 155 7328 minecraft:stone_brick_slab[type=top]\n"
                    "setblock 7559 152 7328 minecraft:jungle_wall_sign[facing=west]{front_text:{messages:['\"HARBOUR\"']}}")
    rep = A.Report()
    A.check_mark(DOC, {"harbour_mark": west}, A.DATA, rep)
    assert not [e for e in rep.errors if "arm points" in e or "faces" in e], rep.errors
    rep = A.Report()
    A.check_mark(DOC, {"harbour_mark": east}, A.DATA, rep)
    assert rep.has("mark", "arm points") and rep.has("mark", "not along the arm")


# Without it a temple cache could pay out more than any other find at its tier.
def test_a_cache_over_the_economy_curve_is_named(tmp_path):
    for f in ("regions.json", "encounter_design.json", "world.json"):
        (tmp_path / f).write_bytes((A.DATA / f).read_bytes())
    rw = json.loads((A.DATA / "rewards.json").read_text(encoding="utf-8"))
    for r in rw["rewards"]:
        if r["id"] == "jungle_temple_ring_court_undercroft":
            r["contents"] = [{"item": "cobblemon:sun_stone", "count": 4}, {"item": "cobblemon:moon_stone", "count": 4}]
    (tmp_path / "rewards.json").write_text(json.dumps(rw), encoding="utf-8")
    own = {c["reward"] for t in DOC["temples"] for c in t["caches"]}
    curve = A.economy_curve(tmp_path, own)
    assert curve[8], "no tier-8 peers to build the curve from"
    rep = A.Report()
    A.check_caches(DOC, BY["ring_court"], A.Replay(""), (7202, 127, 7526), None, curve, rep, tmp_path)
    assert rep.has("caches", "evolution stones") and rep.has("caches", "items;"), rep.errors


# Without it the audit could be dropped from prepare, or the temples' step moved past the Habitat Blocks, unseen.
def test_wiring_is_read_from_reapply():
    rep = A.Report()
    A.check_wiring(DOC, rep, REAPPLY)
    assert not rep.errors, rep.errors
    rep = A.Report()
    A.check_wiring(DOC, rep, REAPPLY.replace('add("jungle_temples_audit", "jungle_temples_audit.py", *src)', ""))
    assert rep.has("wiring", "no prepare job jungle_temples_audit")
    rep = A.Report()
    A.check_wiring(DOC, rep, REAPPLY.replace('WORLD_LOCAL = ("cobblers_scenes",', 'WORLD_LOCAL = ("cobblers_jungle_temples", "cobblers_scenes",'))
    assert rep.has("wiring", "WORLD_LOCAL")


# Without it a tool could start building the six drowned ruins again.
def test_superseded_ruins_named_only_in_prose(tmp_path):
    rep = A.Report()
    A.check_ruins(rep, A.DATA, ROOT / "tools", tmp_path / "none")
    assert not rep.errors, rep.errors
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "a.py").write_text('"""ruin_great_hall in prose"""\nX = 1\n', encoding="utf-8")
    (tmp_path / "t" / "b.py").write_text('IDS = ["ruin_west_wall"]\n', encoding="utf-8")
    rep = A.Report()
    A.check_ruins(rep, A.DATA, tmp_path / "t", tmp_path / "none")
    assert rep.errors == ["ruins: tools/b.py names ['ruin_west_wall'] in its code"], rep.errors


# Without it the six records could have been edited while being moved, and the hand-authored seats lost.
def test_superseded_ruins_are_the_records_as_they_were():
    try:
        old = subprocess.run(["git", "show", "30be32d~1:data/placements.json"], cwd=ROOT, capture_output=True,
                             text=True, encoding="utf-8")
    except OSError:
        pytest.skip("NOT_EXECUTED: no git")
    if old.returncode != 0:
        pytest.skip("NOT_EXECUTED: the commit before 30be32d is not in this clone")
    before = {p["id"]: p for p in json.loads(old.stdout)["placements"]}
    now = json.loads((A.DATA / "placements.json").read_text(encoding="utf-8"))
    sup = {r["id"]: r for r in now["superseded_placements"]["records"]}
    for r in A.RUINS:
        assert sup[r] == before[r], r


# Without it a KNOWN fault could outlive its fix.
def test_classify_known_and_stale():
    known = [("mark", "x", "w"), ("ground", "y", "w")]
    real, hits, stale = A.classify(["mark: x here", "writes: z"], known)
    assert real == ["writes: z"] and hits == ["mark: x here"] and stale == [known[1]]


# ------------------------------------------------------------------ the generator mutated, data untouched


def build(tmp_path, monkeypatch, g, mutate=None):
    import jungle_temples as J
    import resident_encounters as RE
    # the generator's own guards off, as files(check=False): its dry-ground refusal would stop a broken plan before
    # the audit ever saw it
    monkeypatch.setattr(RE, "Wet", lambda g_, centres: (lambda x, z: False))
    orig = J.plan
    if mutate is not None:
        monkeypatch.setattr(J, "plan", lambda doc, t, gg, wet: mutate(orig, doc, t, gg, wet))
    doc = J.load()
    written, _b = J.files(doc, g, wet=lambda x, z: False, check=False)
    pack = tmp_path / ("pack_%s" % (mutate.__name__ if mutate else "base"))
    for rel, text in written.items():
        f = pack / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    steps = J.placement_steps(doc, g)
    return A.audit(json.loads(json.dumps(DOC)), g, dry, pack, steps, ruins=False)


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    try:
        return set(build(tmp_path_factory.mktemp("base"), mp, flat(100)).errors)
    finally:
        mp.undo()


def site_of(s):
    return s.cx, s.cz, next(iter(s.floors.values()))


def drop_the_ladder(orig, doc, t, g, wet):
    s = orig(doc, t, g, wet)
    for k, v in list(s.hung.items()):
        if v.startswith("minecraft:ladder"):
            s.hung[k] = "minecraft:air"
    return s


def on_y60_ground(orig, doc, t, g, wet):
    if t["id"] == "ring_court":
        t = dict(t, site=dict(t["site"], centre=[t["site"]["centre"][0] + 500, t["site"]["centre"][1]]))
    return orig(doc, t, g, wet)


def unbacked_vines(orig, doc, t, g, wet):
    s = orig(doc, t, g, wet)
    if t["id"] == "vine_pyramid":
        for k in [k for k, v in s.hung.items() if v.startswith("minecraft:vine") and "south=true" in v]:
            s.hung[(k[0], k[1], k[2] - 1)] = s.hung.pop(k)
    return s


def a_chest(orig, doc, t, g, wet):
    s = orig(doc, t, g, wet)
    if t["id"] == "vine_pyramid":
        for k, v in list(s.solid.items()):
            if v.startswith("minecraft:barrel"):
                s.solid[k] = "minecraft:chest[facing=north,type=single,waterlogged=false]"
    return s


def stair_rebuilt(orig, doc, t, g, wet):
    s = orig(doc, t, g, wet)
    if t["id"] == "vine_pyramid":
        cx, cz, f = site_of(s)
        s.solid[(cx, f + 6, cz + 5)] = "minecraft:mossy_stone_bricks"
        s.solid[(cx, f + 8, cz + 4)] = "minecraft:air"
    return s


def trapdoor_sealed(orig, doc, t, g, wet):
    s = orig(doc, t, g, wet)
    for d in (s.solid, s.hung):
        for k, v in list(d.items()):
            if "trapdoor" in v:
                d[k] = "minecraft:stone_bricks"
    return s


def arm_east(orig, doc, t, g, wet):
    s = orig(doc, t, g, wet)
    if t["id"] == "harbour_mark":
        for k, v in list(s.solid.items()):
            if "_slab" in v and (k[0], k[2]) != (s.cx, s.cz):
                del s.solid[k]
                s.solid[(2 * s.cx - k[0], k[1], k[2])] = v
    return s


def a_cobweb(orig, doc, t, g, wet):
    s = orig(doc, t, g, wet)
    if t["id"] == "harbour_mark":
        cx, cz, f = site_of(s)
        s.hung[(cx + 3, f + 4, cz + 3)] = "minecraft:cobweb"
    return s


def raised_three(orig, doc, t, g, wet):
    s = orig(doc, t, g, wet)
    if t["id"] == "harbour_mark":
        s.solid = {(x, y + 3, z): v for (x, y, z), v in s.solid.items()}
        s.hung = {(x, y + 3, z): v for (x, y, z), v in s.hung.items()}
    return s


def past_the_bbox(orig, doc, t, g, wet):
    s = orig(doc, t, g, wet)
    if t["id"] == "harbour_mark":
        x0, z0, x1, z1 = t["bbox"]
        s.solid[(x1 + 5, next(iter(s.floors.values())) + 1, s.cz)] = "minecraft:mossy_stone_bricks"
    return s


MUTATIONS = [
    (drop_the_ladder, flat(100), [("reach", "ring_court"), ("eye", "a ladder of 0")]),
    (on_y60_ground, lambda x, z: 60 if 7650 <= x <= 7760 and 7480 <= z <= 7580 else 100, [("ground", "at or below y62")]),
    (unbacked_vines, flat(100), [("hold", "vine_pyramid"), ("reach", "by the vines on a north face")]),
    (a_chest, flat(100), [("writes", "minecraft:chest"), ("caches", "vine_pyramid")]),
    (stair_rebuilt, flat(100), [("reach", "without climbing")]),
    (trapdoor_sealed, flat(100), [("reach", "ring_court")]),
    (arm_east, flat(100), [("mark", "arm points")]),
    (a_cobweb, flat(100), [("writes", "spawn condition")]),
    (raised_three, flat(100), [("ground", "does not rest on the ground")]),
    (past_the_bbox, flat(100), [("writes", "outside the bbox")]),
]


# Without it the audit could share the generator's blind spots: each broken generator must fail a named check that the
# unmutated build does not already fail.
@pytest.mark.parametrize("mutate,g,want", MUTATIONS, ids=[m[0].__name__ for m in MUTATIONS])
def test_a_mutated_generator_fails_a_named_check(tmp_path, monkeypatch, baseline, mutate, g, want):
    rep = build(tmp_path, monkeypatch, g, mutate)
    new = [e for e in rep.errors if e not in baseline]
    for cat, text in want:
        assert any(e.startswith(cat + ":") and text in e for e in new), (cat, text, new[:8])


# ------------------------------------------------------------------ the committed build, on the canonical heightmap


# Without it the committed records (floors, containers, triggers, bboxes) could disagree with the real ground unseen.
def test_the_committed_build_on_the_heightmap_has_only_the_known_faults(tmp_path):
    import terrain
    if not terrain.env_source_root():
        pytest.skip("NOT_EXECUTED: no COBBLERS_SOURCE_ROOT (environment or .claude/settings.json): the heightmap is outside the repo")
    import ground
    import jungle_temples as J
    g = ground.load()
    doc = J.load()
    written, _b = J.files(doc, g)                            # the generator's own checks ON: it must build
    for rel, text in written.items():
        f = tmp_path / "pack" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    water = A.Water(g, [tuple(t["site"]["centre"]) for t in DOC["temples"]])
    try:
        jar = A.jar_names()
    except Exception:
        jar = None
    rep = A.audit(json.loads(json.dumps(DOC)), g, water, tmp_path / "pack", J.placement_steps(doc, g), jar=jar,
                  ruins=False)
    real, hits, stale = A.classify(rep.errors)
    assert not real, real[:5]
    assert not stale, "KNOWN fault no longer reported (fixed?): remove it from KNOWN: %s" % stale
