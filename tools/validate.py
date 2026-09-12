#!/usr/bin/env python
"""validate.py - structural checks on tracked pack/campaign content.

Stdlib only. Walks:
  modpack/                       our overlay (manifests, config, datapacks, ...)
  campaign/                      campaign content (if it exists yet)
  world/                         authored world assets and structure manifests
  base-pack/cobbleverse/config   base config snapshot
  base-pack/cobbleverse/datapacks  base datapacks, including inside .zip files

Checks (see CHECKS at the bottom):
  json_parses           every .json / .mcmeta parses; .json5 / .toml are parsed only if a
                        parser module is importable, otherwise just their presence is noted
  datapack_pack_mcmeta  every datapack (folder or zip) has a pack.mcmeta at its root
  duplicate_basenames   warning when the same file name appears twice inside one
                        data/<namespace>/<registry> tree
  hash_csv_wellformed   base-pack/inventory/pack_hashes.csv has the expected columns,
                        64-hex sha256, integer sizes, unique paths
  manifest_sanity       modpack/manifest/*.json have the expected top-level shape

Issues under base-pack/ are reported as warnings by default (we do not own that
content); pass --strict-base to make them errors.

Extension points: the CHECKS registry. Structure dependencies have a real schema
and check; future campaign checks (duplicate ids, missing Pokemon references,
broken encounter/trainer/reward references, invalid progression dependencies)
remain registered as stubs until their content schemas exist.

Exit code: 1 if any error, else 0.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import struct
import sys
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WALK_ROOTS = [
    "modpack",
    "data",
    "kits",
    "base-pack/cobbleverse/config",
    "base-pack/cobbleverse/datapacks",
]
HASH_CSV = ROOT / "base-pack" / "inventory" / "pack_hashes.csv"
STRUCTURE_MANIFEST = Path("kits/structures/manifests/structure-dependencies.json")
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "cache"}

try:  # optional parsers
    import tomllib as _toml  # Python 3.11+
except ImportError:  # pragma: no cover
    try:
        import tomli as _toml  # type: ignore
    except ImportError:
        _toml = None
try:
    import json5 as _json5  # type: ignore
except ImportError:
    _json5 = None


@dataclass
class Issue:
    level: str  # "error" | "warning" | "info"
    path: str
    message: str


@dataclass
class Entry:
    """One file, on disk or inside a zip. `rel` is repo-relative (zip members: 'x.zip!inner/path')."""

    rel: str
    name: str
    read: object  # callable -> bytes


class Context:
    def __init__(self, root: Path, strict_base: bool):
        self.root = root
        self.strict_base = strict_base
        self.entries: list[Entry] = []
        self.datapacks: dict[str, set[str]] = {}  # datapack root (rel) -> set of member paths
        self.issues: list[Issue] = []

    def add(self, level: str, path: str, message: str) -> None:
        if level == "error" and not self.strict_base and path.startswith("base-pack/"):
            level = "warning"
        self.issues.append(Issue(level, path, message))


# ---------------------------------------------------------------- collection
def collect(ctx: Context) -> None:
    for r in WALK_ROOTS:
        base = ctx.root / r
        if not base.exists():
            ctx.add("info", r, "not present (skipped)")
            continue
        for p in sorted(base.rglob("*")):
            if any(part in SKIP_DIRS for part in p.relative_to(ctx.root).parts):
                continue
            if not p.is_file():
                continue
            rel = p.relative_to(ctx.root).as_posix()
            if p.suffix.lower() == ".zip":
                collect_zip(ctx, p, rel)
            else:
                ctx.entries.append(Entry(rel, p.name, lambda p=p: p.read_bytes()))
    # datapack folders: any dir that contains pack.mcmeta or lives directly under a datapacks/ root
    for r in ("modpack/datapacks", "base-pack/cobbleverse/datapacks", "campaign"):
        base = ctx.root / r
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            if d.is_dir() and d.name not in ("extra",) and (d / "pack.mcmeta").exists() or (d.is_dir() and (d / "data").is_dir()):
                rel = d.relative_to(ctx.root).as_posix()
                ctx.datapacks[rel] = {q.relative_to(d).as_posix() for q in d.rglob("*") if q.is_file()}


def collect_zip(ctx: Context, path: Path, rel: str) -> None:
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        ctx.add("error", rel, f"bad zip: {exc}")
        return
    names = [n for n in zf.namelist() if not n.endswith("/")]
    if "datapacks/" in rel + "/" or "/datapacks/" in "/" + rel:
        ctx.datapacks[rel] = set(names)
    for n in names:
        ctx.entries.append(Entry(f"{rel}!{n}", n.rsplit("/", 1)[-1], lambda zf=zf, n=n: zf.read(n)))


# -------------------------------------------------------------------- checks
def check_json_parses(ctx: Context) -> None:
    counts = defaultdict(int)
    for e in ctx.entries:
        low = e.name.lower()
        if low.endswith((".json", ".mcmeta")):
            counts["json"] += 1
            try:
                json.loads(e.read().decode("utf-8-sig"))
            except (ValueError, UnicodeDecodeError) as exc:
                ctx.add("error", e.rel, f"invalid JSON: {exc}")
        elif low.endswith(".json5"):
            counts["json5"] += 1
            if _json5 is not None:
                try:
                    _json5.loads(e.read().decode("utf-8-sig"))
                except Exception as exc:  # json5 raises ValueError subclasses
                    ctx.add("error", e.rel, f"invalid JSON5: {exc}")
        elif low.endswith(".toml"):
            counts["toml"] += 1
            if _toml is not None:
                try:
                    _toml.loads(e.read().decode("utf-8-sig"))
                except Exception as exc:
                    ctx.add("error", e.rel, f"invalid TOML: {exc}")
    ctx.add(
        "info",
        "-",
        f"parsed {counts['json']} json/mcmeta; {counts['json5']} json5 ({'parsed' if _json5 else 'presence only, no json5 module'}); "
        f"{counts['toml']} toml ({'parsed' if _toml else 'presence only, no tomllib/tomli'})",
    )


def check_datapack_pack_mcmeta(ctx: Context) -> None:
    for dp, members in ctx.datapacks.items():
        if "pack.mcmeta" not in members:
            ctx.add("error", dp, "datapack has no pack.mcmeta at its root")
        elif not any(m.startswith("data/") for m in members):
            ctx.add("warning", dp, "datapack has pack.mcmeta but no data/ folder")
    ctx.add("info", "-", f"{len(ctx.datapacks)} datapacks checked")


_NS_RE = re.compile(r"^(?:.*!)?(?:.*/)?data/([^/]+)/(.+)$")


def check_duplicate_basenames(ctx: Context) -> None:
    """Same file name twice inside one data/<namespace>/<registry> tree (different sub-folders).

    Not an error in Minecraft (the id includes the sub-path) but a common source of
    confusion in authored content. Base-pack content is skipped unless --strict-base.
    """
    seen: dict[tuple, list[str]] = defaultdict(list)
    for e in ctx.entries:
        if e.rel.startswith("base-pack/") and not ctx.strict_base:
            continue
        m = _NS_RE.match(e.rel)
        if not m:
            continue
        ns, rest = m.group(1), m.group(2).split("/")
        # registries nest one level deeper under worldgen/ and tags/
        depth = 2 if rest[0] in ("worldgen", "tags") and len(rest) > 2 else 1
        reg, sub = "/".join(rest[:depth]), "/".join(rest[depth:])
        if len(rest) <= depth:
            continue
        container = e.rel.split("!", 1)[0] if "!" in e.rel else e.rel.split("/data/", 1)[0]
        seen[(container, ns, reg, e.name)].append(sub)
    by_tree: dict[tuple, list[str]] = defaultdict(list)
    for (container, ns, reg, name), paths in seen.items():
        if len(paths) > 1:
            by_tree[(container, ns, reg)].append(f"{name} ({', '.join(paths)})")
    for (container, ns, reg), items in by_tree.items():
        shown = "; ".join(items[:3]) + (f"; ... {len(items) - 3} more" if len(items) > 3 else "")
        ctx.add("warning", container, f"{len(items)} duplicate file name(s) in data/{ns}/{reg}: {shown}")


def check_hash_csv_wellformed(ctx: Context) -> None:
    if not HASH_CSV.exists():
        ctx.add("error", "base-pack/inventory/pack_hashes.csv", "missing")
        return
    rel = HASH_CSV.relative_to(ctx.root).as_posix()
    with open(HASH_CSV, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        if rd.fieldnames != ["relative_path", "size_bytes", "sha256"]:
            ctx.add("error", rel, f"unexpected columns {rd.fieldnames}")
            return
        paths = set()
        for i, row in enumerate(rd, start=2):
            if row["relative_path"] in paths:
                ctx.add("error", rel, f"line {i}: duplicate path {row['relative_path']}")
            paths.add(row["relative_path"])
            if not re.fullmatch(r"[0-9a-f]{64}", row["sha256"] or ""):
                ctx.add("error", rel, f"line {i}: bad sha256")
            if not (row["size_bytes"] or "").isdigit():
                ctx.add("error", rel, f"line {i}: bad size")
    ctx.add("info", rel, f"{len(paths)} hash rows")


def check_manifest_sanity(ctx: Context) -> None:
    mdir = ctx.root / "modpack" / "manifest"
    base = mdir / "base-cobbleverse-1.7.42.json"
    overlay = mdir / "overlay.json"
    if base.exists():
        try:
            d = json.loads(base.read_text(encoding="utf-8"))
            for key in ("schema", "base", "target", "files"):
                if key not in d:
                    ctx.add("error", "modpack/manifest/base-cobbleverse-1.7.42.json", f"missing key {key}")
        except ValueError:
            pass  # reported by json_parses
    else:
        ctx.add("warning", "modpack/manifest/base-cobbleverse-1.7.42.json", "missing (run tools/pack_manifest.py generate)")
    if overlay.exists():
        try:
            d = json.loads(overlay.read_text(encoding="utf-8"))
            for key in ("target", "replace", "remove", "add", "server_exclude"):
                if key not in d:
                    ctx.add("error", "modpack/manifest/overlay.json", f"missing key {key}")
        except ValueError:
            pass
    else:
        ctx.add("warning", "modpack/manifest/overlay.json", "missing")


def check_structure_manifest(ctx: Context) -> None:
    """Validate the lightweight structure catalog and campaign dependency records."""
    path = ctx.root / STRUCTURE_MANIFEST
    rel = STRUCTURE_MANIFEST.as_posix()
    if not path.exists():
        ctx.add("error", rel, "missing")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        ctx.add("error", rel, f"invalid JSON: {exc}")
        return

    if not isinstance(data, dict):
        ctx.add("error", rel, "root must be an object")
        return
    if data.get("schema") != "cobblers.structure-dependencies/1":
        ctx.add("error", rel, "unexpected or missing schema")
    components = data.get("components")
    verified = data.get("verified_structures")
    campaign = data.get("campaign_structures")
    if not isinstance(components, dict) or not isinstance(verified, list) or not isinstance(campaign, list):
        ctx.add("error", rel, "components must be an object; verified_structures and campaign_structures must be arrays")
        return

    base_manifest = ctx.root / "modpack" / "manifest" / "base-cobbleverse-1.7.42.json"
    known_mod_ids: set[str] = set()
    known_filenames: set[str] = set()
    if base_manifest.is_file():
        try:
            base_data = json.loads(base_manifest.read_text(encoding="utf-8"))
            for item in base_data.get("files", []):
                if isinstance(item, dict):
                    if isinstance(item.get("mod_id"), str):
                        known_mod_ids.add(item["mod_id"])
                    if isinstance(item.get("filename"), str):
                        known_filenames.add(item["filename"])
        except (ValueError, UnicodeDecodeError):
            pass  # manifest_sanity/json_parses report the source error
    for name, component in components.items():
        where = f"{rel}:components.{name}"
        if not isinstance(component, dict):
            ctx.add("error", where, "component must be an object")
            continue
        kind = component.get("kind")
        runtime_id = component.get("runtime_id")
        if kind not in ("mod", "datapack") or not isinstance(runtime_id, str):
            ctx.add("error", where, "kind must be mod/datapack and runtime_id must be a string")
        elif known_mod_ids or known_filenames:
            if kind == "mod" and runtime_id not in known_mod_ids:
                ctx.add("error", where, f"runtime mod id {runtime_id!r} is absent from the base manifest")
            if kind == "datapack" and runtime_id not in known_filenames:
                ctx.add("error", where, f"runtime datapack {runtime_id!r} is absent from the base manifest")

    ids: set[str] = set()
    for i, entry in enumerate(verified):
        where = f"{rel}:verified_structures[{i}]"
        if not isinstance(entry, dict):
            ctx.add("error", where, "entry must be an object")
            continue
        catalog_id = entry.get("catalog_id")
        if not isinstance(catalog_id, str) or not catalog_id:
            ctx.add("error", where, "missing catalog_id")
        elif catalog_id in ids:
            ctx.add("error", where, f"duplicate catalog_id {catalog_id}")
        else:
            ids.add(catalog_id)
        source = entry.get("source_component")
        if not isinstance(source, str) or source not in components:
            ctx.add("error", where, f"unknown source_component {source!r}")
        structure_id = entry.get("structure_id")
        if not isinstance(structure_id, str) or not re.fullmatch(r"[a-z0-9_.-]+:[a-z0-9_./-]+", structure_id):
            ctx.add("error", where, f"invalid structure_id {structure_id!r}")
        if not entry.get("implementation") or not entry.get("evidence"):
            ctx.add("error", where, "implementation and evidence are required")
        dims = entry.get("dimensions")
        if dims is not None and (not isinstance(dims, list) or len(dims) != 3 or not all(isinstance(n, int) and n > 0 for n in dims)):
            ctx.add("error", where, "dimensions must be null or three positive integers")

    asset_root = ctx.root / "kits" / "structures" / "campaign"
    asset_root_resolved = asset_root.resolve()
    documented_assets: set[str] = set()
    campaign_ids: set[str] = set()
    for i, entry in enumerate(campaign):
        where = f"{rel}:campaign_structures[{i}]"
        if not isinstance(entry, dict):
            ctx.add("error", where, "entry must be an object")
            continue
        campaign_id = entry.get("id")
        if not isinstance(campaign_id, str) or not re.fullmatch(r"campaign:[a-z0-9_./-]+", campaign_id):
            ctx.add("error", where, f"invalid campaign id {campaign_id!r}")
        elif campaign_id in campaign_ids:
            ctx.add("error", where, f"duplicate campaign id {campaign_id}")
        else:
            campaign_ids.add(campaign_id)
        based_on = entry.get("based_on")
        if based_on is not None and (not isinstance(based_on, str) or based_on not in ids):
            ctx.add("error", where, f"based_on references unknown verified structure {based_on!r}")
        required = entry.get("required_components")
        if not isinstance(required, list) or not required:
            ctx.add("error", where, "required_components must be a non-empty array")
        else:
            for component in required:
                if not isinstance(component, str) or component not in components:
                    ctx.add("error", where, f"unknown required component {component!r}")
        asset = entry.get("asset")
        if not isinstance(asset, str) or not asset.startswith("kits/structures/campaign/"):
            ctx.add("error", where, "asset must be under kits/structures/campaign/")
        else:
            candidate = (ctx.root / asset).resolve()
            try:
                candidate.relative_to(asset_root_resolved)
            except ValueError:
                ctx.add("error", where, f"asset escapes campaign structure root: {asset}")
                continue
            documented_assets.add(asset)
            if not candidate.is_file():
                ctx.add("error", where, f"missing asset {asset}")

    if asset_root.is_dir():
        actual = {
            p.relative_to(ctx.root).as_posix()
            for p in asset_root.rglob("*")
            if p.is_file() and p.name != ".gitkeep"
        }
        for asset in sorted(actual - documented_assets):
            ctx.add("error", asset, "campaign structure has no dependency-manifest entry")
    ctx.add("info", rel, f"{len(ids)} verified upstream structures; {len(campaign_ids)} campaign structures")


def _stub(name: str, what: str):
    """Placeholder for a future campaign check. Reports 'skipped' so nobody mistakes it for coverage."""

    def check(ctx: Context) -> None:
        ctx.add("info", "-", f"{name}: skipped (not implemented) - would check {what}")

    check.__name__ = f"check_{name}"
    return check


# Registry: (name, function). Add new checks here. Stubs mark planned campaign
# checks; implement them once the campaign content schema exists.
CHECKS = [
    ("json_parses", check_json_parses),
    ("datapack_pack_mcmeta", check_datapack_pack_mcmeta),
    ("duplicate_basenames", check_duplicate_basenames),
    ("hash_csv_wellformed", check_hash_csv_wellformed),
    ("manifest_sanity", check_manifest_sanity),
    ("structure_manifest", check_structure_manifest),
    # --- extension points (EXP-001..EXP-007 will define the data these need) ---
    ("duplicate_ids", _stub("duplicate_ids", "duplicate campaign ids across routes/trainers/rewards")),
    ("missing_pokemon_refs", _stub("missing_pokemon_refs", "species/form names that Cobblemon does not know")),
    ("broken_refs", _stub("broken_refs", "encounter/trainer/reward references pointing at nothing")),
    ("progression_deps", _stub("progression_deps", "progression dependencies that cycle or reference unknown steps")),
]


# ---------------------------------------------------------------------- main
def run(root: Path = ROOT, strict_base: bool = False, verbose: bool = False, only: list[str] | None = None) -> int:
    ctx = Context(root, strict_base)
    collect(ctx)
    for name, fn in CHECKS:
        if only and name not in only:
            continue
        try:
            fn(ctx)
        except Exception as exc:  # a broken check must not hide other results
            ctx.add("error", "-", f"check {name} crashed: {exc!r}")
    errors = [i for i in ctx.issues if i.level == "error"]
    warnings = [i for i in ctx.issues if i.level == "warning"]
    infos = [i for i in ctx.issues if i.level == "info"]
    for i in errors + warnings + (infos if verbose else []):
        print(f"{i.level.upper():8} {i.path}: {i.message}")
    print(f"\n{len(ctx.entries)} files scanned, {len(ctx.datapacks)} datapacks, "
          f"{len(errors)} errors, {len(warnings)} warnings, {len(infos)} info (use -v to list)")
    return 1 if errors else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=str(ROOT))
    p.add_argument("--strict-base", action="store_true", help="errors under base-pack/ fail the run")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--only", nargs="*", help="run only these checks")
    p.add_argument("--list", action="store_true", help="list registered checks and exit")
    a = p.parse_args(argv)
    if a.list:
        for name, fn in CHECKS:
            print(f"{name:22} {(fn.__doc__ or '').strip().splitlines()[0] if fn.__doc__ else ''}")
        return 0
    return run(Path(a.root), a.strict_base, a.verbose, a.only)


if __name__ == "__main__":
    sys.exit(main())
