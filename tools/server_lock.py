"""Take, inspect and release the shared server coordination lock.

CLAUDE.md, "Live server safety": before any command that could reach the local `cobblers-server` runtime, a session
makes a process/port check and acquires the shared external lock, created atomically outside the server tree and
recording the owning agent/task and a timestamp. `tools/runtime_guard.py` is the *reader* -- it refuses runtime
access unless COBBLERS_SERVER_LOCK names a lock whose `owner:` line equals COBBLERS_LOCK_OWNER. Until this file
there was no writer, so every session wrote the lock by hand.

Taking is atomic (O_CREAT|O_EXCL): a lock that already exists is somebody's lock. Taking it over is possible but
never silent -- `--supersede <text>` must match the current owner line, so a session cannot take a lock it has not
read, and the superseded owner is recorded in the new file.

  python tools/server_lock.py status
  python tools/server_lock.py take --owner "<agent/task line>" [--supersede "<substring of current owner>"]
  python tools/server_lock.py release --owner "<the same line>"
  python tools/server_lock.py env --owner "<the same line>"    # shell exports for runtime_guard

A lock is NOT proof the server is free. The process/port check is a separate step and comes first.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LOCK = Path("C:/Users/wnd/Documents/github/.cobblers-server-agent.lock")


def _read(lock: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    try:
        text = lock.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return fields
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields.setdefault(key.strip().lower(), value.strip())
    return fields


def _stamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _body(owner: str, superseded: str | None) -> str:
    lines = ["owner: %s" % owner, "acquired: %s" % _stamp()]
    if superseded:
        lines.append("superseded: %s" % superseded)
    return "\n".join(lines) + "\n"


def cmd_status(args) -> int:
    lock = Path(args.lock)
    if not lock.exists():
        print("free: no lock at %s" % lock)
        return 0
    fields = _read(lock)
    print("held: %s" % lock)
    for key in ("owner", "acquired", "superseded"):
        if fields.get(key):
            print("  %s: %s" % (key, fields[key]))
    return 0


def cmd_take(args) -> int:
    lock = Path(args.lock)
    owner = args.owner.strip()
    if not owner:
        print("server_lock: --owner must be a non-empty line naming the agent/task", file=sys.stderr)
        return 2
    superseded = None
    if lock.exists():
        current = _read(lock).get("owner") or ""
        if not args.supersede:
            print("server_lock: %s is held by %r. It is somebody's lock; do not assume it is stale because the "
                  "server is down. Resolve ownership with the user or the other agent, then pass --supersede with "
                  "text matching that owner line." % (lock, current), file=sys.stderr)
            return 1
        if args.supersede not in current:
            print("server_lock: refusing to supersede: --supersede %r does not match the current owner %r. Read the "
                  "lock first (status)." % (args.supersede, current), file=sys.stderr)
            return 1
        superseded = "%s (acquired %s)" % (current, _read(lock).get("acquired") or "unknown")
        lock.unlink()
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print("server_lock: %s was created by someone else between the check and the write; nothing done." % lock,
              file=sys.stderr)
        return 1
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(_body(owner, superseded))
    print("took %s" % lock)
    if superseded:
        print("  superseded: %s" % superseded)
    return 0


def cmd_release(args) -> int:
    lock = Path(args.lock)
    if not lock.exists():
        print("server_lock: %s is already free; nothing done." % lock)
        return 0
    current = _read(lock).get("owner") or ""
    if current != args.owner.strip():
        print("server_lock: refusing to release: %s is held by %r, not by %r. Only the holder releases a lock."
              % (lock, current, args.owner.strip()), file=sys.stderr)
        return 1
    lock.unlink()
    print("released %s" % lock)
    return 0


def cmd_env(args) -> int:
    lock = Path(args.lock)
    current = _read(lock).get("owner") or ""
    if current != args.owner.strip():
        print("server_lock: %s is held by %r, not by %r; runtime_guard would refuse."
              % (lock, current, args.owner.strip()), file=sys.stderr)
        return 1
    print('export COBBLERS_SERVER_LOCK="%s"' % lock)
    print('export COBBLERS_LOCK_OWNER="%s"' % current)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lock", default=str(DEFAULT_LOCK), help="lock file path (default: %(default)s)")
    subs = parser.add_subparsers(dest="command", required=True)

    subs.add_parser("status", help="print who holds the lock").set_defaults(func=cmd_status)

    take = subs.add_parser("take", help="acquire the lock atomically")
    take.add_argument("--owner", required=True, help="the owning agent/task line")
    take.add_argument("--supersede", help="text that must appear in the CURRENT owner line to take it over")
    take.set_defaults(func=cmd_take)

    release = subs.add_parser("release", help="release a lock this owner holds")
    release.add_argument("--owner", required=True)
    release.set_defaults(func=cmd_release)

    env = subs.add_parser("env", help="print the shell exports runtime_guard needs")
    env.add_argument("--owner", required=True)
    env.set_defaults(func=cmd_env)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
