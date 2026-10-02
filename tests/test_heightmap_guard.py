"""A run that skipped heightmap tests is not green (tests/conftest.py).

On 2026-10-02 a session's shell did not inherit COBBLERS_SOURCE_ROOT and 47 terrain tests skipped among 5,300
passes; the run exited 0 and read as clean. Without this guard that happens again silently: every heightmap
test turns into a skip, and a skip does not fail a run.

Each case runs pytest in a subprocess on a throwaway directory holding a copy of the real conftest, so the
guard is exercised exactly as the suite loads it.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

CONFTEST = Path(__file__).resolve().parent / "conftest.py"


def run(tmp_path, body, *args, env_root=None):
    shutil.copy(CONFTEST, tmp_path / "conftest.py")
    (tmp_path / "test_case.py").write_text("import pytest\n\n" + body, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "COBBLERS_SOURCE_ROOT"}
    if env_root:
        env["COBBLERS_SOURCE_ROOT"] = env_root
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tmp_path), *args],
                       cwd=tmp_path, env=env, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


HEIGHTMAP_SKIP = '''
def test_passes():
    pass

def test_terrain():
    pytest.skip("NOT_EXECUTED: COBBLERS_SOURCE_ROOT is not set: the canonical heightmap is outside the repo")
'''


def test_a_heightmap_skip_makes_an_otherwise_green_run_fail(tmp_path):
    code, out = run(tmp_path, HEIGHTMAP_SKIP)
    assert code == 1, out
    assert "heightmap tests NOT EXECUTED" in out and "test_terrain" in out


def test_a_module_level_heightmap_skip_is_caught_too(tmp_path):
    code, out = run(tmp_path, 'pytest.skip("canonical heightmap not available: x", allow_module_level=True)\n')
    # a module skipped whole collects nothing; pytest's own code for that is 5, and it must not become 0
    assert code != 0, out
    assert "heightmap tests NOT EXECUTED" in out


def test_the_flag_accepts_a_partial_run_and_still_says_so(tmp_path):
    code, out = run(tmp_path, HEIGHTMAP_SKIP, "--allow-no-heightmap")
    assert code == 0, out
    assert "heightmap tests NOT EXECUTED" in out and "accepted as partial" in out


def test_an_unrelated_skip_does_not_fail_the_run(tmp_path):
    code, out = run(tmp_path, 'def test_x():\n    pytest.skip("needs a prepared build/")\n')
    assert code == 0, out
    assert "NOT EXECUTED" not in out


def test_a_missing_plan_named_after_a_heightmap_tool_is_not_a_heightmap_skip(tmp_path):
    # 2026-10-02: four gulch tests skip for want of derived/rift_sculpt/plan.json, "tools/rift_heightmap.py's
    # plan", with the heightmap present; the first guard counted them and failed a run that had the heightmap
    body = "def test_x():\n    pytest.skip(\"no derived/rift_sculpt/plan.json (tools/rift_heightmap.py's plan)\")\n"
    code, out = run(tmp_path, body)
    assert code == 0, out


def test_a_real_failure_keeps_its_own_exit_code(tmp_path):
    code, out = run(tmp_path, HEIGHTMAP_SKIP + "\ndef test_bad():\n    assert False\n")
    assert code == 1, out


def test_the_header_names_an_unset_root(tmp_path):
    # -v cancels run()'s -q, so the header prints
    _, out = run(tmp_path, "def test_x():\n    pass\n", "-v")
    assert "COBBLERS_SOURCE_ROOT is NOT SET" in out
    _, out = run(tmp_path, "def test_x():\n    pass\n", "-v", env_root="C:/somewhere")
    assert "COBBLERS_SOURCE_ROOT=C:/somewhere" in out
