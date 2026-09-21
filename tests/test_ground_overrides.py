"""A settlement that does not stand on the heightmap (the Displaced City's cavern floor, Relic Island's islet) gets
its own measured ground inside its box and the heightmap everywhere else: tools/ground.py for_settlement."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import ground as G  # noqa: E402


def fake_ground(h=100.0, n=64):
    g = G.Ground.__new__(G.Ground)
    g.heights = np.full((n, n), h)
    g.world = {"grid": {"origin_x": 0, "origin_z": 0}}
    g.ox = g.oz = 0
    g.kind = "heightmap"
    g.ceiling = None
    return g


def doc(kind):
    return {"settlements": {"town": {"ground": kind} if kind else {}}}


def test_heightmap_settlement_is_untouched():
    g = fake_ground()
    out = G.for_settlement("town", placements=doc(None), base=g)
    assert out.kind == "heightmap" and out(5, 5) == 100


def test_cavern_floor_replaces_only_its_box(monkeypatch):
    floor = np.full((10, 10), 30)
    ceiling = np.full((10, 10), 80)
    monkeypatch.setattr(G, "cavern_floor", lambda: ((20, 20, 29, 29), floor, ceiling))
    g = G.for_settlement("town", placements=doc("cavern_floor"), base=fake_ground())
    assert g.kind == "cavern_floor"
    assert g(25, 25) == 30 and g(19, 25) == 100 and g(30, 30) == 100
    assert g.ceiling["box"] == (20, 20, 29, 29) and g.ceiling["grid"][0, 0] == 80


def test_islet_replaces_only_island_columns(monkeypatch):
    top = np.full((5, 5), np.nan)
    top[2, 2] = 68.0
    monkeypatch.setattr(G, "islet_top", lambda g: ((10, 10, 14, 14), top))
    g = G.for_settlement("town", placements=doc("islet"), base=fake_ground(h=35.0))
    assert g(12, 12) == 68 and g(11, 12) == 35


def test_unknown_ground_is_refused():
    with pytest.raises(SystemExit):
        G.for_settlement("town", placements=doc("floating"), base=fake_ground())
