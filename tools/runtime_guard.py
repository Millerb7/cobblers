"""Refuse paths into the live server runtime unless the caller holds the coordination lock.

The project rule (CLAUDE.md, "Live server safety"): tools never enumerate, read, copy or write the live world, and
touch the rest of the `cobblers-server` runtime only while holding the shared lock. This module is the enforcement
point for every tool that takes a world folder, a server directory, an install target or RCON.

  - A path inside a directory named exactly `cobblers-server` that is, or lies inside, a world folder (a directory
    holding `level.dat` or `region/`) is refused outright. Work on an offline snapshot outside the runtime (for
    example under `cobblers-server-retired/`) or on a disposable copy.
  - Any other path inside `cobblers-server` (mods, datapacks, config, the RCON password) is allowed only while the
    caller HOLDS the lock (`require_lock`): COBBLERS_SERVER_LOCK names the lock file, and its `owner:` line equals
    COBBLERS_LOCK_OWNER. A lock file that merely exists is somebody's lock, not ours; until 2026-09-21 any existing
    file passed, and tools/reapply.py set the path itself when it was missing, so a run could proceed on another
    agent's lock (Codex review). Tools that drive a server or a world call `require_lock` before anything else.

Nothing here has a default server or world path. Every caller passes one explicitly.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RUNTIME_DIR_NAME = "cobblers-server"
LOCK_ENV = "COBBLERS_SERVER_LOCK"
OWNER_ENV = "COBBLERS_LOCK_OWNER"


class RuntimeAccessRefused(SystemExit):
    pass


def _runtime_root(path: Path) -> Path | None:
    for parent in (path, *path.parents):
        if parent.name == RUNTIME_DIR_NAME:
            return parent
    return None


def _is_world(d: Path) -> bool:
    return (d / "level.dat").exists() or (d / "region").is_dir()


def lock_owner(lock_path) -> str | None:
    """The `owner:` line of a lock file, or None."""
    try:
        for line in Path(lock_path).read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("owner:"):
                return line.split(":", 1)[1].strip() or None
    except OSError:
        return None
    return None


def require_lock(purpose: str = "use the server") -> Path:
    """The lock file's path when the caller holds the coordination lock, else raise RuntimeAccessRefused.

    Held means: COBBLERS_SERVER_LOCK names an existing lock file, and its `owner:` line equals COBBLERS_LOCK_OWNER.
    There is no default for either: a caller that did not take the lock cannot name it."""
    lock = os.environ.get(LOCK_ENV)
    owner = (os.environ.get(OWNER_ENV) or "").strip()
    if not lock or not Path(lock).is_file() or Path(lock).stat().st_size == 0:
        raise RuntimeAccessRefused(
            "runtime_guard: refusing to %s without the coordination lock. Acquire it (CLAUDE.md, Live server "
            "safety), set %s to its path and %s to the owner line you wrote in it." % (purpose, LOCK_ENV, OWNER_ENV))
    held_by = lock_owner(lock)
    if not owner or held_by != owner:
        raise RuntimeAccessRefused(
            "runtime_guard: refusing to %s: the lock %s is held by %r, and this caller declares %r (%s). A lock "
            "file that exists is not a lock you hold." % (purpose, lock, held_by, owner or None, OWNER_ENV))
    return Path(lock)


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
    require_lock("%s %s inside the server runtime" % (purpose, p))
    return p


def rcon(server_dir):
    """(rcon module, password) for a server directory, only under the lock."""
    server = check(server_dir, "use RCON through")
    sys.path.insert(0, str(server))
    import rcon as module  # noqa: E402  (the server directory's own client)
    return module, (server / ".rcon-password").read_text(encoding="utf8").strip()
