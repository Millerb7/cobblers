"""tools/reapply.py takes the coordination lock before touching a server or a world.

Codex review, 2026-09-21: `install` checked only port 25565 and `run` set COBBLERS_SERVER_LOCK to a default path
itself when it was missing, so the driver could write into the server runtime without holding the lock. These
fixtures reproduce both and stay as tests.
"""
import ast
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import reapply  # noqa: E402
import runtime_guard as G  # noqa: E402


@pytest.fixture
def no_lock(monkeypatch, tmp_path):
    monkeypatch.delenv("COBBLERS_SERVER_LOCK", raising=False)
    monkeypatch.delenv("COBBLERS_LOCK_OWNER", raising=False)
    server = tmp_path / "cobblers-server"
    (server / "datapacks").mkdir(parents=True)
    world = tmp_path / "staging" / "w"
    (world / "region").mkdir(parents=True)
    touched = []
    # anything the driver would do to disk or the network counts as having got past the lock
    monkeypatch.setattr(shutil, "copytree", lambda *a, **k: touched.append(("copytree", a)))
    monkeypatch.setattr(shutil, "rmtree", lambda *a, **k: touched.append(("rmtree", a)))
    monkeypatch.setattr(reapply, "py", lambda *a, **k: touched.append(("py", a)) or "")
    monkeypatch.setattr(reapply, "Rcon", lambda *a, **k: touched.append(("rcon", a)))
    return server, world, touched


@pytest.mark.parametrize("argv", [
    ["prepare", "--source-root", "x", "--server-dir", "{server}"],
    ["install", "--server-dir", "{server}", "--world-dir", "{world}"],
    ["run", "--server-dir", "{server}"],
    ["audit", "--server-dir", "{server}", "--world", "{world}"],
])
def test_every_subcommand_refuses_without_the_lock_and_touches_nothing(no_lock, argv):
    server, world, touched = no_lock
    argv = [a.format(server=server, world=world) for a in argv]
    with pytest.raises(SystemExit):
        reapply.main(argv)
    assert touched == []


def test_a_lock_held_by_another_agent_does_not_let_install_through(no_lock, monkeypatch, tmp_path):
    server, world, touched = no_lock
    lock = tmp_path / "lock"
    lock.write_text("owner: Codex, another task\n", encoding="utf-8")
    monkeypatch.setenv("COBBLERS_SERVER_LOCK", str(lock))
    monkeypatch.setenv("COBBLERS_LOCK_OWNER", "Claude, this task")
    with pytest.raises(SystemExit):
        reapply.main(["install", "--server-dir", str(server), "--world-dir", str(world)])
    assert touched == []


def test_plan_needs_no_lock(no_lock, capsys):
    assert reapply.main(["plan"]) == 0


def _calls(tree, dotted):
    mod, fn = dotted.split(".")
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == fn and isinstance(n.func.value, ast.Name) and n.func.value.id == mod]


def test_main_calls_the_guard_before_dispatching():
    tree = ast.parse((ROOT / "tools" / "reapply.py").read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    guard = _calls(main, "runtime_guard.require_lock")
    assert guard, "reapply.main does not call runtime_guard.require_lock"
    dispatch = [n for n in ast.walk(main) if isinstance(n, ast.Return) and isinstance(n.value, ast.BoolOp)]
    assert dispatch and guard[0].lineno < dispatch[0].lineno


@pytest.mark.parametrize("tool", sorted(p.name for p in (ROOT / "tools").glob("*.py")))
def test_no_tool_names_the_lock_for_itself(tool):
    # The bypass: a tool that sets COBBLERS_SERVER_LOCK (or the owner) in its own environment when it is missing.
    tree = ast.parse((ROOT / "tools" / tool).read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        targets = n.targets if isinstance(n, ast.Assign) else [n.target] if isinstance(n, ast.AugAssign) else []
        for t in targets:
            if isinstance(t, ast.Subscript) and "environ" in ast.unparse(t.value):
                key = ast.unparse(t.slice)
                assert "LOCK" not in key.upper(), "%s:%d sets %s itself" % (tool, n.lineno, key)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("setdefault", "update") \
                and "environ" in ast.unparse(n.func.value):
            assert "LOCK" not in ast.unparse(n).upper(), "%s:%d sets the lock itself" % (tool, n.lineno)
