"""Independent review of the cut-back Rift dig camp mines: tools/rift_mines.py's packs and tools/rift_mines_audit.py.

Rewritten by the test author for the cut-back spur (72f8ddb, SOUTHERN_RIFT_MEGA.md decisions 1-2), not by the session
that built it. On packs the generator builds (copied into tmp_path):

  envelope   the generator's model and the audit's plan agree on every carved cell, and none is gated
  crystal    exactly one mega_stone_crystal is ever written (every write, not only the last), in the face box, on its
             front's bottom row, facing out; the grille's iron bars stand in every grille cell at the end
  sealed     a flood from the face's front through every cell that ends as air, with the grille shut, stays behind the
             grille, never meets a cell the build did not write (unknown ground: the worst case) nor the grid's edge;
             with the grille open it reaches the adit's mouth
  gate gone  no knock, exit, gate-ward or zone advancement is left: the only one is the tease's ward
  blocks     no block written (every write) is a spawn condition, a fluid, minecraft:light or a meteorid ore; nothing
             is summoned but the tagged minecarts
  bounds     every write is inside the data's grid and off the camp's streets, plaza, anchors and lots
  refill     the staging refill writes rock into exactly the retired gated section's envelope, rasterised here from
             the data's `geometry` words (not by either tool), and nothing into the live mine, the collapse or the
             camp; the retired section is the gated section the spur build had (5d18aa5), feature for feature
  audit      mutation checks on the output: each of a seal cell opened, a write outside the grid, a block on a camp
             lot, a spawn-condition block, water, a second crystal, a retired gate advancement and a meteorid ore makes
             the audit report it; a pack with no grille at all is not reported (a finding, marked strict xfail)

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT) and derived/towns/rift_dig_camp_plan.json (python
tools/town_plan.py rift_dig_camp); SKIPS without them, and a skip is not a pass.

Not covered, and it needs a running server: that the ward advancement fires, that the tease restores in game, that
the carts summon on their rails, and that the refill run on staging closes what the old carve opened in that world
(the refill writes the envelope; what the world holds there is not read here).
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import rift_mines as RM  # noqa: E402
import rift_mines_audit as RA  # noqa: E402
import test_rift_mines_ward as W  # noqa: E402

SPEC = json.loads((ROOT / "data" / "rift_mines.json").read_text(encoding="utf-8"))
TEASE = SPEC["mine"]["tease"]
SPAWN = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
AIRS = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
FLUIDS = {"minecraft:water", "minecraft:lava", "minecraft:flowing_water", "minecraft:flowing_lava"}
CRYSTAL = "mega_showdown:mega_stone_crystal"
CMD = re.compile(r"^(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))? (\S+)")

pytestmark = pytest.mark.slow


def box_cells(b):
    return {(x, y, z) for x in range(b[0], b[3] + 1) for y in range(b[1], b[4] + 1) for z in range(b[2], b[5] + 1)}


def chamber(centre, r, height):
    """geometry.chamber, in this file's words: columns with d = hypot(dx, dz) <= r + 0.5; feet to
    feet + max(3, floor((height - 1) * sqrt(1 - (d / (r + 0.5))^2) + 0.5))."""
    cx, feet, cz = centre
    out = set()
    R = r + 0.5
    for dx in range(-r - 1, r + 2):
        for dz in range(-r - 1, r + 2):
            d = math.hypot(dx, dz)
            if d <= R:
                top = feet + max(3, int(math.floor((height - 1) * math.sqrt(max(0.0, 1 - (d / R) ** 2)) + 0.5)))
                out |= {(cx + dx, y, cz + dz) for y in range(feet, top + 1)}
    return out


def retired_envelope(features):
    out = set()
    for f in features:
        if f["kind"] == "tube":
            out |= W.tube(f["path"], f["r"], f["height"])
            if f.get("pocket"):
                out |= W.pocket(f["pocket"]["at"], f["pocket"]["r"])
        elif f["kind"] == "pocket":
            out |= W.pocket(f["at"], f["r"])
        elif f["kind"] == "chamber":
            out |= chamber(f["centre"], f["r"], f["height"])
        else:
            raise AssertionError("a retired feature of kind %s: rasterise it here" % f["kind"])
    return out


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """(pack dir, refill function dir, generator model, audit plan) for the committed data, built into tmp_path."""
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("COBBLERS_SOURCE_ROOT is not set: the heightmap is outside the repo")
    if not RA.CAMP_PLAN.is_file():
        pytest.skip("no derived/towns/rift_dig_camp_plan.json: run python tools/town_plan.py rift_dig_camp")
    assert RM.main(["build", "--source-root", root]) == 0
    tmp = tmp_path_factory.mktemp("mines")
    out = tmp / "cobblers_rift_mines"
    shutil.copytree(RM.OUT, out)
    refill = tmp / "cobblers_rift_mines_refill"
    shutil.copytree(RM.REFILL, refill)
    m, _near = RM.model(root)
    g = RA.GR.Ground(root)
    gated, ungated, eff, cutcols = RA.plan(SPEC, g)
    return out, refill / "data" / "cobblers" / "function" / "rift_mines_refill", m, (gated, ungated, eff, cutcols, g)


def fn_dir(pack):
    return pack / "data" / "cobblers" / "function" / "rift_mines"


def writes(fdir):
    """[(x, y, z, block)] of every block write, in the index order the re-apply runs them."""
    names = [n for n in (fdir / "index.txt").read_text(encoding="utf-8").split("\n") if n.strip()]
    assert names
    out = []
    for n in names:
        for ln in (fdir / (n + ".mcfunction")).read_text(encoding="utf-8").splitlines():
            mm = CMD.match(ln.strip())
            if not mm:
                continue
            a = [int(v) for v in mm.groups()[1:4]]
            b = [int(v) for v in mm.groups()[4:7]] if mm.group(5) else a
            for x in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                for y in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
                    for z in range(min(a[2], b[2]), max(a[2], b[2]) + 1):
                        out.append((x, y, z, mm.group(8)))
    return out


def final_state(fdir):
    fin = {}
    for x, y, z, b in writes(fdir):
        fin[(x, y, z)] = b
    return fin


def model_cells(m, arr):
    import numpy as np
    xs, zs, ys = np.nonzero(arr)
    return {(int(x) + m.X0, int(y) + m.Y0, int(z) + m.Z0) for x, z, y in zip(xs, zs, ys)}


# Without it the two implementations of the data's geometry drift apart on the real ground and every check below is
# about the wrong cells; and a gated cell (a section nobody can now enter) creeps back.
def test_the_generator_and_the_audit_agree_on_every_envelope_cell_and_none_is_gated(built):
    _pack, _refill, m, (gated, ungated, *_rest) = built
    assert not gated and not m.gated.any()
    env = model_cells(m, m.env)
    assert len(env) > 1000 and env == ungated, (len(env ^ ungated), sorted(env ^ ungated)[:5])


# Without it the seam holds no crystal, a second one (the 39 others were retired with the galleries), or one a player
# cannot see from the grille; or the grille is missing from the pack, and the crystal is in the open.
def test_exactly_one_crystal_is_written_on_the_faces_front_and_the_grille_stands(built):
    pack, *_rest = built
    w = writes(fn_dir(pack))
    crystals = [(x, y, z, b) for x, y, z, b in w if b.split("[")[0] == CRYSTAL]
    assert len(crystals) == TEASE["face"]["crystals"] == 1, crystals
    (x, y, z, b), = crystals
    fb = TEASE["face"]["box"]
    front = TEASE["face"]["front"]
    assert (x, y, z) in box_cells(fb) and y == fb[1], (x, y, z)
    assert {"south": z == fb[5], "north": z == fb[2], "east": x == fb[3], "west": x == fb[0]}[front]
    assert "facing=%s" % front in b, b
    fin = final_state(fn_dir(pack))
    assert all(fin.get(c) == "minecraft:iron_bars" for c in W.GRILLE), sorted((c, fin.get(c)) for c in W.GRILLE)[:3]
    assert all(fin.get(c, "").startswith("mega_showdown:") for c in W.FACE), "the face box is not all meteorid"


# Without it the crystal can be walked to round the grille through a gap the build left (a hole in the seal to a
# natural cave or the quarries), or the flood reaches rock nobody wrote.
def test_the_crystal_is_sealed_behind_the_grille(built):
    pack, _refill, _m, (_gated, ungated, eff, _cut, g) = built
    fin = final_state(fn_dir(pack))
    grid = RA.Grid(SPEC)
    step = {"south": (0, 0, 1), "north": (0, 0, -1), "east": (1, 0, 0), "west": (-1, 0, 0)}[TEASE["face"]["front"]]
    front = sorted({(x + step[0], y + step[1], z + step[2]) for x, y, z in W.FACE} - W.FACE)
    start = next(c for c in front if fin.get(c) in AIRS)
    mouth = tuple(SPEC["mine"]["features"][0]["path"][0])

    def flood(blocked, opened=frozenset()):
        seen, stack, unknown, escaped = {start}, [start], [], []
        while stack:
            x, y, z = stack.pop()
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                q = (x + d[0], y + d[1], z + d[2])
                if q in seen or q in blocked:
                    continue
                if q in opened:
                    seen.add(q)
                    stack.append(q)
                    continue
                if not grid.has(*q):
                    escaped.append(q)
                    continue
                b = fin.get(q)
                if b is None:
                    if q[1] > eff.get((q[0], q[2]), g(q[0], q[2])):
                        escaped.append(q)             # open sky over the ground: the outside
                    else:
                        unknown.append(q)
                    continue
                if b in AIRS or b.split("[")[0] in FLUIDS:
                    seen.add(q)
                    stack.append(q)
                if len(seen) > 300000:
                    return seen, unknown, ["runaway"]
        return seen, unknown, escaped
    reach, unknown, escaped = flood(W.GRILLE)
    assert not escaped and not unknown, (escaped[:3], unknown[:3])
    assert mouth not in reach
    gz = TEASE["grille"]["z"]
    assert all(z < gz for _x, _y, z in reach), "the flood from the face passed the grille's plane"
    reach2, _u, escaped2 = flood(set(), opened=W.GRILLE)
    assert mouth in reach2 or escaped2, "with the grille open the face does not lead back to the adit"


# Without it the retired gate still acts: a knock that teleports a flag holder into rock, a zone check that turns back
# anyone near the seam, or the old ward fatiguing players at the collapse. The pack's only advancement is the tease ward.
def test_no_retired_gate_or_zone_advancement_is_left(built):
    pack, *_rest = built
    adv = pack / "data" / "cobblers" / "advancement" / "rift_mines"
    rewards = {p.stem: json.loads(p.read_text(encoding="utf-8"))["rewards"]["function"] for p in adv.glob("*.json")}
    assert rewards == {"tease_ward": "cobblers:rift_mines/tease/ward"}, rewards
    assert not (fn_dir(pack) / "gate").exists()


# Without it the mine decides what spawns in it (a spawn-condition block written anywhere, even one later overwritten),
# floods itself, lights itself with invisible light blocks, drops evolution stones from a meteorid ore, or summons
# something other than its carts.
def test_no_written_block_is_a_spawn_condition_a_fluid_light_or_meteorid_ore(built):
    pack, refill, *_rest = built
    for fdir in (fn_dir(pack), refill):
        used = {b.split("[")[0] for _x, _y, _z, b in writes(fdir)}
        assert not used & SPAWN, sorted(used & SPAWN)
        assert not used & FLUIDS and "minecraft:light" not in used
        assert not [b for b in used if b.startswith("mega_showdown:mega_meteorid_") and b.endswith("_ore")]
    text = "\n".join(p.read_text(encoding="utf-8") for p in fn_dir(pack).rglob("*.mcfunction"))
    summons = re.findall(r"summon (\S+)", text)
    assert summons and set(summons) == {"minecraft:minecart"}
    assert all('Tags:["cobblers_rift_mines"]' in l for l in text.splitlines() if l.startswith("summon"))


def _camp_cells():
    plan = json.loads(RA.CAMP_PLAN.read_text(encoding="utf-8"))
    cells = {}

    def rect(r, what):
        for x in range(r[0], r[2] + 1):
            for z in range(r[1], r[3] + 1):
                cells[(x, z)] = what
    for sid, st in plan["streets"].items():
        for z, _y, xa, xb in st["cells"]:
            for x in range(xa, xb + 1):
                cells[(x, z)] = "street %s" % sid
    rect(plan["plaza"]["rect"], "plaza")
    for a in plan["anchors"]:
        rect(a["rect"], "anchor %s" % a["id"])
    for lot in plan["lots"]:
        rect(lot["rect"], "lot %s" % lot["id"])
    return cells


# Without it the mine or the refill writes past the declared grid or onto the camp's streets, plaza, anchor lots and
# house lots, which R16 builds and the mine would overwrite.
def test_nothing_is_written_outside_the_grid_or_onto_the_camps_lots_and_roads(built):
    pack, refill, *_rest = built
    grid = RA.Grid(SPEC)
    camp = _camp_cells()
    assert len(camp) > 500
    for fdir in (fn_dir(pack), refill):
        w = writes(fdir)
        assert not [(x, y, z) for x, y, z, _b in w if not grid.has(x, y, z)]
        on = {camp[(x, z)] for x, _y, z, _b in w if (x, z) in camp}
        assert not on, sorted(on)[:5]


# Without it the staging refill leaves part of the retired galleries open (a void under the camp a player can fall or
# dig into) or fills more than they took (rock in the live drifts, the adit hall or the collapse). Rasterised here from
# the retired features by the data's geometry words, roughness ignored (the refill fills the whole envelope): exactly
# those cells, all rock of the data's palette, none in the live envelope or the collapse.
def test_the_refill_writes_rock_into_exactly_the_retired_envelope(built):
    _pack, refill, _m, (_gated, ungated, *_rest) = built
    env = retired_envelope(SPEC["retired_gated_section"]["features"])
    fin = final_state(refill)
    assert len(env) > 5000 and set(fin) == env, (len(fin), len(env), len(env - set(fin)), len(set(fin) - env))
    rock = set(SPEC["palette"]["rock_upper"]) | set(SPEC["palette"]["rock_lower"])
    assert {b.split("[")[0] for b in fin.values()} <= rock
    assert not env & ungated, sorted(env & ungated)[:3]
    assert not env & box_cells(SPEC["mine"]["collapse"]["box"])


# Without it the retired section is not what the spur build carved: a feature dropped from it (a gallery left open on
# staging) or changed on the way. The gated features of data/rift_mines.json at 5d18aa5 (the spur build, before the cut)
# are the retired features, minus only the flag each carried. Reads git history; skips where it is not available.
def test_the_retired_section_is_the_gated_section_the_spur_had():
    try:
        old = subprocess.run(["git", "show", "5d18aa5:data/rift_mines.json"], cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        pytest.skip("NOT_EXECUTED: the spur build's data (5d18aa5) is not in this checkout: %s" % e)
    before = [f for f in json.loads(old)["mine"]["features"] if f.get("gated")]
    after = SPEC["retired_gated_section"]["features"]
    assert [f["id"] for f in before] == [f["id"] for f in after]
    for a, b in zip(before, after):
        for k in ("kind", "path", "r", "height", "pocket", "at", "centre"):
            assert a.get(k) == b.get(k), (a["id"], k)
    assert retired_envelope(before) == retired_envelope(after)


# ------------------------------------------------------------------------------------------------ the audit, mutated

@pytest.fixture(scope="module")
def audit_plan(built):
    """What RA.audit computes before it replays the output, once."""
    _pack, _refill, _m, (gated, ungated, eff, cutcols, g) = built
    top = lambda x, z: eff.get((x, z), g(x, z))           # noqa: E731
    cols, _street = RA.plan_columns(SPEC, gated, ungated, cutcols)
    return gated, ungated, top, cols


def _audit_output(pack, audit_plan, monkeypatch):
    gated, ungated, top, cols = audit_plan
    monkeypatch.setattr(RA, "PACK", pack)
    monkeypatch.setattr(RA, "FN", fn_dir(pack))
    return RA.output_problems(SPEC, RA.Grid(SPEC), gated, ungated, top, cols, {})


def _copy(built, tmp_path):
    pack = tmp_path / "cobblers_rift_mines"
    shutil.copytree(built[0], pack)
    return pack


def _append(pack, *lines):
    fdir = fn_dir(pack)
    last = [n for n in (fdir / "index.txt").read_text(encoding="utf-8").split("\n") if n.strip()][-1]
    with open(fdir / (last + ".mcfunction"), "a", encoding="utf-8") as fh:
        # the marker keeps tools/function_limits.py from reporting the extra writes' chunks instead of what is tested
        fh.write("# chunks-loaded-by: test\n" + "\n".join(lines) + "\n")


def _mutations(audit_plan):
    gated, ungated, top, _cols = audit_plan
    grid = RA.Grid(SPEC)
    camp = _camp_cells()
    lot = next(c for c, w in camp.items() if w.startswith("lot "))
    in_env = sorted(ungated)[len(ungated) // 2]
    ring = sorted({(x - 1, y, z) for x, y, z in W.POCKET} - ungated - W.FACE)
    seal = ring[len(ring) // 2]
    spawn_block = sorted(b for b in SPAWN if b.startswith("minecraft:"))[0]
    gate_adv = json.dumps({"criteria": {"here": {"trigger": "minecraft:location"}},
                           "rewards": {"function": "cobblers:rift_mines/gate/zone"}})

    def stale_zone(p):
        d = p / "data" / "cobblers" / "advancement" / "rift_mines"
        (d / "zone.json").write_text(gate_adv, encoding="utf-8")
    return {
        "one seal cell opened": (lambda p: _append(p, "setblock %d %d %d minecraft:air" % seal), "sealed"),
        "a write outside the grid": (lambda p: _append(p, "setblock %d 70 %d minecraft:stone" % (grid.x1 + 5, grid.z0)),
                                     "inside"),
        "a block on a camp lot": (lambda p: _append(p, "setblock %d %d %d minecraft:stone" % (lot[0], top(*lot) + 1, lot[1])),
                                  "inside"),
        "a spawn-condition block": (lambda p: _append(p, "setblock %d %d %d %s" % (in_env + (spawn_block,))), "blocks"),
        "water": (lambda p: _append(p, "setblock %d %d %d minecraft:water" % in_env), "blocks"),
        "a meteorid ore": (lambda p: _append(p, "setblock %d %d %d mega_showdown:mega_meteorid_fire_ore" % seal), "blocks"),
        "a second crystal": (lambda p: _append(p, "setblock %d %d %d %s[facing=north]" % (in_env + (CRYSTAL,))), "crystal"),
        "a retired zone advancement": (stale_zone, "crystal"),
    }


MUTATIONS = ["one seal cell opened", "a write outside the grid", "a block on a camp lot", "a spawn-condition block",
             "water", "a meteorid ore", "a second crystal", "a retired zone advancement"]


# Without it the audit passes the pack unchanged only because it checks nothing: the unmodified copy is clean.
def test_the_audit_is_clean_on_the_pack_as_built(built, audit_plan, tmp_path, monkeypatch):
    assert _audit_output(_copy(built, tmp_path), audit_plan, monkeypatch) == []


# Without it the audit's output checks could be blind to the failure each exists for.
@pytest.mark.parametrize("what", MUTATIONS)
def test_the_audit_catches_a_broken_pack(built, audit_plan, tmp_path, monkeypatch, what):
    mutate, prefix = _mutations(audit_plan)[what]
    pack = _copy(built, tmp_path)
    mutate(pack)
    probs = _audit_output(pack, audit_plan, monkeypatch)
    assert any(p.startswith(prefix) for p in probs), (what, probs)


# Without it a pack that never builds the grille passes the audit: its docstring says "the grille's cells are envelope
# and close drift C whole", but that is checked on the data (plan_problems), and the replayed output is never asked
# whether iron bars stand there; the grille cells are envelope, so air there is not a "stray" either. Found by this
# suite on the cut-back audit (72f8ddb). The test above (exactly_one_crystal...) checks the generator's output
# directly; this marks the audit's blind spot.
@pytest.mark.xfail(strict=True, reason="tools/rift_mines_audit.py output_problems never checks that the grille's iron "
                                       "bars are written: a pack with the grille set to air audits clean")
def test_the_audit_catches_a_pack_without_its_grille(built, audit_plan, tmp_path, monkeypatch):
    pack = _copy(built, tmp_path)
    _append(pack, *["setblock %d %d %d minecraft:air" % c for c in sorted(W.GRILLE)])
    assert _audit_output(pack, audit_plan, monkeypatch) != []
