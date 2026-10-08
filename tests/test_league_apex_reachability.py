"""The League out of z4, checked by a second reader (audit of fdbe1e5, CRITICAL_PATH_WALK_2 item 4, review N132).

The League stood in z4, the apex zone gated on 120 species, for fifteen days with nothing saying so. fdbe1e5 moved
the behind_league cut to z2360, carried its wall to the rim, and added `report` check 8c. This file checks the same
three properties WITHOUT the builder's derivation:

  - the League's positions: the footprint from data/placements.json under this file's own copy of vanilla
    StructureTemplate's rotation about the origin corner, the settlement plan's points, the NPC seats, and the five
    trainer spawners swept out of kanto_league.nbt by this file's own NBT reader (not tools/nbt.py, not
    rift_zones.template_spawners, not rift_zones.placed_cell);
  - reachability: a flood fill over tools/ground.py (the canonical heightmap, rounded; never a world) plus the
    blocks the EMITTED wall and gatehouse functions set, parsed here (fill/setblock), with this file's own step
    rules: four-connected, rise at most UP, drop at most DOWN, two blocks of headroom. Not
    rift_zones.simulate_function, not the cut's `line` from the data, not tests/test_rift_zones_apply.walker;
  - the generator mutations: tools/rift_zones.py's SOURCE is changed (data/ untouched), traced and built into a
    scratch copy, and the checks here must fail on that output.

Measured 2026-10-08 on the canonical heightmap: a walker in z4 (rise 2, any fall) reaches 3,804 columns and none
outside; nothing outside steps into them. From G5's arrival, z4's boxes forbidden, every League point is reached;
from G5's turn-back with z4's and z5's boxes forbidden, none. The league_gate wall has no column from x3675 to
x3712, where the ground is a walkable slope y99-108 that the floor_band rule calls scarp, and a walker from G5's
turn-back with no zone check reaches 81,711 of z5's 92,224 box columns: carried as a strict xfail below.

NOT COVERED (needs a running server, then an experiment in experiments/):
  - riders and potions. The seal holds for rise <= 2 (Jump Boost II); at rise 3 and a 4-block drop G4's own
    gatehouse roof is a way over, and at rise 4 the behind_league crest at (3653, 2359) stands 4 above the ground
    south of it (y99 against the crest y103). A Cobblemon 1.8 mount's jump height is not known here; a vanilla horse
    can clear 4. The zone check, not the wall, is what stops those, and nothing here runs it;
  - fliers, pearls, block placing and digging: no wall stops them; the full-height zone boxes are meant to. 2,622 of
    the 3,804 columns of z4's sealed pocket are in no z4 box (floor between rift.extent and the rim, and 8-grid
    raster edges), so a flier lands there unchecked. Empty today; it matters the day the postgame puts anything there;
  - the League building's own blocks (ignored: its footprint is treated as heightmap ground), the Victory Road caves
    (not on the heightmap), water, and whether any command here actually runs in game.
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import io
import json
import re
import shutil
import struct
import sys
import types
import zipfile
from collections import deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DONOR = "COBBLEVERSE-DP-v31.zip"
TEMPLATE_ENTRY = "data/cobbleverse/structure/kanto_league.nbt"
SPAWNER = "rctmod:trainer_spawner"
FRAME = (3150, 1950, 4150, 3100)                      # x0, z0, x1, z1: the apex, the precinct and the floor south
AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
CMD = re.compile(r"^(?:execute .* run )?(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))? "
                 r"([a-z0-9_:]+)")
SEAL_UP, SEAL_DOWN = 2, 200                            # Jump Boost II, and any fall at all
WALK_UP, WALK_DOWN = 1, 3                              # a player on foot who takes no damage


def spec_of(path=ROOT / "data" / "rift_zones.json"):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def data(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ the template, read here

def _tag(f, t):
    rd = f.read
    if t == 1:
        return struct.unpack(">b", rd(1))[0]
    if t == 2:
        return struct.unpack(">h", rd(2))[0]
    if t == 3:
        return struct.unpack(">i", rd(4))[0]
    if t == 4:
        return struct.unpack(">q", rd(8))[0]
    if t == 5:
        return struct.unpack(">f", rd(4))[0]
    if t == 6:
        return struct.unpack(">d", rd(8))[0]
    if t in (7, 11, 12):
        n = struct.unpack(">i", rd(4))[0]
        w = {7: 1, 11: 4, 12: 8}[t]
        raw = rd(n * w)
        return raw if t == 7 else list(struct.unpack(">%d%s" % (n, "i" if t == 11 else "q"), raw))
    if t == 8:
        return rd(struct.unpack(">H", rd(2))[0]).decode("utf-8", "replace")
    if t == 9:
        et = rd(1)[0]
        return [_tag(f, et) for _ in range(struct.unpack(">i", rd(4))[0])]
    if t == 10:
        out = {}
        while True:
            ct = rd(1)[0]
            if ct == 0:
                return out
            name = rd(struct.unpack(">H", rd(2))[0]).decode("utf-8", "replace")
            out[name] = _tag(f, ct)
    raise ValueError("NBT tag type %d" % t)


def read_nbt(raw):
    f = io.BytesIO(gzip.decompress(raw))
    t = f.read(1)[0]
    f.read(struct.unpack(">H", f.read(2))[0])
    return _tag(f, t)


def donor_zip():
    import glob
    hits = sorted(glob.glob("C:/Users/wnd/Documents/cobblers-local/server-snapshot-*/datapacks/" + DONOR), reverse=True)
    return Path(hits[0]) if hits else None


def swept_spawners(zp):
    """{(x, y, z) template cell: [trainer ids]} -- every block whose state is the spawner OR whose block entity is one."""
    with zipfile.ZipFile(zp) as zf:
        root = read_nbt(zf.read(TEMPLATE_ENTRY))
    pal = root["palette"] if "palette" in root else root["palettes"][0]
    return {tuple(b["pos"]): list((b.get("nbt") or {}).get("TrainerIds") or []) for b in root["blocks"]
            if pal[b["state"]]["Name"] == SPAWNER or (b.get("nbt") or {}).get("id") == SPAWNER}


def placed(rec, cell):
    """A template cell's world position for an unmirrored `place template`: vanilla StructureTemplate.transform about
    the origin corner (pivot 0): CLOCKWISE_90 (x, z) -> (-z, x), 180 -> (-x, -z), COUNTERCLOCKWISE_90 -> (z, -x)."""
    assert rec.get("mirror", "none") == "none" and rec.get("anchor_mode") == "corner", rec.get("id")
    x, y, z = cell
    rx, rz = {"none": (x, z), "clockwise_90": (-z, x), "180": (-x, -z),
              "counterclockwise_90": (z, -x)}[rec.get("rotation", "none")]
    p = rec["position"]
    return p["x"] + rx, p["y"] + y, p["z"] + rz


def league_record():
    recs = [q for q in data("placements.json")["placements"]
            if isinstance(q, dict) and q.get("pack_template") == "cobbleverse:kanto_league"]
    assert len(recs) == 1, [q.get("id") for q in recs]
    return recs[0]


def league_positions():
    """[(what, (x0, z0, x1, z1))] -- every place a player must stand at or pass to fight the Elite Four."""
    rec = league_record()
    sx, _sy, sz = rec["size"]
    a, b = placed(rec, (0, 0, 0)), placed(rec, (sx - 1, 0, sz - 1))
    out = [("footprint", (min(a[0], b[0]), min(a[2], b[2]), max(a[0], b[0]), max(a[2], b[2])))]
    plan = data("placements.json")["settlements"][rec["settlement"]]["plan"]
    for e in plan.get("entries") or []:
        out.append(("arrival from %s" % e["from"], tuple(e["at"][:2]) * 2))
    out.append(("waystone", tuple(plan["waystone"]["position"][:2]) * 2))
    for an in plan.get("anchors") or []:
        out.append((an["id"], tuple(an["rect"])))
    for s in data("npc_seats.json")["seats"]:
        if s.get("settlement") == rec["settlement"]:
            out.append((s["id"], (s["at"][0], s["at"][2]) * 2))
    zp = donor_zip()
    cells = swept_spawners(zp) if zp else {tuple(r["cell"]): r["trainers"] for r in spec_of()["league"]["spawners"]}
    for cell, ids in cells.items():
        x, _y, z = placed(rec, cell)
        out.append(("spawner %s" % "/".join(ids), (x, z, x, z)))
    return out


def zones_holding(spec, rect, but):
    return sorted({zid for zid, z in spec["zones"].items() if zid != but
                   and not str(z.get("status", "")).startswith("SUPERSEDED")
                   for b in z.get("boxes") or [] if b[0] <= rect[2] and rect[0] <= b[2] and b[1] <= rect[3]
                   and rect[1] <= b[3]})


def league_in_other_zones(spec):
    lz = spec["league"]["zone"]
    return [(w, r, zones_holding(spec, r, lz)) for w, r in league_positions() if zones_holding(spec, r, lz)]


# ------------------------------------------------------------------ the world, read here

def emitted(fn_dir):
    """{(x, z): {y: block}} from every wall_* and gatehouse_* function, walls first (a gatehouse cuts its wall)."""
    vox = {}
    names = sorted(fn_dir.glob("wall_*.mcfunction")) + sorted(fn_dir.glob("gatehouse_*.mcfunction"))
    assert names, "no wall or gatehouse function in %s" % fn_dir
    for p in names:
        for line in p.read_text(encoding="utf-8").splitlines():
            m = CMD.match(line.strip())
            if not m:
                continue
            a = [int(v) for v in m.group(2, 3, 4)]
            b = [int(v) for v in m.group(5, 6, 7)] if m.group(5) else a
            for x in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                for z in range(min(a[2], b[2]), max(a[2], b[2]) + 1):
                    col = vox.setdefault((x, z), {})
                    for y in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
                        col[y] = m.group(8)
    return vox


class World:
    def __init__(self, heights, vox):
        self.h, self.vox = heights, vox

    def g(self, x, z):
        return int(self.h[z - FRAME[1], x - FRAME[0]])

    def solid(self, x, z, y):
        c = self.vox.get((x, z))
        if c is not None and y in c:
            return c[y] not in AIR
        return y <= self.g(x, z)

    def feet(self, x, z):
        c, g = self.vox.get((x, z)), self.g(x, z)
        if c is None:
            return (g + 1,)
        return tuple(y for y in range(min(min(c), g) - 1, max(max(c), g) + 3)
                     if self.solid(x, z, y - 1) and not self.solid(x, z, y) and not self.solid(x, z, y + 1))

    def clear(self, x, z, y0, y1):
        if (x, z) not in self.vox:
            return y0 > self.g(x, z)
        return not any(self.solid(x, z, y) for y in range(y0, y1 + 1))

    def step(self, a, b, up, down):
        (x, z, y), (nx, nz, ny) = a, b
        if ny > y:
            return ny - y <= up and self.clear(x, z, y, ny + 1) and self.clear(nx, nz, ny, ny + 1)
        if ny < y:
            return y - ny <= down and self.clear(nx, nz, ny, y + 1)
        return self.clear(nx, nz, ny, ny + 1)

    def around(self, node):
        x, z, _y = node
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if FRAME[0] <= nx <= FRAME[2] and FRAME[1] <= nz <= FRAME[3]:
                for ny in self.feet(nx, nz):
                    yield (nx, nz, ny)

    def start(self, x, z):
        return (x, z, min(self.feet(x, z), key=lambda v: abs(v - self.g(x, z) - 1)))

    def flood(self, seeds, up, down, forbid=()):
        seen = {self.start(*s) for s in seeds}
        q = deque(seen)
        while q:
            cur = q.popleft()
            for n in self.around(cur):
                if n not in seen and not in_boxes(forbid, n[0], n[1]) and self.step(cur, n, up, down):
                    seen.add(n)
                    q.append(n)
        return seen


def in_boxes(boxes, x, z):
    return any(b[0] <= x <= b[2] and b[1] <= z <= b[3] for b in boxes)


def columns(nodes):
    return {(x, z) for x, z, _ in nodes}


@pytest.fixture(scope="module")
def heights():
    import ground as GD
    try:
        gr = GD.load()
    except Exception as e:  # noqa: BLE001 -- only the heightmap's absence is a skip
        if type(e).__name__ != "TerrainUnavailable":
            raise
        pytest.skip("the canonical heightmap is not readable here")
    return gr.box(*FRAME)


# ------------------------------------------------------------------ the generator, run into a scratch copy

MUTATIONS = {
    # the frontier of behind_league moved 200 blocks south, which is where the cut stood until fdbe1e5 (z2560)
    "split_200_south": ('        masks[less] = both & (idx < c["at"])\n        masks[ge] = both & (idx >= c["at"])',
                        '        masks[less] = both & (idx < c["at"] + 200)\n'
                        '        masks[ge] = both & (idx >= c["at"] + 200)'),
    # wall_to_rim keeps its rim ends but never fills the columns between the frontier and them
    "no_rim_fill": ("        for t in range(a + 1, b):\n            out.add(col(r, t))\n", ""),
}


def generator(tmp, mutation=None):
    """tools/rift_zones.py compiled with SPEC and PACKS pointed into `tmp` and, if named, one MUTATIONS edit."""
    src = (ROOT / "tools" / "rift_zones.py").read_text(encoding="utf-8")
    edits = [('SPEC = ROOT / "data" / "rift_zones.json"', 'SPEC = Path(r"%s")' % (tmp / "rift_zones.json")),
             ('PACKS = ROOT / "build" / "datapacks"', 'PACKS = Path(r"%s")' % (tmp / "packs"))]
    if mutation:
        edits.append(MUTATIONS[mutation])
    for old, new in edits:
        assert src.count(old) == 1, "the line to edit is not in tools/rift_zones.py exactly once: %r" % old
        src = src.replace(old, new)
    shutil.copy(ROOT / "data" / "rift_zones.json", tmp / "rift_zones.json")
    mod = types.ModuleType("rift_zones_%s" % (mutation or "scratch"))
    mod.__file__ = str(ROOT / "tools" / "rift_zones.py")
    exec(compile(src, mod.__file__, "exec"), mod.__dict__)
    return mod


def run_generator(tmp, mutation=None, trace=True, gate_on_report=True):
    """(spec written, function dir) after trace (if asked) and build. `gate_on_report=False` builds past `report`,
    because a mutation `report` already catches would otherwise emit nothing for the checks here to read."""
    mod = generator(tmp, mutation)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        if trace:
            mod.cmd_trace(argparse.Namespace(source_root=None))
        if not gate_on_report:
            mod.cmd_report = lambda a, quiet=False: 0
        mod.cmd_build(argparse.Namespace(source_root=None))
    return spec_of(tmp / "rift_zones.json"), tmp / "packs" / mod.PACK / "data" / mod.NS / "function" / mod.FOLDER


def z4_breaches(spec, world):
    """Where a z4 walker and the rest of the world meet without the barrier: (pocket, [what is wrong])."""
    z4 = spec["zones"]["z4"]
    pocket = world.flood([(int(z4["arrive"][0]), int(z4["arrive"][2]))], SEAL_UP, SEAL_DOWN)
    cols = columns(pocket)
    bad = []
    edge = [c for c in cols if c[0] in (FRAME[0], FRAME[2]) or c[1] in (FRAME[1], FRAME[3])]
    if edge:
        bad.append("the pocket runs off the frame at %s" % edge[:3])
    others = {zid for zid, z in spec["zones"].items() if zid != "z4" for c in cols if in_boxes(z.get("boxes") or [], *c)}
    if others:
        bad.append("from z4 a walker reaches the boxes of %s" % sorted(others))
    turned = (int(z4["turn_back"][0]), int(z4["turn_back"][2]))
    if turned in cols:
        bad.append("from z4 a walker reaches G4's own turn-back %s" % (turned,))
    # what can get INTO the pocket: every node with a path to it (the reverse flood). Rim tops beside it can (a fall
    # off the rim lands in z4). Every node of any path into the pocket is in this set, so if it stays inside the
    # frame and holds none of the outside places, nothing outside reaches z4 at all, however far round it goes.
    back, q = set(pocket), deque(pocket)
    while q:
        p = q.popleft()
        for n in world.around(p):
            if n not in back and world.step(n, p, SEAL_UP, SEAL_DOWN):
                back.add(n)
                q.append(n)
    feeders = columns(back) - cols
    edge = [c for c in feeders if c[0] in (FRAME[0], FRAME[2]) or c[1] in (FRAME[1], FRAME[3])]
    if edge:
        bad.append("what falls into z4 runs off the frame at %s" % edge[:3])
    places = {"%s %s" % (zid, k): world.start(int(spec["zones"][zid][k][0]), int(spec["zones"][zid][k][2]))
              for zid, k in (("z4", "turn_back"), ("z5", "arrive"), ("z5", "turn_back"))}
    hit = sorted(k for k, n in places.items() if n in back)
    if hit:
        bad.append("a walker at %s gets into z4's pocket (%d nodes lead in)" % (hit, len(back) - len(pocket)))
    return cols, bad


# ------------------------------------------------------------------ the tests

# Without it, data/rift_zones.json league.spawners (what `report` 8c falls back to without the zip) could drift from
# the template and the five fights would be checked at positions nobody stands at.
def test_the_league_spawner_record_is_the_templates_own_block_sweep():
    zp = donor_zip()
    if zp is None:
        pytest.skip("%s is local only (no-redistribution) and absent here" % DONOR)
    swept = swept_spawners(zp)
    assert len(swept) == 5 and all(len(v) == 1 for v in swept.values()), swept
    rec = league_record()
    recorded = {tuple(r["cell"]): (r["trainers"], tuple(r["at"])) for r in spec_of()["league"]["spawners"]}
    assert {c: t for c, (t, _a) in recorded.items()} == swept
    assert {c: a for c, (_t, a) in recorded.items()} == {c: placed(rec, c) for c in swept}
    upstream = {t["upstream_trainer_id"] for t in data("league_trainers.json")["trainers"] if t.get("upstream_trainer_id")}
    assert upstream == {t for ts in swept.values() for t in ts}


# Without it, the League, the Elite Four or the Champion could stand behind any gate but the crisis flag -- the 120
# species of z4 again -- and only `report`'s own 8c would say so.
def test_no_league_position_stands_in_any_zone_but_the_leagues_own():
    spec = spec_of()
    assert spec["zones"][spec["league"]["zone"]]["pass"]["kind"] == "flag"
    assert league_in_other_zones(spec) == []


# Without it, the behind_league wall could stop short of the rim, or G4 be walked round, and a player without 120
# species would step into z4 (or a z4 player out of it) with only the zone check between them.
@pytest.mark.slow
def test_a_walker_cannot_cross_between_z4_and_anywhere_else_but_through_the_barrier(heights, tmp_path):
    spec, fn = run_generator(tmp_path, trace=False)
    cols, bad = z4_breaches(spec, World(heights, emitted(fn)))
    assert bad == [], "\n".join(bad)
    assert sum(1 for c in cols if in_boxes(spec["zones"]["z4"]["boxes"], *c)) > 1000, "the pocket is not z4's floor"


# Without it, the League could be reachable only through z4, or open to a player who never resolved the crisis.
@pytest.mark.slow
def test_the_league_is_reached_with_z5s_pass_and_never_without_it(heights, tmp_path):
    spec, fn = run_generator(tmp_path, trace=False)
    w = World(heights, emitted(fn))
    z2, z4, z5 = (spec["zones"][k] for k in ("z2", "z4", "z5"))
    # a point of each position a player stands on: rects by their south-east corner's row midpoint (the forecourts and
    # the footprint face south, onto the apron the trunk climbs to); the spawners are inside the building, not here
    points = [(what, ((r[0] + r[2]) // 2, r[3])) for what, r in league_positions() if not what.startswith("spawner")]
    held = columns(w.flood([(int(z5["arrive"][0]), int(z5["arrive"][2]))], WALK_UP, WALK_DOWN, z4["boxes"]))
    assert [p for p in points if p[1] not in held] == []
    shut = columns(w.flood([(int(z5["turn_back"][0]), int(z5["turn_back"][2]))], WALK_UP, WALK_DOWN,
                           z4["boxes"] + z5["boxes"]))
    assert len(shut) > 100000 and any(in_boxes(z2["boxes"], *c) for c in shut), "the z2 side did not flood"
    assert [p for p in points if p[1] in shut] == []


# The league_gate wall ends where the floor_band rule calls the ground scarp (more than 15 over y84), and from x3675
# to x3712 that ground is a walkable slope, y99-108: a player with eight badges and no crisis flag walks round G5 and
# only z5's zone check turns them back. Strict, so a fix turns this into a failure that says to drop the mark.
@pytest.mark.slow
@pytest.mark.xfail(strict=True, reason="league_gate can be walked round at x3675-3712 (ground y99-108): measured "
                                       "2026-10-08, 81,711 of z5's 92,224 box columns reached from G5's turn-back")
def test_league_gate_cannot_be_walked_round_without_z5s_pass(heights, tmp_path):
    spec, fn = run_generator(tmp_path, trace=False)
    w = World(heights, emitted(fn))
    z5 = spec["zones"]["z5"]
    out = columns(w.flood([(int(z5["turn_back"][0]), int(z5["turn_back"][2]))], WALK_UP, WALK_DOWN))
    inside = sum(1 for c in out if in_boxes(z5["boxes"], *c))
    assert inside < 200, "%d of z5's box columns are walked to from G5's turn-back with no zone check" % inside


# Without it, the League check above could pass for a reason of its own. The GENERATOR's split moved 200 south
# (where the cut stood before fdbe1e5), data/ untouched: the footprint, the spawners and the forecourts must land in z4.
@pytest.mark.slow
def test_moving_the_generators_split_south_puts_the_league_back_in_z4(tmp_path):
    spec = spec_of()
    mod = generator(tmp_path, "split_200_south")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        mod.cmd_trace(argparse.Namespace(source_root=None))
    hit = league_in_other_zones(spec_of(tmp_path / "rift_zones.json"))
    assert league_in_other_zones(spec) == []
    names = {w for w, _r, zs in hit if "z4" in zs}
    assert "footprint" in names and sum(1 for n in names if n.startswith("spawner")) == 5, sorted(names)


# Without it, the seal check above could pass for a reason of its own. wall_to_rim's fill dropped from the GENERATOR
# (rim ends kept, the columns between them not walled; data/ untouched), built past `report` (whose 6b catches it):
# a walker must now get round the wall's ends.
@pytest.mark.slow
def test_dropping_the_rim_fill_from_the_generator_lets_a_walker_round_the_wall(heights, tmp_path):
    spec, fn = run_generator(tmp_path, "no_rim_fill", gate_on_report=False)
    cut = next(c for c in spec["cuts"] if c["id"] == "behind_league")
    assert cut["columns"] < 294, "the mutation no longer shortens the wall"
    _cols, bad = z4_breaches(spec, World(heights, emitted(fn)))
    assert bad, "a wall stopping short of the rim still sealed z4: the seal check does not bite"
