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
