"""The cave systems (data/cave_systems.json, tools/cave_systems.py, tools/cave_systems_audit.py).

Offline: the canonical heightmap and the data, no world, no server. Written in the same session as the generator because the brief
asked for it; the audit shares nothing of the generator's geometry (tests/test_cave_systems.py::test_audit_imports_no_generator).

What each group protects, and what breaks without it:

  the record      the brief's numbers are in data/cave_systems.json and the tool reads them from there
  the real build  the three systems build, pass the audit, are deterministic, fit the server's command limits, and the pack
                  indexes shells before carves. Without it a prepare would stop on the audit with nothing found earlier
  the audit bites MUTATIONS OF THE GENERATOR, not of the record (CLAUDE.md "How to prove an audit is independent"): the generator
                  is made to believe the ground is 40 higher, to ignore water, to ignore what is authored, to ring the shell one
                  cell thin, to skip the second carve and to run carves before shells; the audit must report each. A test that
                  only edited the data would pass a shared derivation happily
  the wiring      tools/reapply.py lists the pack, builds and audits it in prepare and runs step R9CS, and the spawn-block policy
                  names the ores
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import cave_systems as CS            # noqa: E402
import cave_systems_audit as CSA     # noqa: E402
import function_limits as FL         # noqa: E402
import ground as G                   # noqa: E402


@pytest.fixture(scope="module")
def spec():
    return CS.load()


@pytest.fixture(scope="module")
def ground():
    return G.Ground()


@pytest.fixture(scope="module")
def real(spec, ground, tmp_path_factory):
    """The real three systems, built once into a temp pack, and the audit over it."""
    out = tmp_path_factory.mktemp("cs_real") / "pack"
    results, files, summary = CS.build_all(spec, g=ground)
    CS.write_pack(files, CS.index_lines(files), out)
    problems, report = CSA.audit(spec, out, g=ground)
    return {"results": results, "files": files, "summary": summary, "pack": out, "problems": problems, "report": report}


# ------------------------------------------------------------------ the record

def test_the_record_carries_the_briefs_numbers(spec):
    r = spec["rules"]
    # without these the tool would be reading numbers from its own code, not from the data a reviewer can see
    assert r["cover_min"] == 8 and r["water_reach"] == 12 and r["authored_clearance"] == 32 and r["shell"] == 2
    assert r["write_limit_x"] == 4032 and r["east_limit_x"] <= 4032 - 5      # the shell reaches 5 beyond a carved cell
    assert r["width"] == [3.0, 7.0] and r["cavern"]["across"][1] == 80 and r["cavern"]["tall"] == [15, 40]
    assert [lv["id"] for lv in r["levels"]][:3] == ["upper", "middle", "deep"]
    assert any(lv["y"] < 0 for lv in r["levels"])          # deepslate variants only exist under y0


def test_the_systems_are_west_and_have_three_to_six_mouths(spec):
    assert 2 <= len(spec["systems"]) <= 3
    ids = [s["id"] for s in spec["systems"]]
    assert len(set(ids)) == len(ids)
    for s in spec["systems"]:
        assert s["centre"][0] + s["radius"] <= 4000, s["id"]       # all x < 4096, 64 west of it with the shell
        assert 3 <= len(s["mouths"]) <= 6, s["id"]
        assert 2000 <= s["target_length"] <= 5000, s["id"]
        for m in s["mouths"]:
            assert m["x"] < 4000


def test_the_sea_level_the_generator_assumes_is_the_worlds():
    assert CS.SEA_LEVEL == json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))["vertical"]["sea_level"]


def test_the_policy_names_every_spawn_condition_ore_the_tool_can_place(spec):
    sb = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    policy = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    allowed = {b for w in policy["whitelist"] if CS.POLICY_SCOPE in (w.get("scope") or "") for b in w["blocks"]}
    placed = set()
    for t in spec["rules"]["ore"]["types"]:
        placed |= {t["stone"], t["deepslate"]}
    # an ore that draws Pokemon with no policy entry is a spawn the owner has not agreed to
    assert (placed & sb) <= allowed, sorted((placed & sb) - allowed)


# ------------------------------------------------------------------ the real build

def test_the_real_build_passes_the_audit(real):
    assert real["problems"] == [], real["problems"][:5]


def test_every_system_meets_the_size_the_owner_asked_for(real):
    for s in real["summary"]:
        assert s["centreline_blocks"] >= 2000, s["id"]
        assert len(s["mouths"]) >= 3
        assert len(s["caverns"]) >= 3
        assert s["ore_blocks"] >= 1500, s["id"]
    for sid, rp in [(k, v) for k, v in real["report"].items() if not k.startswith("_")]:
        # the longest single walk from a mouth, measured on the replayed cells and not on the plan
        assert rp["longest_walk_from_mouth_0"] >= 1000, sid
        assert rp["reachable_floor_columns"] >= 9000, sid          # 1,500 columns for each of six players
        assert rp["reachable_standing_fraction"] >= 0.95, sid


def test_the_build_is_deterministic(spec, ground):
    # seeded hash noise only: two builds of one system are byte-identical, or a re-run would move the passages
    one = [s for s in spec["systems"] if s["id"] == "old_seams"][0]
    sp = copy.deepcopy(spec)
    sp["systems"] = [one]
    h = []
    for _ in range(2):
        _r, files, _s = CS.build_all(sp, g=ground)
        h.append(hashlib.sha256("\n".join("%s:%s" % (k, "\n".join(files[k])) for k in sorted(files)).encode()).hexdigest())
    assert h[0] == h[1]


def test_every_function_is_within_the_server_limits(real, spec):
    assert CS.check_files(real["files"], spec["rules"]) == []
    for name, lines in real["files"].items():
        assert FL.check_lines(lines, name) == [], name
    total = sum(len(v) for v in real["files"].values())
    assert 5000 < total < 200000          # sanity: not empty, not a runaway


def test_a_function_writes_only_inside_its_tile_and_the_tile_is_held(real, spec):
    tile = spec["rules"]["tile"]
    for name, lines in real["files"].items():
        if not (name.endswith("_shell") or name.endswith("_carve")):
            continue
        _sid, _kind, (x0, z0, x1, z1) = CS.tile_name_box(name, tile)
        assert (x1 - x0 + 1) // 16 * ((z1 - z0 + 1) // 16) <= 256         # forceload's chunk limit
        assert x0 % 16 == 0 and z0 % 16 == 0


def test_the_index_runs_every_shell_before_any_carve(real):
    idx = CS.index_lines(real["files"])
    kinds = [n.rsplit("_", 1)[1] for n in idx]
    assert kinds == sorted(kinds, key=lambda k: 0 if k == "shell" else 1)
    assert set(kinds) == {"shell", "carve"}


def test_the_steps_hold_each_tile_and_release_it(spec, real):
    steps = CS.placement_steps(spec, real["pack"])
    assert len(steps) % 4 == 0
    for i in range(0, len(steps), 4):
        add, wait, fn, rem = steps[i:i + 4]
        assert add[0] == "cmd" and add[1].startswith("forceload add ")
        assert wait[0] == "wait" and fn[0] == "fn" and rem[1] == add[1].replace("add", "remove")
    assert len(steps) // 4 == len([n for n in real["files"] if n.endswith(("_shell", "_carve"))])


def test_the_ore_is_richer_deeper_and_the_mouths_are_near_something(real):
    for sid, rp in [(k, v) for k, v in real["report"].items() if not k.startswith("_")]:
        d = list(rp["ore_per_1000_wall_cells_by_depth"].values())
        assert d[-1][2] >= 1.2 * d[0][2], (sid, d)
        for m in rp["mouths"]:
            assert 40 <= m["nearest_town_route_or_settlement"] <= 200


# ------------------------------------------------------------------ the audit bites: mutate the GENERATOR

def synth(spec, sid, centre, radius, mouths, target=700, caverns=2, seed=5):
    sp = copy.deepcopy(spec)
    sp["systems"] = [{"id": sid, "name": sid, "seed": seed, "centre": centre, "radius": radius, "target_length": target,
                      "caverns": caverns, "mouths": [{"id": "%s_%d" % (sid, i), "x": x, "z": z, "near": "test"} for i, (x, z) in enumerate(mouths)]}]
    return sp


def build_and_audit(sp, ground, tmp_path, patches=()):
    """Build with the generator as patched, write the pack, audit it against the UNPATCHED data and heightmap."""
    results, files, _s = CS.build_all(sp, g=ground)
    out = tmp_path / "pack"
    CS.write_pack(files, CS.index_lines(files), out)
    problems, report = CSA.audit(sp, out, g=ground)
    return problems, report, results


def has(problems, needle):
    return [p for p in problems if needle in p]


COVER = "under 8 blocks of rock"
ABOVE = "above the ground"
WATER = ("within 12 of sea or lake water", "river course's edge")
AUTH = ("within 32 of the authored point", "footprint rectangle", "exclusion disc", "the Rift region")


def any_has(problems, needles):
    return any(has(problems, n) for n in needles)


OLD = [(1914, 5142), (1806, 5302), (1650, 4950)]          # three of the Old Seams' mouths


@pytest.fixture(scope="module")
def clean(spec, ground, tmp_path_factory):
    sp = synth(spec, "t_clean", [2100, 5000], 520, OLD)
    return build_and_audit(sp, ground, tmp_path_factory.mktemp("cs_clean")) + (sp,)


def test_a_small_clean_system_has_no_cover_water_authored_or_shell_problem(clean):
    problems, report, _res, _sp = clean
    for needle in (COVER, ABOVE, "carved cells with no water", "last write is the shell", "ring cells", "shell cells are more than",
                   "never written to air", "past the eastern limit", "outside its tile") + WATER + AUTH:
        assert not has(problems, needle), (needle, has(problems, needle))


def test_audit_catches_a_generator_that_believes_the_ground_is_forty_higher(spec, ground, tmp_path, monkeypatch):
    # the generator plans cover against ground + 40, so every passage sits 40 closer to the surface than it thinks; the audit reads
    # the real heightmap and must find carved cells under less than 8 blocks of rock or above the ground
    orig = CS.ground_grid
    monkeypatch.setattr(CS, "ground_grid", lambda g, box: orig(g, box) + 40)
    sp = synth(spec, "t_high", [2100, 5000], 520, OLD)
    problems, _r, _res = build_and_audit(sp, ground, tmp_path)
    assert has(problems, COVER) or has(problems, ABOVE), problems[:5]


def test_audit_catches_a_generator_that_ignores_water_and_what_is_authored(spec, ground, tmp_path, monkeypatch):
    # the generator is made to keep clear of nothing but the map's own edges; a system is put over Lake Viltri and the Misty-side
    # country, where both water and authored points lie. The audit, reading the data itself, must find carved columns beside water
    # and within 32 of an authored point
    orig = CS.blocked_grid

    def nothing(rules, box, H):
        b, parts = orig(rules, box, H)
        return parts["limits"], parts
    monkeypatch.setattr(CS, "blocked_grid", nothing)
    monkeypatch.setattr(CS, "walk_problems", lambda res: [])          # and it does not walk its own output either
    sp = synth(spec, "t_lake", [1630, 2990], 330, [(1266, 2878), (1602, 3130), (1518, 3106)], target=3000, caverns=1)
    problems, _r, _res = build_and_audit(sp, ground, tmp_path)
    assert any_has(problems, WATER), problems[:6]
    assert any_has(problems, AUTH), problems[:6]


def test_audit_catches_a_shell_one_cell_too_thin(spec, ground, tmp_path, monkeypatch):
    orig = CS.dilate_cube
    monkeypatch.setattr(CS, "dilate_cube", lambda m, r: orig(m, 1))
    monkeypatch.setitem(spec["rules"], "shell_block", 1)           # and no coarse blocks, so the thin ring is not rounded back up
    sp = synth(spec, "t_thin", [2100, 5000], 520, OLD)
    problems, _r, _res = build_and_audit(sp, ground, tmp_path)
    assert has(problems, "ring cells") , problems[:5]


def test_audit_catches_a_carve_that_is_not_run_again_after_the_shell(spec, ground, tmp_path, monkeypatch):
    monkeypatch.setattr(CS, "CARVE_AGAIN", False)
    sp = synth(spec, "t_once", [2100, 5000], 520, OLD)
    problems, _r, _res = build_and_audit(sp, ground, tmp_path)
    assert has(problems, "last write is the shell") or has(problems, "never written to air"), problems[:5]


def test_audit_catches_carves_that_run_before_the_shells(spec, ground, tmp_path, monkeypatch):
    def carves_first(files):
        shells = sorted(k for k in files if k.endswith("_shell"))
        carves = sorted(k for k in files if k.endswith("_carve"))
        return carves + shells
    monkeypatch.setattr(CS, "index_lines", carves_first)
    sp = synth(spec, "t_order", [2100, 5000], 520, OLD)
    problems, _r, _res = build_and_audit(sp, ground, tmp_path)
    assert has(problems, "every shell must come before every carve"), problems[:5]


def test_audit_catches_a_write_east_of_x_4032(spec, tmp_path):
    # a hand-made pack, not a generator run: one tile at x 4032..4223 whose carve writes x 4040. The audit's own limit (the brief's
    # 64 blocks west of x 4096) must refuse it even though the record is edited to allow it
    base = tmp_path / "pack" / "data" / "cobblers" / "function" / "cave_systems"
    base.mkdir(parents=True)
    tx = 4032 // 192            # tile 21 starts at x 4032
    name = "t_%d_5" % tx
    x0, x1 = tx * 192 + 8, tx * 192 + 12
    shell = "\n".join(["# chunks-loaded-by: test", "fill %d 40 960 %d 44 962 minecraft:stone replace minecraft:water" % (x0, x1)]) + "\n"
    carve = "\n".join(["# chunks-loaded-by: test", "fill %d 40 960 %d 44 962 minecraft:air" % (x0, x1)]) + "\n"
    (base / (name + "_shell.mcfunction")).write_text(shell, encoding="utf-8")
    (base / (name + "_carve.mcfunction")).write_text(carve, encoding="utf-8")
    (base / "index.txt").write_text("\n".join([name + "_shell", name + "_carve"]) + "\n", encoding="utf-8")
    sp = copy.deepcopy(spec)
    sp["rules"]["east_limit_x"] = 4300
    a = CSA.Audit(sp, tmp_path / "pack")
    a.replay()
    a.check_commands()
    assert has(a.problems, "past the eastern limit"), a.problems


# ------------------------------------------------------------------ each audit check on its own, on cells made by hand

_HAND = {}


def hand_audit(spec, tmp_path, ground):
    a = CSA.Audit(spec, tmp_path, g=ground)
    a._auth = _HAND.setdefault("auth", CSA.authored_inputs())
    a._attr = _HAND.setdefault("attr", CSA.attractors_for_audit())
    a.report["h"] = {}
    return a


def test_the_cover_check_flags_a_cell_three_below_the_ground_and_one_above_it(spec, ground, tmp_path):
    import numpy as np
    a = hand_audit(spec, tmp_path, ground)
    x, z = 2100, 5000
    g = int(round(ground.heights[z, x]))
    a.check_cover("h", np.array([x, x]), np.array([g - 3, g + 2]), np.array([z, z]), mouths=[])
    assert has(a.problems, COVER) and has(a.problems, ABOVE), a.problems
    b = hand_audit(spec, tmp_path, ground)
    b.check_cover("h", np.array([x]), np.array([g - 9]), np.array([z]), mouths=[])
    assert b.problems == []            # nine blocks of rock is enough
    c = hand_audit(spec, tmp_path, ground)
    c.check_cover("h", np.array([x]), np.array([g - 1]), np.array([z]), mouths=[{"x": x, "z": z}])
    assert c.problems == []            # inside a mouth zone only "not above the ground" holds


def test_the_water_check_flags_a_cell_beside_the_sea_and_not_one_far_inland(spec, ground, tmp_path):
    import numpy as np
    H = np.asarray(ground.heights)
    sub = H[2000:4000, 60:900]
    sea = sub <= 62
    near = CS.dilate_disc(sea, 5)
    land = sub >= 64
    iz, ix = np.nonzero(near & land)
    z, x = int(iz[0]) + 2000, int(ix[0]) + 60              # land within 5 of the sea
    g = int(round(H[z, x]))
    a = hand_audit(spec, tmp_path, ground)
    a.check_water("h", np.array([x, x + 1]), np.array([z, z]))
    assert has(a.problems, "within 12 of sea"), a.problems
    b = hand_audit(spec, tmp_path, ground)
    b.check_water("h", np.array([2100, 2101]), np.array([5000, 5000]))      # the Old Seams: nowhere near water
    assert b.problems == []


def test_the_authored_check_flags_a_cell_beside_a_town_centre_and_not_one_far_off(spec, ground, tmp_path):
    import numpy as np
    a = hand_audit(spec, tmp_path, ground)
    a.check_authored("h", np.array([1470, 1471]), np.array([5300, 5300]))          # Pallet's centre is 1462, 5293
    assert has(a.problems, AUTH[0]) or any_has(a.problems, AUTH), a.problems
    b = hand_audit(spec, tmp_path, ground)
    b.check_authored("h", np.array([2100, 2101]), np.array([5000, 5000]))
    assert b.problems == []


def test_the_walk_check_refuses_a_ledge_the_player_cannot_climb(spec, ground, tmp_path):
    import numpy as np
    a = hand_audit(spec, tmp_path, ground)
    x, z = 2100, 5000
    g = int(round(ground.heights[z, x]))
    # two chambers of cells, one 4 higher than the other, touching: a player cannot step up four
    cells = [(xx, y, zz) for xx in range(x, x + 6) for zz in range(z, z + 3) for y in range(g - 20, g - 17)]
    cells += [(xx, y, zz) for xx in range(x + 6, x + 12) for zz in range(z, z + 3) for y in range(g - 16, g - 13)]
    X, Y, Z = (np.array([c[i] for c in cells]) for i in range(3))
    a.report["h"] = {}
    a.check_walk("h", X, Y, Z, [{"id": "m", "x": x + 1, "z": z + 1}])
    assert has(a.problems, "walk") or has(a.problems, "standing cells"), a.problems


# ------------------------------------------------------------------ independence and wiring

def test_audit_imports_no_generator():
    src = (ROOT / "tools" / "cave_systems_audit.py").read_text(encoding="utf-8")
    names = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import):
            names |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            names.add(n.module)
    assert "cave_systems" not in names and not any(x.startswith("cave_systems.") for x in names if x)


def test_the_generator_reads_no_world_and_does_not_import_the_audit():
    src = (ROOT / "tools" / "cave_systems.py").read_text(encoding="utf-8")
    assert "cave_systems_audit" not in src.split('"""', 2)[2]
    assert CS.WORLD_READS == set()
    assert not re.search(r"\.mca|region/|session\.lock|level\.dat", src.split('"""', 2)[2])


def test_reapply_lists_builds_audits_and_runs_the_pack():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    sys.path.insert(0, str(ROOT / "tools"))
    import reapply
    assert "cobblers_cave_systems" in reapply.SERVER_PACKS
    assert 'add("cave_systems:build", "cave_systems.py", "build", *src)' in src
    assert 'add("cave_systems_audit", "cave_systems_audit.py", *src)' in src
    assert src.index('add("cave_systems:build"') < src.index('add("cave_systems_audit"')
    assert '("R9CS",' in src and "cave_systems.placement_steps()" in src
    assert src.index('("R9CK",') < src.index('("R9CS",') < src.index('("R9E",')
    # a pack that nothing calls at play time is stripped from the heap after the run: it must not be world-local runtime
    assert "cobblers_cave_systems" not in reapply.WORLD_LOCAL


def test_the_pack_has_no_runtime_data(real):
    base = Path(real["pack"])
    kinds = {p.relative_to(base / "data" / "cobblers").parts[0] for p in (base / "data" / "cobblers").rglob("*") if p.is_file()}
    assert kinds == {"function"}
    assert not (base / "data" / "minecraft").exists()          # no tick or load tag: nothing runs by itself
