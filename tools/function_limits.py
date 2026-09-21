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
  unloaded    every fill, setblock, clone and place template with absolute coordinates writes into
              chunks the function has force-loaded before it (a write into an unloaded chunk does
              nothing and reports nothing). A function whose caller holds the chunks says so with a
              `# chunks-loaded-by: <function>` line.

The unloaded rule, measured on the disposable world on 2026-09-21: `forceload add` makes a chunk writable
within the same function (setblock and fill both landed), and without it a setblock into an unloaded chunk
did nothing. The town prep functions force-loaded nothing, so they only took effect where chunks happened
still to be loaded from the step before; the audit found Brock's streets laid a block off their plan there.

It is a static check: it reads the text, not the world. A command that passes can still fail for other
reasons, which is what a placement's own verify pass and tools/town_audit.py are for.

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


WRITE = re.compile(r"(?:^|\brun\s+)(fill|setblock|clone|place\s+template\s+\S+)\s+%s\s+%s\s+%s(?:\s+%s\s+%s\s+%s)?"
                   % ((NUM,) * 6))


def _chunks(x0, z0, x1, z1):
    return {(cx, cz) for cx in range(min(x0, x1) // 16, max(x0, x1) // 16 + 1)
            for cz in range(min(z0, z1) // 16, max(z0, z1) // 16 + 1)}


def unloaded_writes(lines):
    """[(line number, command, chunk)] for block writes into chunks not force-loaded at that point."""
    if any(re.match(r"#\s*chunks-loaded-by:", l.strip()) for l in lines):
        return []
    forced, out = set(), []
    for n, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"forceload\s+(add|remove)\s+(all|%s\s+%s(?:\s+%s\s+%s)?)\s*$" % ((NUM,) * 4), line)
        if m:
            verb, _all, x0, z0, x1, z1 = m.groups()
            if _all == "all":
                forced = set()
                continue
            box = _chunks(int(x0), int(z0), int(x1 if x1 is not None else x0), int(z1 if z1 is not None else z0))
            forced = forced | box if verb == "add" else forced - box
            continue
        m = WRITE.search(line)
        if not m:
            continue
        what, x0, _y0, z0, x1, _y1, z1 = m.groups()
        x0, z0 = int(x0), int(z0)
        if what in ("fill", "clone") and x1 is not None:
            need = _chunks(x0, z0, int(x1), int(z1))
        else:
            need = _chunks(x0, z0, x0, z0)
        missing = sorted(need - forced)
        if missing:
            out.append((n, line[:90], missing[0]))
    return out


TEMPLATE_REACH = 32     # blocks round a `place template` origin held loaded: the text does not say how big it is


def written_chunks(lines):
    """Every chunk a block write in these lines touches, and every chunk the lines already force-load.
    A template may extend a way from its origin and be rotated either way, so its origin is held with
    TEMPLATE_REACH blocks round it."""
    out = set()
    for raw in lines:
        line = raw.strip()
        if line.startswith("#"):
            continue
        m = re.match(r"forceload\s+add\s+%s\s+%s(?:\s+%s\s+%s)?\s*$" % ((NUM,) * 4), line)
        if m:
            x0, z0, x1, z1 = m.groups()
            out |= _chunks(int(x0), int(z0), int(x1 if x1 is not None else x0), int(z1 if z1 is not None else z0))
            continue
        m = WRITE.search(line)
        if not m:
            continue
        what, x0, _y0, z0, x1, _y1, z1 = m.groups()
        x0, z0 = int(x0), int(z0)
        if what in ("fill", "clone") and x1 is not None:
            out |= _chunks(x0, z0, int(x1), int(z1))
        elif what.startswith("place"):
            out |= _chunks(x0 - TEMPLATE_REACH, z0 - TEMPLATE_REACH, x0 + TEMPLATE_REACH, z0 + TEMPLATE_REACH)
        else:
            out |= _chunks(x0, z0, x0, z0)
    return out


def _fill_boxes(x0, y0, z0, x1, y1, z1, limit=FILL_LIMIT):
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    z0, z1 = min(z0, z1), max(z0, z1)
    area = (x1 - x0 + 1) * (z1 - z0 + 1)
    if area > limit:
        half = (x0 + x1) // 2
        return _fill_boxes(x0, y0, z0, half, y1, z1, limit) + _fill_boxes(half + 1, y0, z0, x1, y1, z1, limit)
    per = max(1, limit // area)
    return [(x0, y, z0, x1, min(y1, y + per - 1), z1) for y in range(y0, y1 + 1, per)]


def split_fills(lines):
    """The same lines with every fill over the block limit split into fills under it, the rest of each command
    (block, mode, filter) kept. A town lot levelled for the League came to 83,205 blocks in one fill."""
    out = []
    for raw in lines:
        m = re.match(r"(\s*)fill\s+%s\s+%s\s+%s\s+%s\s+%s\s+%s(\s.*)$" % ((NUM,) * 6), raw)
        if m and _volume(*m.groups()[1:7]) > FILL_LIMIT:
            ind, rest = m.group(1), m.group(8)
            out += ["%sfill %d %d %d %d %d %d%s" % ((ind,) + b + (rest,)) for b in _fill_boxes(*map(int, m.groups()[1:7]))]
        else:
            out.append(raw)
    return out


def ensure_loaded(lines):
    """The same function, holding every chunk it writes for its whole run.

    A function that already force-loads what it writes is returned unchanged. Otherwise its own forceload
    lines are dropped (a release half way through, as the hometown function had, unloads chunks a later
    write needs) and replaced by one set of `forceload add` commands before the first command and the
    matching `forceload remove` after the last, covering every chunk it writes or asked for: one per run of
    chunks along a chunk row, so each stays far under the 256-chunk limit. Fills over the block limit are split
    first (split_fills)."""
    lines = split_fills(lines)
    if not unloaded_writes(lines):
        return list(lines)
    chunks = written_chunks(lines)
    rows = {}
    for cx, cz in chunks:
        rows.setdefault(cz, []).append(cx)
    boxes = []
    for cz, cxs in sorted(rows.items()):
        cxs.sort()
        start = prev = cxs[0]
        for cx in cxs[1:] + [None]:
            if cx is not None and cx == prev + 1 and cx - start < FORCELOAD_CHUNK_LIMIT - 1:
                prev = cx
                continue
            boxes.append("%d %d %d %d" % (start * 16, cz * 16, prev * 16 + 15, cz * 16 + 15))
            if cx is not None:
                start = prev = cx
    body = [l for l in lines if not re.match(r"\s*forceload\s+(add|remove)\b", l)]
    head = 0
    while head < len(body) and (not body[head].strip() or body[head].strip().startswith("#")):
        head += 1
    note = ["# chunks: force-loaded here for the whole function (tools/function_limits.py ensure_loaded)"]
    return (body[:head] + note + ["forceload add %s" % b for b in boxes] + body[head:]
            + ["forceload remove %s" % b for b in boxes])


def check_lines(lines, where="<lines>"):
    """[(line number, command, problem)] for everything the server would refuse or silently drop."""
    out = []
    lost = unloaded_writes(lines)
    if lost:
        n, cmd, chunk = lost[0]
        out.append((n, cmd, "%d block write(s) into chunks this function never force-loads (first: chunk %s): "
                            "in an unloaded chunk they do nothing and say nothing. Force-load the box first, or "
                            "mark the function `# chunks-loaded-by: <caller>`" % (len(lost), chunk)))
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
