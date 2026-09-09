---
name: security-review
description: Run a bounded security and privacy review of changes that touch untrusted web content or stored user data — navigation, URL handling, JavaScript execution, downloads, cookies or profiles, permissions, certificates, DevTools, renderer IPC, CEF command-line switches, the sandbox setting, or local persistence. Use before committing such a change, or when asked whether something is safe.
context: fork
agent: security-reviewer
---

# Security review

Runs in a forked context so the reviewer can read broadly without polluting the main session; only the findings return.

**Inputs:** the change to review — a diff, a set of files, or "the current working tree". If unspecified, review the uncommitted diff.

The checklist, threat model, and output format live in the `security-reviewer` agent definition and `.claude/rules/security.md`. Do not restate them here.

## What this skill adds

1. **Scope it first.** Get the diff and identify which security areas the change actually touches; skip the rest rather than padding the report.
2. **Establish reachability** for each touched area — whether a malicious page, or a compromised renderer with filesystem access, can reach the code. Say so explicitly; unreachable code is lower severity.
3. **Report, do not fix.** Recommend precisely; the caller decides.

After the review, triage the findings: fix what is cheap and in scope, and record the rest with a reason rather than dropping them.
