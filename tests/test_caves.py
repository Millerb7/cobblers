"""The cave kit (tools/caves.py, tools/caves_audit.py, data/caves.json), which since 2026-10-12 builds the natural caves only (N1-N3).

The kitted caves K1-K6 were retired the same day (the owner: "I hate the cave look"): K1 went, K2-K6 became the open-air sanctuaries
of data/sanctuaries.json (tools/sanctuaries.py), and their gate, keeper, Habitat Block, roster and C25 tests moved with them to
tests/test_sanctuaries.py. What stays here is what the natural caves still use: the record's rules, the independent audit (with the
generator mutations that still apply to a cave with no gate), the records, the wiring and the natural caves' own tests.
"""
from __future__ import annotations

import copy
import functools
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import caves as C  # noqa: E402
import caves_audit as A  # noqa: E402

SPEC = json.loads((ROOT / "data" / "caves.json").read_text(encoding="utf-8"))
CAVES = {c["id"]: c for c in SPEC["caves"]}
KITTED = [c for c in SPEC["caves"] if c.get("mode") != "natural"]      # none since 2026-10-12: K1-K6 are data/sanctuaries.json's
NATURALS = [c for c in SPEC["caves"] if c.get("mode") == "natural"]    # N1-N3: a mouth, a winding passage and a hall, nothing in them
BOSSES = [c for c in KITTED if c["occupant"]["mode"] == "area_boss"]
BOSS_IDS = [c["id"] for c in BOSSES]
def _ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


@pytest.fixture(scope="module")
def ground():
    return A.cached(_ground())


@functools.lru_cache(maxsize=None)
def _raw_ground():
    return _ground()


def make_pack(g, spec=None):
    """(fns, callback, plan) of the pack the generator makes from the committed record: geometry only, no clearance inputs."""
    spec = spec or SPEC
    plan = [{"cave": c, "geometry": C.geometry(spec, c, g)} for c in spec["caves"]]
    files = C.pack_files(spec, plan)
    pre = "data/cobblers/function/caves/"
    fns = {k[len(pre):-len(".mcfunction")]: v.splitlines() for k, v in files.items() if k.endswith(".mcfunction")}
    return fns, files.get("data/cobblemon/callbacks/pokemon_captured/cobblers_caves.molang", ""), plan


@pytest.fixture(scope="module")
def pack(ground):
    return make_pack(_raw_ground())


def audit(g, fns, cb, **kw):
    probs, _w = A.audit(SPEC, fns, cb, g, **kw)
    return probs


# ------------------------------------------------------------------ the record

def test_the_committed_record_is_valid():
    # without it a cave with a gate no flag opens, an unknown feature or a level over its gate's cap reaches the builder
    assert C.static_problems(SPEC) == []


def test_every_cave_is_sited_with_its_site_recorded():
    for c in SPEC["caves"]:
        assert c["mouth"]["front"] in C.FRONTS and len(c["mouth"]["anchor"]) == 2, c["id"]
        assert c["site"]["subregion"] and c["site"]["subregion_band"][0] <= c["site"]["subregion_band"][1], c["id"]


def _edit(spec, cave, f):
    s = copy.deepcopy(spec)
    f(next(c for c in s["caves"] if c["id"] == cave))
    return s


@pytest.mark.parametrize("name,cave,edit,needle", [
    ("first passage is not an incline", "cave_hoarfrost_hollow", lambda c: c["passages"][0].update(kind="drift"), "must be an incline"),
    ("an even width", "cave_hoarfrost_hollow", lambda c: c["passages"][1].update(width=4), "must be odd"),
])
def test_the_loader_refuses_a_record_that_breaks_a_rule(name, cave, edit, needle):
    # without it the kit would build a trap or an unwinnable boss from a record nobody could tell was wrong
    probs = C.static_problems(_edit(SPEC, cave, edit))
    assert any(needle in p for p in probs), (name, probs)


# ------------------------------------------------------------------ the build

def test_the_committed_pack_passes_the_independent_audit(pack, ground):
    fns, cb, _plan = pack
    assert audit(ground, fns, cb) == []


def test_the_pack_the_generator_makes_is_deterministic(ground):
    a = make_pack(_raw_ground())
    b = make_pack(_raw_ground())
    assert a[0] == b[0] and a[1] == b[1]


def _mutated(monkeypatch, ground, patch):
    patch(monkeypatch)
    fns, cb, _p = make_pack(_raw_ground())
    return audit(ground, fns, cb)


def _wrap_geometry(monkeypatch, fix):
    real = C.geometry

    def geometry(spec, cave, g, anchor=None, front=None):
        gm = real(spec, cave, g, anchor, front)
        fix(cave, gm)
        return gm
    monkeypatch.setattr(C, "geometry", geometry)


def _wrap_files(monkeypatch, name, fix):
    real = getattr(C, name)

    def wrapped(*a, **k):
        out = real(*a, **k)
        fix(out)
        return out
    monkeypatch.setattr(C, name, wrapped)


def test_a_wider_oval_is_caught_as_cells_outside_the_rules(monkeypatch, ground):
    # the audit's expectation is its own: widening the chamber inside the GENERATOR (rx + 2), the record untouched, must fail
    real = C.in_oval
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(C, "in_oval", lambda u, d, dc, rx, rz: real(u, d, dc, rx + 2, rz)))
    assert any("not in the rules" in p or "differ from the rules" in p for p in probs), probs


def test_a_roof_cell_of_the_shell_left_out_breaks_the_seal(monkeypatch, ground):
    def fix(cave, gm):
        if cave["id"] == "cave_dusk_burrow":
            x, _y, z = gm["centre"]
            del gm["cells"][(x, gm["yh"] + cave["chamber"]["h"] + 1, z)]       # the cell over the middle of the chamber's roof
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_geometry(mp, fix))
    assert any("shell does not seal it" in p for p in probs) and any("not written" in p for p in probs), probs


# ------------------------------------------------------------------ the records in the shared files

def test_the_derived_records_match_the_geometry(pack):
    # drift between the cave and the Habitat Blocks / pools / probes it keeps in other files is a fault (python tools/caves.py author)
    _fns, _cb, plan = pack
    assert C.record_problems(SPEC, plan) == []


def test_the_cave_records_in_the_shared_files_are_ours_only_and_complete():
    ours = {h["id"] for c in KITTED for h in c["habitat"]}
    blocks = {b["id"]: b for b in json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]}
    assert ours <= set(blocks) and all(blocks[i].get("generated_by") == "tools/caves.py" for i in ours)
    gen = {b["id"] for b in blocks.values() if b.get("generated_by") == "tools/caves.py"}
    assert gen == ours, "a generated Habitat Block the record no longer names: %s" % sorted(gen - ours)
    sp = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    pools = {c["id"]: [h["pool"]["id"] for h in c["habitat"]] for c in KITTED}
    have = {h["id"] for h in sp["habitats"]}
    assert {p for ps in pools.values() for p in ps} <= have
    scopes = {e.get("scope") for e in sp["entries"]}
    assert {p for ps in pools.values() for p in ps} <= scopes


# ------------------------------------------------------------------ the wiring

def test_no_block_the_pack_places_is_a_spawn_condition(pack):
    _f, _c, plan = pack
    assert C.pack_problems(SPEC, plan) == []


def _reapply():
    return (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")


def test_reapply_names_the_pack_the_step_and_the_prepare_jobs():
    src = _reapply()
    assert src.count('"cobblers_caves"') >= 2                    # SERVER_PACKS and WORLD_LOCAL
    assert 'add("caves:build", "caves.py", "build", *src)' in src and '"caves_audit.py"' in src
    assert '("R9CK",' in src and "caves.placement_steps()" in src
    assert src.index('("R9CK",') < src.index('("R9E",')        # the Habitat Blocks stand on cells the caves write
    assert src.index('("R9OC",') < src.index('("R9CK",')


def test_the_step_holds_builds_and_releases_each_cave(ground):
    steps = C.placement_steps(SPEC, _raw_ground())
    assert [s[0] for s in steps] == ["cmd", "wait", "fn", "cmd"] * len(SPEC["caves"])
    assert [s[1] for s in steps if s[0] == "fn"] == C.build_functions(SPEC)
    for (k1, v1), (k2, v2) in zip(steps[0::4], steps[3::4]):
        assert v1.startswith("forceload add ") and v2 == v1.replace("forceload add ", "forceload remove ")


def test_every_function_of_the_pack_is_run_by_a_step_or_named_by_another_file(pack):
    # tools/reapply.py unreferenced(): a function nothing calls is a silent loss. Re-derived here from the pack's own text
    fns, cb, _p = pack
    text = "\n".join("\n".join(v) for v in fns.values()) + "\n" + cb + json.dumps({"values": ["cobblers:caves/load"]})
    refs = set(re.findall(r"([a-z0-9_.-]+:[a-z0-9_./-]+)", text))
    run = set(C.build_functions(SPEC))
    lost = [n for n in fns if "cobblers:caves/%s" % n not in refs and "cobblers:caves/%s" % n not in run]
    assert lost == []


def test_the_load_tag_and_the_callback_are_in_the_pack(ground):
    spec = SPEC
    plan = [{"cave": c, "geometry": C.geometry(spec, c, _raw_ground())} for c in spec["caves"]]
    files = C.pack_files(spec, plan)
    assert json.loads(files["data/minecraft/tags/function/load.json"])["values"] == ["cobblers:caves/load"]
    # no cave has a boss since K3, K5 and K6 became sanctuaries (tools/sanctuaries.py): no capture callback is emitted
    assert not [k for k in files if "callbacks" in k] and not BOSSES


# ------------------------------------------------------------------ keeping clear of what the siting reads from other files

def _gm_stub(cave_id, x, z):
    gm = make_pack(_raw_ground())[2]
    real = next(p["geometry"] for p in gm if p["cave"]["id"] == cave_id)
    return dict(real, columns=[(x, z)], centre=[x, real["centre"][1], z], ante_centre=[x, real["centre"][1], z])


def test_a_cave_inside_a_spawn_free_zone_is_refused():
    # without it a cave could be sited inside the League's precinct or a gym lot, where nothing may spawn: its Habitat Block
    # would be dead and its keeper would bring a wild alpha into a precinct the owner closed to wild Pokemon
    zones = json.loads((ROOT / "data" / "spawn_suppression.json").read_text(encoding="utf-8"))["spawn_free_zones"]
    z = zones[0]
    x0, z0, x1, z1 = z["box"]
    cave = CAVES["cave_dusk_burrow"]
    probs = C.foreign_problems(SPEC, cave, _gm_stub("cave_dusk_burrow", (x0 + x1) // 2, (z0 + z1) // 2))
    assert any("spawn-free zone %s" % z["id"] in p for p in probs), probs
    assert not C.foreign_problems(SPEC, cave, _gm_stub("cave_dusk_burrow", x0 - 400, z0 - 400))


def test_the_audit_refuses_a_cave_inside_a_spawn_free_zone_too(monkeypatch, ground, pack):
    fns, cb, plan = pack
    n3 = next(p["geometry"] for p in plan if p["cave"]["id"] == "cave_dusk_burrow")
    x, _y, z = n3["centre"]
    real = A.jload

    def jload(name):
        doc = real(name)
        if name == "spawn_suppression.json":
            doc = copy.deepcopy(doc)
            doc["spawn_free_zones"].append({"id": "test_zone", "box": [x - 3, z - 3, x + 3, z + 3]})
        return doc
    monkeypatch.setattr(A, "jload", jload)
    assert any("spawn-free zone test_zone" in p for p in audit(ground, fns, cb)), "the audit did not see the zone"


# ------------------------------------------------------------------ the natural caves (the owner, 2026-10-12)
# "We need to have caves on Northlight, Long Isle, and Sunset. They don't have to go anywhere or have a reward; just a cave would
# seem natural." A `natural` cave: a mouth, a winding passage, a dead-end hall; no gate, occupant, Habitat Block, reward or keeper.

NATURAL_IDS = {"cave_hoarfrost_hollow": ("N1", "south_pine_isle"), "cave_greenwither_cleft": ("N2", "long_isle_south"),
               "cave_dusk_burrow": ("N3", "sunset_west")}


def test_the_three_natural_caves_stand_on_the_three_islands_the_owner_named():
    # without it a natural cave could be sited on another island, or one of the three could be missing
    assert {c["id"] for c in NATURALS} == set(NATURAL_IDS)
    for c in NATURALS:
        kind, sub = NATURAL_IDS[c["id"]]
        assert c["kind"] == kind and c["site"]["subregion"] == sub, c["id"]
    assert {CAVES[i]["near"] for i in NATURAL_IDS} == {"pine_isles", "long_isle_south", "sunset_isle"}


def test_the_natural_caves_differ_in_size_and_each_one_winds():
    # "vary sizes so the three feel different": three distinct hall volumes and lengths, and a bend in each
    sizes = {(c["chamber"]["rx"], c["chamber"]["rz"], c["chamber"]["h"]) for c in NATURALS}
    lengths = {C.layout(SPEC, c)["total"] for c in NATURALS}
    assert len(sizes) == 3 and len(lengths) == 3, (sizes, lengths)
    for c in NATURALS:
        assert any(p.get("bend") for p in c["passages"][1:]), c["id"]
        assert C.layout(SPEC, c)["chamber"]["uc"] == sum(p.get("bend", 0) for p in c["passages"])


def test_a_natural_cave_carries_none_of_occupant_gate_habitat_antechamber_reward_keeper():
    # the committed record: a dead end with nothing in it (the owner: no reward, no occupant)
    for c in NATURALS:
        assert not set(C.NATURAL_FORBIDDEN) & set(c), c["id"]
        assert c["mode"] == "natural" and c["light"]["dark_by_design"] is True


@pytest.mark.parametrize("field,value", [
    ("occupant", {"mode": "power_line", "species": "gible"}), ("gate", {"kind": "none"}), ("habitat", []),
    ("antechamber", {"length": 4, "half_width": 3, "height": 5}), ("reward", {"item": "x"}), ("keeper", {})])
def test_a_natural_cave_with_a_forbidden_field_is_refused(field, value):
    # breaks if: a natural cave quietly grows an occupant, a gate or a reward; the loader must name the field
    probs = C.static_problems(_edit(SPEC, "cave_hoarfrost_hollow", lambda c: c.update({field: value})))
    assert any("a natural cave carries no %s" % field in p for p in probs), probs


@pytest.mark.parametrize("name,edit,needle", [
    ("no bend at all", lambda c: [p.pop("bend", None) for p in c["passages"]], "must carry a bend"),
    ("a bend longer than its passage", lambda c: c["passages"][1].update(bend=40), "moves at most one step"),
    ("a narrow bending passage", lambda c: c["passages"][1].update(width=1), "width >= 3"),
    ("lit by design", lambda c: c["light"].update(dark_by_design=False), "dark by design"),
    ("a mouth frame's timber in the palette", lambda c: c["palette"].update(timber="minecraft:spruce_log"), "no mouth frame"),
    ("no ore in the walls", lambda c: c["palette"].pop("vein"), "palette lacks vein"),
    ("a chamber feature of the kitted caves", lambda c: c["chamber"].update(feature="crystal"), "none or knobs"),
    ("an incline that bends", lambda c: c["passages"][0].update(bend=1), "incline does not bend"),
])
def test_the_loader_refuses_a_natural_cave_that_does_not_wind_or_is_lit(name, edit, needle):
    probs = C.static_problems(_edit(SPEC, "cave_greenwither_cleft", edit))
    assert any(needle in p for p in probs), (name, probs)


def test_nothing_in_the_shared_files_or_the_pack_names_a_natural_cave(pack):
    # no Habitat Block, no spawn pool or entry, no gate or boss function, no probe for a boss: a natural cave is a hole in the rock
    fns, cb, _p = pack
    hb = (ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8")
    sp = (ROOT / "data" / "spawns.json").read_text(encoding="utf-8")
    for cid in NATURAL_IDS:
        assert cid not in hb and cid not in sp, cid
        assert [n for n in fns if cid in n] == ["build_%s" % cid], [n for n in fns if cid in n]
        assert not any(cid in l for n, ls in fns.items() if n != "build_%s" % cid for l in ls), cid
        assert cid not in cb
        assert "scoreboard players set #%s_open" % cid not in "\n".join(fns["build_%s" % cid])


def test_the_natural_caves_write_only_their_palette_and_air_and_no_light(pack):
    # dark by design: not a lantern, a post, a beam, a column, a door or a crystal; and every written block is the cave's own palette
    fns, _cb, _p = pack
    for c in NATURALS:
        written = A.replay(fns["build_%s" % c["id"]])
        used = {A.base(v) for v in written.values()}
        assert used <= set(A.base(v) for v in c["palette"].values()) | {"minecraft:air"}, (c["id"], used)
        assert not [b for b in used if any(w in b for w in A.LIGHT)], c["id"]


def test_the_natural_caves_dressing_is_present_and_shows(pack):
    # nonempty on purpose: ore only where it shows (an air neighbour), patches on floors, knobs standing on the hall's floor
    fns, _cb, plan = pack
    for e in plan:
        c = e["cave"]
        if c.get("mode") != "natural":
            continue
        w = A.replay(fns["build_%s" % c["id"]])
        vein, patch, knob = (A.base(c["palette"][k]) for k in ("vein", "patch", "knob"))
        cells = e["geometry"]["cells"]
        veins = [p for p, r in cells.items() if r == "vein"]
        assert veins and all(A.base(w[p]) == vein for p in veins), c["id"]
        for (x, y, z) in veins:
            assert any(w.get((x + a, y + b, z + d)) in A.PASS for a, b, d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))), (c["id"], x, y, z)
        assert [p for p, r in cells.items() if r == "patch"], c["id"]
        knobs = [p for p, r in cells.items() if r == "knob"]
        assert 1 <= len(knobs) <= c["chamber"]["knob_count"] and all(p[1] == e["geometry"]["yh"] + 1 for p in knobs), c["id"]


def test_the_natural_caves_probes_are_in_the_probe_file_for_r9ck():
    # tools/presence_audit.py reads places.caves; R9CK builds the caves and the probes come from the same record
    probes = json.loads((ROOT / "data" / "world_probes.json").read_text(encoding="utf-8"))["places"]["caves"]
    for cid in NATURAL_IDS:
        mine = [p for p in probes if p["what"].startswith(cid + ":")]
        assert len(mine) == 6, (cid, len(mine))
        assert not [p for p in mine if "boss" in p["what"] or "Habitat" in p["what"] or "beam" in p["what"] or "door" in p["what"]]
    assert 'caves.placement_steps()' in _reapply()


def _natural_only(fix):
    def wrapped(cave, gm):
        if cave.get("mode") == "natural":
            fix(cave, gm)
    return wrapped


def test_a_generator_that_straightens_the_passage_is_caught(monkeypatch, ground):
    # mutate the GENERATOR (the bend is dropped from every row inside caves.layout), the record untouched: the audit's own
    # derivation of the offset rows must disagree, and its read of the written air must see a passage that does not wind
    real = C.layout

    def layout(spec, cave):
        lay = real(spec, cave)
        if C.is_natural(cave):
            for r in lay["rows"]:
                r["c"] = 0
            lay["chamber"]["uc"] = 0
        return lay
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(C, "layout", layout))
    assert any("not in the rules" in p or "differ from the rules" in p for p in probs), probs
    assert any("does not wind" in p or "never turns back" in p for p in probs), probs


def test_a_generator_that_changes_the_dressing_rule_is_caught(monkeypatch, ground):
    # mutate the hash the dressing keys on (inside tools/mines.h32 as caves.py calls it): ore and patches land on other cells
    real = C.M.h32

    def h32(*vals):
        return real(*vals) + (1 if len(vals) == 5 else 0)
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(C.M, "h32", h32))
    assert any("not in the rules" in p or "differ from the rules" in p or "not written" in p for p in probs), probs


def test_a_generator_that_hangs_a_lantern_in_a_natural_cave_is_caught(monkeypatch, ground):
    def fix(cave, gm):
        x, _y, z = gm["centre"]
        gm["cells"][(x, gm["yh"] + 3, z)] = "lantern"
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_geometry(mp, _natural_only(fix)))
    assert any("writes minecraft:lantern" in p for p in probs) and any("not in the rules" in p or "differ from the rules" in p for p in probs), probs


def test_a_generator_that_blocks_the_passage_is_caught_by_the_walk(monkeypatch, ground):
    # one whole row of a winding passage turned to rock: the hall can no longer be walked to from outside the mouth
    def fix(cave, gm):
        if cave["id"] != "cave_greenwither_cleft":
            return
        lay = gm["layout"]
        row = [r for r in lay["rows"] if r["kind"] == "level"][6]
        cells = gm["cells"]
        xz = C.M.frame(tuple(gm["anchor"]), gm["front"])
        for u in range(row["c"] - row["hw"], row["c"] + row["hw"] + 1):
            x, z = xz(u, row["d"])
            for y in range(row["ft"] + 1, row["ft"] + row["h"] + 1):
                cells[(x, y, z)] = "shell"
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_geometry(mp, fix))
    assert any("not walkable" in p for p in probs), probs


def test_a_generator_that_gives_a_natural_cave_a_keeper_is_caught(monkeypatch, ground):
    # a boss function for a cave that has no boss: the audit refuses it by name, whatever the record says
    def wrapped(*a, **k):
        out = real(*a, **k)
        out["data/cobblers/function/caves/boss/cave_dusk_burrow/keep.mcfunction"] = "say hello\n"
        return out
    real = C.pack_files
    monkeypatch.setattr(C, "pack_files", wrapped)
    fns, cb, _p = make_pack(_raw_ground())
    probs = audit(ground, fns, cb)
    assert any("boss functions exist for a natural cave" in p for p in probs), probs


def test_a_natural_cave_given_a_habitat_block_record_is_caught_by_the_audit(monkeypatch, ground, pack):
    fns, cb, _p = pack
    real = A.jload

    def jload(name):
        doc = real(name)
        if name == "habitat_blocks.json":
            doc = copy.deepcopy(doc)
            doc["blocks"].append({"id": "x", "place": "Dusk Burrow (cave_dusk_burrow, N3) in data/caves.json", "style": "activated"})
        return doc
    monkeypatch.setattr(A, "jload", jload)
    assert any("Habitat Block x names a natural cave" in p for p in audit(ground, fns, cb))
