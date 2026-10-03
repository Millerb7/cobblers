"""tools/water_shape.py's helpers that other tools build on after the water export was applied: the Rift's columns in
build_protect (rift_sculpt_mask) and the re-sited sea town (resited_plan, resited_town, to_town_endpoints).

Two faults found on 2026-10-02 by the builders of tools/lake_life.py and tools/sea_life.py, both of which had to work
round them:

1. build_protect's `rift_sculpt` part diffed the pre-Rift heightmap against whatever heightmap its Ctx held. On the
   canonical heightmap (the applied water export) it also caught every column the export changed near the Rift, and
   protected 85% of Arrow Lake, 49% of Shrew Lake and 97% of the Watering Hole. It now diffs the Rift's own input and
   output (data/world.json heightmap.rift_sculpted_from against data/water_shape.json applies_to), both sha-checked.
2. resited_town asked data/sea_town.json for a `resite` block that `sea_town.py fold-resite` has folded into the plan,
   and raised, so the gate line to the re-sited town (`pacifidlog_nearest_land`) could not be computed.

Independent sources: synthetic heightmaps written here (the Rift's change and a later stage's change at known
columns), the sculpt's own record of how many columns it changed (rift_sculpted_from.columns_changed), the deck cells
of the plan as tools/sea_town.py lays them out, and data/sea_town.json's authored site.

The real-heightmap tests need COBBLERS_SOURCE_ROOT and SKIP without it. A skip is not a pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import water_shape as WS  # noqa: E402
import sea_town as ST  # noqa: E402


# ---------------------------------------------------------------------------------------------- 1. the Rift's columns

N = 600
BOX = (250, 250, 350, 350)              # the Rift region's box; rbox is this grown by 200: (50, 50, 550, 550)


def _png(path, arr):
    Image.fromarray(arr.astype(np.uint16)).save(path)
    return WS.sha256_file(path)


@pytest.fixture()
def chain(tmp_path):
    """pre (the Rift's input) -> post (the Rift's output, 20x20 changed) -> later (post plus a 40x40 change of a later
    stage, inside rbox: what the water export did to the lakes near the Rift)."""
    pre = np.full((N, N), 30000, np.uint16)
    post = pre.copy()
    post[290:310, 290:310] -= 500
    later = post.copy()
    later[100:140, 400:440] -= 300
    hp = {name: tmp_path / ("%s.png" % name) for name in ("pre", "post", "later")}
    sha = {name: _png(hp[name], arr) for name, arr in (("pre", pre), ("post", post), ("later", later))}
    world = {"heightmap": {"path": "later.png", "sha256": sha["later"],
                           "rift_sculpted_from": {"path": "pre.png", "sha256": sha["pre"], "columns_changed": 400},
                           "water_shaped_from": {"path": "post.png", "sha256": sha["post"]}}}
    spec = {"applies_to": {"heightmap_path": "post.png", "heightmap_sha256": sha["post"]}}
    expect = np.zeros((N, N), bool)
    expect[290:310, 290:310] = True
    return SimpleNamespace(world=world, spec=spec, raw={"post": post, "later": later}, path=hp, expect=expect)


def _ctx(c, which):
    raw = c.raw[which]
    return WS.Ctx(c.world, c.spec, raw, raw, c.path[which])


def test_rift_mask_is_the_rifts_columns_on_a_later_heightmap(chain):
    """The fault: a Ctx on the later heightmap (today's canonical one) must not protect the later stage's columns."""
    rbox, m = WS.rift_sculpt_mask(_ctx(chain, "later"), BOX)
    assert rbox == (50, 50, 550, 550)
    want = WS.grow(chain.expect[WS.sl(rbox)], 8)
    assert np.array_equal(m, want)
    assert not m[100 - 50:140 - 50, 400 - 50:440 - 50].any(), "the later stage's columns are protected as the Rift's"


def test_rift_mask_does_not_depend_on_the_ctx_heightmap(chain):
    a = WS.rift_sculpt_mask(_ctx(chain, "later"), BOX)
    b = WS.rift_sculpt_mask(_ctx(chain, "post"), BOX)
    assert a[0] == b[0] and np.array_equal(a[1], b[1])


def test_rift_mask_refuses_a_file_that_does_not_hash(chain):
    chain.spec["applies_to"]["heightmap_sha256"] = "0" * 64
    chain.world["heightmap"]["water_shaped_from"]["sha256"] = "0" * 64
    with pytest.raises(WS.ShapeError, match="does not hash"):
        WS.rift_sculpt_mask(_ctx(chain, "later"), BOX)


def test_rift_mask_refuses_more_columns_than_the_sculpt_changed(chain):
    """If applies_to named the later file, the diff would hold the later stage too: the sculpt's own count refuses it."""
    chain.spec["applies_to"] = {"heightmap_path": "later.png", "heightmap_sha256": WS.sha256_file(chain.path["later"])}
    chain.world["heightmap"]["water_shaped_from"]["sha256"] = chain.spec["applies_to"]["heightmap_sha256"]
    with pytest.raises(WS.ShapeError, match="more than the 400"):
        WS.rift_sculpt_mask(_ctx(chain, "later"), BOX)


def test_rift_mask_refuses_when_applies_to_is_not_the_water_exports_input(chain):
    chain.world["heightmap"]["water_shaped_from"]["sha256"] = "f" * 64
    with pytest.raises(WS.ShapeError, match="ambiguous"):
        WS.rift_sculpt_mask(_ctx(chain, "later"), BOX)


@pytest.fixture(scope="module")
def canonical():
    import terrain as T
    wp = ROOT / "data" / "world.json"
    world = T.load_world(wp)
    try:
        hm = T.resolve_heightmap(world, wp, None)
    except (T.TerrainUnavailable, FileNotFoundError, OSError) as e:
        pytest.skip("NOT_EXECUTED: the canonical heightmap is unavailable (%s); set COBBLERS_SOURCE_ROOT" % e)
    spec = json.loads(WS.SPEC.read_text(encoding="utf-8"))
    return SimpleNamespace(world=world, spec=spec, hm=hm, raw=np.array(Image.open(hm)))


def test_real_rift_mask_on_the_canonical_heightmap(canonical):
    """On the canonical heightmap (the applied water export) the Rift's part holds no more columns than the sculpt
    recorded changing (512,952 at the time of writing, read from data/world.json), where the old diff against the
    canonical heightmap held the export's columns too."""
    c = canonical
    ctx = WS.Ctx(c.world, c.spec, c.raw, c.raw, c.hm)
    rs = c.spec["protect"]["rift"]
    box, _ = ctx.region_mask(rs["region"], int(rs["grow_blocks"]))
    rbox, m = WS.rift_sculpt_mask(ctx, box)
    cap = int(c.world["heightmap"]["rift_sculpted_from"]["columns_changed"])
    pre = c.hm.parent / c.world["heightmap"]["rift_sculpted_from"]["path"]
    raw_pre = np.array(Image.open(pre).crop(rbox))
    old = int((raw_pre != c.raw[WS.sl(rbox)]).sum())             # the old diff: pre-Rift against the canonical file
    post = c.hm.parent / c.spec["applies_to"]["heightmap_path"]
    new = int((raw_pre != np.array(Image.open(post).crop(rbox))).sum())
    assert 0 < new <= cap, (new, cap)
    assert old > cap, "the canonical heightmap no longer differs from the Rift's output near the Rift: re-read this test"
    assert np.array_equal(m, WS.grow(raw_pre != np.array(Image.open(post).crop(rbox)), 8))


# ------------------------------------------------------------------------------------------- 2. the re-sited sea town


def _decks(plan, skip_jetty):
    out = set()
    for e in ST.elements(plan):
        if e["decor"] or (skip_jetty and e["district"] == "mainland_jetty"):
            continue
        out |= ST.cells(e["rect"])
    return out


def test_resited_town_reads_the_folded_plan():
    """The fault: data/sea_town.json has no resite block any more; resited_town must not raise, and its decks are the
    folded plan's (its mainland jetty left out: that is the far shore of the gate line)."""
    plan = ST.load()
    assert not plan.get("resite"), "data/sea_town.json carries a resite block again: this test's premise is gone"
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    town = WS.resited_town(SimpleNamespace(world=world))
    assert town["deck"] and town["deck"] == _decks(plan, skip_jetty=True)
    # independent: the authored site's centre lies inside the decks' bounding box
    cx, cz = plan["site"]["centre"]
    xs = [p[0] for p in town["deck"]]
    zs = [p[1] for p in town["deck"]]
    assert min(xs) <= cx <= max(xs) and min(zs) <= cz <= max(zs), ((cx, cz), (min(xs), min(zs), max(xs), max(zs)))


def test_resited_plan_still_translates_an_unfolded_resite(tmp_path, monkeypatch):
    """Before the fold the plan is the resite block translated by tools/sea_town.py resited(), as it always was."""
    plan = ST.load()
    plan["resite"] = {"shift": [10, -20]}
    p = tmp_path / "sea_town.json"
    p.write_text(json.dumps(plan), encoding="utf-8")
    seen = []
    monkeypatch.setattr(ST, "resited", lambda pl: seen.append(pl) or {"translated": True})
    assert WS.resited_plan({"heightmap": {}}, p) == {"translated": True}
    assert seen and seen[0]["resite"] == {"shift": [10, -20]}


def test_resited_plan_refuses_a_plan_without_resite_before_the_export(tmp_path):
    """A plan with no resite block is the folded re-site only once the water export is applied, as fold-resite says."""
    with pytest.raises(WS.ShapeError, match="not the folded re-site"):
        WS.resited_plan({"heightmap": {}})


def test_real_gate_line_to_the_resited_town(canonical):
    """pacifidlog_nearest_land's endpoints, as tools/sea_life.py computes them (on the water export's input), are a dry
    column and a deck cell of the folded plan."""
    c = canonical
    wsd = c.world["heightmap"]["water_shaped_from"]
    pre = c.hm.parent / wsd["path"]
    if not pre.is_file() or WS.sha256_file(pre) != wsd["sha256"]:
        pytest.skip("NOT_EXECUTED: the water export's input %s is not under the source root" % pre)
    raw = np.array(Image.open(pre))
    G0 = WS.ground_of_raw(raw, c.world)
    ctx = WS.Ctx(c.world, c.spec, raw, G0, pre)
    cr = next(x for x in c.spec["crossings"] if x["id"] == "pacifidlog_nearest_land")
    (lx, lz), (tx, tz) = WS.to_town_endpoints(ctx, cr, ctx.G0, "before")
    assert (tx, tz) in _decks(ST.load(), skip_jetty=True)
    assert G0[lz, lx] >= WS.SEA
