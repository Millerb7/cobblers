"""The heightmap root resolves without the harness injecting COBBLERS_SOURCE_ROOT.

Without this, a tool's answer depends on whether the harness happened to inject the variable into that shell: on
2026-10-02 it was missing from one session's shell and from three of six agents' worktrees (each had to pass
--source-root by hand), while CLAUDE.md said it always arrived. Written by the session that made the fix (no
separate test author was available for a one-function change), and said so here per .claude/rules/testing.md.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import terrain  # noqa: E402


def _configured():
    env = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")).get("env", {})
    return env.get("COBBLERS_SOURCE_ROOT")


# Without it, a shell the harness did not inject into gets "source_root is unset" from every terrain tool.
def test_the_root_comes_from_settings_when_the_environment_lacks_it(monkeypatch):
    if not _configured():
        pytest.skip(".claude/settings.json configures no COBBLERS_SOURCE_ROOT")
    monkeypatch.delenv("COBBLERS_SOURCE_ROOT", raising=False)
    local = ROOT / ".claude" / "settings.local.json"
    want = _configured()
    if local.exists():
        want = json.loads(local.read_text(encoding="utf-8")).get("env", {}).get("COBBLERS_SOURCE_ROOT") or want
    assert terrain.env_source_root() == want


# Without it, an explicit environment (a test pointing at a fixture, a CI runner) would be overridden by the file.
def test_the_environment_wins_over_the_file(monkeypatch):
    monkeypatch.setenv("COBBLERS_SOURCE_ROOT", "X:/somewhere/else")
    assert terrain.env_source_root() == "X:/somewhere/else"


# Without it, the next tool written reads os.environ directly and the gap reopens one tool at a time.
def test_no_tool_reads_the_variable_around_the_resolver():
    direct = re.compile(r"""os\.environ(\.get\(|\[)\s*["']COBBLERS_SOURCE_ROOT["']\s*\)?(?!\s*=)""")
    offenders = []
    for p in sorted((ROOT / "tools").glob("*.py")):
        if p.name == "terrain.py":
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if direct.search(line) and not re.search(r"""os\.environ\[["']COBBLERS_SOURCE_ROOT["']\]\s*=""", line):
                offenders.append("%s:%d" % (p.name, n))
    assert not offenders, offenders
