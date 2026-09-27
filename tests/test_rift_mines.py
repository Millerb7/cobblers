"""The Rift dig camp's mines, cut back to the seam (tools/rift_mines.py), and their offline audit (tools/rift_mines_audit.py).

Rewritten by the test author for the cut-back spur (72f8ddb; SOUTHERN_RIFT_MEGA.md decisions 1-2): the gated
galleries, chambers and Heart are retired (data/rift_mines.json retired_gated_section, rock put back on staging by the
refill pack), the company gate and zone check are gone, and drift C ends at the company's grille with one crystal in
the seam behind it, warded per player until gym6_cleared (mine.tease). The tease ward's reach and flag are in
tests/test_rift_mines_ward.py; the built pack, replayed, in tests/test_rift_mines_review.py.

What is asserted, without the heightmap:
  - the generator and the audit rasterise every live and every retired tube, pocket and chamber to the same cells, and
    a cut's benches and a pit's ramp follow the data's words (two implementations of `geometry`);
  - the audit's plan checks, on a small made-up mine: clean as made; a gated feature, a feature carrying crystals, a
    grille that leaves a gap, a face box in the envelope, a ward too small, a ward that fatigues everyone, and a
    collapse in the envelope are each reported;
  - the committed data: every track straight, the flag gym6_cleared and a real progression flag, no placed block a
    spawn condition, the tease's restore a filtered fill that spares a player's chest;
  - tools/reapply.py runs the pack as R9M between R9C and R9E, installs it world-local, and never runs or installs the
    staging-only refill.
With the heightmap (slow, skipped without COBBLERS_SOURCE_ROOT): the model's own checks pass with one crystal, the pack
builds, the audit is clean, and taking one block out of the seal round the drift C pocket makes it fail.

Not covered, and it needs a running server: that the functions land, that the ward's advancement fires for the right
player, that the tease face restores in game (`fill ... replace #tag`, proof P-3), that the carts summon.
"""
import json
import os
import shutil
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import rift_mines as RM  # noqa: E402
import rift_mines_audit as RA  # noqa: E402

SPEC = json.loads((ROOT / "data" / "rift_mines.json").read_text(encoding="utf-8"))
RETIRED = SPEC["retired_gated_section"]["features"]


def _features(kind, feats=None):
    return [f for f in (feats if feats is not None else SPEC["mine"]["features"] + RETIRED) if f["kind"] == kind]


# Without it the two implementations of the data's geometry drift apart, and the audit (and the refill check, which
# rasterises the retired section the same way) is about the wrong cells.
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


# Without it a pit's benches step the wrong way or its ramp becomes a staircase a cart cannot use.
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

FLAG = "cobblers:flag/gym6_cleared"


def _mini():
    """An adit along z30, a drift south to north ending in a pocket, the grille across the drift at z15 and a face box
    north of the pocket whose south side faces it; a collapse off to the side. Nothing gated."""
    return {
        "seed": 1, "cover_min": 4, "town": {"cuts": []},
        "flag": {"advancement": FLAG, "badge": 6},
        "palette": {"meteorid": "mega_showdown:mega_meteorid_block",
                    "meteorid_radiated": "mega_showdown:mega_meteorid_radiated_block",
                    "mega_stone_crystal": "mega_showdown:mega_stone_crystal"},
        "mine": {
            "features": [
                {"id": "adit", "gated": False, "kind": "tube", "path": [[0, 80, 30], [20, 80, 30]], "r": 1, "height": 4},
                {"id": "drift_c", "gated": False, "kind": "tube", "path": [[20, 80, 30], [20, 80, 10]], "r": 1, "height": 4,
                 "pocket": {"at": [20, 80, 8], "r": 2}},
            ],
            "collapse": {"box": [40, 79, 28, 42, 83, 32]},
            "tease": {"drift": "drift_c", "grille": {"x": [19, 21], "z": 15, "y": [80, 83]},
                      "face": {"box": [19, 80, 3, 21, 82, 5], "front": "south", "crystals": 1, "radiated": 2},
                      "period_ticks": 1000, "approach": [0, 60, 0, 50, 100, 40], "ward_margin": 7,
                      "resettable_tag": "t", "resettable": ["minecraft:air"]},
        },
    }


def _plan(spec, monkeypatch, tmp_path, ward=None, ward_fn=None):
    """RA.plan_problems on the made-up mine, with the pack's ward (its advancement box and function) taken from the
    generator's tease_files for that spec, unless `ward` / `ward_fn` replace them."""
    files, fn = RM.tease_files(types.SimpleNamespace(spec=spec))
    pos = files["advancement/%s/tease_ward.json" % RM.FOLDER]["criteria"]["here"]["conditions"]["player"][0]
    p = pos["predicate"]["location"]["position"]
    box = ((p["x"]["min"], p["y"]["min"], p["z"]["min"]), (p["x"]["max"] - 1, p["y"]["max"] - 1, p["z"]["max"] - 1))
    monkeypatch.setattr(RA, "adv_box", lambda name: (ward or box) if name == "tease_ward.json" else None)
    fdir = tmp_path / "fn"
    (fdir / "tease").mkdir(parents=True)
    (fdir / "tease" / "ward.mcfunction").write_text("\n".join(ward_fn or fn["tease/ward"]) + "\n", encoding="utf-8")
    monkeypatch.setattr(RA, "FN", fdir)
    gated, ungated, _eff, _cuts = RA.plan(spec, lambda x, z: 120)
    probs, _notes = RA.plan_problems(spec, gated, ungated)
    return probs


def test_the_mini_mine_is_clean(monkeypatch, tmp_path):
    assert _plan(_mini(), monkeypatch, tmp_path) == []


# Without each, the audit passes a spur that brings back what decision 1 retired or breaks the tease: a gated feature
# (a section nobody can enter now the gate is gone), crystals on a feature (the seam's one crystal is the tease's), a
# grille that leaves part of the drift open (the crystal reached without passing it), a face box inside the carved
# space, a ward the grille, pocket or face sit within ward_margin of its edge, a ward that fatigues players holding the
# flag (it must lift for them), or the collapse inside the envelope.
@pytest.mark.parametrize("what,prefix", [
    ("a gated feature", "gated:"), ("a feature carrying crystals", "gated: features still carry crystals"),
    ("a grille with a gap", "tease: the face's front is reached from the adit"),
    ("a face box in the envelope", "tease: the face box overlaps the envelope"),
    ("a ward too small", "of the ward's edge"), ("a ward for everyone", "tease: the ward's function does not give the effect only"),
    ("the collapse in the envelope", "collapse:")])
def test_the_audit_plan_catches_a_broken_tease(monkeypatch, tmp_path, what, prefix):
    spec = _mini()
    kw = {}
    t = spec["mine"]["tease"]
    if what == "a gated feature":
        spec["mine"]["features"].append({"id": "gallery", "gated": True, "kind": "tube", "path": [[0, 80, 50], [9, 80, 50]],
                                         "r": 1, "height": 4})
    elif what == "a feature carrying crystals":
        spec["mine"]["features"][0]["crystals"] = 2
    elif what == "a grille with a gap":
        t["grille"]["x"] = [19, 20]
    elif what == "a face box in the envelope":
        t["face"]["box"] = [19, 80, 5, 21, 82, 7]
    elif what == "a ward too small":
        _files, _fn = RM.tease_files(types.SimpleNamespace(spec=spec))
        lo, hi = RM.ward_box(dict(spec, mine=dict(spec["mine"], tease=dict(t, ward_margin=2))))
        kw["ward"] = (tuple(lo), tuple(hi))
    elif what == "a ward for everyone":
        kw["ward_fn"] = ["advancement revoke @s only cobblers:rift_mines/tease_ward",
                         "execute if entity @s[gamemode=!creative,gamemode=!spectator] run effect give @s "
                         "minecraft:mining_fatigue 3 3 true"]
    elif what == "the collapse in the envelope":
        spec["mine"]["collapse"]["box"] = [4, 80, 29, 6, 82, 31]
    probs = _plan(spec, monkeypatch, tmp_path, **kw)
    assert any(prefix in p for p in probs), (what, probs)


# ------------------------------------------------------------------ the committed data

# Without it a powered-rail track the data draws diagonally cannot be laid.
def test_every_track_is_straight_so_a_powered_rail_can_lay_it():
    for t in SPEC["town"]["tracks"]:
        (xa, za), (xb, zb) = t["from"], t["to"]
        assert xa == xb or za == zb, t["id"]


# Without it the tease lifts on a flag nothing grants, or on the wrong badge: decision 2 keys the seam's crystal to the
# sixth badge (the one whose leader gives the Mega Bracelet), the same flag the gulch opens on.
def test_the_tease_lifts_on_the_sixth_badges_flag_a_real_progression_flag():
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    ids = {f["id"] for f in prog["flags"]}
    adv = SPEC["flag"]["advancement"]
    assert adv == FLAG and SPEC["flag"]["badge"] == 6
    assert adv.startswith("cobblers:flag/") and adv.split("/", 1)[1] in ids
    gulch = json.loads((ROOT / "data" / "gulch_mine.json").read_text(encoding="utf-8"))
    assert gulch["flag"]["advancement"] == adv, "decision 2 and 3: the seam and the gulch open on the same flag"


# Without it the mine decides what spawns in it: no block the data names to place (the restore's filter tag lists what
# the fill may replace, water and lava among them, and places none of them) is a spawn condition.
def test_no_block_the_data_places_is_a_spawn_condition():
    sb = json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"]
    named = set()

    def walk(o):
        if isinstance(o, str) and ":" in o and o.split(":")[0] in ("minecraft", "mega_showdown"):
            named.add(o.split("[")[0])
        elif isinstance(o, dict):
            for k, v in o.items():
                if k not in ("resettable",):
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk({k: v for k, v in SPEC.items() if k not in ("flag",)})
    assert named and not (named & set(sb)), named & set(sb)
    assert not [b for b in named if b.startswith("mega_showdown:mega_meteorid_") and b.endswith("_ore")], \
        "a meteorid ore drops evolution stones (SOUTHERN_RIFT_MEGA.md 4)"


# Without it the daily restore overwrites what a player left in the face box (STONE_ECONOMY.md 5.4: a chest survives
# with its contents) or places a block the tag lists: the fill replaces only the tag, every crystal setblock is guarded
# by it, the tag is the data's list and holds no container, and exactly the data's one crystal is written per restore.
def test_the_tease_restore_is_a_filtered_fill_that_spares_a_players_chest():
    t = SPEC["mine"]["tease"]
    _files, fn = RM.tease_files(types.SimpleNamespace(spec=SPEC))
    body = [l for l in fn["tease/restore"] if not l.startswith("#")]
    tag = "#%s:%s" % (RM.NS, t["resettable_tag"])
    x0, y0, z0, x1, y1, z1 = t["face"]["box"]
    assert body[0] == "fill %d %d %d %d %d %d %s replace %s" % (x0, y0, z0, x1, y1, z1, SPEC["palette"]["meteorid"], tag)
    for l in body[1:]:
        assert l.startswith("execute if block ") and (" %s run setblock " % tag) in l, l
    assert sum("mega_stone_crystal" in l for l in body) == t["face"]["crystals"] == 1
    assert not [b for b in t["resettable"] if any(k in b for k in ("chest", "barrel", "shulker", "hopper", "furnace"))]
    drive = [l for l in fn["tease/drive"] if not l.startswith("#")]
    assert drive.index("execute if score #d rm.t < #period rm.t run return 0") < drive.index("function %s:%s/tease/restore"
                                                                                           % (RM.NS, RM.FOLDER))


# ------------------------------------------------------------------ the re-apply step and the install

# Without it a re-apply builds the mines before the caves or after the Habitat Blocks, or skips the carts.
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


# Without it the pack's ward and daily face (which act on their own) are installed where every world loads them, or the
# staging-only refill (rock back into the retired galleries) reaches a server or a fresh export, or a step runs it.
def test_the_pack_is_world_local_and_the_refill_is_never_installed_or_run(monkeypatch):
    import reapply
    assert "cobblers_rift_mines" in reapply.SERVER_PACKS and "cobblers_rift_mines" in reapply.WORLD_LOCAL
    assert "cobblers_rift_mines" not in reapply.EXCLUDED
    refill = "cobblers_rift_mines_refill"
    assert refill in reapply.EXCLUDED and "staging only" in reapply.EXCLUDED[refill]
    assert refill not in reapply.SERVER_PACKS and refill not in reapply.WORLD_LOCAL
    monkeypatch.setattr(reapply, "indexed", lambda pack, folder: ["x"])
    acts = [a for s in reapply.steps() for a in s[2]]
    assert not [a for a in acts if a[0] == "fn" and "rift_mines_refill" in a[1]], acts
    assert RM.REFILL.name == refill


# ------------------------------------------------------------------ with the heightmap

def _source_root():
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("COBBLERS_SOURCE_ROOT is not set: the heightmap is outside the repo")
    return root


# Without it the model builds a gated cell, a second crystal, or a tease its own checks reject.
@pytest.mark.slow
def test_the_model_passes_its_own_checks_with_one_crystal():
    root = _source_root()
    m, near = RM.model(root)
    assert RM.check(m, near) == []
    assert m.counts["mega stone crystals"] == SPEC["mine"]["tease"]["face"]["crystals"] == 1
    assert m.counts["gated carved cells"] == 0


# Without it the audit passes a pack whose drift C pocket is open to the natural rock round it: with one block of the
# seal next to the pocket replaced by air, the audit must report the seal.
@pytest.mark.slow
def test_the_audit_is_clean_and_fails_when_one_seal_block_is_taken_out(tmp_path, monkeypatch):
    root = _source_root()
    if not RA.CAMP_PLAN.is_file():
        pytest.skip("no derived/towns/rift_dig_camp_plan.json: run tools/town_plan.py rift_dig_camp")
    assert RM.main(["build", "--source-root", root]) == 0
    probs, _notes = RA.audit(root)
    assert probs == []
    pack = tmp_path / "cobblers_rift_mines"
    shutil.copytree(RA.PACK, pack)
    fn = pack / "data" / "cobblers" / "function" / "rift_mines"
    drift = next(f for f in SPEC["mine"]["features"] if f["id"] == "drift_c")
    pocket = RA.stamp_pocket(drift["pocket"]["at"], drift["pocket"]["r"])
    _gated, ungated, _eff, _c = RA.plan(SPEC, RA.GR.Ground(root))
    fb = SPEC["mine"]["tease"]["face"]["box"]
    face = {(x, y, z) for x in range(fb[0], fb[3] + 1) for y in range(fb[1], fb[4] + 1) for z in range(fb[2], fb[5] + 1)}
    ring = sorted({(x - 1, y, z) for x, y, z in pocket} - ungated - face)
    hole = ring[len(ring) // 2]
    last = [n for n in (fn / "index.txt").read_text(encoding="utf-8").split("\n") if n.strip()][-1]
    with open(fn / (last + ".mcfunction"), "a", encoding="utf-8") as fh:
        fh.write("setblock %d %d %d minecraft:air\n" % hole)
    monkeypatch.setattr(RA, "PACK", pack)
    monkeypatch.setattr(RA, "FN", fn)
    probs, _notes = RA.audit(root)
    assert any(p.startswith("sealed") for p in probs), probs
