#!/usr/bin/env python
"""Where did each agent's spend go? Usage: python tools/agent_spend.py <session-id> (from tools/session_cost.py).

 Attribute every turn's re-sent context to the item that put it there.

Weighted cost per turn = input + 1.25 cache writes + 0.1 cache reads + 5 output (tools/session_cost.py). An item of
T tokens that enters the context at turn k is re-read on every later turn, so it costs about 1.25 T + 0.1 T (n - k)
over a run of n turns. Tokens are estimated as chars / 3.6 for the item and scaled so the items plus the starting
context sum to the transcript's measured context at the last turn.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

SESSION = sys.argv[1]
d = next(p for p in Path.home().joinpath(".claude", "projects").glob("*cobblers*") if (p / SESSION).is_dir()) / SESSION
agents = sorted((d / "subagents").glob("agent-*.jsonl"))


def cat_bash(cmd):
    c = cmd.strip()
    if "pytest" in c:
        return "bash: pytest"
    m = re.search(r"python\S*\s+(?:-m\s+)?(?:\S*/)?tools/(\w+)\.py(?:\s+(\w+))?", c)
    if m:
        t = m.group(1)
        if t.endswith("_audit"):
            return "bash: run own/other audit"
        if t in ("validate_data", "validate", "id_authorship", "reapply", "local_inputs", "build_encounters",
                 "compile_spawns", "compile_dialogue", "npc_model_audit"):
            return "bash: repo-wide tool (%s)" % t
        return "bash: run a generator/tool"
    if c.startswith("python") or "python -c" in c or c.startswith("PYTHONPATH"):
        return "bash: inline python (measuring, probing data)"
    if c.startswith(("grep", "rg ")) or " grep " in c:
        return "bash: grep"
    if c.startswith(("git ",)):
        return "bash: git"
    if c.startswith(("sed", "cat", "head", "tail", "awk", "wc", "ls", "find")):
        return "bash: read via shell (sed/cat/ls)"
    return "bash: other"


def cat_read(path):
    p = path.replace("\\", "/")
    if "scratchpad" in p:
        return "read: the brief"
    if "/tools/" in p:
        return "read: existing tools (patterns)"
    if "/data/" in p:
        return "read: data files"
    if "/docs/" in p or p.endswith("CLAUDE.md"):
        return "read: docs / CLAUDE.md"
    if "/tests/" in p:
        return "read: tests"
    return "read: other"


rows = []
for f in agents:
    meta = f.with_suffix(".meta.json")
    desc = json.loads(meta.read_text(encoding="utf-8")).get("description", "") if meta.is_file() else f.stem
    usage, order, events = {}, [], []          # events: (turn_index, category, chars)
    uses = {}
    turn = 0
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        msg = o.get("message") or {}
        if o.get("type") == "assistant":
            mid = msg.get("id")
            if mid and mid not in usage:
                order.append(mid)
                turn = len(order)
            if mid:
                usage[mid] = msg.get("usage", {})
            for b in msg.get("content") or []:
                if b.get("type") == "tool_use":
                    name, inp = b.get("name"), b.get("input", {})
                    if name == "Bash" or name == "PowerShell":
                        cat = cat_bash(inp.get("command", ""))
                    elif name == "Read":
                        cat = cat_read(inp.get("file_path", ""))
                    elif name in ("Grep", "Glob"):
                        cat = "grep/glob tool"
                    elif name in ("Write", "Edit", "MultiEdit"):
                        cat = "writing files (own output, in context)"
                    else:
                        cat = "other tool: %s" % name
                    uses[b.get("id")] = cat
                    events.append((turn, cat if name in ("Write", "Edit") else "tool inputs", len(json.dumps(inp))))
                elif b.get("type") == "text":
                    events.append((turn, "agent's own prose", len(b.get("text", ""))))
                elif b.get("type") == "thinking":
                    pass                         # thinking is not re-sent
        elif o.get("type") == "user":
            for b in (msg.get("content") or []) if isinstance(msg.get("content"), list) else []:
                if b.get("type") == "tool_result":
                    c = b.get("content")
                    n = len(c) if isinstance(c, str) else sum(len(x.get("text", "")) for x in c or [] if isinstance(x, dict))
                    events.append((turn, uses.get(b.get("tool_use_id"), "tool result: unknown"), n))
    n = len(order)
    if not n:
        continue
    u = [usage[m] for m in order]
    ctx = [x.get("input_tokens", 0) + x.get("cache_creation_input_tokens", 0) + x.get("cache_read_input_tokens", 0) for x in u]
    w = sum(x.get("input_tokens", 0) + 1.25 * x.get("cache_creation_input_tokens", 0)
            + 0.1 * x.get("cache_read_input_tokens", 0) + 5 * x.get("output_tokens", 0) for x in u)
    out_w = sum(5 * x.get("output_tokens", 0) for x in u)
    base = ctx[0]
    est = sum(c for _, _, c in events) / 3.6
    scale = max(ctx[-1] - base, 1) / max(est, 1)
    spend = defaultdict(float)
    for k, cat, chars in events:
        t = chars / 3.6 * scale
        spend[cat] += 1.25 * t + 0.1 * t * max(n - k, 0)
    spend["starting context (system + CLAUDE.md + brief), re-read every turn"] = 1.25 * base + 0.1 * base * n
    spend["output tokens (x5)"] = out_w
    rows.append((desc, n, w, ctx[0], ctx[-1], spend))

tot = defaultdict(float)
for desc, n, w, c0, c1, spend in rows:
    acc = sum(spend.values())
    print("\n%s: %d turns, %.2fM weighted, context %dk -> %dk" % (desc, n, w / 1e6, c0 // 1000, c1 // 1000))
    for k, v in sorted(spend.items(), key=lambda kv: -kv[1])[:9]:
        print("   %5.1f%%  %-62s %.2fM" % (100 * v / acc, k, v * w / acc / 1e6))
        tot[k] += v * w / acc
allw = sum(r[2] for r in rows)
print("\nALL %d agents: %.1fM weighted, %d turns" % (len(rows), allw / 1e6, sum(r[1] for r in rows)))
for k, v in sorted(tot.items(), key=lambda kv: -kv[1])[:14]:
    print("   %5.1f%%  %-62s %.2fM" % (100 * v / allw, k, v / 1e6))
