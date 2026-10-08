"""rift_skin.py and rift_deep.py without --source-root (OVERNIGHT_REVIEW N16): they resolve the root through
terrain.env_source_root() and, with none anywhere, stop with a usage error instead of crashing on Path(None)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import terrain  # noqa: E402


@pytest.mark.parametrize("name", ["rift_skin", "rift_deep"])
def test_no_source_root_anywhere_is_a_usage_error_not_a_crash(name, monkeypatch):
    mod = __import__(name)
    monkeypatch.setattr(terrain, "env_source_root", lambda: None)
    called = []
    monkeypatch.setattr(mod, "build", lambda *a, **k: called.append(a) or (_ for _ in ()).throw(AssertionError("built")))
    with pytest.raises(SystemExit) as e:
        mod.main(["build"])
    assert e.value.code == 2 and not called


@pytest.mark.parametrize("name", ["rift_skin", "rift_deep"])
def test_the_fallback_root_reaches_build(name, monkeypatch):
    mod = __import__(name)
    monkeypatch.setattr(terrain, "env_source_root", lambda: "X:/fallback")
    seen = []

    def fake_build(source_root, server_dir=None):
        seen.append(source_root)
        raise RuntimeError("stop here")

    monkeypatch.setattr(mod, "build", fake_build)
    with pytest.raises(RuntimeError):
        mod.main(["build"])
    assert seen == ["X:/fallback"]
