#!/usr/bin/env python
"""pack_manifest.py - base manifest + overlay tooling for the cobblers modpack.

Stdlib only. Subcommands:

  generate         build modpack/manifest/base-cobbleverse-1.7.42.json from
                   base-pack/inventory (+ hashes of local jars/zips, + Modrinth
                   hash lookup unless --offline)
  resolve-overlay  fill Modrinth version ids / URLs / hashes into overlay.json
                   "replace" entries that carry a modrinth slug + to_version
  plan             print the effective target file list = base + overlay
  verify DIR       compare a mods/ (or any) directory against the plan
  download         download plan entries from recorded Modrinth URLs
                   (does nothing without --yes; prints the plan instead)

Never downloads anything unless `download --yes` is given explicitly.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INVENTORY_DIR = ROOT / "base-pack" / "inventory"
MANIFEST_DIR = ROOT / "modpack" / "manifest"
BASE_MANIFEST = MANIFEST_DIR / "base-cobbleverse-1.7.42.json"
OVERLAY = MANIFEST_DIR / "overlay.json"
CACHE_DIR = MANIFEST_DIR / "cache"
DEFAULT_PACK_DIR = ROOT / "base-pack" / "cobbleverse"

MODRINTH = "https://api.modrinth.com/v2"
USER_AGENT = "cobblers-bootstrap/0.1 (github.com/Millerb7/cobblers)"

BASE_INFO = {
    "name": "COBBLEVERSE",
    "slug": "cobbleverse",
    "modrinth_project_id": "Jkb29YJU",
    "version": "1.7.42",
    "mrpack_version_id": "4SKGla61",
    "released": "2026-07-21",
}
BASE_TARGET = {
    "minecraft": "1.21.1",
    "loader": "fabric",
    "loader_min": "0.18.4",
    "java": 21,
    "cobblemon": "1.7.3+1.21.1",
}


# ----------------------------------------------------------------- helpers
def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def load_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def hash_file(path: Path) -> dict:
    h = {"sha1": hashlib.sha1(), "sha256": hashlib.sha256(), "sha512": hashlib.sha512()}
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            for d in h.values():
                d.update(chunk)
    return {k: d.hexdigest() for k, d in h.items()}


def modrinth(method: str, path: str, body=None):
    req = urllib.request.Request(
        MODRINTH + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)


def trim_version(v: dict) -> dict:
    """Keep only the fields we need from a Modrinth version object."""
    return {
        "id": v["id"],
        "project_id": v["project_id"],
        "version_number": v.get("version_number"),
        "name": v.get("name"),
        "version_type": v.get("version_type"),
        "date_published": v.get("date_published"),
        "game_versions": v.get("game_versions"),
        "loaders": v.get("loaders"),
        "dependencies": v.get("dependencies", []),
        "files": [
            {k: f.get(k) for k in ("filename", "url", "primary", "size", "hashes")}
            for f in v.get("files", [])
        ],
    }


def primary_file(v: dict) -> dict:
    files = v.get("files") or []
    for f in files:
        if f.get("primary"):
            return f
    return files[0] if files else {}


def side_of(environment: str | None) -> str:
    return {"client": "client", "server": "server"}.get(environment or "*", "both")


# ---------------------------------------------------------------- generate
def cmd_generate(a: argparse.Namespace) -> int:
    inventory = load_json(INVENTORY_DIR / "mod_inventory.json")
    by_jar = {r["jar"]: r for r in inventory}
    with open(INVENTORY_DIR / "pack_hashes.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    pack_dir = Path(a.jar_dir) if a.jar_dir else DEFAULT_PACK_DIR
    files, mismatches, local_hashed = [], [], 0
    # inventory jars missing from the CSV (e.g. the .disabled duplicate) still get a record
    csv_names = {r["relative_path"].replace("\\", "/").rsplit("/", 1)[-1] for r in rows}
    for inv in inventory:
        if inv["jar"] not in csv_names:
            rows.append({"relative_path": "mods/" + inv["jar"], "size_bytes": "0", "sha256": None, "_not_in_csv": True})
    for row in rows:
        rel = row["relative_path"].replace("\\", "/")
        top = rel.split("/", 1)[0]
        kind = {"mods": "mod", "resourcepacks": "resourcepack", "datapacks": "datapack", "shaderpacks": "shaderpack"}.get(top, top)
        fname = rel.rsplit("/", 1)[-1]
        rec = {
            "path": rel,
            "kind": kind,
            "filename": fname,
            "size": int(row["size_bytes"]),
            "sha256": row["sha256"],
            "sha1": None,
            "sha512": None,
            "side": "client" if kind in ("resourcepack", "shaderpack") else "both",
            "in_hash_csv": not row.get("_not_in_csv"),
            "source": {"type": "unresolved"},
        }
        inv = by_jar.get(fname)
        if inv:
            rec.update(
                {
                    "mod_id": inv["mod_id"],
                    "name": inv["name"],
                    "version": inv["version"],
                    "side": side_of(inv["environment"]),
                    "classification": inv["classification"],
                    "disabled": bool(inv["disabled"]),
                    "depends_cobblemon": inv.get("dep_cobblemon"),
                    "cobblemon_1_8_status": inv.get("cobblemon_1_8_status"),
                    "notes": inv.get("notes"),
                }
            )
        elif kind == "mod":
            log(f"WARN: {fname} in pack_hashes.csv but not in mod_inventory.json")
        local = pack_dir / rel
        if local.is_file():
            h = hash_file(local)
            local_hashed += 1
            if row["sha256"] is None:
                rec["sha256"], rec["size"] = h["sha256"], local.stat().st_size
            elif h["sha256"] != row["sha256"]:
                mismatches.append(rel)
                log(f"WARN: sha256 mismatch vs pack_hashes.csv: {rel}")
            rec["sha1"], rec["sha512"] = h["sha1"], h["sha512"]
        files.append(rec)

    resolution = {"attempted": False, "method": None, "resolved": 0, "unresolved": []}
    if not a.offline:
        resolution.update(resolve_by_hash(files, cache=not a.no_cache))
    else:
        log("offline: skipping Modrinth resolution")
    resolution["unresolved"] = [f["path"] for f in files if f["source"]["type"] != "modrinth"]
    resolution["resolved"] = len(files) - len(resolution["unresolved"])

    manifest = {
        "schema": "cobblers.base-manifest/1",
        "generated": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "base": BASE_INFO,
        "target": BASE_TARGET,
        "sources": {
            "inventory": "base-pack/inventory/mod_inventory.json",
            "hashes": "base-pack/inventory/pack_hashes.csv",
            "jar_dir": str(pack_dir),
            "local_files_hashed": local_hashed,
            "sha256_mismatches": mismatches,
        },
        "resolution": resolution,
        "files": files,
    }
    out = Path(a.out) if a.out else BASE_MANIFEST
    save_json(out, manifest)
    log(
        f"wrote {out} ({len(files)} files, {local_hashed} hashed locally, "
        f"{resolution['resolved']} resolved on Modrinth, {len(resolution['unresolved'])} unresolved)"
    )
    return 1 if mismatches else 0


def resolve_by_hash(files: list[dict], cache: bool) -> dict:
    hashes = [f["sha1"] for f in files if f["sha1"]]
    if not hashes:
        log("no local sha1 hashes available; cannot resolve on Modrinth (pass --jar-dir)")
        return {"attempted": False, "method": "sha1 lookup (no local files)"}
    found: dict[str, dict] = {}
    try:
        for i in range(0, len(hashes), 60):
            chunk = hashes[i : i + 60]
            resp = modrinth("POST", "/version_files", {"hashes": chunk, "algorithm": "sha1"})
            found.update({k: trim_version(v) for k, v in resp.items()})
            log(f"modrinth version_files: {len(chunk)} sent, {len(resp)} hits")
    except (urllib.error.URLError, OSError) as exc:
        log(f"Modrinth unavailable ({exc}); manifest written with local data only")
        return {"attempted": True, "method": "sha1 lookup", "error": str(exc)}
    for f in files:
        v = found.get(f["sha1"] or "")
        if not v:
            continue
        pf = next((x for x in v["files"] if (x.get("hashes") or {}).get("sha1") == f["sha1"]), primary_file(v))
        f["source"] = {
            "type": "modrinth",
            "project_id": v["project_id"],
            "version_id": v["id"],
            "version_number": v["version_number"],
            "date_published": v["date_published"],
            "url": pf.get("url"),
            "filename": pf.get("filename"),
        }
        if not f["sha512"] and pf.get("hashes"):
            f["sha512"] = pf["hashes"].get("sha512")
    if cache:
        save_json(CACHE_DIR / "modrinth_version_files.json", found)
    return {"attempted": True, "method": "POST /v2/version_files algorithm=sha1", "hits": len(found)}


# --------------------------------------------------------- resolve-overlay
def cmd_resolve_overlay(a: argparse.Namespace) -> int:
    overlay = load_json(OVERLAY)
    changed = 0
    for entry in overlay.get("replace", []) + overlay.get("add", []):
        m = entry.get("modrinth") or {}
        slug, want = m.get("slug"), entry.get("to_version") or entry.get("version")
        if not slug or not want:
            continue
        try:
            versions = modrinth("GET", f"/project/{slug}/version?loaders=%5B%22fabric%22%5D")
        except (urllib.error.URLError, OSError) as exc:
            log(f"{slug}: Modrinth unavailable ({exc})")
            continue
        trimmed = [trim_version(v) for v in versions]
        save_json(CACHE_DIR / f"modrinth_versions_{slug}.json", trimmed[:25])
        hit = next((v for v in trimmed if v["version_number"] == want and "1.21.1" in (v["game_versions"] or [])), None)
        if not hit:
            log(f"{slug}: no fabric/1.21.1 version numbered {want!r}; newest: "
                + ", ".join(v["version_number"] for v in trimmed[:5]))
            entry["verification"] = "unverified"
            continue
        pf = primary_file(hit)
        m.update(
            {
                "project_id": hit["project_id"],
                "version_id": hit["id"],
                "version_number": hit["version_number"],
                "date_published": hit["date_published"],
                "url": pf.get("url"),
                "filename": pf.get("filename"),
                "size": pf.get("size"),
                "dependencies": hit["dependencies"],
            }
        )
        entry["modrinth"] = m
        entry["to_file"] = pf.get("filename") or entry.get("to_file")
        entry["sha512"] = (pf.get("hashes") or {}).get("sha512")
        entry["sha1"] = (pf.get("hashes") or {}).get("sha1")
        entry["verification"] = "verified via Modrinth API " + _dt.date.today().isoformat()
        changed += 1
        log(f"{slug}: {want} -> version {hit['id']} {pf.get('filename')}")
    save_json(OVERLAY, overlay)
    log(f"updated {changed} entries in {OVERLAY}")
    return 0


# -------------------------------------------------------------------- plan
def build_plan(base: dict, overlay: dict | None, side: str | None = None, kind: str | None = "mod") -> list[dict]:
    """Effective file list: base files with overlay replace/remove/add applied."""
    replace = (overlay or {}).get("replace", [])
    remove = (overlay or {}).get("remove", [])

    def match(entries, f):
        # an entry with "file" targets exactly that file (needed when two jars share a mod id);
        # otherwise it targets every file with that mod_id
        return next((e for e in entries if (e.get("file") == f["filename"]) or (not e.get("file") and e["mod_id"] == f.get("mod_id"))), None)

    plan = []
    for f in base["files"]:
        if kind and f["kind"] != kind:
            continue
        e = {
            "filename": f["filename"],
            "kind": f["kind"],
            "mod_id": f.get("mod_id"),
            "version": f.get("version"),
            "side": f["side"],
            "sha256": f["sha256"],
            "sha512": f.get("sha512"),
            "sha1": f.get("sha1"),
            "size": f.get("size"),
            "status": "base",
            "source": f["source"],
            "replaces": None,
        }
        rm, r = match(remove, f), match(replace, f)
        if f.get("disabled"):
            e["status"] = "disabled"
        if rm:
            e["status"], e["reason"] = "remove", rm["reason"]
        elif r:
            m = r.get("modrinth") or {}
            e.update(
                {
                    "filename": r.get("to_file") or f["filename"],
                    "version": r.get("to_version"),
                    "sha256": None,
                    "sha512": r.get("sha512"),
                    "sha1": r.get("sha1"),
                    "size": m.get("size"),
                    "status": "replace",
                    "replaces": f["filename"],
                    "verification": r.get("verification", "unverified"),
                    "source": {"type": "modrinth", **{k: m.get(k) for k in ("project_id", "version_id", "url", "filename")}}
                    if m.get("url")
                    else {"type": "unresolved"},
                }
            )
        plan.append(e)
    for add in (overlay or {}).get("add", []):
        m = add.get("modrinth") or {}
        plan.append(
            {
                "filename": add.get("to_file") or add.get("file"),
                "kind": add.get("kind", "mod"),
                "mod_id": add["mod_id"],
                "version": add.get("version"),
                "side": add.get("side", "both"),
                "sha256": add.get("sha256"),
                "sha512": add.get("sha512"),
                "sha1": add.get("sha1"),
                "size": m.get("size"),
                "status": "add",
                "source": {"type": "modrinth", **{k: m.get(k) for k in ("project_id", "version_id", "url", "filename")}}
                if m.get("url")
                else {"type": "unresolved"},
                "replaces": None,
                "reason": add.get("reason"),
            }
        )
    if side:
        plan = [e for e in plan if e["side"] in ("both", side)]
    return plan


def load_plan(a: argparse.Namespace) -> list[dict]:
    base = load_json(Path(a.manifest) if a.manifest else BASE_MANIFEST)
    overlay = None if getattr(a, "no_overlay", False) else load_json(Path(a.overlay) if a.overlay else OVERLAY)
    return build_plan(base, overlay, side=a.side, kind=None if a.all_kinds else "mod")


def active(plan: list[dict]) -> list[dict]:
    return [e for e in plan if e["status"] in ("base", "replace", "add")]


def cmd_plan(a: argparse.Namespace) -> int:
    plan = load_plan(a)
    if a.json:
        print(json.dumps(plan, indent=1))
        return 0
    w = max(len(e["filename"]) for e in plan) if plan else 20
    print(f"{'STATUS':9} {'SIDE':6} {'FILE':{w}}  MOD_ID / SOURCE")
    for e in plan:
        src = e["source"].get("version_id") or e["source"]["type"]
        extra = f" (replaces {e['replaces']}; {e.get('verification')})" if e["status"] == "replace" else ""
        extra = f" ({e.get('reason')})" if e["status"] == "remove" else extra
        print(f"{e['status']:9} {e['side']:6} {e['filename']:{w}}  {e['mod_id'] or '-'} / {src}{extra}")
    act = active(plan)
    counts = {s: sum(1 for e in plan if e["status"] == s) for s in ("base", "replace", "add", "remove", "disabled")}
    print(f"\n{len(act)} files in effective set; {counts}")
    return 0


# ------------------------------------------------------------------ verify
def cmd_verify(a: argparse.Namespace) -> int:
    target = Path(a.dir)
    if not target.is_dir():
        log(f"not a directory: {target}")
        return 2
    plan = active(load_plan(a))
    present = {p.name: p for p in target.iterdir() if p.is_file()}
    missing, mismatch, unverified, ok = [], [], [], []
    for e in plan:
        p = present.pop(e["filename"], None)
        if p is None:
            missing.append(e["filename"])
            continue
        h = hash_file(p)
        algo = next((k for k in ("sha512", "sha256", "sha1") if e.get(k)), None)
        if algo is None:
            unverified.append(e["filename"])
        elif h[algo] != e[algo]:
            mismatch.append(e["filename"])
        else:
            ok.append(e["filename"])
    extra = sorted(n for n in present if n.lower().endswith((".jar", ".zip", ".disabled")))
    for label, items in (("MISSING", missing), ("HASH MISMATCH", mismatch), ("EXTRA", extra), ("PRESENT, NO HASH ON RECORD", unverified)):
        for n in items:
            print(f"{label:27} {n}")
    print(f"\n{len(ok)} ok, {len(missing)} missing, {len(mismatch)} mismatched, {len(extra)} extra, {len(unverified)} unverified")
    return 1 if (missing or mismatch) else 0


# ---------------------------------------------------------------- download
def cmd_download(a: argparse.Namespace) -> int:
    plan = active(load_plan(a))
    if a.replacements_only:
        plan = [e for e in plan if e["status"] in ("replace", "add")]
    target = Path(a.target)
    todo, no_url = [], []
    for e in plan:
        if e["source"]["type"] == "modrinth" and e["source"].get("url"):
            todo.append(e)
        else:
            no_url.append(e["filename"])
    total = sum(e.get("size") or 0 for e in todo)
    print(f"target dir: {target}")
    print(f"{len(todo)} files downloadable from Modrinth ({total / 1e6:.1f} MB); {len(no_url)} have no recorded URL:")
    for n in no_url:
        print(f"  no URL: {n}")
    if not a.yes:
        for e in todo:
            print(f"  would GET {e['source']['url']} -> {e['filename']}")
        print("\nDRY RUN. Nothing downloaded. Re-run with --yes to actually download.")
        return 0
    target.mkdir(parents=True, exist_ok=True)
    failures = 0
    for e in todo:
        dest = target / e["filename"]
        algo = next((k for k in ("sha512", "sha1", "sha256") if e.get(k)), None)
        if dest.is_file() and algo and hash_file(dest)[algo] == e[algo]:
            print(f"  skip (present, hash ok): {dest.name}")
            continue
        print(f"  GET {e['source']['url']}")
        req = urllib.request.Request(e["source"]["url"], headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=300) as resp, open(dest.with_suffix(dest.suffix + ".part"), "wb") as out:
                for chunk in iter(lambda: resp.read(1 << 20), b""):
                    out.write(chunk)
        except (urllib.error.URLError, OSError) as exc:
            print(f"  FAILED {dest.name}: {exc}")
            failures += 1
            continue
        part = dest.with_suffix(dest.suffix + ".part")
        if algo and hash_file(part)[algo] != e[algo]:
            print(f"  HASH MISMATCH, discarded: {dest.name}")
            part.unlink()
            failures += 1
            continue
        part.replace(dest)
        print(f"  ok {dest.name}" + ("" if algo else " (no hash on record)"))
    return 1 if failures else 0


# -------------------------------------------------------------------- main
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="build the base manifest from base-pack/inventory")
    g.add_argument("--jar-dir", help=f"pack dir holding mods/ resourcepacks/ datapacks/ (default {DEFAULT_PACK_DIR})")
    g.add_argument("--out", help=f"output path (default {BASE_MANIFEST})")
    g.add_argument("--offline", action="store_true", help="skip Modrinth hash lookup")
    g.add_argument("--no-cache", action="store_true", help="do not write modpack/manifest/cache/")
    g.set_defaults(fn=cmd_generate)

    r = sub.add_parser("resolve-overlay", help="fill Modrinth ids/urls/hashes into overlay.json replace/add entries")
    r.set_defaults(fn=cmd_resolve_overlay)

    def common(sp):
        sp.add_argument("--manifest", help=f"base manifest (default {BASE_MANIFEST})")
        sp.add_argument("--overlay", help=f"overlay (default {OVERLAY})")
        sp.add_argument("--no-overlay", action="store_true", help="ignore the overlay (pure base pack)")
        sp.add_argument("--side", choices=["server", "client"], help="filter to files needed on that side")
        sp.add_argument("--all-kinds", action="store_true", help="include resourcepacks/datapacks, not only mods")

    pl = sub.add_parser("plan", help="print the effective target file list")
    common(pl)
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(fn=cmd_plan)

    v = sub.add_parser("verify", help="check a directory of jars against the plan")
    v.add_argument("dir")
    common(v)
    v.set_defaults(fn=cmd_verify)

    d = sub.add_parser("download", help="download plan entries from Modrinth (dry-run unless --yes)")
    common(d)
    d.add_argument("--target", required=True, help="directory to download into")
    d.add_argument("--yes", action="store_true", help="actually download (otherwise only print the plan)")
    d.add_argument(
        "--replacements-only",
        action="store_true",
        help="download only overlay replace/add entries (use local base-pack files for everything else)",
    )
    d.set_defaults(fn=cmd_download)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
