#!/usr/bin/env python
"""Keep the committed record of the server's config in step with the config the server runs.

Why: `modpack/config/DistantHorizons.toml` said `enableServerGeneration = true` while the server had run `false` since
the 10240 export, and a copy would have re-enabled generation that ignores the world border (2026-09-26). The fix is
not only that one key. It is that every value the server runs is in the repo.

Where each value lives:
  modpack/config/<path>       our overlay: the players' client pack, copied to the server too (modpack/config/README.md)
  server/config/mods/<path>   the server's running copy of every config that differs from the base pack and has no
                              overlay, plus server-only config files. Backups, images and unpack caches are left out.
  base-pack/cobbleverse/config/<path>   everything else, unchanged upstream

  python tools/server_config_record.py check  --server-dir <server>   report every disagreement; exit 1 on any
  python tools/server_config_record.py record --server-dir <server>   rewrite server/config/mods from the server

Run it under the coordination lock (CLAUDE.md, live server safety). It reads the server's `config/` folder only,
never the world. `check` treats the Distant Horizons `serverId` as the server's own: DH generates it, and it must not
be copied between servers.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERLAY = ROOT / "modpack" / "config"
MIRROR = ROOT / "server" / "config" / "mods"
BASE = ROOT / "base-pack" / "cobbleverse" / "config"
SKIP = re.compile(r"(\.bak$|\.pre-reexport-|/\.archive-unpack/|\.png$|\.icns$|\.ico$|\.jpg$|\.gif$|/\.data\.json$)")
OWN_KEYS = {"DistantHorizons.toml": re.compile(r"^\s*serverId\s*=.*$", re.M)}


def files(folder):
    return {p.relative_to(folder).as_posix(): p for p in folder.rglob("*") if p.is_file()} if folder.is_dir() else {}


def comparable(rel, data):
    """Content as the mod reads it: line endings and trailing blanks normalised, JSON parsed, own keys removed."""
    text = data.decode("utf-8", "replace").replace("\r\n", "\n")
    pat = OWN_KEYS.get(rel)
    if pat:
        text = pat.sub("", text)
    if rel.endswith(".json"):
        try:
            return json.dumps(json.loads(text), sort_keys=True)
        except ValueError:
            pass
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def expected(rel):
    """The file the repo says the server should run at config/<rel>, or None (a file the repo does not record)."""
    for folder in (OVERLAY, MIRROR, BASE):
        p = folder / rel
        if p.is_file():
            return p
    return None


def check(server_config):
    problems = []
    running = {r: p for r, p in files(server_config).items() if not SKIP.search("/" + r) and not r.endswith(".md")}
    for rel, p in sorted(running.items()):
        e = expected(rel)
        if e is None:
            problems.append("%s: runs on the server, recorded nowhere in the repo" % rel)
        elif comparable(rel, e.read_bytes()) != comparable(rel, p.read_bytes()):
            problems.append("%s: the server's copy differs from %s" % (rel, e.relative_to(ROOT).as_posix()))
    for rel in sorted(set(files(OVERLAY)) | set(files(MIRROR))):
        if rel.endswith(".md"):
            continue
        if rel not in running:
            problems.append("%s: recorded in the repo, absent on the server" % rel)
    return problems


def record(server_config):
    for p in sorted(MIRROR.rglob("*"), reverse=True) if MIRROR.exists() else []:   # contents, not the folder
        if p.is_file() and p.name != "README.md":
            p.unlink()
        elif p.is_dir() and not any(p.iterdir()):
            p.rmdir()
    overlay = set(files(OVERLAY))
    n = 0
    for rel, p in sorted(files(server_config).items()):
        if rel in overlay or SKIP.search("/" + rel):
            continue
        b = BASE / rel
        if b.is_file() and b.read_bytes() == p.read_bytes():
            continue
        dest = MIRROR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
        n += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["check", "record"])
    ap.add_argument("--server-dir", required=True)
    a = ap.parse_args(argv)
    cfg = Path(a.server_dir) / "config"
    if not cfg.is_dir():
        sys.exit("no config folder at %s" % cfg)
    if a.cmd == "record":
        print("recorded %d files in %s" % (record(cfg), MIRROR.relative_to(ROOT)))
        return 0
    problems = check(cfg)
    for m in problems:
        print("DRIFT", m)
    print("%d disagreements" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
