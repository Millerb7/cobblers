"""The Rift dig camp's mines (tools/rift_mines.py) and their offline audit (tools/rift_mines_audit.py).

What is asserted, without the heightmap:
  - the generator and the audit rasterise the committed data's tubes, pockets, rooms and chambers to the same cells
    (two implementations of the data's `geometry`; the audit's expectations are worthless if they drift apart);
  - a cut's benches and a pit's ramp follow the data's words;
  - the audit's plan checks catch a gated gallery brought next to an ungated one, a gate whose plug does not span the
    gap, an arrival inside the exit box, a gated pocket cut off from the arrival, and thin cover;
  - the committed data: every track straight, the flag a real progression flag, no block a spawn condition names;
  - tools/reapply.py runs the pack as R9M between R9C and R9E, every block function in index order then the carts,
    and installs the pack in the world's folder (it acts on its own).
With the heightmap (slow, skipped without COBBLERS_SOURCE_ROOT): the model's own checks pass, the pack builds, the
audit is clean, and removing one block of the seal round the gated section makes the audit fail.

Not covered, and it needs a running server: that the functions land, that the advancements fire for the right player,
that the teleports put a player where they say, that the carts summon, and how any of it looks.
"""
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import rift_mines as RM  # noqa: E402
import rift_mines_audit as RA  # noqa: E402

SPEC = json.loads((ROOT / "data" / "rift_mines.json").read_text(encoding="utf-8"))


def _features(kind):
    return [f for f in SPEC["mine"]["features"] if f["kind"] == kind]


@pytest.mark.parametrize("f", _features("tube"), ids=lambda f: f["id"])
def test_generator_and_audit_rasterise_every_tube_alike(f):
    a = RM.tube_cells(f["path"], f["r"], f["height"])
    b = RA.stamp_tube(f["path"], f["r"], f["height"])
    if f.get("pocket"):
        a |= RM.pocket_cells(f["pocket"]["at"], f["pocket"]["r"])
        b |= RA.stamp_pocket(f["pocket"]["at"], f["pocket"]["r"])
    assert a and a == b


@pytest.mark.parametrize("f", _features("chamber"), ids=lambda f: f["id"])
def test_generator_and_audit_rasterise_every_chamber_alike(f):
    a = RM.chamber_cells(f["centre"], f["r"], f["height"])
    assert a and a == RA.stamp_chamber(f["centre"], f["r"], f["height"])


@pytest.mark.parametrize("f", _features("pocket"), ids=lambda f: f["id"])
def test_generator_and_audit_rasterise_every_pocket_alike(f):
    a = RM.pocket_cells(f["at"], f["r"])
    assert a and a == RA.stamp_pocket(f["at"], f["r"])


@pytest.mark.parametrize("cut", SPEC["town"]["cuts"], ids=lambda c: c["id"])
def test_generator_and_audit_agree_on_every_cut_floor(cut):
    x0, z0, x1, z1 = cut["rect"]
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            assert RM.cut_floor(cut, x, z) == RA.floor_of_cut(cut, x, z)


def test_a_pit_steps_up_to_its_rim_and_its_ramp_runs_down_to_the_floor():
    cut = next(c for c in SPEC["town"]["cuts"] if c["kind"] == "pit")
    x0, z0, x1, z1 = cut["rect"]
    b = cut["bench"]
    assert RM.cut_floor(cut, (x0 + x1) // 2, (z0 + z1) // 2) == cut["floor"]
    assert RM.cut_floor(cut, x0 + 1, (z0 + z1) // 2) == cut["floor"] + b["rise"] * (b["levels"] - 1)
    rp = cut["ramp"]
    xs = rp["x"][0]
    assert RM.cut_floor(cut, xs, rp["z"][1]) == cut["floor"]
    down = [RM.cut_floor(cut, xs, z) for z in range(rp["z"][0], rp["z"][1] + 1)]
    assert all(a >= b_ for a, b_ in zip(down, down[1:])), "the ramp climbs somewhere on the way down"
    assert all(a - b_ <= 1 for a, b_ in zip(down, down[1:])), "the ramp drops more than a block in a step"


def test_a_hillside_with_no_benches_is_one_floor():
    cut = next(c for c in SPEC["town"]["cuts"] if c["id"] == "seam_cut")
    x0, z0, x1, z1 = cut["rect"]
    assert {RM.cut_floor(cut, x, z) for x in (x0, x1) for z in (z0, z1)} == {cut["floor"]}


# ------------------------------------------------------------------ the audit's plan checks, on a small made-up mine

def _mini(**over):
    """A decline, a gate and a gated gallery with one pocket, on flat ground at y120."""
    spec = {
        "cover_min": 4,
        "town": {"cuts": []},
        "mine": {
            "features": [
                {"id": "decline", "gated": False, "kind": "tube", "path": [[0, 80, 0], [20, 80, 0]], "r": 1, "height": 4},
                {"id": "gallery", "gated": True, "kind": "tube", "path": [[32, 80, 0], [60, 80, 0]], "r": 1, "height": 4},
                {"id": "face", "gated": True, "kind": "pocket", "at": [45, 80, 4], "r": 2},
            ],
            "gate": {"plug": [22, 79, -2, 30, 85, 2], "knock": [19, 80, -1, 21, 82, 1], "arrive": [35.5, 80, 0.5, -90],
                     "exit": [31, 80, -1, 31, 83, 1], "turn_back": [10.5, 80, 0.5, 90]},
        },
    }
    for k, v in over.items():
        spec["mine"]["gate"][k] = v
    return spec


def _plan(spec, ground=120):
    gated, ungated, eff, _cuts = RA.plan(spec, lambda x, z: ground)
    return RA.plan_problems(spec, gated, ungated, lambda x, z: eff.get((x, z), ground))


def test_the_mini_mine_is_clean():
    probs, _notes, _cells = _plan(_mini())
    assert probs == []


def test_a_gated_gallery_brought_beside_an_ungated_one_is_caught():
    spec = _mini()
    spec["mine"]["features"][1]["path"] = [[23, 80, 0], [60, 80, 0]]
    spec["mine"]["gate"]["plug"] = [22, 79, -2, 22, 85, 2]
    spec["mine"]["gate"]["exit"] = [22, 80, -1, 22, 83, 1]
    probs, _n, _c = _plan(spec)
    assert any(p.startswith("separation") for p in probs), probs


def test_a_plug_that_leaves_a_gap_of_rock_is_not_a_gate():
    probs, _n, _c = _plan(_mini(plug=[22, 79, -2, 28, 85, 2]))
    assert any("does not reach the arrival" in p for p in probs), probs


def test_an_arrival_inside_the_exit_box_is_caught():
    probs, _n, _c = _plan(_mini(arrive=[31.5, 80, 0.5, -90]))
    assert any("inside the exit box" in p for p in probs), probs


def test_a_turn_back_point_in_mid_air_is_caught():
    probs, _n, _c = _plan(_mini(turn_back=[10.5, 81, 0.5, 90]))
    assert any("turn-back" in p for p in probs), probs


def test_a_gated_pocket_cut_off_from_the_arrival_is_caught():
    spec = _mini()
    spec["mine"]["features"][2]["at"] = [45, 80, 9]
    probs, _n, _c = _plan(spec)
    assert any(p.startswith("connected") for p in probs), probs


def test_thin_cover_over_the_gated_gallery_is_caught():
    probs, _n, _c = _plan(_mini(), ground=88)
    assert any(p.startswith("cover") for p in probs), probs


# ------------------------------------------------------------------ the committed data

def test_every_track_is_straight_so_a_powered_rail_can_lay_it():
    for t in SPEC["town"]["tracks"]:
        (xa, za), (xb, zb) = t["from"], t["to"]
        assert xa == xb or za == zb, t["id"]


def test_the_gate_opens_on_a_real_progression_flag():
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    ids = {f["id"] for f in prog["flags"]}
    adv = SPEC["flag"]["advancement"]
    assert adv.startswith("cobblers:flag/") and adv.split("/", 1)[1] in ids


def test_no_block_the_data_names_is_a_spawn_condition():
    sb = json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"]
    named = set()

    def walk(o):
        if isinstance(o, str) and ":" in o and o.split(":")[0] in ("minecraft", "mega_showdown"):
            named.add(o.split("[")[0])
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk({k: v for k, v in SPEC.items() if k not in ("flag",)})
    assert named and not (named & set(sb)), named & set(sb)


def test_every_chamber_is_shell_only_and_names_a_guardian_mode():
    modes = {"wild_mega", "trainer_echo", "outlier"}
    for f in _features("chamber"):
        g = f["guardian"]
        assert g["mode"] in modes and g["fallback_mode"] in modes
        assert g["species"] is None and g["level"] is None


# ------------------------------------------------------------------ the re-apply step and the install

def test_reapply_runs_the_pack_as_r9m_between_the_caves_and_the_habitat_blocks(monkeypatch):
    import reapply
    listed = {"cobblers_rift_mines": ["1shell_48_48", "2air_48_48", "4surface_49_51"]}
    monkeypatch.setattr(reapply, "indexed", lambda pack, folder: listed.get(pack, ["x"]))
    ids = [s[0] for s in reapply.steps()]
    assert ids.index("R9C") < ids.index("R9M") < ids.index("R9E")
    assert ids.index("R9") < ids.index("R9M") < ids.index("R16")
    acts = next(s for s in reapply.steps() if s[0] == "R9M")[2]
    assert acts == [("fn", "cobblers:rift_mines/%s" % f) for f in listed["cobblers_rift_mines"]] + \
        [("fn", "cobblers:rift_mines/carts"), ("wait", 5)]


def test_the_pack_is_installed_in_the_worlds_own_folder():
    import reapply
    assert "cobblers_rift_mines" in reapply.SERVER_PACKS
    assert "cobblers_rift_mines" in reapply.WORLD_LOCAL
    assert "cobblers_rift_mines" not in reapply.EXCLUDED


# ------------------------------------------------------------------ with the heightmap

def _source_root():
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("COBBLERS_SOURCE_ROOT is not set: the heightmap is outside the repo")
    return root


@pytest.mark.slow
def test_the_model_passes_its_own_checks():
    root = _source_root()
    m, near = RM.model(root)
    boxes = RM.zone_boxes(m)
    assert RM.check(m, near) + RM.zone_problems(m, boxes) == []
    assert m.counts["mega stone crystals"] == sum(f.get("crystals", 0) for f in SPEC["mine"]["features"])


@pytest.mark.slow
def test_the_audit_is_clean_and_fails_when_one_seal_block_is_taken_out(tmp_path, monkeypatch):
    root = _source_root()
    if not RA.CAMP_PLAN.is_file():
        pytest.skip("no derived/towns/rift_dig_camp_plan.json: run tools/town_plan.py rift_dig_camp")
    assert RM.main(["build", "--source-root", root]) == 0
    probs, _notes = RA.audit(root)
    assert probs == []
    # take one block of rock out of the seal: replace it with air at the end of the last function
    pack = tmp_path / "cobblers_rift_mines"
    shutil.copytree(RA.PACK, pack)
    fn = pack / "data" / "cobblers" / "function" / "rift_mines"
    spec = SPEC
    g = next(f for f in spec["mine"]["features"] if f["id"] == "gallery_bc")
    x, y, z = g["path"][0][0] + 8, g["path"][0][1] + 6, g["path"][0][2]
    last = [n for n in (fn / "index.txt").read_text(encoding="utf-8").split("\n") if n.strip()][-1]
    with open(fn / (last + ".mcfunction"), "a", encoding="utf-8") as fh:
        fh.write("# chunks-loaded-by: test\n")
    gated, _ungated, _eff, _c = RA.plan(spec, RA.GR.Ground(root))
    ring = sorted(c for c in {(a + dx, b + dy, c_ + dz) for a, b, c_ in gated
                              for dx, dy, dz in ((0, 1, 0),)} if c not in gated)
    hole = min(ring, key=lambda c: abs(c[0] - x) + abs(c[1] - y) + abs(c[2] - z))
    with open(fn / (last + ".mcfunction"), "a", encoding="utf-8") as fh:
        fh.write("setblock %d %d %d minecraft:air\n" % hole)
    monkeypatch.setattr(RA, "PACK", pack)
    monkeypatch.setattr(RA, "FN", fn)
    probs, _notes = RA.audit(root)
    assert any(p.startswith("sealed") for p in probs), probs
