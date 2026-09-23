"""Build the Rift's connected-textures resource pack from the installed mod jars.

A 200-block rock face made of one 16x16 texture reads as a grid, which is what made the Rift's walls look built
rather than torn (owner, second flyover, 2026-09-22). The pack ships Continuity and Athena already, so the fix
costs a resource pack and no new dependency: for each rock the Rift is built from, this writes an OptiFine
`method=random` entry with eight variants of the mod's own texture (four rotations, each also mirrored), so
neighbouring blocks no longer repeat.

The variants are derived from a mod's art, so the output is disposable and never committed: it is written under
build/resourcepacks/ and regenerated from the local jars. Legendary Monuments is MPL-2.0, which permits
redistribution with the notice this tool writes beside the pack; whether we ship it to players is a decision for
docs/decisions/, not for this tool.

    python tools/ctm_pack.py --server-dir <server>            # build the pack
    python tools/ctm_pack.py --server-dir <server> --check    # say what it would write, write nothing
"""
import argparse
import glob
import io
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "resourcepacks" / "cobblers_rift_ctm"
SPEC = ROOT / "data" / "rift_fracture.json"
PACK_FORMAT = 34          # Minecraft 1.21.1

WORLD_READS = ()          # jars and data only: this tool never reads a world


class CtmError(Exception):
    pass


def rocks(spec):
    """The blocks the Rift's rim and faces are built from, in the order the spec names them, without duplicates."""
    out = []
    for b in (spec["rim"]["materials"] + [spec["rim"]["streak"]["block"]]
              + [spec["palette"][r]["block"] for r in ("face_upper", "face_lower", "tread")]):
        if b not in out and not b.startswith("minecraft:"):
            out.append(b)
    return out


def texture_of(jars, block):
    """The block's own texture, read out of the jar that defines it: its model's first texture, or its name."""
    ns, name = block.split(":")
    for z in jars:
        model = "assets/%s/models/block/%s.json" % (ns, name)
        cand = []
        if model in z.namelist():
            m = json.loads(z.read(model))
            for v in (m.get("textures") or {}).values():
                if isinstance(v, str) and not v.startswith("#"):
                    cand.append(v)
        cand.append("%s:block/%s" % (ns, name))
        for c in cand:
            tns, tpath = c.split(":") if ":" in c else (ns, c)
            p = "assets/%s/textures/%s.png" % (tns, tpath)
            if p in z.namelist():
                if (p + ".mcmeta") in z.namelist():
                    continue          # animated: rotating its frames would scramble the animation
                return p, z.read(p)
    return None, None


def variants(png):
    """Eight of the same texture: four rotations, each also mirrored. Enough to break the repeat without inventing
    any art of our own."""
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    if im.width != im.height:
        raise CtmError("texture is %dx%d, not square" % (im.width, im.height))
    out = []
    for turn in (0, 90, 180, 270):
        r = im.rotate(turn)
        for mirror in (False, True):
            out.append(r.transpose(Image.FLIP_LEFT_RIGHT) if mirror else r)
    return out


def build(server_dir, check=False):
    import runtime_guard
    runtime_guard.require_lock("read the server's mod jars")
    mods = runtime_guard.check(Path(server_dir) / "mods", "read the mod jars in")
    jars = []
    for j in sorted(glob.glob(str(mods / "*.jar"))):
        try:
            jars.append(zipfile.ZipFile(j))
        except Exception:
            pass
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    want = rocks(spec)
    if not want:
        raise CtmError("the spec names no mod rock: nothing to give connected textures to")
    found, missing = [], []
    for b in want:
        path, png = texture_of(jars, b)
        (missing if png is None else found).append(b if png is None else (b, path, png))
    if missing:
        raise CtmError("no usable texture for %s: the pack would silently cover only part of the rim" % missing)
    if check:
        for b, path, png in found:
            print("%-52s %s (%d bytes)" % (b, path, len(png)))
        print("%d rocks would get 8 variants each" % len(found))
        return 0
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets" / "minecraft" / "optifine" / "ctm" / "rift").mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps(
        {"pack": {"pack_format": PACK_FORMAT,
                  "description": "Cobblers: the Rift's rock, without the repeating grid"}}, indent=2) + "\n",
        encoding="utf-8")
    licences = {b.split(":")[0] for b, _, _ in found}
    (OUT / "NOTICE.md").write_text(
        "# Notice\n\n"
        "Generated by tools/ctm_pack.py from the mod jars installed locally. Every texture here is a rotation or a\n"
        "mirror of a texture belonging to its mod; no art is ours.\n\n"
        + "".join("- `%s` — Legendary Monuments by JorgaoMC, MPL-2.0. The originals are in its jar; these variants\n"
                  "  are modifications of those files and stay under the same licence.\n" % ns for ns in sorted(licences))
        + "\nThis pack is disposable: it is rebuilt from the jars and is not committed.\n", encoding="utf-8")
    n = 0
    for b, path, png in found:
        ns, name = b.split(":")
        d = OUT / "assets" / "minecraft" / "optifine" / "ctm" / "rift" / name
        d.mkdir(parents=True)
        for i, im in enumerate(variants(png)):
            im.save(d / ("%d.png" % i))
            n += 1
        (d / ("%s.properties" % name)).write_text(
            "# %s: the same rock, eight ways round, so a big face does not tile\n"
            "matchBlocks=%s\nmethod=random\ntiles=0-7\nsymmetry=all\n" % (b, b), encoding="utf-8")
    where = OUT.relative_to(ROOT) if ROOT in OUT.parents else OUT
    print("wrote %s: %d rocks, %d tiles" % (where, len(found), n))
    print("  install: copy the folder into the client's resourcepacks and enable it above the pack's own packs")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--server-dir", required=True, help="the server whose mods/ holds the jars (needs the lock)")
    ap.add_argument("--check", action="store_true", help="report what it would write, write nothing")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        return build(a.server_dir, a.check)
    except CtmError as e:
        print("FAIL: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
