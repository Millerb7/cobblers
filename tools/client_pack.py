#!/usr/bin/env python
"""client_pack.py - build the players' Modrinth modpack (.mrpack) and check an installed instance.

Stdlib only. Subcommands:

  build            write build/client/cobblers-client-<version>.mrpack and a report beside it
  plan             print what the .mrpack would hold (URL files, embedded files, MANUAL files); writes nothing
  verify DIR       check a player's instance (mods/, resourcepacks/, shaderpacks/) against the client plan
  manual           copy the MANUAL files out of a COBBLEVERSE .mrpack the player downloaded themselves

Inputs, all in the repository:
  modpack/manifest/base-cobbleverse-1.7.42.json + overlay.json  the pack (via pack_manifest.build_plan)
  data/client_pack.json                                         this pack's own choices
  docs/STATE.md "Runtime"                                       the Fabric Loader version the server runs
  tracked config (git ls-files)                                 what is embedded under overrides/

Format: Modrinth's "Modrinth Modpack Format (.mrpack)" (support.modrinth.com/en/articles/8802351, read
2026-10-04): a zip holding modrinth.index.json (formatVersion 1, game "minecraft", versionId, name,
summary, files[{path, hashes{sha1, sha512}, env{client, server}, downloads[https], fileSize}],
dependencies{minecraft, fabric-loader}) and an overrides/ folder copied into the instance root.

LICENCES. A file entry is a URL plus hashes: each player's launcher fetches the author's own upload, and
nothing is redistributed. overrides/ carries only plain-text config and licence notices from tracked
files. A jar, a zip, an image, a binary or anything gitignored is never embedded; the build fails if one
would be. Files with no URL (COBBLEVERSE's own no-redistribution zips) are MANUAL: the player takes them
from the COBBLEVERSE .mrpack they download from Modrinth themselves (`manual`, or by hand).

WHAT THIS DOES NOT COVER. Datapacks are left out (world data comes from the server). The client's
config/ after first launch is whatever the mods rewrite it to; `verify` does not check config. Nothing
here proves the pack boots or joins: that needs a running client.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pack_manifest as pm  # noqa: E402

ROOT = pm.ROOT
CONFIG = ROOT / "data" / "client_pack.json"
OUT_DIR = ROOT / "build" / "client"

KIND_DIR = {"mod": "mods", "resourcepack": "resourcepacks", "shaderpack": "shaderpacks", "datapack": "datapacks"}
# Modrinth's upload whitelist for download URLs; other https hosts are allowed by the spec but warned about.
MODRINTH_DOMAINS = ("cdn.modrinth.com", "github.com", "raw.githubusercontent.com", "gitlab.com")
URL_OK = re.compile(r"^https://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+$")
BINARY_MAGIC = (b"PK\x03\x04", b"PK\x05\x06", b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"%PDF", b"\x1f\x8b", b"\xca\xfe\xba\xbe")
ZIP_DATE = (2026, 1, 1, 0, 0, 0)


class PackError(Exception):
    """A fault that must stop the build: the pack would be wrong or would redistribute something."""


# ------------------------------------------------------------------ inputs
def load_config(path: Path = CONFIG) -> dict:
    return pm.load_json(path)


def fabric_loader(cfg: dict, root: Path = ROOT) -> str:
    src = cfg["fabric_loader_from"]
    text = (root / src["file"]).read_text(encoding="utf-8")
    m = re.search(src["pattern"], text)
    if not m:
        raise PackError(f"no Fabric Loader version found in {src['file']} (pattern {src['pattern']!r})")
    return m.group(1)


def safe_path(p: str) -> bool:
    """Modrinth's rule: no '..', no leading slash or backslash, no drive letter."""
    return bool(p) and ".." not in p.replace("\\", "/").split("/") and not re.match(r"^([A-Za-z]:|[/\\])", p)


# ------------------------------------------------------------------- plan
def client_plan(base: dict, overlay: dict | None, cfg: dict) -> dict:
    """Split the effective client file list into URL entries, MANUAL files and exclusions.

    Returns {"files": [index entries], "manual": [...], "manual_optional": [...], "excluded": [...]}.
    Raises PackError when a required file has neither a URL nor a recorded manual source.
    """
    plan = pm.active(pm.build_plan(base, overlay, side="client", kind=None))
    base_path = {f["filename"]: f["path"] for f in base["files"]}
    server_exclude = set((overlay or {}).get("server_exclude", []))
    cv = cfg.get("cobbleverse_mrpack", {})
    override_files = cv.get("override_files", {})
    manual_optional = cfg.get("manual_optional", {})
    exclude_kinds = cfg.get("exclude_kinds", {})

    files, manual, manual_opt, excluded, faults = [], [], [], [], []
    for e in plan:
        if e["status"] == "base":
            path = base_path[e["filename"]]
        elif e["status"] == "replace":
            path = str(Path(base_path[e["replaces"]]).parent / e["filename"]).replace("\\", "/")
        else:
            path = f"{KIND_DIR[e['kind']]}/{e['filename']}"
        if e["kind"] in exclude_kinds:
            excluded.append({"path": path, "reason": exclude_kinds[e["kind"]]})
            continue
        if not safe_path(path):
            faults.append(f"unsafe path {path!r}")
            continue
        src = e["source"]
        if src.get("type") == "modrinth" and src.get("url"):
            missing = [k for k in ("sha1", "sha512", "size") if not e.get(k)]
            if missing:
                faults.append(f"{path}: has a URL but no {', '.join(missing)} on record")
                continue
            if not URL_OK.match(src["url"]):
                faults.append(f"{path}: download URL is not an RFC 3986 https URL: {src['url']!r}")
                continue
            server = "unsupported" if (e["side"] == "client" or e.get("mod_id") in server_exclude) else "required"
            files.append(
                {
                    "path": path,
                    "hashes": {"sha1": e["sha1"], "sha512": e["sha512"]},
                    "env": {"client": "required", "server": server},
                    "downloads": [src["url"]],
                    "fileSize": e["size"],
                }
            )
            continue
        rec = {
            "path": path,
            "size": e.get("size"),
            "sha512": e.get("sha512"),
            "sha1": e.get("sha1"),
            "from": f"{cv.get('filename', 'COBBLEVERSE .mrpack')} -> {cv.get('overrides_prefix', 'overrides/')}{path}",
        }
        if path in manual_optional:
            manual_opt.append({**rec, "reason": manual_optional[path]})
        elif path in override_files:
            if e.get("size") is not None and override_files[path] != e["size"]:
                faults.append(f"{path}: COBBLEVERSE .mrpack holds {override_files[path]} bytes, manifest says {e['size']}")
            manual.append(rec)
        else:
            faults.append(f"{path}: required on the client, no download URL and no manual source recorded")

    for opt in cfg.get("optional_files", []):
        m = opt["modrinth"]
        if not (opt.get("sha1") and opt.get("sha512") and opt.get("size") and URL_OK.match(m.get("url", ""))):
            faults.append(f"optional {opt['path']}: needs sha1, sha512, size and an https URL")
            continue
        if not safe_path(opt["path"]):
            faults.append(f"unsafe path {opt['path']!r}")
            continue
        files.append(
            {
                "path": opt["path"],
                "hashes": {"sha1": opt["sha1"], "sha512": opt["sha512"]},
                "env": {"client": "optional", "server": "unsupported"},
                "downloads": [m["url"]],
                "fileSize": opt["size"],
            }
        )

    seen: dict[str, int] = {}
    for f in files:
        seen[f["path"].lower()] = seen.get(f["path"].lower(), 0) + 1
    faults += [f"two entries install to {p}" for p, n in seen.items() if n > 1]
    if faults:
        raise PackError("client plan refused:\n  " + "\n  ".join(faults))
    files.sort(key=lambda f: f["path"])
    return {"files": files, "manual": manual, "manual_optional": manual_opt, "excluded": excluded}


def build_index(cfg: dict, plan: dict, minecraft: str, loader: str, version: str | None = None) -> dict:
    pack = cfg["pack"]
    return {
        "formatVersion": 1,
        "game": "minecraft",
        "versionId": version or pack["version"],
        "name": pack["name"],
        "summary": pack["summary"],
        "files": plan["files"],
        "dependencies": {"minecraft": minecraft, "fabric-loader": loader},
    }


# ----------------------------------------------------------------- embeds
def git_ls_files(root: Path, rel: str) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", rel], capture_output=True, check=True
    ).stdout.decode("utf-8")
    return [p for p in out.split("\0") if p]


def collect_embeds(cfg: dict, root: Path = ROOT, ls=git_ls_files) -> dict[str, Path]:
    """Instance-relative path -> source file, for tracked plain-text files only. Later sources win."""
    emb = cfg["embed"]
    skip = set(emb.get("skip_names", []))
    exclude = emb.get("exclude", {})
    out: dict[str, Path] = {}
    for s in emb["sources"]:
        src = s["from"].rstrip("/")
        for rel in ls(root, src):
            name = rel.rsplit("/", 1)[-1]
            if name in skip:
                continue
            if s.get("suffixes") and not name.lower().endswith(tuple(s["suffixes"])):
                continue
            sub = rel[len(src) + 1:]
            dest = f"{s['to']}/{sub}" if s["to"] else sub
            if any(dest == x or (x.endswith("/") and dest.startswith(x)) for x in exclude):
                continue
            out[dest] = root / rel
    return out


def check_embeds(embeds: dict[str, Path], blocked_names: set[str]) -> None:
    faults = []
    for dest, p in sorted(embeds.items()):
        data = p.read_bytes()
        low = dest.lower()
        if not safe_path(dest):
            faults.append(f"unsafe path {dest!r}")
        if low.endswith((".jar", ".zip", ".disabled", ".mrpack", ".png", ".jpg", ".ogg", ".pdf")):
            faults.append(f"{dest}: archive/media file type is never embedded")
        if data.startswith(BINARY_MAGIC) or b"\x00" in data:
            faults.append(f"{dest}: binary content is never embedded")
        if p.name in blocked_names:
            faults.append(f"{dest}: same name as a pack file that has its own source")
    if faults:
        raise PackError("embed refused:\n  " + "\n  ".join(faults))


# ------------------------------------------------------------------ write
def write_mrpack(out: Path, index: dict, embeds: dict[str, Path]) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        def put(name: str, data: bytes) -> None:
            info = zipfile.ZipInfo(name, ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)

        put("modrinth.index.json", (json.dumps(index, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
        for dest in sorted(embeds):
            put(f"overrides/{dest}", embeds[dest].read_bytes())
    tmp.replace(out)
    return {"path": str(out), "size": out.stat().st_size, **{k: v for k, v in pm.hash_file(out).items() if k != "sha256"}}


def report(index: dict, plan: dict, embeds: dict[str, Path], built: dict | None, cfg: dict) -> dict:
    cv = cfg.get("cobbleverse_mrpack", {})
    req = [f for f in index["files"] if f["env"]["client"] == "required"]
    return {
        "mrpack": built,
        "versionId": index["versionId"],
        "dependencies": index["dependencies"],
        "counts": {
            "url_required": len(req),
            "url_optional": len(index["files"]) - len(req),
            "url_bytes": sum(f["fileSize"] for f in index["files"]),
            "embedded": len(embeds),
            "manual_required": len(plan["manual"]),
            "manual_optional": len(plan["manual_optional"]),
            "excluded": len(plan["excluded"]),
        },
        "optional": [f["path"] for f in index["files"] if f["env"]["client"] == "optional"],
        "manual_source": {k: cv.get(k) for k in ("page", "filename", "url", "sha1", "size")},
        "manual": plan["manual"],
        "manual_optional": plan["manual_optional"],
        "manual_cosmetic": cv.get("cosmetic_prefixes", {}),
        "excluded": plan["excluded"],
        "embedded": sorted(embeds),
    }


def make(args, with_embeds: bool = True) -> tuple[dict, dict, dict, dict]:
    cfg = load_config(Path(args.config) if getattr(args, "config", None) else CONFIG)
    base = pm.load_json(Path(args.manifest) if getattr(args, "manifest", None) else pm.BASE_MANIFEST)
    overlay = pm.load_json(Path(args.overlay) if getattr(args, "overlay", None) else pm.OVERLAY)
    loader = fabric_loader(cfg)
    minecraft = overlay.get("target", {}).get("minecraft") or base["target"]["minecraft"]
    plan = client_plan(base, overlay, cfg)
    index = build_index(cfg, plan, minecraft, loader, getattr(args, "version", None))
    if not with_embeds:
        return cfg, plan, index, {}
    embeds = collect_embeds(cfg)
    blocked = {Path(f["path"]).name for f in index["files"]} | {Path(m["path"]).name for m in plan["manual"] + plan["manual_optional"]}
    check_embeds(embeds, blocked)
    return cfg, plan, index, embeds


# --------------------------------------------------------------- commands
def print_summary(rep: dict) -> None:
    c = rep["counts"]
    print(f"{rep['versionId']}: minecraft {rep['dependencies']['minecraft']}, fabric-loader {rep['dependencies']['fabric-loader']}")
    print(f"  by URL: {c['url_required']} required + {c['url_optional']} optional ({c['url_bytes'] / 1e6:.1f} MB, fetched by the launcher)")
    print(f"  embedded under overrides/: {c['embedded']} plain-text files")
    print(f"  MANUAL: {c['manual_required']} required, {c['manual_optional']} optional, from {rep['manual_source']['filename']}")
    for m in rep["manual"]:
        print(f"    MANUAL {m['path']}")
    for m in rep["manual_optional"]:
        print(f"    MANUAL (optional) {m['path']}")
    print(f"  excluded: {c['excluded']} ({', '.join(sorted({Path(e['path']).parts[0] for e in rep['excluded']})) or '-'})")
    for p in rep["optional"]:
        print(f"  OPTIONAL by URL: {p}")


def cmd_plan(a) -> int:
    try:
        cfg, plan, index, embeds = make(a)
    except PackError as exc:
        pm.log(str(exc))
        return 1
    print_summary(report(index, plan, embeds, None, cfg))
    return 0


def cmd_build(a) -> int:
    try:
        cfg, plan, index, embeds = make(a)
    except PackError as exc:
        pm.log(str(exc))
        return 1
    out_dir = Path(a.out_dir) if a.out_dir else OUT_DIR
    out = out_dir / f"cobblers-client-{index['versionId']}.mrpack"
    built = write_mrpack(out, index, embeds)
    rep = report(index, plan, embeds, built, cfg)
    pm.save_json(out.with_suffix(".report.json"), rep)
    print_summary(rep)
    print(f"wrote {out} ({built['size']} bytes, sha1 {built['sha1']})")
    print(f"report {out.with_suffix('.report.json')}")
    return 0


def game_dir(d: Path) -> Path:
    """Accept a Prism instance folder (holding .minecraft/ or minecraft/) or the game folder itself."""
    if (d / "mods").is_dir():
        return d
    for sub in (".minecraft", "minecraft"):
        if (d / sub / "mods").is_dir():
            return d / sub
    return d


def verify_instance(gdir: Path, index: dict, plan: dict) -> dict:
    expect = [(f["path"], f["hashes"], f["env"]["client"] == "required") for f in index["files"]]
    expect += [(m["path"], {k: m[k] for k in ("sha512", "sha1") if m.get(k)}, True) for m in plan["manual"]]
    expect += [(m["path"], {k: m[k] for k in ("sha512", "sha1") if m.get(k)}, False) for m in plan["manual_optional"]]
    res = {"ok": [], "missing": [], "mismatch": [], "optional_absent": [], "extra_mods": [], "unchecked": []}
    for path, hashes, required in expect:
        p = gdir / path
        if not p.is_file():
            res["missing" if required else "optional_absent"].append(path)
            continue
        algo = next((k for k in ("sha512", "sha1") if hashes.get(k)), None)
        if algo is None:
            res["unchecked"].append(path)
        elif pm.hash_file(p)[algo] != hashes[algo]:
            res["mismatch"].append(path)
        else:
            res["ok"].append(path)
    wanted = {path for path, _, _ in expect if path.startswith("mods/")}
    mods = gdir / "mods"
    if mods.is_dir():
        res["extra_mods"] = sorted(
            f"mods/{p.name}" for p in mods.iterdir() if p.is_file() and p.name.endswith(".jar") and f"mods/{p.name}" not in wanted
        )
    return res


def cmd_verify(a) -> int:
    target = Path(a.dir)
    if not target.is_dir():
        pm.log(f"not a directory: {target}")
        return 2
    try:
        cfg, plan, index, embeds = make(a, with_embeds=False)
    except PackError as exc:
        pm.log(str(exc))
        return 1
    gdir = game_dir(target)
    res = verify_instance(gdir, index, plan)
    print(f"instance: {gdir}")
    for label, key in (("MISSING", "missing"), ("HASH MISMATCH", "mismatch"), ("EXTRA MOD", "extra_mods"), ("NO HASH ON RECORD", "unchecked")):
        for n in res[key]:
            print(f"{label:18} {n}")
    for n in res["optional_absent"]:
        print(f"{'optional, absent':18} {n}")
    print(
        f"\n{len(res['ok'])} ok, {len(res['missing'])} missing, {len(res['mismatch'])} mismatched, "
        f"{len(res['extra_mods'])} extra mods, {len(res['optional_absent'])} optional absent"
    )
    if res["extra_mods"]:
        print("An extra mod is not an error by itself, but the server does not have it; remove it if joining fails.")
    return 1 if (res["missing"] or res["mismatch"]) else 0


def extract_manual(src: Path, gdir: Path, plan: dict, cfg: dict, cosmetic: bool, optional: bool) -> dict:
    cv = cfg["cobbleverse_mrpack"]
    prefix = cv.get("overrides_prefix", "overrides/")
    wanted = list(plan["manual"]) + (list(plan["manual_optional"]) if optional else [])
    res = {"copied": [], "present": [], "failed": [], "cosmetic": 0}
    with zipfile.ZipFile(src) as z:
        names = set(z.namelist())
        for m in wanted:
            dest = gdir / m["path"]
            algo = next((k for k in ("sha512", "sha1") if m.get(k)), None)
            if dest.is_file() and algo and pm.hash_file(dest)[algo] == m[algo]:
                res["present"].append(m["path"])
                continue
            name = prefix + m["path"]
            if name not in names:
                res["failed"].append(f"{m['path']}: not in {src.name}")
                continue
            data = z.read(name)
            if algo and getattr(hashlib, algo)(data).hexdigest() != m[algo]:
                res["failed"].append(f"{m['path']}: hash differs from the manifest; not copied")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            res["copied"].append(m["path"])
        if cosmetic:
            for pre in cv.get("cosmetic_prefixes", {}):
                for name in sorted(n for n in names if n.startswith(prefix + pre) and not n.endswith("/")):
                    rel = name[len(prefix):]
                    if not safe_path(rel):
                        continue
                    dest = gdir / rel
                    if dest.exists():
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(z.read(name))
                    res["cosmetic"] += 1
    return res


def cmd_manual(a) -> int:
    src = Path(a.cobbleverse)
    if not src.is_file():
        pm.log(f"not a file: {src}")
        return 2
    try:
        cfg, plan, index, embeds = make(a, with_embeds=False)
    except PackError as exc:
        pm.log(str(exc))
        return 1
    cv = cfg["cobbleverse_mrpack"]
    got = pm.hash_file(src)["sha1"]
    if got != cv["sha1"] and not a.any_version:
        pm.log(f"{src.name} has sha1 {got}, not COBBLEVERSE 1.7.42's {cv['sha1']}. Download it from {cv['page']}.")
        return 1
    gdir = game_dir(Path(a.instance))
    if not (gdir / "mods").is_dir():
        pm.log(f"no mods/ folder under {a.instance}: import the Cobblers .mrpack first, then run this")
        return 2
    res = extract_manual(src, gdir, plan, cfg, cosmetic=not a.no_cosmetic, optional=a.include_optional)
    for p in res["copied"]:
        print(f"copied   {p}")
    for p in res["failed"]:
        print(f"FAILED   {p}")
    print(f"\n{len(res['copied'])} copied, {len(res['present'])} already present, {len(res['failed'])} failed, {res['cosmetic']} cosmetic files added")
    return 1 if res["failed"] else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--config", help=f"pack choices (default {CONFIG.relative_to(ROOT)})")
        sp.add_argument("--manifest", help="base manifest (default modpack/manifest/base-cobbleverse-1.7.42.json)")
        sp.add_argument("--overlay", help="overlay (default modpack/manifest/overlay.json)")
        sp.add_argument("--version", help="override the pack version (versionId)")

    b = sub.add_parser("build", help="write build/client/cobblers-client-<version>.mrpack and its report")
    common(b)
    b.add_argument("--out-dir", help=f"output folder (default {OUT_DIR.relative_to(ROOT)})")
    b.set_defaults(func=cmd_build)
    pl = sub.add_parser("plan", help="print what the .mrpack would hold; writes nothing")
    common(pl)
    pl.set_defaults(func=cmd_plan)
    v = sub.add_parser("verify", help="check a player's instance against the client plan")
    common(v)
    v.add_argument("dir", help="the instance folder (Prism: the instance, or its .minecraft/; Modrinth App: the profile)")
    v.set_defaults(func=cmd_verify)
    m = sub.add_parser("manual", help="copy MANUAL files from a COBBLEVERSE 1.7.42 .mrpack into an instance")
    common(m)
    m.add_argument("--cobbleverse", required=True, help="path to 'COBBLEVERSE 1.7.42.mrpack' downloaded from Modrinth")
    m.add_argument("--instance", required=True, help="the instance folder")
    m.add_argument("--no-cosmetic", action="store_true", help="skip menu art, splash art and the COBBLEVERSE shaders")
    m.add_argument("--include-optional", action="store_true", help="also copy optional MANUAL files (ATMxMSD RP.zip)")
    m.add_argument("--any-version", action="store_true", help="accept a .mrpack whose sha1 is not 1.7.42's")
    m.set_defaults(func=cmd_manual)
    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
