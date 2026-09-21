#!/usr/bin/env python
"""Derive each roster entry's spawnable position type from the installed Cobblemon jar and write it
into data/spawns.json as `spawnable_position`.

Why: tools/compile_spawns.py used to hardcode "grounded" for every compiled entry. 28 authored
species never spawn on dry land in Cobblemon's own data — Magikarp, Gyarados, Basculin, Goldeen,
Barboach, Whiscash, Shellder, Surskit and the rest — so they were being asked to stand on the ground
and almost certainly never appeared at all.

The rule, applied per species against Cobblemon's own spawn_pool_world data:
  - count the position types the species actually uses upstream, ignoring "fishing" (that needs a rod)
  - if it has any dry-land entry, it keeps "grounded"
  - otherwise it takes its most-used water position ("submerged", "surface" or "seafloor")
  - a species with no upstream data at all keeps "grounded" and is reported

The value is written into data/spawns.json so the decision is reviewable in the authored source
rather than recomputed at compile time from whatever jar happens to be installed.

  python tools/position_types.py --jar <Cobblemon jar> --check   # report what would change
  python tools/position_types.py --jar <Cobblemon jar>           # write data/spawns.json

Ownership: writes data/spawns.json entries' `spawnable_position` only; it never touches rosters,
weights, buckets or levels.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JAR_GLOB = "Cobblemon-fabric-*.jar"


def default_jar():
    """The installed Cobblemon jar, from COBBLERS_SERVER_ROOT; the runtime path is never hard-coded."""
    root = os.environ.get("COBBLERS_SERVER_ROOT")
    if not root:
        return None
    found = sorted(Path(root, "mods").glob(JAR_GLOB))
    return found[-1] if found else None


WATER_POS = ("submerged", "surface", "seafloor")
WATER_BLOCK = re.compile(r"water|lily|coral|kelp|seagrass")


def upstream_positions(jar):
    """{species: Counter(position type)} from Cobblemon's own spawn files, "fishing" dropped.

    An entry that stands on land but requires water nearby still counts as dry land: the species can
    be met on foot.
    """
    out = {}
    with zipfile.ZipFile(jar) as z:
        for n in z.namelist():
            if "/spawn_pool_world/" not in n or not n.endswith(".json"):
                continue
            try:
                doc = json.loads(z.read(n).decode("utf-8"))
            except Exception:
                continue
            for s in (doc.get("spawns") or []):
                parts = (s.get("pokemon") or "").split()
                if not parts:
                    continue
                pos = s.get("spawnablePositionType", "grounded")
                if pos == "fishing":
                    continue
                out.setdefault(parts[0].lower(), Counter())[pos] += 1
    return out


def choose(species, positions):
    """(position type, reason)."""
    c = positions.get(species.split()[0].lower())
    if not c:
        return "grounded", "no upstream spawn data"
    dry = sum(v for k, v in c.items() if k not in WATER_POS)
    if dry:
        return "grounded", "%d of %d upstream entries are on dry land" % (dry, sum(c.values()))
    best = max((k for k in c if k in WATER_POS), key=lambda k: c[k])
    return best, "every upstream entry is in water; %s is the most used (%d of %d)" % (best, c[best], sum(c.values()))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--spawns", default=str(ROOT / "data" / "spawns.json"))
    p.add_argument("--jar", default=None, help="Cobblemon jar; defaults to $COBBLERS_SERVER_ROOT/mods/" + JAR_GLOB)
    p.add_argument("--check", action="store_true", help="report only, write nothing")
    a = p.parse_args(argv)
    path = Path(a.spawns)
    spawns = json.loads(path.read_text(encoding="utf-8"))
    jar = a.jar or default_jar()
    if not jar:
        raise SystemExit("no Cobblemon jar: pass --jar, or set COBBLERS_SERVER_ROOT")
    positions = upstream_positions(jar)
    changed, unknown = [], []
    for e in spawns["entries"]:
        pos, why = choose(e["species"], positions)
        if why == "no upstream spawn data":
            unknown.append(e["species"])
        if e.get("spawnable_position") != pos:
            changed.append((e["scope"], e["species"], e.get("spawnable_position") or "grounded (implicit)", pos, why))
        e["spawnable_position"] = pos
    wet = [c for c in changed if c[3] != "grounded"]
    print("entries %d, changed %d, moved off dry land %d" % (len(spawns["entries"]), len(changed), len(wet)))
    for scope, sp, old, new, why in wet:
        print("  %-28s %-14s -> %-10s %s" % (scope, sp, new, why))
    if unknown:
        print("no upstream data, left grounded: %s" % " ".join(sorted(set(unknown))))
    if a.check:
        return 0
    path.write_text(json.dumps(spawns, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
