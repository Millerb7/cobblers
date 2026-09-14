#!/usr/bin/env python
"""Find and patch Pokémon models a client resource pack breaks under Cobblemon 1.8.

Cobblemon 1.8 poses a model either with a built-in Kotlin poser or with a JSON poser
(`bedrock/pokemon/posers/<form>.json`). JSON posers are registered after the built-in ones
and replace them, and they tolerate a missing root bone. Built-in posers do not: they
look parts up by name (`ModelPart.getChild`), so a resource pack model with renamed bones
throws "Can't find part <name>" the first time that Pokémon renders, and the client goes
black. First seen 2026-09-14: Alolan Persian, from COBBLEVERSE RP.

  python tools/client_model_fix.py scan    --instance "<client instance dir>"
  python tools/client_model_fix.py build   --instance "<client instance dir>" [--out build/client/cobblers-model-fixes.zip]
  python tools/client_model_fix.py install --instance "<client instance dir>" [--zip build/client/cobblers-model-fixes.zip]

scan    reads the enabled pack order from options.txt, finds the model each geometry id
        resolves to (models are keyed by file name, the highest pack wins), and flags every form
        posed by a built-in poser whose effective model lacks a part Cobblemon's own model has.
        Exit code 1 when a flagged form is not covered by an installed, top-priority fix pack.
build   writes a resource pack that puts Cobblemon's own geometry back for exactly those forms,
        at every path a pack uses for that geometry id. Nothing is copied from third-party packs.
install copies the zip into resourcepacks/ and puts it at the top of the enabled list in
        options.txt (backup beside it). The game must be closed.

Rerun scan after every modpack, resource pack or Cobblemon update
(docs/research/CLIENT_MODEL_FIXES.md). The zip holds Cobblemon assets and is built locally,
never committed.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

MODELS = "assets/cobblemon/bedrock/pokemon/models/"
POSERS = "assets/cobblemon/bedrock/pokemon/posers/"
POSER_CLASSES = "com/cobblemon/mod/common/client/render/models/blockbench/pokemon/"
PACK_NAME = "cobblers-model-fixes.zip"
PACK_FORMAT = 34  # Minecraft 1.21.1 resource packs
JAR_LAYER = "<cobblemon jar>"


def enabled_packs(instance: Path) -> list[str]:
    for line in (instance / "options.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("resourcePacks:"):
            return json.loads(line.split(":", 1)[1])
    return []


def cobblemon_jar(instance: Path) -> Path:
    jars = sorted((instance / "mods").glob("Cobblemon-fabric-*.jar"))
    if not jars:
        raise SystemExit("no Cobblemon-fabric-*.jar in %s" % (instance / "mods"))
    return jars[-1]


def bones(data: bytes) -> list[str]:
    try:
        doc = json.loads(data.decode("utf-8-sig", "replace"))
    except ValueError:
        return []
    return [b["name"] for geo in doc.get("minecraft:geometry") or [] for b in geo.get("bones") or [] if b.get("name")]


def layers(instance: Path):
    """[(name, ZipFile)] lowest priority first: the Cobblemon jar, then enabled file/ packs in order."""
    out = [(JAR_LAYER, zipfile.ZipFile(cobblemon_jar(instance)))]
    for p in enabled_packs(instance):
        if not p.startswith("file/") or p[5:] == PACK_NAME:
            continue
        path = instance / "resourcepacks" / p[5:]
        if path.is_file():
            try:
                out.append((p[5:], zipfile.ZipFile(path)))
            except zipfile.BadZipFile:
                continue
    return out


def builtin_poser_forms(jar: zipfile.ZipFile) -> set[str]:
    """Form ids with a built-in Kotlin poser, e.g. PersianAlolanModel -> persian_alolan (approximate by class name)."""
    forms = set()
    for n in jar.namelist():
        m = re.match(re.escape(POSER_CLASSES) + r"gen\d+/(\w+?)Model\.class$", n)
        if m:
            forms.add(re.sub(r"(?<!^)(?=[A-Z])", "_", m.group(1)).lower())
    return forms


def scan(instance: Path) -> dict:
    stack = layers(instance)
    jar = stack[0][1]
    geo, poser = {}, {}
    for name, z in stack:
        for n in z.namelist():
            if n.startswith(MODELS) and n.endswith(".geo.json"):
                geo.setdefault(n.rsplit("/", 1)[1][:-len(".geo.json")], []).append((name, n))
            elif n.startswith(POSERS) and n.endswith(".json"):
                poser.setdefault(n.rsplit("/", 1)[1][:-len(".json")], []).append(name)
    builtin = builtin_poser_forms(jar)
    zips = dict(stack)
    flagged = []
    for form, providers in sorted(geo.items()):
        top_name, top_path = providers[-1]
        if top_name == JAR_LAYER or form in poser or form not in builtin:
            continue
        own = [p for p in providers if p[0] == JAR_LAYER]
        if not own:
            continue
        ours = [b for b in bones(jar.read(own[0][1])) if not b.startswith("locator")]
        theirs = set(bones(zips[top_name].read(top_path)))
        missing = [b for b in ours if b not in theirs]
        if ours and missing:
            flagged.append({"form": form, "pack": top_name, "pack_path": top_path, "cobblemon_path": own[0][1],
                            "root_missing": ours[0] in missing, "missing_parts": missing,
                            "paths_to_shadow": sorted({p for n, p in providers if n != JAR_LAYER})})
    fix = instance / "resourcepacks" / PACK_NAME
    fix_enabled = ("file/" + PACK_NAME) in enabled_packs(instance) and fix.is_file()
    fix_files = set(zipfile.ZipFile(fix).namelist()) if fix_enabled else set()
    for f in flagged:
        f["covered_by_fix_pack"] = fix_enabled and enabled_packs(instance)[-1] == "file/" + PACK_NAME \
            and all(p in fix_files for p in f["paths_to_shadow"])
    return {"instance": str(instance), "cobblemon": cobblemon_jar(instance).name,
            "fix_pack_enabled_on_top": fix_enabled and enabled_packs(instance)[-1] == "file/" + PACK_NAME,
            "uncovered": [f["form"] for f in flagged if not f["covered_by_fix_pack"]],
            "packs_scanned": [n for n, _ in stack[1:]], "geometry_ids_overridden": sum(1 for v in geo.values() if v[-1][0] != JAR_LAYER),
            "rule": "built-in poser (no JSON poser anywhere in the stack) whose effective model lacks a non-locator part of Cobblemon's model",
            "flagged": flagged}


def build(instance: Path, out: Path) -> dict:
    report = scan(instance)
    jar = zipfile.ZipFile(cobblemon_jar(instance))
    files = {}
    for f in report["flagged"]:
        for path in f["paths_to_shadow"]:
            files[path] = f["cobblemon_path"]
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"built": datetime.datetime.now().isoformat(timespec="seconds"), "cobblemon": report["cobblemon"],
                "flagged": report["flagged"], "files": dict(sorted(files.items()))}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("pack.mcmeta", json.dumps({"pack": {"pack_format": PACK_FORMAT,
                    "description": "Cobblers: Cobblemon 1.8 models for forms other packs break"}}, indent=1))
        zf.writestr("cobblers-model-fixes.json", json.dumps(manifest, indent=1))
        for dst, src in sorted(files.items()):
            zf.writestr(dst, jar.read(src))
    return manifest


def install(instance: Path, zip_path: Path) -> list[str]:
    shutil.copy2(zip_path, instance / "resourcepacks" / PACK_NAME)
    opts = instance / "options.txt"
    backup = opts.with_name("options.txt.pre-cobblers-model-fixes")
    if not backup.exists():
        shutil.copy2(opts, backup)
    lines = opts.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("resourcePacks:"):
            packs = [p for p in json.loads(line.split(":", 1)[1]) if p != "file/" + PACK_NAME]
            packs.append("file/" + PACK_NAME)   # last = highest priority
            lines[i] = "resourcePacks:" + json.dumps(packs, ensure_ascii=False, separators=(",", ":"))
            break
    else:
        raise SystemExit("options.txt has no resourcePacks line")
    opts.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return packs


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("scan", "build", "install"):
        s = sub.add_parser(name)
        s.add_argument("--instance", required=True, type=Path)
        if name == "build":
            s.add_argument("--out", type=Path, default=Path("build/client") / PACK_NAME)
        if name == "install":
            s.add_argument("--zip", type=Path, default=Path("build/client") / PACK_NAME)
    a = p.parse_args(argv)
    if a.cmd == "scan":
        r = scan(a.instance)
        print(json.dumps(r, indent=1))
        return 1 if r["uncovered"] else 0
    if a.cmd == "build":
        m = build(a.instance, a.out)
        print("%d flagged form(s), %d file(s) -> %s" % (len(m["flagged"]), len(m["files"]), a.out))
        for dst, src in m["files"].items():
            print("  %s <- %s" % (dst, src))
        return 0
    packs = install(a.instance, a.zip)
    print("installed; top of the pack list:", packs[-3:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
