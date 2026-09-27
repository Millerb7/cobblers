"""Independent review of the Rift dig camp's mines: tools/rift_mines.py's pack and tools/rift_mines_audit.py.

Written by the test author, not by the session that built the mines (077bb55..f9fce1a), whose own tests are
tests/test_rift_mines.py. Those cross-check the two rasterisers, exercise the audit's plan checks on a mini mine and
take one seal block out of a built pack. This file adds, on a pack the generator builds into tmp_path:

  sealed     a flood from the arrival through every cell that ends as air, or is never written (unknown ground: the
             worst case), stays inside the gated envelope and never reaches the knock box, the turn-back point or the
             grid's edge; open the plug and it does reach the knock box
  zone       the zone advancement's boxes hold every gated cell (by the generator's model and by the audit's plan,
             which must agree) and no ungated, knock, turn-back or above-ground cell
  flag       the knock's teleport and the zone's turn-back are gated on cobblers:flag/gym5_cleared, the advancement
             tools/progression_pack.py writes for the fifth leader
  blocks     no block written (every write, not only the last) is a spawn condition (data/spawn_blocks.json), a
             fluid or minecraft:light; nothing is summoned but the tagged minecarts
  bounds     every write is inside data/rift_mines.json `grid`, and none lands on the camp's streets, plaza, anchors or
             lots (derived/towns/rift_dig_camp_plan.json) or on its street polylines (data/placements.json)
  audit      mutation checks: a copy of the pack with one plug cell opened, a write outside the grid, a block on a camp
             lot, a spawn-condition block, water, a zone box over the knock, a zone box removed, or a stray air cell
             under the ground next to the gated section, each makes the audit report that problem

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT) and derived/towns/rift_dig_camp_plan.json (python
tools/town_plan.py rift_dig_camp); SKIPS without them, and a skip is not a pass.

Not covered, and it needs a running server: that the advancements fire, that the teleports land where they say, that
the carts summon on their rails, and whether a player can dig round the plug faster than the zone check turns them
back (the check runs on a location trigger).
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import rift_mines as RM  # noqa: E402
import rift_mines_audit as RA  # noqa: E402

SPEC = json.loads((ROOT / "data" / "rift_mines.json").read_text(encoding="utf-8"))
SPAWN = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
AIRS = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
FLUIDS = {"minecraft:water", "minecraft:lava", "minecraft:flowing_water", "minecraft:flowing_lava"}
FLAG = "cobblers:flag/gym5_cleared"
CMD = re.compile(r"^(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))? (\S+)")

pytestmark = pytest.mark.slow


def box_cells(b):
    return {(x, y, z) for x in range(b[0], b[3] + 1) for y in range(b[1], b[4] + 1) for z in range(b[2], b[5] + 1)}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """(pack dir, generator model, audit plan) for the committed data, the pack built into tmp_path."""
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("COBBLERS_SOURCE_ROOT is not set: the heightmap is outside the repo")
    if not RA.CAMP_PLAN.is_file():
        pytest.skip("no derived/towns/rift_dig_camp_plan.json: run python tools/town_plan.py rift_dig_camp")
    # the tool writes its own disposable build/ and derived/ paths (it prints them relative to the checkout); the tests
    # read a copy, so a later build cannot change what they see
    assert RM.main(["build", "--source-root", root]) == 0
    out = tmp_path_factory.mktemp("mines") / "cobblers_rift_mines"
    shutil.copytree(RM.OUT, out)
    m, _near = RM.model(root)
    g = RA.GR.Ground(root)
    gated, ungated, eff, cutcols = RA.plan(SPEC, g)
    return out, m, (gated, ungated, eff, cutcols, g)


def fn_dir(pack):
    return pack / "data" / "cobblers" / "function" / "rift_mines"


def writes(pack):
    """[(x, y, z, block)] of every block write, in the index order the re-apply runs them."""
    fdir = fn_dir(pack)
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


def final_state(pack):
    fin = {}
    for x, y, z, b in writes(pack):
        fin[(x, y, z)] = b.split("[")[0]
    return fin


def model_gated(m):
    import numpy as np
    xs, zs, ys = np.nonzero(m.gated)
    return {(int(x) + m.X0, int(y) + m.Y0, int(z) + m.Z0) for x, z, y in zip(xs, zs, ys)}


def gate_points():
    gt = SPEC["mine"]["gate"]
    arrive = (int(gt["arrive"][0] // 1), gt["arrive"][1], int(gt["arrive"][2] // 1))
    turn = (int(gt["turn_back"][0] // 1), gt["turn_back"][1], int(gt["turn_back"][2] // 1))
    return arrive, turn, box_cells(gt["knock"]), box_cells(gt["plug"])


# ------------------------------------------------------------------------------------------------ the generated pack

# Without it the two implementations of the data's geometry drift apart on the real ground, and the audit's gated
# section is not the generator's: every check below would be about the wrong cells.
def test_the_generator_and_the_audit_agree_on_every_gated_cell(built):
    _pack, m, (gated, *_rest) = built
    mg = model_gated(m)
    assert len(gated) > 1000 and mg == gated, (len(mg ^ gated), sorted(mg ^ gated)[:5])


# Without it the gated galleries leak: a hole in the seal (to a natural cave, a quarry, the camp), or a cell the build
# never wrote, lets a player without the badge walk in round the gate.
def test_the_gated_section_is_sealed_except_through_the_plug(built):
    pack, _m, (gated, ungated, *_rest) = built
    fin = final_state(pack)
    arrive, turn, knock, plug = gate_points()
    grid = RA.Grid(SPEC)

    def flood(extra_open, target=frozenset()):
        seen, stack, escaped = {arrive}, [arrive], []
        while stack:
            if seen & target:
                return seen, escaped                          # through the plug: the ungated side opens to the sky
            x, y, z = stack.pop(0) if target else stack.pop()
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                q = (x + d[0], y + d[1], z + d[2])
                if q in seen:
                    continue
                if not grid.has(*q):
                    escaped.append(q)
                    continue
                b = fin.get(q)
                if b is None or b in AIRS or b in FLUIDS or q in extra_open:
                    seen.add(q)
                    stack.append(q)
                    if len(seen) > 400000:
                        return seen, ["runaway"]
        return seen, escaped
    assert fin.get(arrive) in AIRS, "the arrival point must be open"
    reach, escaped = flood(set())
    assert not escaped, escaped[:3]
    outside = reach - gated
    assert not outside, (len(outside), sorted(outside)[:5])
    assert not reach & knock and turn not in reach
    assert not [c for c in reach if c not in fin], "the flood met a cell the build never wrote"
    # the plug is the one door: opened, it joins the gated section to the knock box
    reach2, _ = flood(plug, frozenset(knock))
    assert reach2 & knock, "even with the plug open, the knock box is not reached"


def zone_boxes(pack):
    adv = json.loads((pack / "data" / "cobblers" / "advancement" / "rift_mines" / "zone.json").read_text(encoding="utf-8"))
    conds = adv["criteria"]["here"]["conditions"]["player"]
    terms = conds[0]["terms"] if conds[0].get("condition") == "minecraft:any_of" else conds
    out = []
    for t in terms:
        p = t["predicate"]["location"]["position"]
        # feet in [min, max] as doubles: block cells min .. max - 1
        out.append((p["x"]["min"], p["y"]["min"], p["z"]["min"], p["x"]["max"] - 1, p["y"]["max"] - 1, p["z"]["max"] - 1))
    return out


# Without it a gated cell lies outside every zone box (a player who digs round the plug into it is never turned back),
# or a box reaches the ungated mine, the knock alcove, the turn-back point or the open air (a player without the badge
# is turned back where they are allowed to be, or teleported in a loop).
def test_the_zone_boxes_cover_every_gated_cell_and_nothing_else(built):
    pack, m, (gated, ungated, eff, _cutcols, g) = built
    boxes = zone_boxes(pack)
    assert boxes

    def inside(c):
        return any(b[0] <= c[0] <= b[3] and b[1] <= c[1] <= b[4] and b[2] <= c[2] <= b[5] for b in boxes)
    arrive, turn, knock, _plug = gate_points()
    missed = [c for c in gated | model_gated(m) if not inside(c)]
    assert not missed, (len(missed), sorted(missed)[:3])
    caught = [c for c in ungated | knock | {turn, (turn[0], turn[1] + 1, turn[2])} if inside(c)]
    assert not caught, (len(caught), sorted(caught)[:3])
    for b in boxes:
        low = min(eff.get((x, z), g(x, z)) for x in range(b[0], b[3] + 1) for z in range(b[2], b[5] + 1))
        assert b[4] < low, ("a zone box reaches the ground", b, low)


# Without it the gate lets through a player without the fifth badge, or turns back one who holds it; or the flag named
# is not the advancement the progression pack writes for the fifth leader.
def test_the_gate_is_the_gym5_flag_both_ways(built):
    pack, _m, _plan = built
    assert SPEC["flag"]["advancement"] == FLAG
    import progression_pack as PP
    import inspect
    assert '"data/%s/advancement/flag/%s.json" % (ns, flag["id"])' in inspect.getsource(PP)
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    assert any(f["id"] == "gym5_cleared" for f in prog["flags"])
    fdir = fn_dir(pack)
    knock = [l for l in (fdir / "gate" / "knock.mcfunction").read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
    tps = [l for l in knock if " tp @s " in l or l.startswith("tp ")]
    assert tps and all(l.startswith("execute if entity @s[advancements={%s=true}] run tp @s " % FLAG) for l in tps), tps
    zone = (fdir / "gate" / "zone.mcfunction").read_text(encoding="utf-8")
    assert "execute if entity @s[gamemode=!creative,gamemode=!spectator,advancements={%s=false}] run function " \
           "cobblers:rift_mines/gate/turn_back" % FLAG in zone
    adv = pack / "data" / "cobblers" / "advancement" / "rift_mines"
    rewards = {p.stem: json.loads(p.read_text(encoding="utf-8"))["rewards"]["function"] for p in adv.glob("*.json")}
    assert rewards == {"gate_knock": "cobblers:rift_mines/gate/knock", "gate_exit": "cobblers:rift_mines/gate/exit",
                       "zone": "cobblers:rift_mines/gate/zone"}, rewards
    # the arrival is behind the plug and the turn-back in front of it, by the data
    gt = SPEC["mine"]["gate"]
    assert gt["arrive"][0] > gt["plug"][3] and gt["turn_back"][0] < gt["plug"][0]


# Without it the mine decides what spawns in it (a spawn-condition block written anywhere, even one later overwritten
# for a tick), floods itself, or lights itself with invisible light blocks.
def test_no_written_block_is_a_spawn_condition_a_fluid_or_light(built):
    pack, _m, _plan = built
    used = {b.split("[")[0] for _x, _y, _z, b in writes(pack)}
    assert len(used) >= 20
    assert not used & SPAWN, sorted(used & SPAWN)
    assert not used & FLUIDS and "minecraft:light" not in used
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
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    for st in (doc["settlements"]["rift_dig_camp"].get("plan") or {}).get("streets") or []:
        half = int(st.get("width", 1)) // 2
        pts = st.get("polyline") or []
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            n = int(max(abs(bx - ax), abs(bz - az))) + 1
            for i in range(n + 1):
                cx, cz = round(ax + (bx - ax) * i / n), round(az + (bz - az) * i / n)
                for dx in range(-half, half + 1):
                    for dz in range(-half, half + 1):
                        cells.setdefault((cx + dx, cz + dz), "street polyline %s" % st.get("id"))
    return cells


# Without it the mine writes past its declared grid (into the Relic area, the haul road, another build) or onto the
# camp's own streets, plaza, anchor lots and house lots, which R16 builds and the mine would overwrite.
def test_nothing_is_written_outside_the_grid_or_onto_the_camps_lots_and_roads(built):
    pack, _m, _plan = built
    grid = RA.Grid(SPEC)
    w = writes(pack)
    outside = [(x, y, z) for x, y, z, _b in w if not grid.has(x, y, z)]
    assert not outside, outside[:3]
    camp = _camp_cells()
    assert len(camp) > 500
    on = {}
    for x, _y, z, _b in w:
        if (x, z) in camp:
            on.setdefault(camp[(x, z)], (x, z))
    assert not on, sorted(on.items())[:5]


# ------------------------------------------------------------------------------------------------ the audit, mutated

@pytest.fixture(scope="module")
def audit_plan(built):
    """What RA.audit computes before it replays the output, once."""
    pack, _m, (gated, ungated, eff, cutcols, g) = built
    top = lambda x, z: eff.get((x, z), g(x, z))           # noqa: E731
    cols, _street = RA.plan_columns(SPEC, gated, ungated, cutcols)
    probs, _notes, (knock, plug, turn) = RA.plan_problems(SPEC, gated, ungated, top)
    assert probs == []
    return gated, ungated, top, cols, knock, plug, turn


def _audit_output(pack, audit_plan, monkeypatch):
    gated, ungated, top, cols, knock, plug, turn = audit_plan
    monkeypatch.setattr(RA, "PACK", pack)
    monkeypatch.setattr(RA, "FN", fn_dir(pack))
    return RA.output_problems(SPEC, RA.Grid(SPEC), gated, ungated, top, cols, knock, plug, turn, {})


def _copy(built, tmp_path):
    pack = tmp_path / "cobblers_rift_mines"
    shutil.copytree(built[0], pack)
    return pack


def _append(pack, *lines):
    fdir = fn_dir(pack)
    last = [n for n in (fdir / "index.txt").read_text(encoding="utf-8").split("\n") if n.strip()][-1]
    with open(fdir / (last + ".mcfunction"), "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _zone_edit(pack, edit):
    p = pack / "data" / "cobblers" / "advancement" / "rift_mines" / "zone.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    edit(doc["criteria"]["here"]["conditions"]["player"][0]["terms"])
    p.write_text(json.dumps(doc), encoding="utf-8")


def _box_term(b):
    return {"condition": "minecraft:entity_properties", "entity": "this", "predicate": {"location": {
        "dimension": "minecraft:overworld", "position": {"x": {"min": b[0], "max": b[3] + 1},
                                                         "y": {"min": b[1], "max": b[4] + 1},
                                                         "z": {"min": b[2], "max": b[5] + 1}}}}}


def _mutations(built, audit_plan):
    gated, ungated, top, cols, knock, plug, _turn = audit_plan
    grid = RA.Grid(SPEC)
    plug_cell = sorted(plug)[len(plug) // 2]
    camp = _camp_cells()
    lot = next(c for c, w in camp.items() if w.startswith("lot "))
    in_env = sorted(gated)[0]
    stray = next((x, y, z) for x, y, z in sorted(gated)
                 for (x2, y2, z2) in [(x, y - 3, z)] if (x2, y2, z2) not in gated | ungated and y2 <= top(x2, z2))
    stray = (stray[0], stray[1] - 3, stray[2])
    spawn_block = sorted(b for b in SPAWN if b.startswith("minecraft:"))[0]
    return {
        "one plug cell opened": (lambda p: _append(p, "setblock %d %d %d minecraft:air" % plug_cell), "sealed"),
        "a write outside the grid": (lambda p: _append(p, "setblock %d 70 %d minecraft:stone" % (grid.x1 + 5, grid.z0)),
                                     "inside"),
        "a block on a camp lot": (lambda p: _append(p, "setblock %d %d %d minecraft:stone" % (lot[0], top(*lot) + 1, lot[1])),
                                  "inside"),
        "a spawn-condition block": (lambda p: _append(p, "setblock %d %d %d %s" % (in_env + (spawn_block,))), "blocks"),
        "water": (lambda p: _append(p, "setblock %d %d %d minecraft:water" % in_env), "blocks"),
        "a zone box over the knock": (lambda p: _zone_edit(p, lambda t: t.append(_box_term(SPEC["mine"]["gate"]["knock"]))),
                                      "zone"),
        "a zone box removed": (lambda p: _zone_edit(p, lambda t: t.pop(0)), "zone"),
        "a stray air cell under the ground": (lambda p: _append(p, "setblock %d %d %d minecraft:air" % stray), "no stray"),
    }


MUTATIONS = ["one plug cell opened", "a write outside the grid", "a block on a camp lot", "a spawn-condition block",
             "water", "a zone box over the knock", "a zone box removed", "a stray air cell under the ground"]


# Without it the audit passes the pack unchanged only because it checks nothing: the unmodified copy is clean.
def test_the_audit_is_clean_on_the_pack_as_built(built, audit_plan, tmp_path, monkeypatch):
    assert _audit_output(_copy(built, tmp_path), audit_plan, monkeypatch) == []


# Without it the audit's output checks could be blind to the failure each exists for.
@pytest.mark.parametrize("what", MUTATIONS)
def test_the_audit_catches_a_broken_pack(built, audit_plan, tmp_path, monkeypatch, what):
    mutate, prefix = _mutations(built, audit_plan)[what]
    pack = _copy(built, tmp_path)
    mutate(pack)
    probs = _audit_output(pack, audit_plan, monkeypatch)
    assert any(p.startswith(prefix) for p in probs), (what, probs)
