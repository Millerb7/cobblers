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
