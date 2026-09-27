"""Independent review of the Windward Deep's city (tools/deep_city.py, tools/deep_city_audit.py) and the refactor of
tools/rift_deep.py it stands on.

Written by the test author, not by the session that built the city (bfd051c..cbdfd0e), whose own tests are
tests/test_deep_city.py. Those show the audit is blind to nothing on a synthetic pit and is clean on the real build.
This file adds, on packs the tools build into tmp_path:

  refactor   the Deep's pack (cobblers_deep) is byte-identical when built by tools/rift_deep.py as it stood at 1b9bbc1
             and as it stands now (model() and lift_sites() split out of build())
  sealed     nothing the city writes or places enters the reserved volumes, derived here from data/rift_regions.json
             sited (the cradle's chamber and 24-block shell, a tube round the passage's own line, the HQ's basement and
             the shaft up to ring 0's tread), nor data/deep_city.json's own reserved boxes, nor the audit's
  mouth      nothing in Victory Road's mouth strip (tools/vr_caves.py's own: 9 either side of the mouth, 75 back) at the
             tunnel's height, and nothing but air in the walk-out lane in front of the mouth
  lifts      every lift block the Deep writes is still a lift after the city (the audit's lift check allows air on
             one; its street check is what refuses that, held below), its rider's space is open, and both ends land on
             a floor with open space above it: the up-lift on a
             block the city built at the upper street's height, the down-lift on rock or a built floor at the lower
             street's height (the audit checks the rider's space there, not the floor)
  blocks     no minecraft:light, no fluid and no waterlogged block anywhere the city writes, the templates it places
             included; no spawn condition in its fills and setblocks, and in the templates only blocks
             data/spawn_block_policy.json whitelists (the audit and tests/test_deep_city.py read the commands only)

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT); SKIPS without it, and a skip is not a pass. The refactor test also
needs git history back to 1b9bbc1.

Not covered, and it needs a running server and a player: that a lumymon lift moves a player by its yOffset as read
from its bytecode, that the templates place, how the city looks and lights.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import deep_city as DC  # noqa: E402
import deep_city_audit as DA  # noqa: E402
import rift_deep as RD  # noqa: E402

REGIONS = json.loads((ROOT / "data" / "rift_regions.json").read_text(encoding="utf-8"))
CITY = json.loads((ROOT / "data" / "deep_city.json").read_text(encoding="utf-8"))
VR = json.loads((ROOT / "data" / "vr_caves.json").read_text(encoding="utf-8"))
DEEP = json.loads((ROOT / "data" / "rift_deep.json").read_text(encoding="utf-8"))
SPAWN = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
POLICY = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
WHITELISTED = {b for w in POLICY.get("whitelist") or [] for b in w.get("blocks") or []}
LIFT = DEEP["lifts"]["block"]
AIRS = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
FLUIDS = {"minecraft:water", "minecraft:lava", "minecraft:flowing_water", "minecraft:flowing_lava",
          "minecraft:bubble_column"}
PASSABLE_END = ("ladder", "_wall_sign", "_sign")
NOT_A_FLOOR = ("_pane", "iron_bars", "ladder", "_sign", "torch", "lantern", "chain", "end_rod", "_door", "_button",
               "rail", "minecraft:light")

pytestmark = pytest.mark.slow


def tree(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(folder).rglob("*") if p.is_file()}


@pytest.fixture(scope="module")
def root():
    r = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not r or not Path(r).is_dir():
        pytest.skip("no COBBLERS_SOURCE_ROOT: the Deep and its city come from the heightmap")
    return r


@pytest.fixture(scope="module")
def deep_pack(root, tmp_path_factory):
    out = tmp_path_factory.mktemp("deep") / "cobblers_deep"
    mp = pytest.MonkeyPatch()
    mp.setattr(RD, "OUT", out)
    try:
        plan, _spec = RD.build(root, None)
        RD.write(plan)
    finally:
        mp.undo()
    return out, plan


@pytest.fixture(scope="module")
def city_pack(root, tmp_path_factory):
    assert DC.main(["build", "--source-root", root]) == 0          # into its own disposable build/ path
    out = tmp_path_factory.mktemp("city") / "cobblers_deep_city"
    shutil.copytree(DC.OUT, out)
    return out


# ------------------------------------------------------------------------------------------------ the refactor

# Without it the refactor that split model() and lift_sites() out of build() could change the Deep a player already
# walks: one tread, one lift or one rock fill different, and the city stands on a pit that is not the one in the world.
def test_the_deeps_pack_is_byte_identical_before_and_after_the_refactor(root, deep_pack, tmp_path):
    got = subprocess.run(["git", "show", "1b9bbc1:tools/rift_deep.py"], cwd=ROOT, capture_output=True)
    if got.returncode != 0:
        pytest.skip("git history back to 1b9bbc1 is not available here")
    old = types.ModuleType("rift_deep_1b9bbc1")
    old.__file__ = str(ROOT / "tools" / "rift_deep_1b9bbc1.py")        # never written: ROOT resolves the same
    exec(compile(got.stdout.decode("utf-8"), old.__file__, "exec"), old.__dict__)
    assert not hasattr(old, "lift_sites"), "this is not the pre-refactor tool"
    old.OUT = tmp_path / "old" / "cobblers_deep"
    old_plan, _ = old.build(root, None)
    old.write(old_plan)
    new_out, new_plan = deep_pack
    assert old_plan["lines"] == new_plan["lines"]
    assert old_plan["checks"] == new_plan["checks"] and old_plan["counts"] == new_plan["counts"]
    a, b = tree(old.OUT), tree(new_out)
    assert len(a) > 50 and a == b, sorted(set(a) ^ set(b))[:5] or [k for k in a if a[k] != b[k]][:5]


# ------------------------------------------------------------------------------------------------ the city's writes

def city_writes(pack):
    fdir = pack / "data" / "cobblers" / "function" / "deep_city"
    lines = []
    for name in (fdir / "index.txt").read_text(encoding="utf-8").split():
        lines += (fdir / (name + ".mcfunction")).read_text(encoding="utf-8").splitlines()
    templates = {}
    import structure_nbt
    for f in (pack / "data").rglob("*.nbt"):
        rel = f.relative_to(pack / "data").parts
        templates["%s:%s" % (rel[0], "/".join(rel[2:])[:-4])] = tuple(int(v) for v in structure_nbt.load(f)["size"])
    assert templates, "the city places templates; none were found"
    return lines, templates


def overlaps(w, box):
    x0, y0, z0, x1, y1, z1 = w[:6]
    return not (x1 < box[0] or x0 > box[3] or y1 < box[1] or y0 > box[4] or z1 < box[2] or z0 > box[5])


def my_sealed(tread_at):
    """The reserved volumes from data/rift_regions.json sited alone (DEEP_CITY.md: a chamber of up to 16 and the
    Displaced City's 24-block rock shell round the cradle; the passage and the HQ's basement)."""
    s = REGIONS["sited"]
    (cx, cz), fy = s["hoopa_cradle"]["centre"], s["hoopa_cradle"]["floor_y"]
    ground_min = REGIONS["regions"]["relic_area_shrine"]["ground"]["min"]
    reach = 16 + 24
    boxes = {"cradle": (cx - reach, fy - 24, cz - reach, cx + reach, min(fy + 16 + 24, ground_min - 8), cz + reach)}
    a, b = s["cradle_passage"]["from"], s["cradle_passage"]["to"]
    n = int(max(abs(b[0] - a[0]), abs(b[2] - a[2])))
    for i in range(0, n + 1, 2):                       # a tube round the passage's own line, 3 wide each side, 6 high
        t = i / n
        x, y, z = (round(a[q] + (b[q] - a[q]) * t) for q in range(3))
        boxes["passage_%03d" % i] = (x - 3, y - 1, z - 3, x + 3, y + 6, z + 3)
    hx, hy, hz = s["haven_compact_hq"]["at"]
    boxes["hq_basement"] = (hx - 6, hy - 2, hz - 6, hx + 6, hy + 8, hz + 6)
    boxes["hq_shaft"] = (hx - 2, hy, hz - 2, hx + 2, tread_at(hx, hz) - 1, hz + 2)
    return boxes


# Without it the city builds into Hoopa's cradle, the passage to it or the HQ's basement and shaft, which the finale
# needs sealed until Codex sends the chamber (a room there, or a lit corridor, would give the finale away).
def test_nothing_is_written_into_the_sealed_volumes(root, city_pack):
    lines, templates = city_writes(city_pack)
    writes = DA.parse(lines, templates)
    m = RD.model(root)
    X0, Z0 = m["box"][0], m["box"][1]

    def tread_at(x, z):
        return int(m["tread_y"][z - Z0, x - X0])
    boxes = dict(my_sealed(tread_at))
    boxes.update({"data:" + r["id"]: tuple(r["box"]) for r in CITY["reserved"]})
    M = DA.load_plan(root)
    boxes.update({"audit:" + k: v for k, v in M["sealed"].items()})
    assert len(boxes) > 30
    hits = [(name, w) for w in writes for name, box in boxes.items() if overlaps(w, box)]
    assert not hits, hits[:5]


# Without it the city stands in Victory Road's mouth (the only way in from below) or walls the lane a player walks out
# of it on.
def test_victory_roads_mouth_and_the_lane_before_it_stay_clear(city_pack):
    lines, templates = city_writes(city_pack)
    writes = DA.parse(lines, templates)
    mx, my, mz = VR["mouth"]["at"]
    assert VR["mouth"]["toward"] == "north"
    # tools/vr_caves.py's mouth_strip (9 either side, 75 back, 1 forward), from the tunnel's floor (the mouth's y) up
    # its height; the Deep's floor under it (y my - 1) is the city's plaza paving, laid flush, and stays allowed
    strip = (mx - 9, my, mz - 75, mx + 9, my + 8, mz + 1)
    lane = (mx - 4, my + 1, mz + 2, mx + 4, my + 4, mz + 24)            # the walk-out lane: floor left alone, air above
    in_strip = [w for w in writes if overlaps(w, strip)]
    assert not in_strip, in_strip[:5]
    flush = [w for w in writes if overlaps(w, (mx - 9, my - 1, mz - 75, mx + 9, my - 1, mz + 1))]
    assert all(w[1] == w[4] == my - 1 for w in flush), "only the flush paving touches the strip's floor"
    in_lane = [w for w in writes if overlaps(w, lane) and DA.base(w[6]) not in AIRS]
    assert not in_lane, in_lane[:5]


# ------------------------------------------------------------------------------------------------ the lifts

class World:
    """The last block the Deep's pack then the city's writes at a position (R9D runs before R9DC); unwritten cells are
    the heightmap's: rock at or under the ground, air over it."""

    def __init__(self, deep_lines, city_lines, templates, ground):
        rows = DA.parse(deep_lines) + DA.parse(city_lines, templates)
        self.box = np.array([r[:6] for r in rows], dtype=np.int64)
        self.block = [r[6] for r in rows]
        self.ground = ground

    def at(self, x, y, z):
        b = self.box
        hit = np.nonzero((b[:, 0] <= x) & (x <= b[:, 3]) & (b[:, 1] <= y) & (y <= b[:, 4]) & (b[:, 2] <= z) & (z <= b[:, 5]))[0]
        if len(hit):
            return self.block[hit[-1]]
        return "unwritten rock" if y <= self.ground(x, z) else "minecraft:air"


def passable(b):
    return b.startswith("template:") is False and (DA.base(b) in AIRS or DA.base(b).endswith(PASSABLE_END))


def floor(b):
    base = DA.base(b)
    return not (base in AIRS or base in FLUIDS or base.endswith(NOT_A_FLOOR))


def deep_lifts(deep_out):
    """[(x, y, z, yOffset)] from the Deep's own pack: every lift block and the yOffset merged into it."""
    text = "\n".join(p.read_text(encoding="utf-8") for p in (deep_out / "data").rglob("*.mcfunction"))
    blocks = {tuple(map(int, m.groups())) for m in re.finditer(r"setblock (-?\d+) (-?\d+) (-?\d+) %s\b" % re.escape(LIFT), text)}
    offs = {tuple(map(int, m.groups()[:3])): int(m.group(4)) for m in
            re.finditer(r"data merge block (-?\d+) (-?\d+) (-?\d+) \{yOffset:(-?\d+),", text)}
    assert blocks and set(offs) == blocks, (len(blocks), len(offs))
    return sorted((x, y, z, offs[(x, y, z)]) for x, y, z in blocks)


# Without it a lift is erased by the city (the audit lets the city write air over one), its rider is boxed in, or it
# sends its rider into mid-air over the lower street or into rock: the lifts are the only way between the rings.
def test_every_lift_survives_the_city_and_both_ends_have_a_floor(root, deep_pack, city_pack):
    import ground as G
    deep_out, _plan = deep_pack
    deep_lines = [l for p in sorted((deep_out / "data").rglob("*.mcfunction")) for l in p.read_text(encoding="utf-8").splitlines()]
    lines, templates = city_writes(city_pack)
    world = World(deep_lines, lines, templates, G.load(root))
    lifts = deep_lifts(deep_out)
    assert len(lifts) >= 8 and sum(1 for l in lifts if l[3] > 0) == sum(1 for l in lifts if l[3] < 0)
    bad = []
    for x, y, z, off in lifts:
        if DA.base(world.at(x, y, z)) != LIFT:
            bad.append(("the lift is gone", (x, y, z), world.at(x, y, z)))
        for dy in (1, 2):
            if not passable(world.at(x, y + dy, z)):
                bad.append(("rider boxed in", (x, y, z), dy, world.at(x, y + dy, z)))
        ty = y + off
        if not floor(world.at(x, ty, z)):
            bad.append(("lands on no floor", (x, y, z), off, world.at(x, ty, z)))
        for dy in (1, 2):
            if not passable(world.at(x, ty + dy, z)):
                bad.append(("lands in a block", (x, y, z), off, dy, world.at(x, ty + dy, z)))
    assert not bad, bad[:6]


# Without it the audit passes a city that erases a lift. Its lift check allows air on the lift block itself
# (tools/deep_city_audit.py lifts, dy 0), so what refuses it is the street check: an erased lift is not standing on
# open ground, or cannot be walked to. Held here for the first lift of a level (the street search's start) and for one
# that is not, lower and upper ends.
@pytest.mark.parametrize("which", [(0, 0), (0, 1), (-1, 0), (-1, 1)])
def test_the_audit_refuses_air_written_onto_a_lift(root, city_pack, which):
    lines, templates = city_writes(city_pack)
    M = DA.load_plan(root)
    p = M["lifts"][which[0]][which[1]]
    problems, _stats = DA.audit(DA.parse(lines + ["setblock %d %d %d minecraft:air" % tuple(p)], templates), M)
    assert any(k in ("lifts", "streets") and str(tuple(p)) in msg for k, msg in problems), (p, problems[:5])


# ------------------------------------------------------------------------------------------------ the blocks

def _palette_names(pack):
    import structure_nbt
    out = {}
    for f in (pack / "data").rglob("*.nbt"):
        t = structure_nbt.load(f)
        out[f.name] = t["palette"]
    return out


# Without it the city lights itself with invisible light blocks, floods a room, or brings a spawn condition into the
# Deep through a placed template, which neither the audit nor tests/test_deep_city.py reads.
def test_no_light_no_fluid_and_no_unwhitelisted_spawn_block_in_writes_or_templates(city_pack):
    lines, _templates = city_writes(city_pack)
    states = [m.group(1) for l in lines for m in [re.match(r"(?:fill(?: -?\d+){6}|setblock(?: -?\d+){3}) (\S+)", l)] if m]
    assert len(states) > 10000
    names = {DA.base(s) for s in states}
    assert "minecraft:light" not in names and not names & FLUIDS
    assert not [s for s in states if "waterlogged=true" in s], "a waterlogged block is water"
    assert not names & SPAWN, sorted(names & SPAWN)
    for name, pal in _palette_names(city_pack).items():
        pnames = {p[0] for p in pal}
        assert "minecraft:light" not in pnames and not pnames & FLUIDS, name
        assert not [p for p in pal if (p[1] or {}).get("waterlogged") == "true"], name
        unallowed = (pnames & SPAWN) - WHITELISTED
        assert not unallowed, (name, sorted(unallowed))
