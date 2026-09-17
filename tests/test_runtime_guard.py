"""tools/runtime_guard.py: no tool reaches the live server runtime by default or without the lock.

Fixtures are synthetic directory trees in tmp_path named like the real layout. The last tests check that the tools
the repository audit flagged no longer carry a default path into the runtime.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import runtime_guard as G  # noqa: E402


@pytest.fixture
def layout(tmp_path, monkeypatch):
    monkeypatch.delenv(G.LOCK_ENV, raising=False)
    server = tmp_path / "cobblers-server"
    (server / "live-world" / "region").mkdir(parents=True)
    (server / "live-world" / "level.dat").write_bytes(b"x")
    (server / "datapacks").mkdir()
    (server / "mods").mkdir()
    snap = tmp_path / "cobblers-server-retired" / "2026-09-17-pre-grass" / "world"
    (snap / "region").mkdir(parents=True)
    (snap / "level.dat").write_bytes(b"x")
    lock = tmp_path / "lock"
    return server, snap, lock


def hold_lock(monkeypatch, lock):
    lock.write_text("owner: test", encoding="utf-8")
    monkeypatch.setenv(G.LOCK_ENV, str(lock))


def test_offline_snapshot_is_allowed(layout):
    _, snap, _ = layout
    assert G.check(snap) == snap.resolve()
    assert G.check(snap / "region" / "r.0.0.mca") == (snap / "region" / "r.0.0.mca").resolve()


def test_live_world_is_refused_even_with_the_lock(layout, monkeypatch):
    server, _, lock = layout
    hold_lock(monkeypatch, lock)
    for p in (server / "live-world", server / "live-world" / "region" / "r.0.0.mca", server / "live-world" / "datapacks"):
        with pytest.raises(G.RuntimeAccessRefused):
            G.check(p)


def test_runtime_directory_needs_the_lock(layout, monkeypatch):
    server, _, lock = layout
    with pytest.raises(G.RuntimeAccessRefused):
        G.check(server / "datapacks")
    lock.write_text("", encoding="utf-8")
    monkeypatch.setenv(G.LOCK_ENV, str(lock))
    with pytest.raises(G.RuntimeAccessRefused):
        G.check(server / "datapacks")                       # an empty lock file is not a held lock
    hold_lock(monkeypatch, lock)
    assert G.check(server / "datapacks") == (server / "datapacks").resolve()


def test_missing_path_is_refused():
    with pytest.raises(G.RuntimeAccessRefused):
        G.check(None)


@pytest.mark.parametrize("tool", sorted(p.name for p in (ROOT / "tools").glob("*.py")))
def test_no_tool_hard_codes_the_runtime(tool):
    src = (ROOT / "tools" / tool).read_text(encoding="utf-8")
    code = re.sub(r'""".*?"""', "", src, flags=re.S)       # usage examples in docstrings are not defaults
    assert not re.search(r"cobblers-server[\\/]+cobblers-10240", code), tool
    assert not re.search(r'default=[^,)]*cobblers-server', code), tool
    assert not re.search(r'["\'][A-Za-z]:[\\/]+[^"\']*cobblers-server(?![-\w])', code), tool
