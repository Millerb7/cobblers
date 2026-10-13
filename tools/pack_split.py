#!/usr/bin/env python
"""Split a generated pack's one-shot placement functions into a sibling `<pack>_build` pack, at the generator.

Why (2026-10-12, docs/research/notes/function-heap.md): Minecraft keeps every function line of a loaded pack parsed in
the heap for as long as the pack is loaded, and a mixed pack -- a runtime keeper beside hundreds of thousands of lines of
shell placement a re-apply step runs once -- can never be unloaded. Split, the placement goes into its own pack that
`tools/pack_roles.py` classes `build` and `tools/reapply.py strip` moves out after the run.

The function ids do NOT change: both packs ship functions under the same namespace folder, which the game merges by id,
so every re-apply step, test and audit that names a function keeps naming it. Only the file's pack changes.

Fail closed, before anything moves: a function the generator names as build must not be named by any command line
(comments skipped) or data file left in the runtime pack -- a runtime caller would be stranded by a strip. A caller in
ANOTHER pack is pack_roles' job: it classes the whole install, and a `_build` pack any runtime function reaches is
`runtime` there and is never stripped.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

SUFFIX = "_build"


class SplitError(SystemExit):
    pass


def function_id(pack_dir, f):
    rel = f.relative_to(Path(pack_dir) / "data").parts
    return "%s:%s" % (rel[0], "/".join(rel[2:])[:-len(".mcfunction")])


def plan(pack_dir, is_build):
    """{function id: file} of the functions is_build(id) names, after the guard."""
    pack_dir = Path(pack_dir)
    moved = {}
    for f in sorted((pack_dir / "data").glob("*/function/**/*.mcfunction")):
        fid = function_id(pack_dir, f)
        if is_build(fid):
            moved[fid] = f
    if not moved:
        return moved
    tok = re.compile(r"[a-z0-9_.\-]+:[a-z0-9_./\-]+")

    def named(ln):
        """The first moved id the line names as a whole token (a prefix of a longer id is not a mention)."""
        for t in tok.findall(ln):
            if t.rstrip(".") in moved:
                return t.rstrip(".")
            # a macro or string-built name (`cobblers:x/$(y)`, `'cobblers:x/' + v`): any moved id under it counts
            if t.endswith("/") and any(i.startswith(t) for i in moved):
                return t + "..."
        return None
    callers = []
    for f in sorted((pack_dir / "data").rglob("*")):
        if not f.is_file() or f.name == "index.txt":
            continue
        if f.suffix == ".mcfunction":
            if function_id(pack_dir, f) in moved:
                continue
            lines = [ln for ln in f.read_text(encoding="utf-8", errors="replace").splitlines()
                     if ln.strip() and not ln.strip().startswith("#")]
        else:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        for ln in lines:
            m = named(ln)
            if m:
                callers.append("%s names %s: %s" % (f.relative_to(pack_dir).as_posix(), m, ln.strip()[:120]))
                break
    if callers:
        raise SplitError("pack_split: %d file(s) left in %s name a function marked build-only; nothing moved:\n  %s"
                         % (len(callers), pack_dir.name, "\n  ".join(callers[:20])))
    return moved


def split(pack_dir, is_build, description):
    """Move every function is_build(id) names from pack_dir into <pack_dir>_build (rebuilt from nothing), with its own
    pack.mcmeta copied from pack_dir's format. Returns (moved count, the build pack's path)."""
    pack_dir = Path(pack_dir)
    out = pack_dir.with_name(pack_dir.name + SUFFIX)
    moved = plan(pack_dir, is_build)
    if out.exists():
        shutil.rmtree(out)
    # written even when nothing moves: install copies every pack in SERVER_PACKS and refuses one not built
    meta = json.loads((pack_dir / "pack.mcmeta").read_text(encoding="utf-8"))
    meta["pack"]["description"] = description
    out.mkdir(parents=True)
    (out / "pack.mcmeta").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n")
    for fid, f in moved.items():
        dest = out / f.relative_to(pack_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), str(dest))
    if not moved:
        return 0, out
    # an emptied folder left behind is harmless to the game, but say nothing that is not there
    for d in sorted((pack_dir / "data").rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    return len(moved), out
