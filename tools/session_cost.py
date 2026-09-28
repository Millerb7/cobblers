#!/usr/bin/env python
"""What a Claude Code session and its agents have really cost, and whether it is time to hand over (CLAUDE.md
"Session length").

The harness's per-agent figure (`totalTokens`, `subagent_tokens`) is the final context, not the spend. The spend is
every turn's context added up: each turn re-sends the whole conversation, at a tenth of the price when it is cached.
This reads the transcripts under ~/.claude/projects/ and reports, per session and per agent:

  turns        model calls
  context now  the last turn's context: what the NEXT turn will cost to send
  weighted     input + 1.25 x cache writes + 0.1 x cache reads + 5 x output, in input-token units

    python tools/session_cost.py                  # the most recently active cobblers session, with its agents
    python tools/session_cost.py --session <id>   # a given session (the transcript's file name)
    python tools/session_cost.py --list           # recent sessions, newest first

Thresholds (CLAUDE.md): context now under 200k is fine; 200k-300k, compact if the job goes on, hand over if it is
done; over 300k, hand over.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"
COMPACT_AT, HANDOVER_AT = 200_000, 300_000


def shape(path):
    """(turns, contexts per turn, weighted cost, cache writes) of one transcript; a streamed message counts once."""
    per, order = {}, []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") != "assistant":
            continue
        m = e.get("message") or {}
        u = m.get("usage") or {}
        if not u:
            continue
        mid = m.get("id")
        if mid not in per:
            order.append(mid)
        prev = per.get(mid, {})
        per[mid] = {k: max(prev.get(k, 0), u.get(k, 0) or 0) for k in
                    ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")}
    ctx = [per[m]["input_tokens"] + per[m]["cache_creation_input_tokens"] + per[m]["cache_read_input_tokens"]
           for m in order]
    w = sum(per[m]["input_tokens"] + 1.25 * per[m]["cache_creation_input_tokens"]
            + 0.1 * per[m]["cache_read_input_tokens"] + 5 * per[m]["output_tokens"] for m in order)
    return len(order), ctx, w


def sessions():
    out = [p for d in PROJECTS.glob("*cobblers*") if d.is_dir() for p in d.glob("*.jsonl")]
    return sorted(out, key=lambda p: p.stat().st_mtime, reverse=True)


def verdict(now):
    if now < COMPACT_AT:
        return "fine"
    if now < HANDOVER_AT:
        return "COMPACT if the job goes on; HAND OVER if it is done"
    return "HAND OVER now: every turn costs %dk to send" % (now // 10_000)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--session")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    all_ = sessions()
    if a.list:
        for p in all_[:15]:
            n, ctx, w = shape(p)
            print("%s  %-40s turns %4d  context now %5dk  weighted %5.1fM" % (
                p.stem, p.parent.name[-40:], n, (ctx[-1] if ctx else 0) // 1000, w / 1e6))
        return 0
    path = next((p for p in all_ if p.stem == a.session), None) if a.session else (all_[0] if all_ else None)
    if not path:
        raise SystemExit("no transcript found under %s" % PROJECTS)
    n, ctx, w = shape(path)
    now = ctx[-1] if ctx else 0
    print("session %s: %d turns, context now %dk (average %dk), weighted %.1fM" % (
        path.stem, n, now // 1000, (sum(ctx) // max(1, n)) // 1000, w / 1e6))
    agents = sorted((path.parent / path.stem / "subagents").glob("agent-*.jsonl"))
    total = 0.0
    for f in agents:
        meta = f.with_suffix(".meta.json")
        desc = json.loads(meta.read_text(encoding="utf-8")).get("description", "") if meta.is_file() else ""
        an, actx, aw = shape(f)
        total += aw
        print("  agent %-42s turns %4d  final context %4dk (the harness's figure)  weighted %5.2fM" % (
            desc[:42], an, (actx[-1] if actx else 0) // 1000, aw / 1e6))
    if agents:
        print("  agents together: %.1fM weighted" % (total / 1e6))
    print("verdict: %s" % verdict(now))
    return 0


if __name__ == "__main__":
    sys.exit(main())
