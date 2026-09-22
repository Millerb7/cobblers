#!/usr/bin/env python
"""The ground rule, checked by AST over every tool: no tool reads a world to decide where something goes.

CLAUDE.md: every tool that decides a position takes its ground from tools/ground.py or measured plan data, never
from a world save, because a world holds whatever was built into it last. Reading a world to CHECK a result is
allowed and required.

The previous detector (tests/test_ground_rule.py until 2026-09-21) scanned a hand-maintained list of 14 tools for
`import world_heights` and `module.extract()` / `module.capture()`. It missed a direct import-then-call
(`from structure_nbt import capture; capture(...)`), any read through a helper (build_audit.World, nbt.region_chunks),
and every tool not on its list (Codex review). This one:

  1. parses every tools/*.py and builds a call graph: `import m as a` then `a.f()`, `from m import f as g` then
     `g()`, a local `f()`, and a class constructed (`m.C(...)` counts as calling every method of C);
  2. seeds it with the primitives that open a world's region files: nbt.region_chunks, and any function whose body
     names a region file (a `.mca` string);
  3. marks every function that reaches a primitive, to a fixed point;
  4. requires every such function to be declared by its own tool, in a module-level `WORLD_READS` set of function
     names, as a check. A tool that reads a world anywhere it did not declare fails; so does a declaration of a
     function that does not read a world (stale).

A declared name means a reviewer has seen that function reads a world only to check. The declarations live beside
the code they excuse, not in a list in a test.

  python tools/ground_rule.py            # report; exit 1 on an undeclared or stale world read
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
PRIMITIVES = {("nbt", "region_chunks")}


class Module:
    def __init__(self, name, tree):
        self.name = name
        self.tree = tree
        self.aliases = {}          # local name -> module name
        self.imported = {}         # local name -> (module, attr)
        self.funcs = {}            # qualified name within module -> node (functions, and "Class" for classes)
        self.classes = {}          # class name -> [method names]
        self.declared = set()


def _index(name, tree):
    m = Module(name, tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                m.aliases[(a.asname or a.name).split(".")[0]] = a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                m.imported[a.asname or a.name] = (node.module.split(".")[0], a.name)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            m.funcs[node.name] = node
        elif isinstance(node, ast.ClassDef):
            m.funcs[node.name] = node
            m.classes[node.name] = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "WORLD_READS" for t in node.targets):
            try:
                m.declared = set(ast.literal_eval(node.value))
            except ValueError:
                pass
    return m


def _calls(mod, node, modules):
    """Every (module, function) a node's body calls or hands on (a function passed to a pool is used, not called),
    resolved through the module's imports."""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and isinstance(n.ctx, ast.Load):
            base = n.value.id
            if base in mod.aliases:
                out.add((mod.aliases[base], n.attr))
            elif base in mod.imported:                       # from pkg import module; module.f()
                out.add((mod.imported[base][1], n.attr))
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            if n.id in mod.imported:
                out.add(mod.imported[n.id])
            elif n.id in mod.funcs:
                out.add((mod.name, n.id))
    return out


def _is_main_guard(node):
    return (isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__")


def _names_a_region_file(node):
    return any(isinstance(n, ast.Constant) and isinstance(n.value, str) and ".mca" in n.value for n in ast.walk(node))


def analyse(tools_dir=TOOLS, sources=None):
    """{module: {"reads": set of top-level names that read a world, "declared": set}}. `sources` ({name: text})
    replaces the files, for tests."""
    if sources is None:
        # this analyser names region files itself; it reads none
        sources = {p.stem: p.read_text(encoding="utf-8") for p in sorted(Path(tools_dir).glob("*.py"))
                   if p.stem != "ground_rule"}
    modules = {name: _index(name, ast.parse(text)) for name, text in sources.items()}
    reads = set()
    for mname, mod in modules.items():
        for fname, node in mod.funcs.items():
            if _names_a_region_file(node):
                reads.add((mname, fname))
    reads |= {p for p in PRIMITIVES if p[0] in modules}
    # module-level code counts as the pseudo-function "<module>"
    bodies = {}
    for mname, mod in modules.items():
        for fname, node in mod.funcs.items():
            calls = _calls(mod, node, modules)
            bodies[(mname, fname)] = calls
        top = ast.Module(body=[n for n in mod.tree.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                               and not _is_main_guard(n)], type_ignores=[])
        bodies[(mname, "<module>")] = _calls(mod, top, modules)
    # a call to a method of a class counts as a call to the class, and constructing it calls its methods
    for mname, mod in modules.items():
        for cname, methods in mod.classes.items():
            for (tm, tf), calls in list(bodies.items()):
                if (mname, cname) in calls:
                    calls |= {(mname, m) for m in methods}
    changed = True
    while changed:
        changed = False
        for caller, calls in bodies.items():
            if caller not in reads and any(c in reads or (c[0] in modules and c[1] in modules[c[0]].classes
                                                          and (c[0], c[1]) in reads) for c in calls):
                reads.add(caller)
                changed = True
        # a class reads a world when a method of it does (methods are indexed by the class name)
        for mname, mod in modules.items():
            for cname, node in mod.classes.items():
                if (mname, cname) not in reads and _names_a_region_file(mod.funcs[cname]):
                    reads.add((mname, cname))
                    changed = True
    out = {}
    for mname, mod in modules.items():
        r = {f for (m, f) in reads if m == mname}
        if r or mod.declared:
            out[mname] = {"reads": r, "declared": set(mod.declared)}
    return out


def problems(result):
    out = []
    for mname, v in sorted(result.items()):
        undeclared = v["reads"] - v["declared"]
        stale = v["declared"] - v["reads"]
        if undeclared:
            out.append("%s.py reads a world in %s and does not declare it in WORLD_READS" % (mname, sorted(undeclared)))
        if stale:
            out.append("%s.py declares %s in WORLD_READS, which do not read a world" % (mname, sorted(stale)))
    return out


def main(argv=None):
    res = analyse()
    for mname, v in sorted(res.items()):
        print("%-22s reads a world in %s" % (mname, sorted(v["reads"])))
    bad = problems(res)
    for p in bad:
        print("GROUND RULE  %s" % p)
    print("%d tools read a world; %d problems" % (len(res), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
