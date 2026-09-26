#!/usr/bin/env python
"""Does the running server hold everything the repo builds for it: packs and configs?

Four times, work done in the repo never reached the running game: the compiled spawn tables, five config overlays
(the starters among them), the re-apply steps, and the structures pack, which was on the server only because it had
been copied there by hand (2026-09-26). This check makes "built but never installed" fail the same way a config
disagreement does. `tools/reapply.py install` runs it last and stops on any problem; CLAUDE.md runs it at session start.

  packs     every pack `tools/reapply.py` installs (SERVER_PACKS; WORLD_LOCAL, SPAWN_PACKS and WORLD_PACKS go into the
            world's folder) must be installed and byte-identical to its build; the patched COBBLEVERSE datapack must
            be the one `tools/patch_cobbleverse_riding.py` makes; and no `cobblers_*` pack may sit in the global folder
            unless the repo installs it there. The live world's own datapacks folder is never read (CLAUDE.md): pass
            --world-dir only for a staging or disposable world.
  configs   tools/server_config_record.py check

  python tools/install_check.py --server-dir <server> [--world-dir <staging world>]
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

PATCHED_DP = ROOT / "build" / "cobbleverse" / "COBBLEVERSE-DP-v31.zip"


def tree(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file()} if folder.is_dir() else None


def compare(name, built, installed):
    b, i = tree(built), tree(installed)
    if b is None:
        return ["%s: not built (%s missing); run `tools/reapply.py prepare`" % (name, built)]
    if i is None:
        return ["%s: built but NOT INSTALLED at %s" % (name, installed)]
    if b != i:
        missing = sorted(set(b) - set(i))
        extra = sorted(set(i) - set(b))
        diff = sorted(k for k in set(b) & set(i) if b[k] != i[k])
        return ["%s: installed copy differs from the build (%d missing, %d extra, %d changed; e.g. %s)"
                % (name, len(missing), len(extra), len(diff), (missing + extra + diff)[:3])]
    return []


def packs(server_dir, world_dir=None):
    import reapply as RA
    import runtime_guard
    server_dir = Path(server_dir)
    gdp = runtime_guard.check(server_dir / "datapacks", "read the installed packs in")
    problems = []
    world_local = set(RA.WORLD_LOCAL)
    for name in RA.SERVER_PACKS:
        if name in world_local:
            if world_dir:
                problems += compare(name, RA.PACKS / name, Path(world_dir) / "datapacks" / name)
            if (gdp / name).exists():
                problems.append("%s: in the global folder, but it belongs in the world's folder" % name)
        else:
            problems += compare(name, RA.PACKS / name, gdp / name)
    if world_dir:
        for name in RA.SPAWN_PACKS:
            if name == "cobblers_suppress":
                if not (Path(world_dir) / "datapacks" / name / "pack.mcmeta").is_file():
                    problems.append("cobblers_suppress: NOT INSTALLED in the world (it is generated at install)")
                continue
            problems += compare(name, RA.PACKS / name, Path(world_dir) / "datapacks" / name)
        for src in RA.WORLD_PACKS:
            problems += compare(src.name, src, Path(world_dir) / "datapacks" / src.name)
    expected_global = {n for n in RA.SERVER_PACKS if n not in world_local}
    for p in sorted(gdp.glob("cobblers_*")):
        if p.name not in expected_global:
            problems.append("%s: in the global folder (which the live world loads) but the repo does not install it "
                            "there" % p.name)
    dp = gdp / PATCHED_DP.name
    if not PATCHED_DP.is_file():
        problems.append("%s: the patched build is missing; run `tools/reapply.py install`" % PATCHED_DP.name)
    elif not dp.is_file() or hashlib.sha256(dp.read_bytes()).digest() != hashlib.sha256(PATCHED_DP.read_bytes()).digest():
        problems.append("%s: the server's copy is not the riding-patched build (tools/patch_cobbleverse_riding.py)"
                        % PATCHED_DP.name)
    return problems


def configs(server_dir):
    import server_config_record as SCR
    return SCR.check(Path(server_dir) / "config")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--server-dir", required=True)
    ap.add_argument("--world-dir", default=None, help="a staging or disposable world (never the live one)")
    a = ap.parse_args(argv)
    if a.world_dir:
        import runtime_guard
        runtime_guard.check(Path(a.world_dir) / "datapacks", "read the world's installed packs in")
    problems = [("PACK", m) for m in packs(a.server_dir, a.world_dir)] + [("CONFIG", m) for m in configs(a.server_dir)]
    for kind, m in problems:
        print("%s %s" % (kind, m))
    print("%d problems (packs and configs)" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
