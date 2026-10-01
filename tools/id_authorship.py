#!/usr/bin/env python
"""Every id that two files in data/ both carry a record for, against data/id_authorship.json.

WHY THIS EXISTS. git merges text. Two branches that author the same ids in DIFFERENT FILES do not
conflict, so the merge is clean, the diff is clean, and the collision is invisible until something that
reads both files reasons over two rival values for one thing. On 2026-10-01 main's #96 generated roster
records for Victory Road's ten (data/trainers.json) while this branch carried their stands
(data/vr_trainers.json); the tenth ended up with two names, two teams and two sets of lines. Nothing
reported it. tools/route_trainers.py refused to emit, with a SystemExit, during pytest collection, and
the whole 5,200-test suite reported `no tests ran` and an INTERNALERROR for six hours instead of a
failure count. The collision cost nothing to make and most of a day to find.

So: a record is an object with a string `id` sitting directly in a top-level array of a data document,
and two files carrying a record for one id are either

  a DECLARED SPACE   -- two halves of one thing, read together by one tool, each owning its own fields
                        (data/trainers.json is a trainer's roster; a seat file is its stand), or
  a DECLARED OVERLAP -- an id two systems both describe in their own terms, listed id by id with the
                        fields they both carry and why that is not two authors for one value, or
  A FAULT.

An overlap is declared by its exact id set, not by a count or a tolerance: an id that joins one fails
and is named. Nothing here is a threshold, and nothing may be widened to make the data pass -- a class
that is really two authors for one value is fixed or recorded as a finding, never blessed.

  python tools/id_authorship.py              # report; exit 1 on any fault
  python tools/id_authorship.py --declare    # print the declaration the data would need (to review BY HAND)

Also runs as `python tools/validate.py --only duplicate_ids`, from tests/test_id_authorship.py, and from
.githooks/post-merge, which is the one that matters: the fault it hunts is made by a merge.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = "data/id_authorship.json"


def records(root: Path = ROOT) -> dict:
    """{id: {file: [record, ...]}} over every top-level array of objects in data/."""
    out: dict[str, dict[str, list]] = {}
    for p in sorted((root / "data").rglob("*.json")):
        rel = p.relative_to(root).as_posix()
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue                      # tools/validate.py json_parses owns malformed files
        if not isinstance(doc, dict):
            continue
        for arr in doc.values():
            if not isinstance(arr, list):
                continue
            for o in arr:
                if isinstance(o, dict) and isinstance(o.get("id"), str):
                    out.setdefault(o["id"], {}).setdefault(rel, []).append(o)
    return out


def registry(root: Path = ROOT) -> dict:
    return json.loads((root / REGISTRY).read_text(encoding="utf-8"))


def _space_of(reg: dict, fa: str, fb: str):
    for s in reg["spaces"]:
        files = {s["owner"]} | set(s["satellites"])
        if fa in files and fb in files:
            return s
    return None


def _local(reg: dict, f: str) -> bool:
    """A file whose record ids are its own: each gym's build plan names its own door_bay and gallery."""
    return any(f == g or (g.endswith("/*.json") and f.startswith(g[:-7] + "/")) for g in reg["file_local_ids"])


def shared_fields(a: dict, b: dict) -> list[str]:
    """Fields both records carry with DIFFERENT values. Equal values are not two authors of anything."""
    return sorted(f for f in set(a) & set(b) - {"id"} if a[f] != b[f])


def pairs(recs: dict, reg: dict):
    """[(file a, file b, id, [fields authored in both])] for every cross-file record, a < b."""
    out = []
    for rid, byfile in sorted(recs.items()):
        files = sorted(byfile)
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                fa, fb = files[i], files[j]
                if _local(reg, fa) and _local(reg, fb):
                    continue
                fields = sorted({f for a in byfile[fa] for b in byfile[fb] for f in shared_fields(a, b)})
                out.append((fa, fb, rid, fields))
    return out


def problems(recs: dict, reg: dict) -> list[str]:
    bad = []
    declared = {(o["files"][0], o["files"][1], f): set(o["ids"]) for o in reg["overlaps"] for f in o["fields"]}
    seen: dict = {}
    for fa, fb, rid, fields in pairs(recs, reg):
        space = _space_of(reg, fa, fb)
        if space is not None:
            owner = space["owner"]
            sat = fb if fa == owner else fa
            for f in fields:
                mode = ("satellite" if f in space["satellite_fields"] else
                        "echo" if f in space["echo_fields"] else
                        "precedence" if f in space["precedence_fields"] else None)
                if mode is None:
                    bad.append("%s: %s and %s both author %s, which the %s space declares for neither. "
                               "The owner (%s) holds %s; the satellite (%s) holds %s."
                               % (rid, fa, fb, f, space["id"], owner, space["owner_is"], sat,
                                  space["satellite_is"]))
                elif mode == "echo":
                    bad.append("%s: %s restates %s's %s and no longer matches it (declared an echo in the "
                               "%s space, which means it must be identical or move to its owner)"
                               % (rid, sat, owner, f, space["id"]))
                elif mode == "satellite":
                    bad.append("%s: %s carries %s, which the %s space gives the satellite (%s)"
                               % (rid, owner, f, space["id"], sat))
            continue
        for f in fields:
            seen.setdefault((fa, fb, f), set()).add(rid)
    for (fa, fb, f), ids in sorted(seen.items()):
        if (fa, fb, f) not in declared:
            bad.append("%s and %s both author %s for %d id(s) (%s) and %s declares no overlap for it. "
                       "Either one of the two values is dead -- say which file owns it -- or the two "
                       "fields mean different things and only share a name, which the registry records "
                       "id by id." % (fa, fb, f, len(ids), ", ".join(sorted(ids)[:4]), REGISTRY))
            continue
        new = ids - declared[(fa, fb, f)]
        if new:
            bad.append("%s and %s now both author %s for %d id(s) that %s does not list: %s. A record "
                       "for an id that already exists in another file is how a clean merge hides a "
                       "collision -- check which file owns the value before adding it to the registry."
                       % (fa, fb, f, len(new), REGISTRY, ", ".join(sorted(new))))
        gone = declared[(fa, fb, f)] - ids
        if gone:
            bad.append("%s lists %d id(s) as a declared %s overlap between %s and %s that no longer "
                       "overlap: %s. Drop them from the registry." % (REGISTRY, len(gone), f, fa, fb,
                                                                      ", ".join(sorted(gone))))
    return bad


def declare(recs: dict, reg: dict) -> str:
    """The overlaps block the data would need. Printed for a HUMAN to read, cut down and give reasons to."""
    seen: dict = {}
    for fa, fb, rid, fields in pairs(recs, reg):
        if _space_of(reg, fa, fb) is not None:
            continue
        for f in fields:
            seen.setdefault((fa, fb), {}).setdefault(f, set()).add(rid)
    out = []
    for (fa, fb), byf in sorted(seen.items()):
        for f, ids in sorted(byf.items()):
            out.append({"files": [fa, fb], "fields": [f], "ids": sorted(ids),
                        "why": "UNREVIEWED -- say why this is not two authors for one value"})
    return json.dumps(out, indent=1, ensure_ascii=False)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--root", default=str(ROOT))
    p.add_argument("--declare", action="store_true", help="print the declaration the data would need")
    a = p.parse_args(argv)
    root = Path(a.root)
    recs, reg = records(root), registry(root)
    if a.declare:
        print(declare(recs, reg))
        return 0
    bad = problems(recs, reg)
    cross = sum(1 for _fa, _fb, _i, f in pairs(recs, reg) if f)
    for b in bad:
        print("FAULT  " + b)
    print("\n%d ids, %d carried by more than one file, %d cross-file records share a field, "
          "%d space(s) and %d declared overlap(s), %d fault(s)"
          % (len(recs), sum(1 for b in recs.values() if len(b) > 1), cross,
             len(reg["spaces"]), len(reg["overlaps"]), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
