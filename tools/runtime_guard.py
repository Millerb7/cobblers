"""Refuse paths into the live server runtime unless the caller holds the coordination lock.

The project rule (CLAUDE.md, "Live server safety"): tools never enumerate, read, copy or write the live world, and
touch the rest of the `cobblers-server` runtime only while holding the shared lock. This module is the enforcement
point for every tool that takes a world folder, a server directory, an install target or RCON.

  - A path inside a directory named exactly `cobblers-server` that is, or lies inside, a world folder (a directory
    holding `level.dat` or `region/`) is refused outright. Work on an offline snapshot outside the runtime (for
    example under `cobblers-server-retired/`) or on a disposable copy.
  - Any other path inside `cobblers-server` (mods, datapacks, config, the RCON password) is allowed only when the
    environment variable COBBLERS_SERVER_LOCK names an existing, non-empty lock file.

Nothing here has a default server or world path. Every caller passes one explicitly.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RUNTIME_DIR_NAME = "cobblers-server"
LOCK_ENV = "COBBLERS_SERVER_LOCK"


class RuntimeAccessRefused(SystemExit):
    pass


def _runtime_root(path: Path) -> Path | None:
    for parent in (path, *path.parents):
        if parent.name == RUNTIME_DIR_NAME:
            return parent
    return None


def _is_world(d: Path) -> bool:
    return (d / "level.dat").exists() or (d / "region").is_dir()


def check(path, purpose: str = "access") -> Path:
    """Return the resolved path, or raise RuntimeAccessRefused. `purpose` only shapes the message."""
    if path is None or str(path) == "":
        raise RuntimeAccessRefused("runtime_guard: no path given to %s; pass one explicitly" % purpose)
    p = Path(path).resolve()
    root = _runtime_root(p)
    if root is None:
        return p
    for d in (p, *p.parents):
        if d == root:
            break
        if d.is_dir() and _is_world(d):
            raise RuntimeAccessRefused(
                "runtime_guard: refusing to %s %s: %s is a world inside the live server runtime. "
                "Use an offline snapshot outside %s or a disposable copy." % (purpose, p, d, RUNTIME_DIR_NAME))
    lock = os.environ.get(LOCK_ENV)
    if not lock or not Path(lock).is_file() or Path(lock).stat().st_size == 0:
        raise RuntimeAccessRefused(
            "runtime_guard: refusing to %s %s inside the server runtime without the coordination lock. "
            "Acquire the lock (CLAUDE.md, Live server safety) and set %s to its path." % (purpose, p, LOCK_ENV))
    return p


def rcon(server_dir):
    """(rcon module, password) for a server directory, only under the lock."""
    server = check(server_dir, "use RCON through")
    sys.path.insert(0, str(server))
    import rcon as module  # noqa: E402  (the server directory's own client)
    return module, (server / ".rcon-password").read_text(encoding="utf8").strip()
