"""No handler may turn a real fault into a benign result.

On 2026-09-22 fourteen tests reported "the canonical heightmap is not available: division by zero" and skipped.
The heightmap was fine; the builder had a genuine crash, and a broad `except Exception` around it reported a
benign reason and skipped. That is the same class as a fail-open audit: the check goes green and the fault is
invisible.

This walks every tool and test and fails on a broad handler whose body only *disposes* of the error -- pass,
continue, a bare return, a default value, or pytest.skip -- without recording it. Narrow the exception, or let it
raise, or record what happened.

A handler that genuinely tolerates bad input from a third-party archive is still allowed: name the exceptions it
tolerates (`zipfile.BadZipFile`, `json.JSONDecodeError`, `OSError`, ...) rather than catching everything.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BROAD = {"Exception", "BaseException"}

# Handlers that catch broadly on purpose and say so, with the reason they are safe.
ALLOWED = {
    # tools/validate.py and tools/validate_data.py: a crashing check is turned into a reported error, which is
    # the opposite of swallowing -- the run goes red and names the check.
    ("tools/validate.py", "a broken check must not hide other results"),
    ("tools/validate_data.py", "a malformed claim must not hide the others"),
    ("tools/validate_data.py", "a template that cannot be read is not a template without triggers"),
    ("tools/validate_data.py", "a broken check must not hide the others"),
}


def _records(node):
    """Does the handler body do anything other than dispose of the error?"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            name = getattr(f, "attr", None) or getattr(f, "id", None)
            if name in ("skip", "xfail"):
                return False                      # a skip is a disposal, not a record
            return True                           # any other call: it reports, logs or re-raises
        if isinstance(sub, (ast.Raise, ast.Assert)):
            return True
    return False


def _sources():
    for d in ("tools", "tests"):
        for p in sorted((ROOT / d).rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            yield p


def test_no_broad_handler_disposes_of_a_crash():
    bad = []
    for p in _sources():
        rel = p.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError as e:
            bad.append("%s: does not parse (%s)" % (rel, e))
            continue
        lines = p.read_text(encoding="utf-8").splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            t = node.type
            names = set()
            if t is None:
                names = {"Exception"}
            elif isinstance(t, ast.Name):
                names = {t.id}
            elif isinstance(t, ast.Tuple):
                names = {e.id for e in t.elts if isinstance(e, ast.Name)}
            if not (names & BROAD):
                continue
            if _records(node):
                continue
            comment = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
            reason = comment.split("#", 1)[1].strip() if "#" in comment else ""
            if any(rel == f and reason.startswith(r[:30]) for f, r in ALLOWED):
                continue
            bad.append("%s:%d catches %s and only disposes of it%s" % (
                rel, node.lineno, "/".join(sorted(names)), (" (# %s)" % reason) if reason else ""))
    assert not bad, "broad handlers that hide a real fault:\n  " + "\n  ".join(bad)
