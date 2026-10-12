#!/usr/bin/env python
"""Every pack tools/reapply.py installs, classified `runtime` or `build`, from the BUILT packs.

WHY (2026-10-12, measured on staging by the orchestrator; relayed): the idle heap was 12.4 GB with nobody online, ~7-8 GB
of it Brigadier's parsed commands, and the parsed-line class had 6,491,795 instances against 6,563,647 installed function
lines: Minecraft keeps every function of every loaded pack parsed for as long as the pack is loaded. Most of those lines
are one-shot placement (a re-apply step runs them once over RCON), and a pack nothing calls at play time can leave the
datapacks folders after the run (`reapply.py strip`) and come back with `reapply.py install`.

A pack is `build` only when ALL of these hold; anything else is `runtime`:
  - none of its functions is reachable from a runtime root;
  - it carries no runtime data (advancements, Cobblemon callbacks, dialogues, NPCs, loot tables, recipes, predicates,
    item modifiers, spawn pools, worldgen, dimensions, trainers ... every kind but functions, function tags, block tags
    and structure templates, and any kind this tool does not know);
  - none of its block tags or structure templates is named by a reachable function or by runtime data;
  - no file of it sits at a path another installed pack also ships (an override: which one wins depends on pack order,
    and a pack taken out and put back is re-enabled in a different place).

Runtime roots: the minecraft:tick and minecraft:load function tags; every function id or function tag named anywhere in a
runtime data file (an advancement's reward, a callback's run_command, a dialogue's action, ...) or in the repo's
modpack/config and server/config; every function id named INSIDE a quoted string or NBT/JSON of any function line (a
command block's Command, a sign's or a text component's click event, an NPC script: those fire in the world after the
build has run); and every function a structure template names (a command block in a template).

Edges, across packs: `function X`, `execute ... run function X`, `execute if function X`, `schedule function X`,
`return run function X`, and a macro line's `$function a:b/$(c)` (every function the pattern can match). A function tag
reaches its values. FAIL-CLOSED: a reference this tool cannot resolve (`function $(f)`, `run $(cmd)`, a callback that
builds a function name from a variable) reaches EVERY function, and the report names it.

Apply-time roots (NOT runtime): the functions tools/reapply.py's steps run. They are reported per step (`steps`: the packs
each step's call closure needs), so `reapply.py run` can refuse a step whose pack has been stripped.

  python tools/pack_roles.py                         # build/datapacks -> build/pack_roles.json (a prepare job)
  python tools/pack_roles.py --packs <dir> --out <file> [--no-steps]
  python tools/pack_roles.py --summary               # print the table only

What it does NOT cover: a function an operator or another tool runs by hand over RCON (`ambient_idle t/<s>/cleanup`, the
probes); functions named only in another mod's own data outside the repo's configs; and anything a world already holds
from a pack that is no longer built. Those are why strip MOVES packs and install puts them back, never deletes.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
BUILD = ROOT / "build"
DEFAULT_PACKS = BUILD / "datapacks"
DEFAULT_OUT = BUILD / "pack_roles.json"
CONFIG_DIRS = (ROOT / "modpack" / "config", ROOT / "server" / "config")

ROOT_TAGS = ("minecraft:tick", "minecraft:load")
# kinds that are inert until something names them: a function (reachability decides), a function tag (a node of the
# graph), a block tag and a structure template (a reference from runtime decides). Every other kind is runtime data.
INERT_KINDS = ("function", "tags/function", "tags/block", "structure")

ID_CHARS = r"[a-z0-9_.\-]"
PATH_CHARS = r"[a-z0-9_./\-]|\$\([a-z0-9_]+\)"
ID_TOKEN = re.compile(r"#?%s+:(?:%s)+" % (ID_CHARS, PATH_CHARS))
CALL_ARG = re.compile(r"\s+(#?(?:%s+:)?(?:%s)+)(?=\s|$)" % (ID_CHARS, PATH_CHARS))
WORD_FUNCTION = re.compile(r"(?<![a-z0-9_:./\-])function(?![a-z0-9_:\-])")
DYNAMIC_IN_TEXT = re.compile(r"function\s*['\"]?\s*\+|function\s+\$\([a-z0-9_]+\)(?![a-z0-9_./\-])")


def kind_of(rel_parts):
    """data/<ns>/<kind...>: 'function', 'tags/function', 'tags/block', 'structure', ... from the parts after data/."""
    if len(rel_parts) < 3:
        return "?"
    if rel_parts[1] == "tags" and len(rel_parts) > 3:
        return "tags/" + (rel_parts[2] if rel_parts[2] != "worldgen" else "worldgen/" + rel_parts[3])
    return rel_parts[1]


def resource_id(rel_parts, kind, suffix):
    ns = rel_parts[0]
    skip = 1 + len(kind.split("/"))
    path = "/".join(rel_parts[skip:])
    return "%s:%s" % (ns, path[:-len(suffix)] if suffix and path.endswith(suffix) else path)


def _mask(line):
    """(top level text with quoted and bracketed spans blanked, [the blanked spans]). A function call at top level is a
    call; a function id inside a span is embedded in a string or NBT and fires later, wherever that string ends up."""
    top, spans, buf = [], [], []
    depth, quote, esc = 0, None, False
    for ch in line:
        inside = depth > 0 or quote is not None
        if quote is not None:
            buf.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                quote = None
                if depth == 0:
                    spans.append("".join(buf))
                    buf = []
            top.append(" ")
            continue
        if ch in "\"'" and (depth > 0 or not top or not top[-1].isalnum()):
            quote = ch
            buf.append(ch)
            top.append(" ")
            continue
        if ch in "{[":
            depth += 1
            buf.append(ch)
            top.append(" ")
            continue
        if ch in "}]" and depth > 0:
            depth -= 1
            buf.append(ch)
            top.append(" ")
            if depth == 0:
                spans.append("".join(buf))
                buf = []
            continue
        if inside:
            buf.append(ch)
            top.append(" ")
        else:
            top.append(ch)
    if buf:
        spans.append("".join(buf))
    return "".join(top), spans


def scan_line(line):
    """One command -> (calls, embedded, unresolved). calls: ids (or patterns with $(x)) the command runs; embedded: ids
    named inside its strings and NBT; unresolved: a call this cannot resolve (fail closed: it reaches everything)."""
    s = line.strip()
    if not s or s.startswith("#"):
        return [], [], []
    macro = s.startswith("$")
    if macro:
        s = s[1:]
    top, spans = _mask(s)
    calls, unresolved = [], []
    if macro and (top.lstrip().startswith("$(") or re.search(r"\brun\s+\$\(", top)):
        unresolved.append(s[:160])                       # the command itself is a macro value
    for m in WORD_FUNCTION.finditer(top):
        a = CALL_ARG.match(top, m.end())
        if not a:
            unresolved.append(s[:160])
            continue
        ref = a.group(1)
        if ref.lstrip("#").startswith("$("):
            unresolved.append(s[:160])
            continue
        if ":" not in ref:
            ref = ("#minecraft:" + ref[1:]) if ref.startswith("#") else "minecraft:" + ref
        if "$(" in ref and not macro:
            unresolved.append(s[:160])
            continue
        calls.append(ref)
    embedded = []
    for sp in spans:
        embedded += ID_TOKEN.findall(sp)
        if DYNAMIC_IN_TEXT.search(sp):
            unresolved.append(s[:160])
    return calls, embedded, unresolved


def pattern_re(ref):
    """A reference with $(x) in it, as a regex over function ids."""
    parts = re.split(r"\$\([a-z0-9_]+\)", ref)
    return re.compile("^" + "[a-z0-9_./\\-]*".join(re.escape(p) for p in parts) + "$")


class Graph:
    def __init__(self):
        self.functions = {}        # id -> pack
        self.lines = {}            # id -> command lines (non-blank, non-comment)
        self.files = {}            # id -> path
        self.tags = {}             # '#ns:path' -> [refs]
        self.tag_pack = {}         # '#ns:path' -> [packs]
        self.edges = {}            # id or tag -> set of refs
        self.roots = {}            # ref -> why (first reason)
        self.unresolved = []       # (where, text)
        self.everything_from = []  # functions with an unresolved call
        self.inert = {}            # block tag '#id' / structure 'id' -> [(pack, kind)]
        self.runtime_data = {}     # pack -> {kind: count}
        self.unknown = {}          # pack -> [kinds]
        self.paths = {}            # 'data/...' relative path -> [packs]
        self.tag_replace = {}      # 'data/.../tags/...json' -> True when any copy says replace:true
        self.pack_lines = {}
        self.pack_functions = {}

    def root(self, ref, why):
        self.roots.setdefault(ref, why)


def _text(p):
    return p.read_text(encoding="utf-8", errors="replace")


def scan_runtime_text(g, text, where):
    """Every function or function tag a runtime data file (or a config) names is a root."""
    for tok in ID_TOKEN.findall(text):
        g.root(tok, "named by %s" % where)
    for m in DYNAMIC_IN_TEXT.finditer(text):
        g.unresolved.append((where, text[max(0, m.start() - 60):m.end() + 60].replace("\n", " ")))
        g.root("*", "an unresolved function reference in %s" % where)


def load(packs):
    """packs: [(name, path)] -> Graph. Reads every file of every pack once."""
    g = Graph()
    texts = []                                           # (where, text) of runtime data, scanned once ids are known
    structures = []
    for name, pdir in packs:
        g.pack_lines[name] = 0
        g.pack_functions[name] = 0
        data = Path(pdir) / "data"
        if not data.is_dir():
            continue
        for f in sorted(data.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(data).parts
            relpath = "data/" + "/".join(rel)
            g.paths.setdefault(relpath, []).append(name)
            kind = kind_of(rel)
            if kind.startswith("tags/") and f.suffix == ".json":
                try:
                    rep = json.loads(_text(f)).get("replace") is True
                except (ValueError, AttributeError):
                    rep = True                           # unreadable: assume it overrides (fail closed)
                if rep:
                    g.tag_replace[relpath] = True
            if kind == "function" and f.suffix == ".mcfunction":
                fid = resource_id(rel, kind, ".mcfunction")
                g.functions[fid] = name
                g.files[fid] = f
                raw = f.read_bytes()
                n = 0
                calls = set()
                for line in raw.decode("utf-8", errors="replace").split("\n"):
                    t = line.strip()
                    if not t or t.startswith("#"):
                        continue
                    n += 1
                    if "function" not in t and not (t.startswith("$") and "$(" in t[1:]):
                        continue
                    c, e, u = scan_line(t)
                    calls.update(c)
                    for ref in e:
                        g.root(ref, "named inside a string or NBT in %s" % fid)
                    if u:
                        g.unresolved += [(fid, x) for x in u]
                        g.everything_from.append(fid)
                        calls.add("*")
                g.lines[fid] = n
                g.pack_lines[name] += n
                g.pack_functions[name] += 1
                g.edges[fid] = calls
            elif kind == "tags/function" and f.suffix == ".json":
                tid = "#" + resource_id(rel, kind, ".json")
                try:
                    vals = json.loads(_text(f)).get("values") or []
                except ValueError:
                    vals = ["*"]
                    g.unresolved.append((relpath, "unparseable function tag"))
                refs = [v if isinstance(v, str) else (v.get("id") or "*") for v in vals]
                g.tags.setdefault(tid, []).extend(refs)
                g.tag_pack.setdefault(tid, []).append(name)
                g.edges.setdefault(tid, set()).update(refs)
                if tid.lstrip("#") in ROOT_TAGS:
                    g.root(tid, "the %s tag of %s" % (tid, name))
            elif kind == "function":
                # a generator's own index.txt beside its functions: tooling, never loaded by the game
                g.inert.setdefault("%s (file)" % relpath, []).append((name, kind))
            elif kind == "tags/block":
                g.inert.setdefault("#" + resource_id(rel, kind, ".json"), []).append((name, kind))
            elif kind == "structure":
                sid = resource_id(rel, kind, ".nbt")
                g.inert.setdefault(sid, []).append((name, kind))
                structures.append((name, sid, f))
            else:
                if kind not in ("advancement", "recipe", "loot_table", "predicate", "item_modifier", "callbacks",
                                "dialogues", "dialogs", "npcs", "trainers", "mobs", "series", "spawn_pool_world",
                                "habitat_pools", "species_additions", "dimension", "dimension_type", "enchantment") \
                        and not kind.startswith("worldgen") and not kind.startswith("tags/"):
                    g.unknown.setdefault(name, []).append(kind)
                g.runtime_data.setdefault(name, {})
                g.runtime_data[name][kind] = g.runtime_data[name].get(kind, 0) + 1
                if f.suffix in (".json", ".molang", ".js", ".txt", ".mcmeta"):
                    texts.append(("%s %s" % (name, relpath), _text(f)))
    for where, text in texts:
        scan_runtime_text(g, text, where)
    # a command block in a template names its command in the NBT: the template is gzip; its strings are UTF-8
    for name, sid, f in structures:
        try:
            raw = gzip.decompress(f.read_bytes())
        except OSError:
            raw = f.read_bytes()
        if b"function" in raw:
            for tok in ID_TOKEN.findall(raw.decode("utf-8", errors="replace")):
                g.root(tok, "named inside the structure template %s (%s)" % (sid, name))
    return g


def config_text(g, dirs=CONFIG_DIRS):
    for d in dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        for f in d.rglob("*"):
            if f.is_file() and f.suffix in (".json", ".json5", ".toml", ".yml", ".yaml", ".txt", ".properties", ".cfg", ".conf"):
                t = _text(f)
                if "function" in t:
                    scan_runtime_text(g, t, str(f.relative_to(ROOT) if ROOT in f.parents else f))


def resolve(g, ref):
    """The graph nodes a reference stands for: a function id, a function tag, a pattern, a prefix ending in '/', or
    '*' (everything). A reference to nothing we ship resolves to nothing (another mod's function)."""
    if ref == "*":
        return list(g.functions)
    if ref.startswith("#"):
        if "$(" in ref:
            rx = pattern_re(ref)
            return [t for t in g.tags if rx.match(t)]
        return [ref] if ref in g.tags else []
    if "$(" in ref:
        rx = pattern_re(ref)
        return [f for f in g.functions if rx.match(f)]
    if ref in g.functions:
        return [ref]
    if ref.endswith("/"):
        return [f for f in g.functions if f.startswith(ref)]
    return []


def reach(g, starts, parents=None):
    """Every function and function tag reachable from the references `starts`. parents, when a dict, is filled with
    node -> the node (or root reference) it was first reached from, for `--why`."""
    seen, todo = set(), []
    for r in starts:
        for x in resolve(g, r):
            todo.append(x)
            if parents is not None:
                parents.setdefault(x, "ROOT %s (%s)" % (r, g.roots.get(r, "a start")))
    everything = False
    while todo:
        n = todo.pop()
        if n in seen:
            continue
        seen.add(n)
        for ref in g.edges.get(n, ()):
            if ref == "*":
                everything = True
            for x in resolve(g, ref):
                if x not in seen:
                    todo.append(x)
                    if parents is not None:
                        parents.setdefault(x, n)
        if everything:
            seen.update(g.functions)
            seen.update(g.tags)
            break
    return seen


def why_reachable(g, node, parents):
    """The chain from a runtime root to node, root first."""
    chain = [node]
    while chain[-1] in parents and len(chain) < 200:
        p = parents[chain[-1]]
        chain.append(p)
        if p.startswith("ROOT "):
            break
    return list(reversed(chain))


def inert_used(g, reachable):
    """{inert id: why} for every block tag or template named by a reachable function or by runtime data."""
    want = set(g.inert)
    used = {}
    for ref, why in g.roots.items():
        if ref in want and not why.startswith("named inside a string"):
            used.setdefault(ref, why)
    bare = {i.lstrip("#"): i for i in want}
    for fid in sorted(x for x in reachable if x in g.files):
        t = _text(g.files[fid])
        for tok in ID_TOKEN.findall(t):
            if tok in want:
                used.setdefault(tok, "named by the runtime function %s" % fid)
            elif tok in bare:
                used.setdefault(bare[tok], "named by the runtime function %s" % fid)
    return used


def override(g, relpath):
    """Does a file two packs ship at this path make pack order matter? A generator's index.txt is never loaded; a tag
    file merges its values with the other packs' unless one says replace:true; anything else is last-wins."""
    if relpath.endswith("/index.txt"):
        return False
    parts = relpath.split("/")
    if len(parts) > 3 and parts[2] == "tags" and relpath.endswith(".json"):
        return bool(g.tag_replace.get(relpath))
    return True


def classify(packs, step_functions=None, config_dirs=CONFIG_DIRS):
    """packs: [(name, dir)] the install loads together. step_functions: {step id: [function ids]} or None.
    Returns the report dict (see build/pack_roles.json)."""
    g = load(packs)
    config_text(g, config_dirs)
    reachable = reach(g, list(g.roots))
    used = inert_used(g, reachable)
    out = {"generated_by": "tools/pack_roles.py", "packs": {}, "unresolved": [list(x) for x in g.unresolved],
           "everything_reachable": "*" in g.roots or any(
               "*" in g.edges.get(f, ()) for f in reachable if f in g.functions)}
    for name, _d in packs:
        why = []
        fr = sorted(f for f, p in g.functions.items() if p == name and f in reachable)
        if fr:
            why.append("%d function(s) reachable at runtime, e.g. %s" % (len(fr), ", ".join(fr[:3])))
        rd = g.runtime_data.get(name)
        if rd:
            why.append("runtime data: %s" % ", ".join("%s %d" % kv for kv in sorted(rd.items())))
        for k in g.unknown.get(name, []):
            why.append("a kind this tool does not know (fail closed): %s" % k)
        for i, owners in sorted(g.inert.items()):
            if any(p == name for p, _k in owners) and i in used:
                why.append("%s is used at runtime (%s)" % (i, used[i]))
        shared = sorted({rel for rel, ps in g.paths.items() if name in ps and len(set(ps)) > 1 and override(g, rel)})
        if shared:
            others = sorted({p for rel in shared for p in g.paths[rel] if p != name})
            why.append("%d file(s) at a path %s also ship(s), e.g. %s" % (len(shared), ", ".join(others), shared[0]))
        out["packs"][name] = {
            "role": "runtime" if why else "build",
            "why": why,
            "functions": g.pack_functions.get(name, 0),
            "lines": g.pack_lines.get(name, 0),
            "reachable_functions": len(fr),
            "reachable_lines": sum(g.lines[f] for f in fr),
        }
    total = sum(v["lines"] for v in out["packs"].values())
    bl = sum(v["lines"] for v in out["packs"].values() if v["role"] == "build")
    out["totals"] = {"lines": total, "build_lines": bl, "runtime_lines": total - bl,
                     "build_packs": sorted(n for n, v in out["packs"].items() if v["role"] == "build"),
                     "build_share": round(bl / total, 4) if total else 0.0}
    if step_functions is not None:
        steps = {}
        for sid, fns in step_functions.items():
            seen = reach(g, fns)
            steps[sid] = sorted({g.functions[f] for f in seen if f in g.functions}
                                | {p for t in seen if t in g.tag_pack for p in g.tag_pack[t]})
        out["steps"] = steps
        for name, rec in out["packs"].items():
            rec["apply_steps"] = sorted(s for s, ps in steps.items() if name in ps)
    return out


def installed_packs(packs_dir):
    """[(name, dir)]: what tools/reapply.py install copies, from its own lists; a name not built is reported, not
    guessed (install refuses an unbuilt pack itself)."""
    import reapply as R
    names = list(R.SERVER_PACKS) + list(R.SPAWN_PACKS)
    out = [(n, Path(packs_dir) / n) for n in names]
    for w in R.WORLD_PACKS:
        p = Path(w)
        out.append((p.name, Path(packs_dir) / p.name if p.parent == R.PACKS else p))
    return out


def step_functions(packs_dir):
    """{step id: [function ids]}: what tools/reapply.py's steps run (apply-time roots), --with-spawns included so every
    step a run can select is covered. Function ids from `fn` actions, `cmd` actions and the scene props' place."""
    import reapply as R
    R.PACKS = Path(packs_dir)
    R.REAPPLY = R.PACKS / "cobblers_reapply"
    out = {}
    for sid, _t, acts in R.steps(True):
        fns = []
        for k, v in acts:
            if k == "fn":
                fns.append(v)
            elif k == "cmd" and isinstance(v, str):
                c, _e, u = scan_line(v)
                fns += c + (["*"] if u else [])
            elif k == "props":
                fns.append("cobblers:scenes/")
        out[sid] = fns
    return out


def summary(rep):
    rows = sorted(rep["packs"].items(), key=lambda kv: (kv[1]["role"], -kv[1]["lines"]))
    lines = ["%-32s %-8s %9s  %s" % ("pack", "role", "lines", "why (first)")]
    for n, v in rows:
        lines.append("%-32s %-8s %9d  %s" % (n, v["role"], v["lines"], (v["why"][:1] or [""])[0][:110]))
    t = rep["totals"]
    lines.append("build: %d pack(s), %d of %d lines (%.1f%%)" % (len(t["build_packs"]), t["build_lines"], t["lines"],
                                                                 100.0 * t["build_share"]))
    if rep["unresolved"]:
        lines.append("unresolved references (fail closed, reach everything): %d, e.g. %s" % (
            len(rep["unresolved"]), rep["unresolved"][0]))
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--packs", default=str(DEFAULT_PACKS), help="the built packs (default build/datapacks)")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--no-steps", action="store_true", help="skip the re-apply steps' closure (needs the built indexes)")
    p.add_argument("--summary", action="store_true", help="print the table; write nothing")
    p.add_argument("--why", nargs="+", metavar="FUNCTION_OR_PREFIX",
                   help="print the chain from a runtime root to each named function (a prefix ending in / takes its "
                        "first 5 reachable functions); write nothing")
    a = p.parse_args(argv)
    packs = installed_packs(a.packs)
    missing = [str(d) for _n, d in packs if not (Path(d) / "pack.mcmeta").is_file()]
    if missing:
        raise SystemExit("pack_roles: %d installed pack(s) are not built, nothing classified:\n  %s"
                         % (len(missing), "\n  ".join(missing)))
    if a.why:
        g = load(packs)
        config_text(g)
        parents = {}
        seen = reach(g, list(g.roots), parents)
        for w in a.why:
            hits = [w] if not w.endswith("/") else sorted(f for f in g.functions if f.startswith(w) and f in seen)[:5]
            for h in hits:
                print("%s: %s" % (h, " -> ".join(why_reachable(g, h, parents)) if h in seen else "NOT reachable at runtime"))
        return 0
    sf = None if a.no_steps else step_functions(a.packs)
    rep = classify(packs, sf)
    rep["packs_dir"] = str(Path(a.packs))
    if rep["everything_reachable"]:
        print("pack_roles: an unresolved reference is reachable at runtime, so EVERY pack is runtime (fail closed)")
    print(summary(rep))
    if not a.summary:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(rep, indent=1, sort_keys=True), encoding="utf-8")
        print("wrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
