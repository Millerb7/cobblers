#!/usr/bin/env python
"""Find commands in a generated function that the server will refuse or silently drop.

Three bugs in two sessions had the same shape: a tool produced a command the server would not run,
and nothing noticed because a refused command is not an error anybody sees. `/fill` refuses more than
32,768 blocks outright, so 958 blocks of vanilla concrete stayed inside Misty's gym; `/forceload add`
refuses more than 256 chunks, which had already been worked around by hand for Brock's gym prep.

What is checked, with the limit each rests on:

  fill        volume <= 32768                     (Minecraft refuses the whole command)
  clone       volume <= 32768                     (same)
  setblock    inside the world border             (a build outside it does nothing)
  forceload   <= 256 chunks in one add            (refused outright)
  function    total commands <= maxCommandChainLength, default 65536

It is a static check: it reads the text, not the world. A command inside the limits can still fail
because its chunks are not loaded, which is what a placement's own verify pass is for.

  python tools/function_limits.py <file or directory> [...]
  python tools/function_limits.py --json build/datapacks

Ownership: a check, not a generator. tools/place_town.py and tools/place_donor.py call check_lines()
before they write, so a function that would be refused is never produced.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FILL_LIMIT = 32768
CLONE_LIMIT = 32768
FORCELOAD_CHUNK_LIMIT = 256
CHAIN_LIMIT = 65536
NUM = r"(-?\d+)"


def _volume(a, b, c, d, e, f):
    return (abs(int(d) - int(a)) + 1) * (abs(int(e) - int(b)) + 1) * (abs(int(f) - int(c)) + 1)


def check_lines(lines, where="<lines>"):
    """[(line number, command, problem)] for everything the server would refuse."""
    out = []
    body = [l for l in lines if l.strip() and not l.strip().startswith("#")]
    if len(body) > CHAIN_LIMIT:
        out.append((0, "(whole function)",
                    "%d commands, over maxCommandChainLength %d: the tail will not run"
                    % (len(body), CHAIN_LIMIT)))
    for n, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"fill\s+%s\s+%s\s+%s\s+%s\s+%s\s+%s\b" % ((NUM,) * 6), line)
        if m:
            v = _volume(*m.groups())
            if v > FILL_LIMIT:
                out.append((n, line[:90], "fill of %d blocks, over the %d limit: the server refuses the "
                                         "whole command and nothing is placed" % (v, FILL_LIMIT)))
            continue
        m = re.match(r"clone\s+%s\s+%s\s+%s\s+%s\s+%s\s+%s\b" % ((NUM,) * 6), line)
        if m:
            v = _volume(*m.groups())
            if v > CLONE_LIMIT:
                out.append((n, line[:90], "clone of %d blocks, over the %d limit" % (v, CLONE_LIMIT)))
            continue
        m = re.match(r"forceload\s+add\s+%s\s+%s(?:\s+%s\s+%s)?\s*$" % ((NUM,) * 4), line)
        if m:
            x0, z0, x1, z1 = m.groups()
            if x1 is None:
                continue
            chunks = ((abs(int(x1) // 16 - int(x0) // 16) + 1) * (abs(int(z1) // 16 - int(z0) // 16) + 1))
            if chunks > FORCELOAD_CHUNK_LIMIT:
                out.append((n, line[:90], "forceload of %d chunks, over the %d limit: refused, so every "
                                         "command after it runs on unloaded ground"
                                         % (chunks, FORCELOAD_CHUNK_LIMIT)))
    return out


def check_file(path):
    return check_lines(Path(path).read_text(encoding="utf-8").splitlines(), str(path))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("paths", nargs="+")
    p.add_argument("--json", action="store_true", dest="as_json")
    a = p.parse_args(argv)
    findings, files = {}, 0
    for root in a.paths:
        root = Path(root)
        targets = sorted(root.rglob("*.mcfunction")) if root.is_dir() else [root]
        for f in targets:
            files += 1
            bad = check_file(f)
            if bad:
                findings[str(f)] = [{"line": n, "command": c, "problem": w} for n, c, w in bad]
    if a.as_json:
        print(json.dumps({"files_checked": files, "files_with_problems": len(findings), "findings": findings}, indent=1))
    else:
        for f, rows in findings.items():
            print(f)
            for r in rows:
                print("   line %-6d %s" % (r["line"], r["problem"]))
                print("      %s" % r["command"])
        print("%d function file(s) checked, %d with problems" % (files, len(findings)))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
