"""The Fossick Deep Galleries entered by the adit of a built hill (2026-10-20, tools/fossick_adit.py, step R9OCF).

The owner, 2026-10-20: "make fossick like route 1". cave_fossick (data/mining_caves.json) loses its free-standing frame
and stair shaft on the flat; a hill is built over the place from the Route 1 old mine's own code (tools/hill_adit.py),
and its adit's incline ends in the hall's near end wall (entry.host.opening). Step R9OCF puts the old mouth back to the
heightmap's terrain in a world that has it, then builds the hill there.

Written by the session that built the change (minecraft-systems-dev), NOT by test-author: .claude/rules/testing.md
asks for a different agent, and this file says so instead. What keeps it honest: the expectations are the audit's
(tools/mining_caves_audit.py, which reads data/mining_caves.json's rules text, the frozen record and data/placements.json
and imports nothing from tools/mining_caves.py, tools/fossick_adit.py or tools/hill_adit.py) or the canonical
heightmap's (tools/ground.py); and every proof that a check bites MUTATES A GENERATOR's source text, data untouched. An
independent review of this file and of the audit's new host checks is owed.

Every test reads the canonical heightmap and skips, naming it, without one. Not covered (it needs a full checkout or a
running server): the audit's keep-clear rules that read derived/ and build/ (the routed legs, the paint, the water
export, the other packs' writes: `python tools/mining_caves_audit.py --inputs-root <full checkout>` runs them); the
world's cells; the restore's surface at the old mouth (basalt, UNVERIFIED offline).
"""
from __future__ import annotations

import json
import math
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import mining_caves_audit as A  # noqa: E402
import test_mining_caves_audit as TA  # noqa: E402

FOSSICK = ROOT / "tools" / "fossick_adit.py"
KIT = ROOT / "tools" / "hill_adit.py"
CAVE = "cave_fossick"


@pytest.fixture(scope="module")
def ground():
    try:
        import ground as G
        g = A.cached(G.Ground())
        g(6767, 5804)
    except Exception as exc:  # noqa: BLE001
        pytest.skip("NOT_EXECUTED: the canonical heightmap is not readable here (%s)" % exc)
    return g


def fresh(path, name, mutation=None):
    """A tool as a fresh module, with one (old, new) source edit that must match exactly once."""
    src = path.read_text(encoding="utf-8")
    if mutation:
        assert src.count(mutation[0]) == 1, "the mutation %r no longer matches %s once" % (mutation[0][:60], path.name)
        src = src.replace(*mutation)
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    exec(compile(src, str(path), "exec"), mod.__dict__)
    return mod


def adit_module(adit_mutation=None, kit_mutation=None):
    """tools/fossick_adit.py, built on tools/hill_adit.py, either one mutated."""
    saved = sys.modules.get("hill_adit")
    try:
        sys.modules["hill_adit"] = fresh(KIT, "hill_adit", kit_mutation)
        return fresh(FOSSICK, "fossick_adit", adit_mutation)
    finally:
        if saved is None:
            sys.modules.pop("hill_adit", None)
        else:
            sys.modules["hill_adit"] = saved


def real_pack(adit_mutation=None, kit_mutation=None):
    """(spec, functions, the builder's problems) for the real data and heightmap, the reroute functions included, with
    the host generator (as the reroute's connect runs it) optionally mutated; keep-clear is TA._NoClearance's."""
    saved = sys.modules.get("fossick_adit")
    if adit_mutation or kit_mutation:
        sys.modules["fossick_adit"] = adit_module(adit_mutation, kit_mutation)
    try:
        mc = TA.builder()
        mc.Clearance = TA._NoClearance
        spec = A.load()
        plan, probs, _notes = mc.model(spec)
        fns = {"build_%s" % e["cave"]["id"]: mc.build_lines(spec, e) for e in plan}
        fns.update(mc.driver_files(spec, plan))
        g = mc.G.Ground()
        for cave in spec["caves"]:
            if cave.get("retired_entry"):
                fns.update(mc.reroute_files(spec, cave, g))
        return spec, fns, probs
    finally:
        if adit_mutation or kit_mutation:
            if saved is None:
                sys.modules.pop("fossick_adit", None)
            else:
                sys.modules["fossick_adit"] = saved


@pytest.fixture(scope="module")
def real(ground):
    return real_pack()


def only(spec, cid=CAVE):
    return dict(spec, caves=[c for c in spec["caves"] if c["id"] == cid])


def recorded():
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    return next(p for p in doc["placements"] if p["id"] == "fossick_adit_hill")


# Without it data/placements.json holds a hill the tool no longer builds (hand-edited, or the tool changed and was not
# re-run), and R8 on a fresh export builds something other than what R9OCF builds in the live world.
def test_the_recorded_adit_is_the_one_the_tool_builds(ground):
    import fossick_adit as FA
    import ground as G
    assert recorded()["commands"] == FA.build(G.Ground())


# Without it the Route 1 old mine would change under the refactor that shares its hill and adit: its recorded earthwork
# must still be what its tool builds, and the kit must not have moved a block of it.
def test_the_route1_old_mine_is_still_what_its_tool_builds(ground):
    import ground as G
    import route1_old_mine as OM
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    rec = next(p for p in doc["placements"] if p["id"] == "route1_old_mine_hill")
    assert rec["commands"] == OM.build(G.Ground())


# Without it the owner's change is undone silently by the data, or the hill is built over a cave that still has its
# own frame: Fossick is entered from its hill, and its old mouth is retired in its own step.
def test_fossick_is_entered_from_its_hill_and_its_old_mouth_is_retired():
    cave = next(c for c in A.load()["caves"] if c["id"] == CAVE)
    assert cave["entry"]["mouth"] is False
    assert cave["entry"]["host"]["settlement"] == "fossick_adit"
    assert cave["entry"]["host"]["placement"] == "fossick_adit_hill"
    assert cave["retired_entry"]["step"] == "R9OCF"


# Without it the change could ship a cave nobody can enter, an old frame left standing, or a restore or a hill that
# buries a player: on the real data the builder reports nothing, and the audit's host, reroute and walk are clean.
def test_the_real_galleries_are_entered_from_the_hill_and_the_old_mouth_is_restored(real, ground):
    spec, fns, probs = real
    assert probs == []
    assert A.host_problems(only(spec), fns, ground) == []
    assert A.reroute_problems(only(spec), fns, ground) == []
    assert A.walk_problems(only(spec), fns, ground) == []


# Without it the frozen record could drift from what R9OC built at Fossick, and the restore would undo cells it never
# wrote: the frozen build text still hashes to the applied sha256 (tools/mining_caves.py raises otherwise).
def test_the_frozen_fossick_build_still_hashes_to_the_applied_one(ground):
    import mining_caves as MC
    cave = next(c for c in MC.load()["caves"] if c["id"] == CAVE)
    MC.retired_geometry(cave, MC.G.Ground())
    assert cave["retired_entry"]["frozen_cave"]["entry"]["anchor"] == [6767, 5804]
    assert "mouth" not in cave["retired_entry"]["frozen_cave"]["entry"]


# Without it the hill is seated on something other than the canonical heightmap's rounded ground (a world's surface,
# a floor instead of a round): the level's feet are one over the ground outside the portal, the incline falls exactly to
# the hall's feet the audit derives from the rules text, and no hill column leaves a gap under itself or floats.
def test_the_adit_is_seated_on_the_heightmap_and_falls_to_the_hall(ground):
    cave = next(c for c in A.load()["caves"] if c["id"] == CAVE)
    host = cave["entry"]["host"]
    px, py, pz, _blk = host["probe"]
    feet = py - 4                                                     # the portal's beam is four over the level's feet
    assert feet == ground(px - 1, pz) + 1
    ex = A.expected(A.load(), cave, ground)
    assert host["opening"][1] == ex["yh"] + 1
    written = A.apply_lines({}, recorded()["commands"])
    cols = {}
    for (x, y, z), b in written.items():
        if b not in A.PASS:
            cols.setdefault((x, z), []).append(y)
    corridor = {(x, z) for (x, z) in cols if abs(z - pz) <= 2 and x >= px}
    floating = sorted(c for c, ys in cols.items() if c not in corridor and min(ys) > ground(*c) + 1)
    assert floating == [], "%d hill columns stand off their ground, e.g. %s" % (len(floating), floating[:3])


# Without it the hill covers something another system placed: a route, a town, another earthwork, or any x/z another
# data file authors (a trainer's seat and so its sight line, a Habitat Block, a portal), swept across every data file.
# The rules that need derived/ and build/ run in the audit's CLI against a full checkout.
def test_the_hill_covers_nothing_the_data_places(ground):
    cave = next(c for c in A.load()["caves"] if c["id"] == CAVE)
    host = cave["entry"]["host"]
    hcols = A.pack_columns({"host": recorded()["commands"]})
    spec = A.load()
    kc = spec["keep_clear"]
    for (ax, az, f) in A.authored_xz(host["settlement"], host["placement"]):
        d = min(math.hypot(x - ax, z - az) for (x, z) in hcols)
        assert d > kc["authored_clearance"], "the hill is %.1f from %s (%s, %s)" % (d, f, ax, az)
    for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]:
        fp = t.get("footprint") or {}
        if fp.get("min_x") is None:
            continue
        inside = [c for c in hcols if fp["min_x"] <= c[0] <= fp["max_x"] and fp["min_z"] <= c[1] <= fp["max_z"]]
        assert inside == [], "the hill writes %d columns inside %s's footprint" % (len(inside), t["id"])
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    for p in doc["placements"]:
        if p.get("commands") and p["id"] != host["placement"]:
            other = A.pack_columns({"o": p["commands"]})
            near = [c for c in hcols if any(abs(c[0] - o[0]) <= kc["earthwork_gap"] and abs(c[1] - o[1]) <= kc["earthwork_gap"]
                                            for o in other)] if any(abs(o[0] - 6778) < 120 and abs(o[1] - 5804) < 120
                                                                     for o in other) else []
            assert near == [], "the hill comes within %d of earthwork %s at %s" % (kc["earthwork_gap"], p["id"], near[:3])
    for name, pts in json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"].items():
        for (ax, az) in [tuple(q[:2]) for q in pts]:
            if abs(ax - 6778) < 200 and abs(az - 5804) < 200:
                assert min(math.hypot(x - ax, z - az) for (x, z) in hcols) >= kc["road_clear"], name


# ------------------------------------------------------------------ mutations of the generators (data untouched)

# Without it the incline stops a stair short of the hall's floor: its fall miscounted by one, the last stair stands two
# over the opening's feet, and the live world's reroute (which runs the generator) would cut a hill nobody can climb
# out of. The audit sees the passage no longer match the recorded earthwork, and walking the mutated build never
# reaches a gallery. (The opening row's own air is not such a proof: the cave's build writes the opening as air anyway.)
def test_mutation_incline_a_stair_short_is_caught(ground, monkeypatch):
    mut = ("    drop = feet - oy0\n", "    drop = feet - oy0 - 1\n")
    spec, fns, _p = real_pack(adit_mutation=mut)
    assert any("differently from what the host's earthwork leaves" in p for p in A.reroute_problems(only(spec), fns, ground))
    import ground as G
    fa = adit_module(adit_mutation=mut)
    monkeypatch.setattr(A, "host_lines", lambda cave: fa.build(G.Ground()))
    assert any("not walkable" in p for p in A.walk_problems(only(spec), fns, ground))


# Without it a timber set's lantern hangs at head height in the level (the kit's set one block lower), and the adit
# cannot be walked: the walk over the mutated hill catches it.
def test_mutation_lantern_at_head_height_is_caught(ground, monkeypatch):
    mut = ('        sb(x, feet + 2, Z, "minecraft:lantern[hanging=true]")\n',
           '        sb(x, feet + 1, Z, "minecraft:lantern[hanging=true]")\n        sb(x, feet + 1, Z - 1, "minecraft:lantern[hanging=true]")\n'
           '        sb(x, feet + 1, Z + 1, "minecraft:lantern[hanging=true]")\n')
    spec, fns, _p = real_pack()
    import ground as G
    fa = adit_module(kit_mutation=mut)
    monkeypatch.setattr(A, "host_lines", lambda cave: fa.build(G.Ground()))
    assert any("not walkable" in p for p in A.walk_problems(only(spec), fns, ground))


# Without it a stair stands two high (the kit's incline steps two at a time): nobody climbs out of the galleries.
def test_mutation_incline_too_steep_is_caught(ground, monkeypatch):
    mut = ("        return self.adit_end + self.sense * i, feet - i\n",
           "        return self.adit_end + self.sense * i, feet - i - (i % 2)\n")
    spec, fns, _p = real_pack()
    import ground as G
    fa = adit_module(kit_mutation=mut)
    monkeypatch.setattr(A, "host_lines", lambda cave: fa.build(G.Ground()))
    assert A.walk_problems(only(spec), fns, ground)


# Without it the passage is gated on a block the hill never leaves at the probe (a beam of another wood), so R9OCF would
# rebuild the whole hill over everything on every run; the audit reads the gate against the recorded earthwork.
def test_mutation_probe_of_the_wrong_block_is_caught(ground):
    import mining_caves as MC
    mut = ('    return [a.portal_x, a.feet(g) + 4, Z_AXIS, "minecraft:spruce_log"]',
           '    return [a.portal_x, a.feet(g) + 4, Z_AXIS, "minecraft:oak_log"]')
    fa = adit_module(adit_mutation=mut)
    spec, fns, _p = real_pack()
    cave = next(c for c in spec["caves"] if c["id"] == CAVE)
    cave = json.loads(json.dumps(cave))
    cave["entry"]["host"]["probe"] = fa.probe(MC.G.Ground())       # the mutated generator's probe, through the builder
    spec = dict(spec, caves=[cave])
    fns.update(MC.reroute_files(spec, cave, MC.G.Ground()))
    assert any("leaves minecraft:spruce_log at the probe" in p for p in A.reroute_problems(spec, fns, ground))


# Without it the worn path runs on into the mining town and paves over its ground: the sweep of the town footprints
# catches the mutated generator's hill.
def test_mutation_path_into_the_town_is_caught(ground):
    import ground as G
    fa = adit_module(adit_mutation=("PATH = ((6757, 5807), (6756, 5807))", "PATH = ((6757, 5807), (6736, 5807))"))
    hcols = A.pack_columns({"host": fa.build(G.Ground())})
    town = next(t for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
                if t["id"] == "mining_town")["footprint"]
    assert any(town["min_x"] <= x <= town["max_x"] and town["min_z"] <= z <= town["max_z"] for (x, z) in hcols)


# Without it the step is not run, runs before the galleries exist, or its refusal is not read back; and R9OCR, already
# applied for the Lower Galleries, must not pick up Fossick.
def test_the_fossick_step_is_wired_after_the_caves_and_reads_its_refusal_back(ground):
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert '("R9OCF",' in src and 'mining_caves.reroute_steps(step="R9OCF")' in src
    assert src.index('("R9OC",') < src.index('("R9OCR",') < src.index('("R9OCF",') < src.index('("R9CK",')
    import mining_caves as MC
    steps = MC.reroute_steps(step="R9OCF")
    assert [k for k, _v in steps] == ["cmd", "wait", "fn", "check", "cmd"]
    assert steps[2][1] == "cobblers:mining_caves/reroute/cave_fossick"
    assert steps[3][1][0] == "chunk_look" and steps[3][1][2] == 0
    assert steps[0][1].startswith("forceload add ") and steps[4][1] == steps[0][1].replace("add", "remove")
    assert [s[1] for s in MC.reroute_steps() if s[0] == "fn"] == ["cobblers:mining_caves/reroute/cave_old_mine"]
