"""tools/articuno_tower.py: the summit tower's re-apply step and the staging cleanup of the shoulder copy.

Written by the same agent that wrote the tool (2026-10-02), disclosed: the repository prefers a different author
for a validator, and this one should be re-read by someone else. To keep it from sharing the tool's derivation:

  the boxes     come from data/adopted_legendary_sites.json corners and seats plus data/structures.json's
                footprint string, parsed here; the tool's own box() is never called.
  the ground    comes from tools/ground.py directly, per column, not through the tool's run grouping.
  the commands  are parsed back into per-column writes and compared with what each column must get.

Mutations are of the GENERATOR (monkeypatched module constants), never of the record: a record-side mutation
moves the expectation and the output together.

NOT COVERED: whether `place template` and the fills do what they say in a running server (the integrating
session's probes, from `python tools/articuno_tower.py plan`), and whether snow_block with a snow layer is the
export's real surface on that shoulder (ASSUMED; compare with the ring round the box in staging).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import articuno_tower as AT  # noqa: E402
import function_limits  # noqa: E402

SITE = next(s for s in json.loads((ROOT / "data" / "adopted_legendary_sites.json").read_text(encoding="utf-8"))["sites"]
            if s["id"] == "adopted_articuno_shrine")
FOOT = next(s for s in json.loads((ROOT / "data" / "structures.json").read_text(encoding="utf-8"))["structures"]
            if s["id"] == SITE["template"])["footprint"]
SX, SH, SZ = (int(v) for v in re.match(r"^(\d+)x(\d+)x(\d+)", FOOT).groups())
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)$")


def _box(placement):
    (x0, z0), y = placement["corner"], placement["y"]
    return x0, y, z0, x0 + SX - 1, y + SH - 1, z0 + SZ - 1


SUMMIT = _box(SITE["placement"])
SHOULDER = _box(SITE["superseded_shoulder_site"]["placement"])


@pytest.fixture(scope="module")
def ground():
    import ground as G
    from terrain import TerrainUnavailable
    try:
        return G.load()
    except TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is not available here (%s)" % (str(e) or type(e).__name__)[:80])


def writes(lines):
    """{(x, z): {y: block}} from the fill lines, applied in order."""
    out = {}
    for line in lines:
        m = FILL.match(line)
        if not m:
            continue
        x0, y0, z0, x1, y1, z1 = (int(v) for v in m.groups()[:6])
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for z in range(min(z0, z1), max(z0, z1) + 1):
                col = out.setdefault((x, z), {})
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    col[y] = m.group(7)
    return out


def cleanup_problems(lines, g):
    """[problem] where the cleanup does not put each shoulder column back to heightmap ground."""
    x0, seat, z0, x1, top, z1 = SHOULDER
    w = writes(lines)
    bad = []
    outside = [c for c in w if not (x0 <= c[0] <= x1 and z0 <= c[1] <= z1)]
    if outside:
        bad.append("%d columns written outside the shoulder box, first %s" % (len(outside), outside[:3]))
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            gy = g(x, z)
            col = w.get((x, z), {})
            for y in range(gy + 2, top + 1):
                if col.get(y) != "minecraft:air":
                    bad.append("(%d, %d): y%d is %s, not air, under the old top y%d" % (x, z, y, col.get(y), top))
                    break
            if col.get(gy + 1) not in ("minecraft:air", AT.COVER):
                bad.append("(%d, %d): y%d above ground is %s" % (x, z, gy + 1, col.get(gy + 1)))
            below = [y for y in col if y < gy]
            if below:
                bad.append("(%d, %d): writes under the ground block, at %s" % (x, z, below))
            if gy >= seat and col.get(gy) != AT.SURFACE:
                bad.append("(%d, %d): ground y%d was replaced by the paste and is not restored" % (x, z, gy))
            if gy < seat and gy in col:
                bad.append("(%d, %d): rewrites ground y%d, which the paste at y%d never touched" % (x, z, gy, seat))
    return bad


def test_the_superseded_site_is_kept_and_does_not_overlap_the_summit():
    # Without it the cleanup could be pointed at the live tower's box.
    assert SITE["superseded_shoulder_site"]["placement"]["corner"] == [904, 320]
    a, b = SUMMIT, SHOULDER
    assert a[3] < b[0] or b[3] < a[0] or a[5] < b[2] or b[5] < a[2]


def test_the_step_holds_the_footprint_then_pastes_the_records_command_then_releases():
    steps = AT.placement_steps()
    x0, _y, z0, x1, _t, z1 = SUMMIT
    kinds = [k for k, _v in steps]
    assert kinds == ["cmd", "wait", "cmd", "cmd", "cmd"]
    assert steps[0][1] == "forceload add %d %d %d %d" % (x0, z0, x1, z1)
    assert steps[2][1] == SITE["placement"]["command"].lstrip("/")
    assert steps[2][1] == "place template %s %d %d %d none none" % (SITE["template"], x0, SITE["placement"]["y"], z0)
    # after the paste, while the chunks are held: the template's base barrel loses its summoning feather (play test
    # 2026-10-05: a free legendary from the tower's chest). Template position (10, 1, 10), read from the server's
    # COBBLEVERSE-DP legendary/articuno.nbt on 2026-10-06
    assert steps[3][1] == ('data remove block %d %d %d storageWrapper.contents.inventory.Items[{id:"lumymon:glacier_feather"}]'
                           % (x0 + 10, SITE["placement"]["y"] + 1, z0 + 10))
    assert steps[4][1] == "forceload remove %d %d %d %d" % (x0, z0, x1, z1)


@pytest.mark.slow
def test_the_cleanup_puts_every_shoulder_column_back_to_heightmap_ground(ground):
    assert cleanup_problems(AT.cleanup_commands(ground), ground) == []


@pytest.mark.slow
def test_the_cleanup_is_a_function_the_server_will_run(ground):
    lines = AT.cleanup_commands(ground)
    assert function_limits.check_lines(lines, "articuno_cleanup/shoulder") == []
    assert lines[3].startswith("forceload add ") and lines[-1].startswith("forceload remove ")


@pytest.mark.slow
def test_a_generator_that_stops_a_block_short_of_the_old_top_is_caught(ground, monkeypatch):
    # Mutates the generator: the roof pad takes the clear one layer under the template's top.
    monkeypatch.setattr(AT, "ROOF_PAD", -1)
    assert any("not air" in p for p in cleanup_problems(AT.cleanup_commands(ground), ground))


@pytest.mark.slow
def test_a_generator_that_restores_the_wrong_surface_is_caught(ground, monkeypatch):
    # Mutates the generator's surface rule: restoring at ground - 1 instead of ground.
    real = AT.cleanup_commands

    def shifted(g, *a, **k):
        class Lower:
            def __call__(self, x, z):
                return g(x, z) - 1

            def box(self, *b):
                return g.box(*b) - 1
        return real(Lower(), *a, **k)
    assert cleanup_problems(shifted(ground), ground) != []


def test_the_cleanup_pack_never_lands_in_build_datapacks(tmp_path):
    # tools/reapply.py demands a step for every pack in build/datapacks; a staging-only cleanup must not be one.
    with pytest.raises(SystemExit):
        AT.write({"pack.mcmeta": {}}, ROOT / "build" / "datapacks" / "cobblers_articuno_cleanup")
