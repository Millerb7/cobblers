#!/usr/bin/env python
"""The loot tables that exist on the server: every data/<ns>/loot_table(s)/**.json in the installed mods, the global
datapacks and our own built packs, plus vanilla's (the server jar, when one is found). See tools/loot_fix.py."""
from __future__ import annotations

import glob
import json
import os
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = Path(os.environ.get("COBBLERS_SERVER_DIR", "C:/Users/wnd/Documents/github/cobblers-server"))
_RX = re.compile(r"^data/([^/]+)/loot_tables?/(.+)\.json$")


def _from_names(names):
    out = set()
    for n in names:
        m = _RX.match(n.replace("\\", "/"))
        if m:
            out.add("%s:%s" % (m.group(1), m.group(2)))
    return out


def _from_zip(path):
    try:
        with zipfile.ZipFile(path) as z:
            names = list(z.namelist())
            found = _from_names(names)
            # a mod jar nests its own jars (jar-in-jar); their tables are loaded too
            for n in names:
                if n.startswith("META-INF/jarjar/") and n.endswith(".jar"):
                    try:
                        import io
                        with zipfile.ZipFile(io.BytesIO(z.read(n))) as inner:
                            found |= _from_names(inner.namelist())
                    except (zipfile.BadZipFile, OSError):
                        pass
            return found
    except (zipfile.BadZipFile, OSError):
        return set()


def _from_dir(path):
    base = Path(path)
    return _from_names(str(p.relative_to(base)) for p in base.rglob("*.json") if "loot_table" in str(p))


def existing(server_dir=None, extra_dirs=()):
    """(set of table ids, {source: count}). Reads mods/, datapacks/ (global packs, never a world folder) and the
    built packs in build/datapacks; vanilla's tables come from versions/*/*.jar or server.jar when present."""
    server = Path(server_dir) if server_dir else SERVER
    tables, by_source = set(), {}
    for j in sorted(glob.glob(str(server / "mods" / "*.jar"))):
        t = _from_zip(j)
        if t:
            tables |= t
            by_source[os.path.basename(j)] = len(t)
    for p in sorted(glob.glob(str(server / "datapacks" / "*"))):
        t = _from_zip(p) if p.endswith(".zip") else (_from_dir(p) if os.path.isdir(p) else set())
        if t:
            tables |= t
            by_source["datapacks/" + os.path.basename(p)] = len(t)
    for jar in glob.glob(str(server / "versions" / "*" / "*.jar")) + glob.glob(str(server / "*.jar")):
        t = _from_zip(jar)
        if t:
            tables |= t
            by_source[os.path.basename(jar)] = len(t)
    for d in list(extra_dirs) + [ROOT / "build" / "datapacks"]:
        d = Path(d)
        if d.is_dir():
            t = _from_dir(d)
            if t:
                tables |= t
                by_source["build:" + d.name] = len(t)
    return tables, by_source


if __name__ == "__main__":
    t, src = existing()
    print(len(t), "tables")
    for k, v in sorted(src.items(), key=lambda kv: -kv[1])[:25]:
        print(v, k)
