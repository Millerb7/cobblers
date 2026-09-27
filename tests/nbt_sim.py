"""Test-side models for tests/test_blackout_recovery_pid.py: command storage as NBT, and a subset of MoLang.

Written by the test author from vanilla Minecraft 1.21.1 and Cobblemon MoLang semantics, not from the generator:

  NbtSim    tests/test_blackout_pack.py's Sim with command storage held as NBT, so `data modify|remove|get storage`,
            `execute if data storage` and `function ... with storage` run as Minecraft runs them. NBT paths are parsed
            by NbtPathArgument's grammar (a compound filter `{...}` may start a path or follow a name, never follow a
            list index or another filter: `scan[0]{a:1}` does not parse); `set` creates missing compounds and appends
            a list filter's pattern when nothing matches (getOrCreate); `set from` with no source element fails and
            changes nothing; filters match by tag type (1b is not 1); macro arguments render a string without quotes
            and anything else as SNBT (MacroFunction).
  Molang    a strict interpreter for the constructs the pack's callbacks use: `t.x = e;`, `cond ? { ... };`,
            `for_each(t.v, list, { ... });`, `return e;`, string `+`, comparisons, `&&`, `||`, `math.mod` and
            `q.run_command`, which is recorded. An unset temp variable reads 0 (MoLang); a context or query field the
            test did not provide raises, so a callback reading something the test did not model fails loudly.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

import test_blackout_pack as TB  # noqa: E402


# ------------------------------------------------------------------------------------------------ NBT values

class Byte(int):
    pass


class Short(int):
    pass


class Long(int):
    pass


class Float(float):
    pass


class IntArray(tuple):
    pass


class ByteArray(tuple):
    pass


class LongArray(tuple):
    pass


def same(a, b):
    """Tag equality, type included."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def matches(pattern, tag):
    """NbtUtils.compareNbt(pattern, tag, partial=true)."""
    if isinstance(pattern, dict):
        return isinstance(tag, dict) and all(k in tag and matches(v, tag[k]) for k, v in pattern.items())
    if isinstance(pattern, list):
        if not isinstance(tag, list):
            return False
        return all(any(matches(p, t) for t in tag) for p in pattern)
    return same(pattern, tag)


class SnbtError(ValueError):
    pass


BARE = re.compile(r"[A-Za-z0-9._+\-]+")
NUM = re.compile(r"^([+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)([bslfdBSLFD]?)$")


def parse_snbt(text, i=0, whole=True):
    """(value, end index) for the SNBT starting at text[i]."""
    def ws(j):
        while j < len(text) and text[j] in " \t\n":
            j += 1
        return j

    def quoted(j):
        q, out, j = text[j], [], j + 1
        while j < len(text):
            c = text[j]
            if c == "\\":
                out.append(text[j + 1])
                j += 2
                continue
            if c == q:
                return "".join(out), j + 1
            out.append(c)
            j += 1
        raise SnbtError("unterminated string in %r" % text)

    def value(j):
        j = ws(j)
        if j >= len(text):
            raise SnbtError("expected a value in %r" % text)
        c = text[j]
        if c == "{":
            out, j = {}, ws(j + 1)
            if text[j] == "}":
                return out, j + 1
            while True:
                j = ws(j)
                if text[j] in "\"'":
                    k, j = quoted(j)
                else:
                    m = BARE.match(text, j)
                    if not m:
                        raise SnbtError("bad key at %d in %r" % (j, text))
                    k, j = m.group(0), m.end()
                j = ws(j)
                if text[j] != ":":
                    raise SnbtError("expected ':' at %d in %r" % (j, text))
                out[k], j = value(j + 1)
                j = ws(j)
                if text[j] == ",":
                    j += 1
                    continue
                if text[j] == "}":
                    return out, j + 1
                raise SnbtError("expected ',' or '}' at %d in %r" % (j, text))
        if c == "[":
            j = ws(j + 1)
            kind = None
            if text[j:j + 2] in ("I;", "B;", "L;"):
                kind, j = text[j], ws(j + 2)
            items = []
            if text[j] == "]":
                j += 1
            else:
                while True:
                    v, j = value(j)
                    items.append(v)
                    j = ws(j)
                    if text[j] == ",":
                        j += 1
                        continue
                    if text[j] == "]":
                        j += 1
                        break
                    raise SnbtError("expected ',' or ']' at %d in %r" % (j, text))
            if kind:
                cls = {"I": IntArray, "B": ByteArray, "L": LongArray}[kind]
                return cls(int(v) for v in items), j
            return items, j
        if c in "\"'":
            return quoted(j)
        m = BARE.match(text, j)
        if not m:
            raise SnbtError("bad value at %d in %r" % (j, text))
        word, j = m.group(0), m.end()
        if word in ("true", "false"):
            return Byte(word == "true"), j
        n = NUM.match(word)
        if not n:
            return word, j                          # an unquoted string
        num, suf = n.group(1), n.group(2).lower()
        if suf == "b":
            return Byte(int(num)), j
        if suf == "s":
            return Short(int(num)), j
        if suf == "l":
            return Long(int(num)), j
        if suf == "f":
            return Float(num), j
        if suf == "d" or "." in num or "e" in num.lower():
            return float(num), j
        return int(num), j

    v, j = value(i)
    if whole:
        if ws(j) != len(text):
            raise SnbtError("trailing text in %r" % text)
        return v
    return v, j


def to_snbt(v):
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, Byte):
        return "%db" % v
    if isinstance(v, Short):
        return "%ds" % v
    if isinstance(v, Long):
        return "%dL" % v
    if isinstance(v, Float):
        return "%rf" % float(v)
    if isinstance(v, float):
        return "%rd" % v
    if isinstance(v, int):
        return str(v)
    if isinstance(v, IntArray):
        return "[I;%s]" % ",".join(str(x) for x in v)
    if isinstance(v, ByteArray):
        return "[B;%s]" % ",".join("%db" % x for x in v)
    if isinstance(v, LongArray):
        return "[L;%s]" % ",".join("%dL" % x for x in v)
    if isinstance(v, list):
        return "[%s]" % ",".join(to_snbt(x) for x in v)
    if isinstance(v, dict):
        return "{%s}" % ",".join("%s:%s" % (k if re.fullmatch(r"[A-Za-z0-9._+-]+", k) else json.dumps(k), to_snbt(x))
                                 for k, x in v.items())
    raise TypeError(v)


def macro_text(v):
    """How MacroFunction substitutes a tag: a string's own text, a number's digits, anything else as SNBT."""
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        raise TypeError(v)
    if isinstance(v, int):
        return str(int(v))
    if isinstance(v, float):
        return repr(float(v))
    return to_snbt(v)


# ------------------------------------------------------------------------------------------------ NBT paths

class PathError(ValueError):
    pass


UNQUOTED_STOP = set(" \"'[]{}.")


def parse_path(text):
    """NbtPathArgument.parse: [(kind, ...)] nodes; kind is root{}, key, keyf (name{filter}), all, idx, match."""
    nodes, i, first = [], 0, True
    while i < len(text) and text[i] != " ":
        c = text[i]
        if c == "{":
            if not first:
                raise PathError("a compound filter cannot follow a list index or a filter: %r" % text)
            f, i = parse_snbt(text, i, whole=False)
            nodes.append(("root", f))
        elif c == "[":
            i += 1
            if i < len(text) and text[i] == "]":
                nodes.append(("all",))
                i += 1
            elif i < len(text) and text[i] == "{":
                f, i = parse_snbt(text, i, whole=False)
                if text[i:i + 1] != "]":
                    raise PathError("expected ] in %r" % text)
                nodes.append(("match", f))
                i += 1
            else:
                m = re.match(r"-?\d+", text[i:])
                if not m or text[i + m.end():i + m.end() + 1] != "]":
                    raise PathError("bad index in %r" % text)
                nodes.append(("idx", int(m.group(0))))
                i += m.end() + 1
        else:
            if c in "\"'":
                q, j = c, i + 1
                while j < len(text) and text[j] != q:
                    j += 2 if text[j] == "\\" else 1
                name, i = text[i + 1:j], j + 1
            else:
                j = i
                while j < len(text) and text[j] not in UNQUOTED_STOP:
                    j += 1
                if j == i:
                    raise PathError("empty name at %d in %r" % (i, text))
                name, i = text[i:j], j
            if i < len(text) and text[i] == "{":
                f, i = parse_snbt(text, i, whole=False)
                nodes.append(("keyf", name, f))
            else:
                nodes.append(("key", name))
        first = False
        if i < len(text):
            c = text[i]
            if c not in " [{":
                if c != ".":
                    raise PathError("expected '.' at %d in %r" % (i, text))
                i += 1
    if not nodes:
        raise PathError("empty path")
    return nodes


def _step(values, node):
    out = []
    for v in values:
        k = node[0]
        if k == "root":
            if matches(node[1], v):
                out.append(v)
        elif k == "key":
            if isinstance(v, dict) and node[1] in v:
                out.append(v[node[1]])
        elif k == "keyf":
            if isinstance(v, dict) and node[1] in v and matches(node[2], v[node[1]]):
                out.append(v[node[1]])
        elif k == "all":
            if isinstance(v, (list, tuple)):
                out.extend(v)
        elif k == "idx":
            if isinstance(v, (list, tuple)) and -len(v) <= node[1] < len(v):
                out.append(v[node[1]])
        elif k == "match":
            if isinstance(v, list):
                out.extend(e for e in v if matches(node[1], e))
    return out


def path_get(root, nodes):
    vals = [root]
    for n in nodes:
        vals = _step(vals, n)
    return vals


def _preferred_parent(next_node):
    return [] if next_node[0] in ("all", "idx", "match") else {}


def _get_or_create(root, nodes):
    """The parents for the last node, creating what getOrCreate creates."""
    vals = [root]
    for i, n in enumerate(nodes[:-1]):
        nxt = nodes[i + 1]
        out = []
        for v in vals:
            if n[0] == "key" and isinstance(v, dict):
                if n[1] not in v:
                    v[n[1]] = _preferred_parent(nxt)
                out.append(v[n[1]])
            elif n[0] == "keyf" and isinstance(v, dict):
                if n[1] not in v:
                    v[n[1]] = copy.deepcopy(n[2])
                if matches(n[2], v[n[1]]):
                    out.append(v[n[1]])
            elif n[0] == "match" and isinstance(v, list):
                hit = [e for e in v if matches(n[1], e)]
                if not hit:
                    v.append(copy.deepcopy(n[1]))
                    hit = [v[-1]]
                out.extend(hit)
            else:
                out.extend(_step([v], n))
        vals = out
    return vals


def path_set(root, nodes, value):
    """Number of tags changed."""
    last, n = nodes[-1], 0
    for parent in _get_or_create(root, nodes):
        if last[0] == "key" and isinstance(parent, dict):
            if not (last[1] in parent and same(parent[last[1]], value)):
                n += 1
            parent[last[1]] = copy.deepcopy(value)
        elif last[0] == "idx" and isinstance(parent, list) and -len(parent) <= last[1] < len(parent):
            parent[last[1]] = copy.deepcopy(value)
            n += 1
        elif last[0] in ("keyf", "match", "all", "root"):
            raise NotImplementedError("set on a %s node" % last[0])
    return n


def path_append(root, nodes, values):
    last = nodes[-1]
    n = 0
    for parent in _get_or_create(root, nodes):
        if last[0] == "key" and isinstance(parent, dict):
            if last[1] not in parent:
                parent[last[1]] = []
            target = [parent[last[1]]]
        else:
            target = _step([parent], last)
        for t in target:
            if isinstance(t, list):
                t.extend(copy.deepcopy(v) for v in values)
                n += len(values)
    return n


def path_remove(root, nodes):
    last, n = nodes[-1], 0
    for parent in path_get(root, nodes[:-1]) if len(nodes) > 1 else [root]:
        if last[0] == "key" and isinstance(parent, dict) and last[1] in parent:
            del parent[last[1]]
            n += 1
        elif last[0] == "keyf" and isinstance(parent, dict) and last[1] in parent and matches(last[2], parent[last[1]]):
            del parent[last[1]]
            n += 1
        elif last[0] == "idx" and isinstance(parent, list) and -len(parent) <= last[1] < len(parent):
            parent.pop(last[1])
            n += 1
        elif last[0] == "match" and isinstance(parent, list):
            keep = [e for e in parent if not matches(last[1], e)]
            n += len(parent) - len(keep)
            parent[:] = keep
        elif last[0] == "all" and isinstance(parent, list):
            n += len(parent)
            parent.clear()
    return n


# ------------------------------------------------------------------------------------------------ the simulator

FAIL = object()


class Res:
    def __init__(self, result, success):
        self.result, self.success = result, success


class NbtSim(TB.Sim):
    """TB.Sim with command storage as NBT. `world(kind, toks)` answers entity, block and `on` tests;
    `entity(selector, path)` answers `data ... from entity` (None: no such entity or path)."""

    def __init__(self, fns=None, query=None, world=None, entity=None):
        super().__init__(fns=fns, query=query, cond=self._cond)
        self.nbt = {}
        self.world = world or (lambda kind, toks: False)
        self.entity = entity or (lambda sel, path: None)
        self.ret = None
        self.last_ret = None
        self.failed = []

    def root(self, ns):
        return self.nbt.setdefault(ns, {})

    def sget(self, ns, path):
        return path_get(self.root(ns), parse_path(path))

    def call(self, name, args=None):
        outer, self.ret = self.ret, None
        super().call(name, args)
        self.last_ret, self.ret = self.ret, outer
        return self.last_ret

    def args_from(self, rest):
        if rest.startswith("with storage "):
            _, _, ns, path = rest.split(" ", 3)
            vals = self.sget(ns, path)
            assert vals and isinstance(vals[-1], dict), "no compound at %s %s for a macro call" % (ns, path)
            return {k: macro_text(v) for k, v in vals[-1].items()}
        if rest.startswith("with "):
            raise AssertionError("simulator: %s" % rest)
        return TB.inline_args(rest)

    def _cond(self, kind, toks):
        if kind == "data" and toks[0] == "storage":
            return bool(self.sget(toks[1], toks[2]))
        return self.world(kind, toks)

    def store(self, st, v):
        if isinstance(v, Res):
            v = v.result if st[0] == "result" else v.success
        if st[1] == "score":
            return super().store(st, v)
        ns, path, typ, scale = st[2], st[3], st[4], float(st[5])
        n = v * scale
        tag = {"int": lambda: int(n), "byte": lambda: Byte(int(n)), "short": lambda: Short(int(n)),
               "long": lambda: Long(int(n)), "float": lambda: Float(n), "double": lambda: float(n)}[typ]()
        path_set(self.root(ns), parse_path(path), tag)

    def value(self, cmd):
        t = cmd.split(" ")
        if t[0] == "function":
            self.last_ret = None
            self.command(cmd)
            r = self.last_ret
            if r is FAIL:
                return Res(0, 0)
            return Res(0 if r is None else r, 1)
        if t[:3] == ["data", "get", "storage"]:
            vals = self.sget(t[3], t[4])
            assert vals, "data get of nothing: %s" % cmd
            v = vals[0]
            return len(v) if isinstance(v, (dict, list, tuple, str)) else v
        return super().value(cmd)

    def command(self, cmd):
        t = cmd.split(" ")
        if t[0] == "return":
            if t[1] == "fail":
                self.ret = FAIL
            elif t[1] == "run":
                self.command(" ".join(t[2:]))
                self.ret = 1
            else:
                self.ret = int(t[1])
            return TB.RETURN
        if t[0] == "data":
            return self.data(cmd, t)
        return super().command(cmd)

    def data(self, cmd, t):
        if t[2] in ("entity", "block"):
            self.log.append(cmd)                          # entity writes: what a server does
            return None
        if t[1] == "remove" and t[2] == "storage":
            if not path_remove(self.root(t[3]), parse_path(t[4])):
                self.failed.append(cmd)
            return None
        if t[1] == "modify" and t[2] == "storage":
            ns, path, op = t[3], t[4], t[5]
            rest = cmd.split(" ", 6)[6]
            if rest.startswith("value "):
                vals = [parse_snbt(rest[len("value "):])]
            elif rest.startswith("from storage "):
                _, _, sns, spath = rest.split(" ", 3)
                vals = self.sget(sns, spath)
            elif rest.startswith("from entity "):
                _, _, sel, epath = rest.split(" ", 3)
                v = self.entity(sel, epath)
                vals = [] if v is None else [v]
            else:
                raise AssertionError("simulator: data modify source %r" % rest)
            if not vals:
                self.failed.append(cmd)                   # "found no elements matching": nothing changes
                return None
            nodes = parse_path(path)
            if op == "set":
                path_set(self.root(ns), nodes, vals[-1])
            elif op == "append":
                path_append(self.root(ns), nodes, vals)
            else:
                raise AssertionError("simulator: data modify %s" % op)
            return None
        raise AssertionError("simulator: %s" % cmd)


# ------------------------------------------------------------------------------------------------ MoLang subset

class MolangError(ValueError):
    pass


TOKEN = re.compile(r"\s*(?:(?P<str>'[^']*')|(?P<num>\d+(?:\.\d+)?)|(?P<id>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
                   r"|(?P<op>==|!=|<=|>=|&&|\|\||[-+*/<>=?:;,(){}!]))")


def tokenize(src):
    out, i = [], 0
    while True:
        while i < len(src) and src[i] in " \t\r\n":
            i += 1
        if i >= len(src):
            return out
        m = TOKEN.match(src, i)
        if not m or m.end() == i:
            raise MolangError("unknown character %r at %d" % (src[i], i))
        kind = m.lastgroup
        out.append((kind, m.group(kind)))
        i = m.end()


class _Return(Exception):
    def __init__(self, v):
        self.v = v


class Molang:
    """Runs one callback script against `context` (c.) and `query` (q.) as nested dicts and lists."""

    def __init__(self, src):
        self.toks = tokenize(src)
        self.i = 0
        self.prog = self.block_body(end=None)

    # ---- parser
    def peek(self, k=0):
        return self.toks[self.i + k] if self.i + k < len(self.toks) else (None, None)

    def eat(self, want=None):
        tok = self.peek()
        if tok[0] is None or (want is not None and tok[1] != want):
            raise MolangError("expected %r, got %r" % (want, tok))
        self.i += 1
        return tok

    def block_body(self, end):
        stmts = []
        while True:
            tok = self.peek()
            if tok[0] is None:
                if end is not None:
                    raise MolangError("unterminated block")
                return stmts
            if tok[1] == end and tok[0] == "op":
                return stmts
            if tok == ("op", ";"):
                self.eat()
                continue
            stmts.append(self.statement())
            if self.peek() != ("op", ";") and self.peek()[1] != end:
                raise MolangError("expected ';' after a statement, got %r" % (self.peek(),))

    def statement(self):
        tok = self.peek()
        if tok == ("id", "return"):
            self.eat()
            return ("return", self.expr())
        if tok[0] == "id" and self.peek(1) == ("op", "="):
            name = self.eat()[1]
            self.eat("=")
            return ("assign", name.lower(), self.expr())
        return ("expr", self.expr())

    def expr(self):
        cond = self.or_()
        if self.peek() == ("op", "?"):
            self.eat()
            then = self.branch()
            other = None
            if self.peek() == ("op", ":"):
                self.eat()
                other = self.branch()
            return ("if", cond, then, other)
        return cond

    def branch(self):
        if self.peek() == ("op", "{"):
            self.eat()
            body = self.block_body("}")
            self.eat("}")
            return ("block", body)
        return self.or_()

    def binary(self, sub, ops):
        left = sub()
        while self.peek()[0] == "op" and self.peek()[1] in ops:
            op = self.eat()[1]
            left = ("bin", op, left, sub())
        return left

    def or_(self):
        return self.binary(self.and_, ("||",))

    def and_(self):
        return self.binary(self.eq, ("&&",))

    def eq(self):
        return self.binary(self.cmp, ("==", "!="))

    def cmp(self):
        return self.binary(self.add, ("<", ">", "<=", ">="))

    def add(self):
        return self.binary(self.unary, ("+", "-"))

    def unary(self):
        if self.peek() == ("op", "!"):
            self.eat()
            return ("not", self.unary())
        return self.primary()

    def primary(self):
        kind, v = self.peek()
        if kind == "num":
            self.eat()
            return ("lit", float(v))
        if kind == "str":
            self.eat()
            return ("lit", v[1:-1])
        if (kind, v) == ("op", "("):
            self.eat()
            e = self.expr()
            self.eat(")")
            return e
        if (kind, v) == ("op", "{"):
            return self.branch()
        if kind == "id":
            self.eat()
            name = v.lower()
            if self.peek() == ("op", "("):
                self.eat()
                if name == "for_each":
                    var = self.eat()[1].lower()
                    self.eat(",")
                    lst = self.expr()
                    self.eat(",")
                    body = self.branch()
                    self.eat(")")
                    return ("for_each", var, lst, body)
                args = []
                if self.peek() != ("op", ")"):
                    while True:
                        args.append(self.expr())
                        if self.peek() == ("op", ","):
                            self.eat()
                            continue
                        break
                self.eat(")")
                return ("call", name, args)
            return ("path", name)
        raise MolangError("unexpected %r" % ((kind, v),))

    # ---- evaluator
    def run(self, context=None, query=None):
        self.temp, self.context, self.query, self.commands = {}, context or {}, query or {}, []
        try:
            self.exec_block(self.prog)
        except _Return:
            pass
        return self.commands

    def exec_block(self, stmts):
        for s in stmts:
            if s[0] == "return":
                raise _Return(self.ev(s[1]))
            if s[0] == "assign":
                parts = s[1].split(".")
                if parts[0] not in ("t", "temp") or len(parts) != 2:
                    raise MolangError("assignment to %s" % s[1])
                self.temp[parts[1]] = self.ev(s[2])
            else:
                self.ev(s[1])

    def lookup(self, name):
        parts = name.split(".")
        head = parts[0]
        if head in ("t", "temp"):
            if parts[1] not in self.temp:
                if len(parts) > 2:
                    raise MolangError("field of an unset variable: %s" % name)
                return 0.0
            v, rest = self.temp[parts[1]], parts[2:]
        elif head in ("c", "context"):
            v, rest = self.context, parts[1:]
        elif head in ("q", "query"):
            v, rest = self.query, parts[1:]
        else:
            raise MolangError("unknown root %s" % name)
        for p in rest:
            if not isinstance(v, dict) or p not in v:
                raise MolangError("the test did not model %s (at %s)" % (name, p))
            v = v[p]
        return v

    @staticmethod
    def num(v):
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        if isinstance(v, (int, float)):
            return float(v)
        raise MolangError("not a number: %r" % (v,))

    def truthy(self, v):
        return self.num(v) != 0.0

    def ev(self, e):
        k = e[0]
        if k == "lit":
            return e[1]
        if k == "path":
            return self.lookup(e[1])
        if k == "block":
            self.exec_block(e[1])
            return 0.0
        if k == "if":
            if self.truthy(self.ev(e[1])):
                return self.ev(e[2])
            return self.ev(e[3]) if e[3] is not None else 0.0
        if k == "not":
            return 0.0 if self.truthy(self.ev(e[1])) else 1.0
        if k == "for_each":
            lst = self.ev(e[2])
            if not isinstance(lst, list):
                raise MolangError("for_each over %r" % (lst,))
            var = e[1].split(".")
            if var[0] not in ("t", "temp") or len(var) != 2:
                raise MolangError("for_each variable %s" % e[1])
            for item in lst:
                self.temp[var[1]] = item
                self.ev(e[3])
            return 0.0
        if k == "call":
            args = [self.ev(a) for a in e[2]]
            if e[1] in ("q.run_command", "query.run_command"):
                assert isinstance(args[0], str), args
                self.commands.append(args[0])
                return 1.0
            if e[1] == "math.mod":
                return float(self.num(args[0]) % self.num(args[1]))
            raise MolangError("unknown function %s" % e[1])
        if k == "bin":
            op = e[1]
            if op == "&&":
                return 1.0 if self.truthy(self.ev(e[2])) and self.truthy(self.ev(e[3])) else 0.0
            if op == "||":
                return 1.0 if self.truthy(self.ev(e[2])) or self.truthy(self.ev(e[3])) else 0.0
            a, b = self.ev(e[2]), self.ev(e[3])
            if op == "+":
                if isinstance(a, str) or isinstance(b, str):
                    if not (isinstance(a, str) and isinstance(b, str)):
                        raise MolangError("string + non-string: %r + %r" % (a, b))
                    return a + b
                return self.num(a) + self.num(b)
            if op in ("==", "!="):
                eq = (a == b) if isinstance(a, str) and isinstance(b, str) else \
                    (not isinstance(a, str) and not isinstance(b, str) and self.num(a) == self.num(b))
                return 1.0 if eq == (op == "==") else 0.0
            a, b = self.num(a), self.num(b)
            if op == "-":
                return a - b
            return 1.0 if {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op] else 0.0
        raise MolangError("cannot evaluate %r" % (e,))
