#!/usr/bin/env python
"""Every NPC class we ship must render as a person, not as Cobblemon's green substitute doll.

How Cobblemon 1.8.0 picks an NPC's model (read from the jar's bytecode, 2026-10-02):

  1. NPCClassAdapter reads an optional "resourceIdentifier" from the class JSON (namespace defaults to "cobblemon").
  2. NPCClass's constructor sets resourceIdentifier = cobblemon:dummy; NPCClasses, on reload, replaces any whose path
     is "dummy" with THE CLASS ID. A class without the field therefore asks for a variation named after itself.
  3. NPCEntity syncs RESOURCE_IDENTIFIER = ForcedResourceIdentifier (entity NBT) ?: class.resourceIdentifier, set on
     setNpc and again on every NBT load.
  4. NPCRenderer asks VaryingModelRepository.getPoser(entity.resourceIdentifier, state); a name with no resolver,
     or a resolver that throws, returns the resolver of cobblemon:substitute. Silently.

So the class id cobblers:npc_x renders as the doll unless a client variation file is named "cobblers:npc_x". This
audit applies rules 1-2 to every class in the packs, then resolves the name the way client_model_fix.py resolves a
species (VaryingRenderableResolver: the last variation, by order, whose aspects the entity has and that sets the
field), with the entity's aspects empty, and requires the model, poser and texture to exist in the asset sources:
the Cobblemon jar (what every client has) plus any --with jar or pack zip, later sources above earlier ones.

Independence: nothing here comes from the generators. The rule is Cobblemon's, and `rule_evidence` re-reads the jar
and fails if its bytecode stops carrying it; the assets are the jar's. The expected model is not named anywhere in
this file: a class passes only if the name it carries resolves.

Not covered: NPCs whose ForcedResourceIdentifier NBT is set at summon (none of ours are), class "presets" (reported,
not followed), and client resource packs that shadow Cobblemon's NPC files (pass them with --with).

  python tools/npc_model_audit.py [--packs DIR ...] [--jar JAR] [--with ZIP_OR_JAR ...] [--out REPORT.json]

Exit 1 when any class does not resolve.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import client_model_fix as CMF  # noqa: E402

DEFAULT_PACKS = ROOT / "build" / "datapacks"
NPC_VAR_DIR = "bedrock/npcs/variations"

# Byte strings that must be in these class files for the rule above to still be the jar's rule.
EVIDENCE = {
    "com/cobblemon/mod/common/util/adapters/NPCClassAdapter.class": [b"resourceIdentifier"],
    "com/cobblemon/mod/common/api/npc/NPCClasses.class": [b"dummy", b"setResourceIdentifier"],
    "com/cobblemon/mod/common/entity/npc/NPCEntity.class": [b"ForcedResourceIdentifier", b"RESOURCE_IDENTIFIER"],
    "com/cobblemon/mod/common/client/render/npc/NPCRenderer.class": [b"getResourceIdentifier", b"getPoser"],
}


def find_jar() -> Path:
    import battle_sim
    try:
        return battle_sim.find_jar()
    except battle_sim.SimError as e:
        raise SystemExit(str(e))


def rule_evidence(jar: zipfile.ZipFile) -> list[str]:
    """Problems if the jar no longer carries the selection rule this audit applies."""
    out = []
    for cls, needles in EVIDENCE.items():
        try:
            b = jar.read(cls)
        except KeyError:
            out.append("%s absent from the jar" % cls)
            continue
        out += ["%s no longer mentions %s" % (cls, n.decode()) for n in needles if n not in b]
    return out


def classes(pack_dirs) -> list[tuple[str, str, str, dict]]:
    """[(pack, path in pack, class id, class json)] for every data/<ns>/npcs/**.json in the packs."""
    out = []
    for pack in pack_dirs:
        pack = Path(pack)
        for f in sorted(pack.glob("data/*/npcs/**/*.json")):
            rel = f.relative_to(pack).as_posix()
            ns = rel.split("/")[1]
            path = rel.split("/npcs/", 1)[1][: -len(".json")]
            out.append((pack.name, rel, "%s:%s" % (ns, path), json.loads(f.read_text(encoding="utf-8"))))
    return out


def resource_identifier(doc: dict, class_id: str) -> str:
    """Rules 1-2: the variation name the client is asked for."""
    rid = doc.get("resourceIdentifier")
    if isinstance(rid, str) and rid:
        rid = CMF.qualify(rid)
        if rid.split(":", 1)[1] != "dummy":
            return rid
    return class_id


class Assets:
    def __init__(self, jar_path: Path, extra=()):
        jar = CMF.file_layer(Path(jar_path), "cobblemon")
        if jar is None:
            raise SystemExit("cannot open %s" % jar_path)
        layers = [jar]
        for p in extra:
            lay = CMF.file_layer(Path(p))
            if lay is None:
                raise SystemExit("cannot open %s" % p)
            layers.append(lay)
        self.jar = jar.zf
        self.stack = CMF.Stack(layers, "cobblemon")
        # Stack indexes bedrock/ and Pokemon textures only; NPC textures live in textures/npcs/.
        self.files = {n[len(lay.prefix):] for lay in layers for n in lay.zf.namelist() if not n.endswith("/")}

    def resolve(self, name: str) -> tuple[dict, list[str]]:
        entries = self.stack.resolvers().get(name)
        if not entries:
            return {}, ["no client variation is named %s" % name]
        allv = CMF.variations(entries)
        got = {k: CMF.resolve(allv, set(), k) for k in ("model", "poser", "texture")}
        got["from"] = sorted({rel for _, rel, _ in entries})
        prob = []
        if not isinstance(got["model"], str) or CMF.qualify(got["model"]) not in self.stack.registry("models"):
            prob.append("model missing: %s" % got["model"])
        if not isinstance(got["poser"], str) or CMF.qualify(got["poser"]) not in self.stack.registry("posers"):
            prob.append("poser missing: %s" % got["poser"])
        ids = CMF.tex_ids(got["texture"])
        if not ids or got["texture"] == "variable":
            prob.append("texture unresolvable without aspects or a player skin: %s" % got["texture"])
        elif any(CMF.tex_rel(i) not in self.files for i in ids):
            prob.append("texture missing: %s" % got["texture"])
        return got, prob


def audit(pack_dirs, jar_path=None, extra=()) -> dict:
    jar_path = Path(jar_path) if jar_path else find_jar()
    assets = Assets(jar_path, extra)
    rows, problems = [], []
    for pack, rel, cid, doc in classes(pack_dirs):
        name = resource_identifier(doc, cid)
        got, prob = assets.resolve(name)
        if doc.get("presets"):
            prob.append("class uses presets, which this audit does not follow: %s" % doc["presets"])
        rows.append({"pack": pack, "file": rel, "class": cid, "resource": name, **got, "problems": prob})
        problems += ["%s/%s (%s -> %s): %s" % (pack, rel, cid, name, p) for p in prob]
    problems = rule_evidence(assets.jar) + problems
    return {"jar": str(jar_path), "with": [str(p) for p in extra], "classes": len(rows),
            "packs": sorted({r["pack"] for r in rows}), "rows": rows, "problems": problems}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--packs", nargs="*", help="datapack folders (default: every folder in build/datapacks)")
    ap.add_argument("--jar", help="Cobblemon 1.8 jar (default: tools/battle_sim.py's)")
    ap.add_argument("--with", dest="extra", nargs="*", default=[], help="more asset jars/zips, above the jar")
    ap.add_argument("--out", help="write the full report here")
    a = ap.parse_args(argv)
    packs = a.packs if a.packs else sorted(p for p in DEFAULT_PACKS.glob("*") if p.is_dir())
    rep = audit(packs, a.jar, a.extra)
    if a.out:
        Path(a.out).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    if not rep["classes"]:
        print("npc_model_audit: no NPC classes found in %d pack(s)" % len(packs))
        return 1
    for p in rep["problems"][:20]:
        print("PROBLEM " + p)
    names = sorted({r["resource"] for r in rep["rows"]})
    print("npc_model_audit: %d class(es) in %s, %d problem(s); variations used: %s"
          % (rep["classes"], ", ".join(rep["packs"]), len(rep["problems"]), ", ".join(names[:5])))
    return 1 if rep["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
