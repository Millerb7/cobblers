#!/usr/bin/env python
"""Assemble a disposable client instance from the base manifest plus overlay.

The command is a dry run unless --apply is supplied. It never downloads files;
use pack_manifest.py download --replacements-only for overlay jars first.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pack_manifest


def copy_tree(source: Path, target: Path, apply: bool) -> int:
    if not source.is_dir():
        return 0
    files = [p for p in source.rglob("*") if p.is_file()]
    if apply:
        shutil.copytree(source, target, dirs_exist_ok=True)
    return len(files)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", default=str(pack_manifest.DEFAULT_PACK_DIR))
    parser.add_argument("--replacements-dir")
    parser.add_argument("--target", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--clean", action="store_true", help="remove jars not present in the effective client plan")
    args = parser.parse_args(argv)

    base_dir = Path(args.base_dir)
    replacements_dir = Path(args.replacements_dir) if args.replacements_dir else None
    target = Path(args.target)
    base = pack_manifest.load_json(pack_manifest.BASE_MANIFEST)
    overlay = pack_manifest.load_json(pack_manifest.OVERLAY)
    plan = pack_manifest.active(pack_manifest.build_plan(base, overlay, side="client", kind="mod"))

    missing = []
    sources = {}
    for entry in plan:
        candidates = []
        if replacements_dir:
            candidates.append(replacements_dir / entry["filename"])
        candidates.append(base_dir / "mods" / entry["filename"])
        source = next((p for p in candidates if p.is_file()), None)
        if source is None:
            missing.append(entry["filename"])
        else:
            sources[entry["filename"]] = source

    print(f"mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print(f"target: {target}")
    print(f"client jars: {len(plan)} planned, {len(missing)} missing")
    for name in missing:
        print(f"MISSING {name}")
    if missing:
        return 1

    mods_dir = target / "mods"
    if args.apply:
        mods_dir.mkdir(parents=True, exist_ok=True)
        for name, source in sources.items():
            shutil.copy2(source, mods_dir / name)
        if args.clean:
            wanted = set(sources)
            for jar in mods_dir.glob("*.jar"):
                if jar.name not in wanted:
                    jar.unlink()

    asset_counts = {}
    for name in ("config", "resourcepacks", "datapacks", "shaderpacks"):
        count = copy_tree(base_dir / name, target / name, args.apply)
        count += copy_tree(pack_manifest.ROOT / "modpack" / name, target / name, args.apply)
        asset_counts[name] = count

    if args.apply:
        verify_plan = {e["filename"]: e for e in plan}
        for jar in mods_dir.glob("*.jar"):
            entry = verify_plan[jar.name]
            algorithm = next((k for k in ("sha512", "sha256", "sha1") if entry.get(k)), None)
            if not algorithm or pack_manifest.hash_file(jar)[algorithm] != entry[algorithm]:
                raise SystemExit(f"hash verification failed: {jar.name}")

    print("assets: " + ", ".join(f"{name}={count}" for name, count in asset_counts.items()))
    print("client assembly verified" if args.apply else "dry run complete; pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
