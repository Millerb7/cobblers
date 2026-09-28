#!/usr/bin/env python
"""The local-only inputs a checkout needs that git does not carry, and how to get them into a fresh one.

Some kit files cannot be committed (CLAUDE.md: only MIT-style sources are): the town kit's house templates, which are
copies of the vanilla, Cobblemon and Repurposed Structures jars' own structure files, and two F4 service buildings
whose licence is in doubt (kits/PROVENANCE.json). A fresh clone or an agent's worktree lacks them, and
`reapply.py prepare` fails on the first place that stamps one.

kits/LOCAL_ONLY.json lists each by path and sha256, with where it comes from:

  jar     the file is byte-identical to an entry in a jar the server already has; `hydrate` extracts it from
          --server-dir (mods/, and versions/<mc>/server-<mc>.jar for minecraft). Nothing is copied between checkouts.
  store   not reproducible from any jar; `hydrate` copies it from --store (a folder the owner keeps, or a checkout
          that has the file), and only when its sha256 matches.

    python tools/local_inputs.py check                                  # what is present, missing or wrong
    python tools/local_inputs.py hydrate --server-dir <server> [--store <dir>]
    python tools/local_inputs.py record --server-dir <server>           # rewrite the manifest from this checkout

Every file written is verified against the manifest's sha256; a mismatch is a failure, never a warning.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "kits" / "LOCAL_ONLY.json"
TOWNKIT = "kits/structures/incoming/townkit/"
MC = "1.21.1"
JARS = {                                   # namespace -> jar glob under the server dir
    "minecraft": "versions/%s/server-%s.jar" % (MC, MC),
    "cobblemon": "mods/Cobblemon-fabric-*.jar",
    "repurposed_structures": "mods/repurposed_structures-*.jar",
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def jar_for(server_dir, ns):
    hits = sorted(glob.glob(str(Path(server_dir) / JARS[ns])))
    if len(hits) != 1:
        raise SystemExit("%s: expected one jar matching %s under %s, found %d" % (ns, JARS[ns], server_dir, len(hits)))
    return Path(hits[0])


def load():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def check(_a=None):
    missing, wrong = [], []
    files = load()["files"]
    for f in files:
        p = ROOT / f["path"]
        if not p.is_file():
            missing.append(f["path"])
        elif sha(p.read_bytes()) != f["sha256"]:
            wrong.append(f["path"])
    print("local-only inputs: %d listed, %d present, %d missing, %d wrong" % (
        len(files), len(files) - len(missing) - len(wrong), len(missing), len(wrong)))
    for p in wrong:
        print("  WRONG   %s (sha256 differs from kits/LOCAL_ONLY.json)" % p)
    for p in missing[:10]:
        print("  MISSING %s" % p)
    if len(missing) > 10:
        print("  ... and %d more missing" % (len(missing) - 10))
    return 1 if missing or wrong else 0


def hydrate(a):
    files = load()["files"]
    zips = {}
    wrote = kept = 0
    need_store = []
    for f in files:
        dest = ROOT / f["path"]
        if dest.is_file() and sha(dest.read_bytes()) == f["sha256"]:
            kept += 1
            continue
        src = f["source"]
        if src["kind"] == "jar":
            if not a.server_dir:
                raise SystemExit("%s comes from a jar: pass --server-dir" % f["path"])
            ns = src["namespace"]
            if ns not in zips:
                zips[ns] = zipfile.ZipFile(jar_for(a.server_dir, ns))
            data = zips[ns].read(src["entry"])
        else:
            if not a.store:
                need_store.append(f["path"])
                continue
            p = Path(a.store) / f["path"]
            if not p.is_file():
                need_store.append(f["path"])
                continue
            data = p.read_bytes()
        if sha(data) != f["sha256"]:
            raise SystemExit("%s: the %s copy does not hash to the manifest's %s" % (f["path"], src["kind"],
                                                                                    f["sha256"][:12]))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        wrote += 1
    print("hydrated %d, already present %d" % (wrote, kept))
    if need_store:
        print("NOT hydrated (kind store; pass --store <a folder or checkout that has them>):")
        for p in need_store:
            print("  " + p)
        return 1
    return 0


def record(a):
    """Rewrite the manifest from the files this checkout holds; a townkit file must match its jar entry exactly."""
    out = subprocess.run(["git", "ls-files", "--others", "--ignored", "--exclude-standard", "kits/"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split("\n")
    prov = json.loads((ROOT / "kits" / "PROVENANCE.json").read_text(encoding="utf-8"))["records"]
    zips = {}
    files = []
    for rel in sorted(p for p in out if p.endswith(".nbt")):
        b = (ROOT / rel).read_bytes()
        rec = {"path": rel, "sha256": sha(b)}
        if rel.startswith(TOWNKIT):
            ns, rest = rel[len(TOWNKIT):].split("/", 1)
            if ns not in zips:
                zips[ns] = zipfile.ZipFile(jar_for(a.server_dir, ns))
            entry = "data/%s/structure/%s" % (ns, rest)
            if zips[ns].read(entry) != b:
                raise SystemExit("%s differs from %s in the %s jar: it is not a plain copy" % (rel, entry, ns))
            rec["source"] = {"kind": "jar", "namespace": ns, "entry": entry}
        else:
            why = next((r.get("source") for r in prov if rel in r.get("paths", [])), None)
            rec["source"] = {"kind": "store", "provenance": why or "not in kits/PROVENANCE.json"}
        files.append(rec)
    doc = {"note": "Kit files git does not carry (tools/local_inputs.py). jar: extracted from the server's own jar by "
                   "`hydrate --server-dir`; store: copied from a folder the owner keeps, by sha256.",
           "files": files}
    body = ",\n".join("  " + json.dumps(f) for f in files)
    MANIFEST.write_text('{"note": %s,\n "files": [\n%s\n]}\n' % (json.dumps(doc["note"]), body), encoding="utf-8")
    kinds = {}
    for f in files:
        kinds[f["source"]["kind"]] = kinds.get(f["source"]["kind"], 0) + 1
    print("wrote %s: %s" % (MANIFEST.relative_to(ROOT), kinds))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    h = sub.add_parser("hydrate")
    h.add_argument("--server-dir")
    h.add_argument("--store")
    r = sub.add_parser("record")
    r.add_argument("--server-dir", required=True)
    a = ap.parse_args(argv)
    return {"check": check, "hydrate": hydrate, "record": record}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
