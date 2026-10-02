import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def tracked_files(repo_root: Path) -> list[Path]:
    """Files git knows about plus untracked-but-not-ignored ones (so new work is covered before commit)."""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=repo_root, capture_output=True, check=True,
    ).stdout.decode("utf-8", "surrogateescape")
    return [repo_root / p for p in out.split("\0") if p]


@pytest.fixture(scope="session")
def python() -> str:
    return sys.executable


def pytest_addoption(parser):
    parser.addoption(
        "--allow-no-heightmap", action="store_true", default=False,
        help="accept a run that skipped tests for want of the canonical heightmap (COBBLERS_SOURCE_ROOT); "
             "without it such a run exits non-zero however many tests passed")


# A skip whose reason names the heightmap or its root is a test that could not run here, not one that
# passed. On 2026-10-02 a session's shell did not inherit COBBLERS_SOURCE_ROOT from .claude/settings.json
# and 47 tests skipped among 5,300 passes: the run read green and the terrain checks had not run at all.
HEIGHTMAP_SKIP = ("COBBLERS_SOURCE_ROOT", "heightmap")
_heightmap_skips: list[str] = []


def _skip_reason(report) -> str:
    lr = report.longrepr
    if isinstance(lr, tuple) and len(lr) == 3:
        return str(lr[2])
    return str(lr or "")


def _note_heightmap_skip(report):
    if report.skipped and not hasattr(report, "wasxfail"):
        # a tool's name is not the heightmap: "tools/rift_heightmap.py's plan" is a missing derived/ file
        reason = _skip_reason(report).replace("rift_heightmap", "")
        if any(k.lower() in reason.lower() for k in HEIGHTMAP_SKIP):
            _heightmap_skips.append("%s: %s" % (report.nodeid, reason.splitlines()[0][:160]))


def pytest_runtest_logreport(report):
    _note_heightmap_skip(report)


def pytest_collectreport(report):
    _note_heightmap_skip(report)


def pytest_report_header(config):
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        return ("COBBLERS_SOURCE_ROOT is NOT SET: every heightmap test will skip and the run will exit "
                "non-zero (pass --allow-no-heightmap to accept a partial run)")
    return "COBBLERS_SOURCE_ROOT=%s" % root


def pytest_sessionfinish(session, exitstatus):
    """Refuse to report green when tests skipped for want of the heightmap: the run did not test terrain."""
    if _heightmap_skips and exitstatus == 0 and not session.config.getoption("--allow-no-heightmap"):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if not _heightmap_skips:
        return
    accepted = config.getoption("--allow-no-heightmap")
    tr = terminalreporter
    tr.section("heightmap tests NOT EXECUTED", sep="=", red=not accepted, yellow=accepted, bold=True)
    tr.line("%d test(s) skipped because the canonical heightmap was not available (COBBLERS_SOURCE_ROOT=%r)."
            % (len(_heightmap_skips), os.environ.get("COBBLERS_SOURCE_ROOT")))
    tr.line("This run is NOT green: %s." % (
        "accepted as partial by --allow-no-heightmap" if accepted
        else "it exits non-zero. Set COBBLERS_SOURCE_ROOT, or pass --allow-no-heightmap to accept a partial run"))
    for line in _heightmap_skips[:10]:
        tr.line("  " + line)
    if len(_heightmap_skips) > 10:
        tr.line("  ... and %d more" % (len(_heightmap_skips) - 10))


def pytest_configure(config):
    # registered so `-m "not slow"` deselects them and --strict-markers accepts the mark
    config.addinivalue_line("markers", "slow: builds from the out-of-repo heightmap and takes seconds")
    # One module that cannot be imported must not cost the other 5,200 tests their result. The default
    # is to stop the run at the first collection error, which is how 2026-10-01 came to report `no tests
    # ran` instead of a count: a run that says nothing cannot be compared with the run before it, so a
    # real regression and a broken import look the same. With this, the error is still listed and still
    # counted in the summary -- it just no longer takes the count with it.
    config.option.continue_on_collection_errors = True


class ToolFailedClosed(Exception):
    """A tool raised SystemExit while a test module was being imported."""


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    """A tool that fails closed during collection fails ONE module loudly; it never kills the run.

    Four test modules call a generator at import time (test_trainer_cycle, test_celebi_wake,
    test_sapling_celebi, test_trainer_holdoff_mixed_progress), because their parametrize lists come from
    the real data. Our tools fail closed with SystemExit, which is a BaseException, so pytest's
    collection does not catch it. On 2026-10-01 one SystemExit out of tools/route_trainers.py -- a
    genuine finding, two authors for one trainer field after a clean merge -- turned the whole suite into
    `no tests ran` and an INTERNALERROR for six hours: no failure count, no passes, nothing tested, and
    the number it had been reporting the day before (7 failed, 5169 passed) was simply gone rather than
    red. A suite that reports nothing is worse than a suite that reports a failure.

    The message is kept verbatim, so the finding still arrives; it arrives as one collection error.
    """
    outcome = yield
    try:
        outcome.get_result()
    except SystemExit as exc:
        from _pytest.reports import CollectReport
        outcome.force_result(CollectReport(
            nodeid=collector.nodeid, outcome="failed", result=[],
            longrepr="%s: a tool raised SystemExit while this module was imported. Reported here as one "
                     "collection error so the rest of the suite still runs and still counts.\n\n"
                     "The tool's message, verbatim:\n\n%s" % (collector.nodeid, exc)))
