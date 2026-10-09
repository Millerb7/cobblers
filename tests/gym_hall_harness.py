"""Helpers shared by tests/test_gym_halls.py and tests/test_gym_trainers_audit.py (not a test module).

A hall test needs three things the audit alone does not give it:

  a pack of the GENERATOR'S output     built into a scratch folder, optionally with the generator broken on purpose
                                       (`mutate`), never with the authored data touched
  the generator's own checks silenced  in a mutant build only: tools/gym_arenas.py refuses to emit a hall that its own
                                       `check` rejects, so a mutant that broke a rule would never reach the audit. The
                                       audit (tools/gym_arenas_audit.py, which imports nothing from the generator) is
                                       what must then say so
  the replayed world                   tools/gym_arenas_audit.py `assemble`, the apply's own order, so a test reads cells
                                       the way the audit does and re-derives each property without the generator's model

Nothing here decides a verdict; each test file states its own property and its own mutation.
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import gym_arenas as GA  # noqa: E402
import gym_arenas_audit as A  # noqa: E402

EPS = A.EPS


def records():
    """[(path, record)] of every data/gym_arenas/gym*.json, read from the folder."""
    return GA.records()


def halls():
    return sorted(d["id"] for _p, d in records() if GA.is_hall(d))


def passage_gyms():
    return sorted(d["id"] for _p, d in records() if GA.passages(d))


def record(gym):
    return GA.record_of(gym)


def two(items):
    """The first and the last of a folder's gyms: a mutation test that cannot afford every hall still never names one."""
    return sorted({items[0], items[-1]}) if items else []


def snapshot_or_skip():
    if not (A.SNAPSHOT / "mods").exists():
        pytest.skip("no server snapshot with the jars at %s" % A.SNAPSHOT)


def ground_or_skip():
    try:
        import ground
        return ground.load()
    except (SystemExit, OSError) as e:
        pytest.skip("no canonical heightmap here: %s" % e)


class Ctx:
    """The heavy inputs, loaded once."""

    def __init__(self):
        snapshot_or_skip()
        self.G = ground_or_skip()
        self.arch = A.Archives()
        self.sizes = A.compare_sizes(self.arch, A.GYMS)


def build_pack(out, gyms=None, mutate=None, G=None):
    """The arena/hall pack for `gyms` (default all), built in-process. With `mutate` the generator is broken first
    (`mutate(mp)` gets a pytest MonkeyPatch and patches tools/gym_arenas.py or what it calls) and its own `check` is
    silenced so the broken output is written; without it the generator's real checks run."""
    G = G or ground_or_skip()
    recs = [(p, d) for p, d in GA.records() if gyms is None or d["id"] in gyms]
    with pytest.MonkeyPatch.context() as mp:
        if mutate is not None:
            mp.setattr(GA, "check", lambda *a, **k: ([], {}))
            mutate(mp)
        GA.build_pack(out, recs, G)
    return Path(out)


def build_demolish(out, mutate=None):
    """The R16F pack built in-process (the CLI ignores --out in an old checkout; tools/gym_demolish.py honours it now)."""
    import gym_demolish as GD
    out = Path(out)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(GD, "PACK", out)
        mp.setattr(GD, "FUNCS", out / "data" / "cobblers" / "function" / "gym_demolish")
        if mutate is not None:
            mutate(mp)
        r = GD.main(["build", "--out", str(out)])
    assert r == 0
    return out


def audit(gym, pack, ctx, demolish, steps=None):
    """tools/gym_arenas_audit.py audit_gym for one gym over `pack`; `steps` replaces reapply.gym_step_functions (the
    order the apply runs the gym's functions), the one input of the audit that is not a pack."""
    import reapply
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(A, "DEMOLISH_PACK", Path(demolish))
        if steps is not None:
            mp.setattr(reapply, "gym_step_functions", steps)
        return A.audit_gym(gym, pack, ctx.G, ctx.arch, ctx.sizes[gym]["size"], hosts=(None, None))


def assembled(gym, pack, ctx, demolish, steps=None):
    """(world, site, bounds, through, arena_writes, host_cells, logs) the apply leaves for one gym."""
    import reapply
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(A, "DEMOLISH_PACK", Path(demolish))
        if steps is not None:
            mp.setattr(reapply, "gym_step_functions", steps)
        return A.assemble(gym, pack, ctx.G, hosts=(None, None))


def problems(facts, *prefixes):
    return [p for p in facts.get("problems", []) if p.startswith(prefixes)]


# ------------------------------------------------------------------------------------------ a player in the replay
def region_box(gym, site, bounds, through):
    """The audit's own walking window for a gym (assemble's bounds, the host, the through boxes, exit passages)."""
    xb = A.exit_boxes(A.declared(gym)[2])
    region = [bounds, site["host_box"]] + list(through) + xb
    return (min(b[0] for b in region) - 2, min(b[1] for b in region) - 3, min(b[2] for b in region) - 2,
            max(b[3] for b in region) + 2, max(b[4] for b in region) + 3, max(b[5] for b in region) + 2)


def street_nodes(world, walker, lot):
    """The nodes a player starts on: every column of the ring just outside the gym lot (data/placements.json), settled
    on the world's own ground."""
    lx0, lz0, lx1, lz1, _lv = lot
    ring = [(x, lz0 - 1) for x in range(lx0 - 1, lx1 + 2)] + [(x, lz1 + 1) for x in range(lx0 - 1, lx1 + 2)] + \
        [(lx0 - 1, z) for z in range(lz0, lz1 + 1)] + [(lx1 + 1, z) for z in range(lz0, lz1 + 1)]
    out = []
    for x, z in ring:
        n = walker.settle(x, world.nature.natural_top(x, z)[0] + 1, z)
        if n:
            out.append(n)
    return out


def feet_cell(n):
    return (n[0], int(math.floor(n[2] + EPS)), n[1])


def eye(n):
    return (n[0] + 0.5, n[2] + 1.62, n[1] + 0.5)


def line_clear(world, a, b, skip=(), step=0.2):
    """No collision shape between points a and b except in the cells listed in `skip`."""
    d = math.dist(a, b)
    n = max(1, int(d / step))
    for i in range(1, n):
        f = i / float(n)
        c = tuple(int(math.floor(a[k] + (b[k] - a[k]) * f)) for k in range(3))
        if c in skip:
            continue
        if A.collides(world.get(*c)):
            return False
    return True


def pressable(world, n, button, reach=4.5):
    """A survival player standing at node n can press the button at cell `button`: its centre within `reach` of the eye
    and nothing with a collision shape between (the cell of the button itself excepted)."""
    target = (button[0] + 0.5, button[1] + 0.5, button[2] + 0.5)
    e = eye(n)
    return math.dist(e, target) <= reach and line_clear(world, e, target, skip={tuple(button)})


def inside(c, box):
    return A.inside(c, box)


def mirrored(button_state, pos):
    """(pos', state') of a wall button moved to the other side of the block it is set on (the cell on the far side of the
    wall block), facing the other way: the button a player on the OTHER side of that wall could press."""
    attach = {"north": (0, 0, 1), "south": (0, 0, -1), "east": (-1, 0, 0), "west": (1, 0, 0)}
    flip = {"north": "south", "south": "north", "east": "west", "west": "east"}
    facing = A.prop(button_state, "facing", "north")
    d = attach[facing]
    new = (pos[0] + 2 * d[0], pos[1] + 2 * d[1], pos[2] + 2 * d[2])
    return new, button_state.replace("facing=%s" % facing, "facing=%s" % flip[facing])
