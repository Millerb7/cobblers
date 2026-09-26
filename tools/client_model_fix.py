#!/usr/bin/env python
"""Find and patch Pokémon models the client resource-pack stack breaks under Cobblemon 1.8.

Three faults are checked, each on the effective stack rebuilt from the client's options.txt
(mod jars under "fabric", built-in mod packs, file/ packs), resolved the way Cobblemon 1.8's
VaryingModelRepository resolves it: models, posers and animation groups are keyed by file
name, the lexicographically last path of a name wins, and the highest pack wins a path.

1. crash        a form posed by a built-in Kotlin poser whose effective model lacks a part
                Cobblemon's own model has. Built-in posers look parts up by name and throw
                "Can't find part <name>" (2026-09-14, Alolan Persian).
2. missing      a spawnable species with no client model: no resolver, or its base variation
                names a model, poser or texture the stack does not have. Cobblemon falls back
                to the green substitute doll, silently (2026-09-26, Vullaby, Oranguru).
                Spawnable = a species in data/spawns.json, or an implemented species in a spawn
                pool of the instance's mod jars and datapacks.
3. uv_mismatch  a model whose UV layout does not fit its effective texture: under half of its
                normalised cube UV rectangles are in the model the texture was drawn for (the
                texture's own pack's model of that id, else the model effective at that pack's
                level), or the texture's aspect ratio differs from the model's UV space. The
                measure is bimodal: most split forms match 95% or more, the broken ones 0-20%
                (2026-09-26, Pidgeot, Talonflame). The cut sits in the empty gap between the two
                modes; Hisuian Samurott, at 20.4%, is a broken one.

  python tools/client_model_fix.py scan    --instance DIR [--with-pack ZIP ...]
  python tools/client_model_fix.py build   --instance DIR [--out build/client/cobblers-model-fixes.zip]
  python tools/client_model_fix.py build   --instance DIR --server-pack [--record-paths]
  python tools/client_model_fix.py install --instance DIR [--zip ZIP]

scan    reports every fault on the stack without our packs ("flagged") and on the effective
        stack ("uncovered": our packs where options.txt enables them, plus each --with-pack zip
        simulated above everything, as a server resource pack is). Exit 1 when anything is
        uncovered.
build   writes cobblers-model-fixes.zip: Cobblemon 1.8's own files, from the local jar, for
        the crash forms and for the uv_mismatch forms whose texture is Cobblemon's (the model at
        every path a pack uses for that id; the poser and the animation groups too where a pack
        shadows Cobblemon's).
        --server-pack writes build/client/cobblers-client-AllTheMons-subset.zip instead: the same
        files plus the ATMxMSD subset for the missing species, derived by simulating ATMxMSD RP
        at its Cobbleverse position. The subset's path list is checked against the committed
        modpack/manifest/client-pack-atm-subset.json (--record-paths rewrites it). The zip is
        deterministic; its sha1 is printed and written beside it for server.properties.
install copies a zip into resourcepacks/ and puts it at the top of options.txt's list (backup
        beside it), for local testing. The game must be closed.

Rerun scan after every modpack, resource pack or Cobblemon update
(docs/research/CLIENT_MODEL_FIXES.md). The zips hold Cobblemon and AllTheMons assets and are
built locally under build/client/, never committed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import struct
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACK_NAME = "cobblers-model-fixes.zip"
SERVER_PACK_NAME = "cobblers-client-AllTheMons-subset.zip"
OUR_PACKS = (PACK_NAME, SERVER_PACK_NAME)
DONOR_PACK = "ATMxMSD RP.zip"
DONOR_PATHS = REPO / "modpack" / "manifest" / "client-pack-atm-subset.json"
BASE_PACK_ORDER = REPO / "base-pack" / "cobbleverse" / "config" / "resourcepackoverrides.json"
SPAWNS = REPO / "data" / "spawns.json"
PACK_FORMAT = 34  # Minecraft 1.21.1 resource packs
UV_THRESHOLD = 0.50  # in the gap: nothing measured between 20.4% and 71% on 2026-09-26
ZIP_DATE = (1980, 1, 1, 0, 0, 0)

POSER_CLASSES = "com/cobblemon/mod/common/client/render/models/blockbench/pokemon/"
TYPES = ["pokemon", "fossils", "npcs", "poke_balls", "generic", "block_entities"]
POSER_DIRS = ["bedrock/posers"] + ["bedrock/%s/posers" % t for t in TYPES]
VAR_DIRS = ["bedrock/species", "bedrock/pokemon/resolvers"] + ["bedrock/%s/variations" % t for t in TYPES]
MODEL_DIRS = ["bedrock/models"] + ["bedrock/%s/models" % t for t in TYPES]
ANIM_DIRS = ["bedrock/animations"] + ["bedrock/%s/animations" % t for t in TYPES]
GROUP_RE = re.compile(r"""bedrock(?:_primary|_stateful|_quirk)?\(\s*['"]([^'"]+)['"]""")


# ---------------------------------------------------------------- reading

def jload(b: bytes):
    """JSON, leniently: packs ship // comments and trailing commas."""
    s = b.decode("utf-8-sig", "replace")
    try:
        return json.loads(s, strict=False)
    except ValueError:
        s = re.sub(r",\s*([}\]])", r"\1", re.sub(r"(?m)^\s*//[^\n]*|\s//[^\n\"]*$", "", s))
        try:
            return json.loads(s, strict=False)
        except ValueError:
            return None


def png_size(b: bytes):
    if b[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", b[16:24])


def geometry(b: bytes) -> dict:
    doc = jload(b) or {}
    geos = doc.get("minecraft:geometry") or [{}]
    return geos[0] if isinstance(geos, list) and geos and isinstance(geos[0], dict) else {}


def bones(b: bytes) -> list[str]:
    return [x["name"] for x in geometry(b).get("bones") or [] if isinstance(x, dict) and x.get("name")]


def uv_layout(b: bytes):
    """Normalised cube UV rectangles, and the model's declared UV space (texture_width, texture_height)."""
    g = geometry(b)
    d = g.get("description") or {}
    tw, th = d.get("texture_width") or 64, d.get("texture_height") or 64
    rects = set()
    for bone in g.get("bones") or []:
        for c in (bone.get("cubes") or []) if isinstance(bone, dict) else []:
            uv = c.get("uv")
            size = tuple(round(x, 3) for x in c.get("size", []) if isinstance(x, (int, float)))
            if isinstance(uv, list) and len(uv) == 2:
                rects.add(("box", round(uv[0] / tw, 4), round(uv[1] / th, 4), size))
            elif isinstance(uv, dict):
                for face, fd in sorted(uv.items()):
                    if isinstance(fd, dict) and isinstance(fd.get("uv"), list) and len(fd["uv"]) == 2:
                        rects.add((face, round(fd["uv"][0] / tw, 4), round(fd["uv"][1] / th, 4)))
    return rects, (tw, th)


def tex_ids(t) -> list[str]:
    if isinstance(t, str):
        return [t]
    if isinstance(t, dict) and isinstance(t.get("frames"), list):
        return [f for f in t["frames"] if isinstance(f, str)]
    return []


def tex_rel(t: str) -> str:
    ns, p = t.split(":", 1) if ":" in t else ("minecraft", t)
    return "assets/%s/%s" % (ns, p)


def qualify(i: str) -> str:
    return i if ":" in i else "cobblemon:" + i


# ---------------------------------------------------------------- the stack

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


class Layer:
    def __init__(self, label: str, zf: zipfile.ZipFile, prefix: str = "", path: Path | None = None):
        self.label, self.zf, self.prefix, self.path = label, zf, prefix, path


def file_layer(path: Path, label: str | None = None) -> Layer | None:
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        return None
    prefix = ""
    if "pack.mcmeta" not in z.namelist():
        cands = [n for n in z.namelist() if n.endswith("/pack.mcmeta") and n.count("/") == 1]
        prefix = cands[0][: -len("pack.mcmeta")] if cands else ""
    return Layer(label or path.name, z, prefix, path)


_MODS: dict = {}


def mod_jars(instance: Path):
    """[(path, ZipFile, mod id)] sorted by file name, opened once per instance."""
    if instance not in _MODS:
        out = []
        for m in sorted((instance / "mods").glob("*.jar")):
            z = zipfile.ZipFile(m)
            try:
                mid = (jload(z.read("fabric.mod.json")) or {}).get("id")
            except KeyError:
                mid = None
            out.append((m, z, mid))
        _MODS[instance] = out
    return _MODS[instance]


def instance_layers(instance: Path, include_ours=True, extra=(), insert=None) -> list[Layer]:
    """Lowest priority first. include_ours=False drops our packs; extra zips go on top;
    insert=(after_entry, zip path) simulates a pack at that position."""
    enabled = list(enabled_packs(instance))
    if insert:
        after, zp = insert
        enabled.insert(enabled.index(after) + 1 if after in enabled else len(enabled), "file/" + zp.name)
    mods = mod_jars(instance)
    by_id = {mid: (m, z) for m, z, mid in mods if mid}
    out = []
    for p in enabled:
        if p == "fabric":
            out += [Layer("mod:" + m.name, z, "", m) for m, z, _ in mods]
        elif p.startswith("file/"):
            name = p[5:]
            if name in OUR_PACKS and not include_ours:
                continue
            path = instance / "resourcepacks" / name
            layer = file_layer(path) if path.is_file() else None
            if layer:
                out.append(layer)
        elif ":" in p and p.split(":", 1)[0] in by_id:
            m, z = by_id[p.split(":", 1)[0]]
            out.append(Layer(p, z, "resourcepacks/%s/" % p.split(":", 1)[1], m))
    for zp in extra:
        layer = file_layer(Path(zp), "simulated:" + Path(zp).name)
        if not layer:
            raise SystemExit("cannot open %s" % zp)
        out.append(layer)
    return out


class Stack:
    def __init__(self, layers: list[Layer], jar_label: str):
        self.layers = layers
        self.jar = next(i for i, l in enumerate(layers) if l.label == jar_label)
        self.prov: dict[str, list[int]] = {}
        for i, layer in enumerate(layers):
            pre = layer.prefix + "assets/"
            for n in layer.zf.namelist():
                if n.startswith(pre) and not n.endswith("/"):
                    rel = n[len(layer.prefix):]
                    if "/bedrock/" in rel or "/textures/pokemon/" in rel:
                        self.prov.setdefault(rel, []).append(i)
        self._reg, self._layer_models, self._cache = {}, {}, {}

    def top(self, rel, upto=None):
        ps = [i for i in self.prov.get(rel, ()) if upto is None or i <= upto]
        return ps[-1] if ps else None

    def label(self, rel, upto=None):
        i = self.top(rel, upto)
        return None if i is None else self.layers[i].label

    def read(self, rel, upto=None, layer=None) -> bytes:
        i = self.top(rel, upto) if layer is None else layer
        key = (rel, i)
        if key not in self._cache:
            lay = self.layers[i]
            self._cache[key] = lay.zf.read(lay.prefix + rel)
        return self._cache[key]

    def listing(self, dirs, suffix, upto=None):
        out = []
        for rel in self.prov:
            if not rel.endswith(suffix) or (upto is not None and self.top(rel, upto) is None):
                continue
            ns, _, path = rel[len("assets/"):].partition("/")
            if any(path.startswith(d + "/") for d in dirs):
                out.append((ns, path, rel))
        return sorted(out)

    def registry(self, kind, upto=None) -> dict[str, str]:
        """id -> winning path. models 'ns:name.geo', posers 'ns:name', anims 'name' (no namespace)."""
        if (kind, upto) not in self._reg:
            dirs, suffix = {"models": (MODEL_DIRS, ".geo.json"), "posers": (POSER_DIRS, ".json"),
                            "anims": (ANIM_DIRS, ".animation.json")}[kind]
            reg = {}
            for d in dirs:
                for ns, path, rel in self.listing([d], suffix, upto):
                    name = path.rsplit("/", 1)[-1]
                    key = name[: -len(".animation.json")] if kind == "anims" else ns + ":" + name[: -len(".json")]
                    reg[key] = rel
            self._reg[(kind, upto)] = reg
        return self._reg[(kind, upto)]

    def paths_for(self, kind, key) -> list[str]:
        """Every path in the stack that registers under this id, whichever layer ships it."""
        dirs, suffix = {"models": (MODEL_DIRS, ".geo.json"), "posers": (POSER_DIRS, ".json"),
                        "anims": (ANIM_DIRS, ".animation.json")}[kind]
        name = key.split(":", 1)[-1] + (".json" if kind != "anims" else ".animation.json")
        ns = key.split(":", 1)[0] if kind != "anims" else None
        return [rel for n_, path, rel in self.listing(dirs, suffix)
                if path.rsplit("/", 1)[-1] == name and (ns is None or n_ == ns)]

    def model_in_layer(self, layer, mid):
        if layer not in self._layer_models:
            reg = {}
            lay = self.layers[layer]
            for n in sorted(lay.zf.namelist()):
                rel = n[len(lay.prefix):]
                m = re.match(r"assets/([^/]+)/(.*)$", rel)
                if m and rel.endswith(".geo.json") and any(m.group(2).startswith(d + "/") for d in MODEL_DIRS):
                    reg[m.group(1) + ":" + rel.rsplit("/", 1)[-1][: -len(".json")]] = rel
            self._layer_models[layer] = reg
        return self._layer_models[layer].get(mid)

    def resolvers(self) -> dict[str, list]:
        if "resolvers" not in self._cache:
            out = {}
            for d in VAR_DIRS:
                for _, _, rel in self.listing([d], ".json"):
                    doc = jload(self.read(rel))
                    if not isinstance(doc, dict):
                        continue
                    sp = doc.get("species") or doc.get("name")
                    if isinstance(sp, str):
                        out.setdefault(qualify(sp), []).append((doc.get("order", 0), rel, doc))
            for lst in out.values():
                lst.sort(key=lambda x: x[0])
            self._cache["resolvers"] = out
        return self._cache["resolvers"]


def variations(entries):
    return [(rel, v) for _, rel, doc in entries for v in (doc.get("variations") or []) if isinstance(v, dict)]


def resolve(allv, aspects: set, field):
    """VaryingRenderableResolver.getVariationValue: the last variation that fits and sets the field."""
    for _, v in reversed(allv):
        if set(v.get("aspects") or []) <= aspects and v.get(field) is not None:
            return v[field]
    return None


def builtin_poser_forms(jar: zipfile.ZipFile) -> set[str]:
    """Form ids with a built-in Kotlin poser, e.g. PersianAlolanModel -> persian_alolan (approximate by class name)."""
    forms = set()
    for n in jar.namelist():
        m = re.match(re.escape(POSER_CLASSES) + r"gen\d+/(\w+?)Model\.class$", n)
        if m:
            snake = re.sub(r"(?<!^)(?=[A-Z])", "_", m.group(1)).lower()
            forms |= {snake, snake.replace("_", "")}   # GimmighoulChestModel poses "gimmighoulchest"
    return forms


# ---------------------------------------------------------------- the three rules

def crash_faults(st: Stack, builtin: set[str]) -> list[dict]:
    models, posers = st.registry("models"), st.registry("posers")
    jar_models = st.registry("models", upto=st.jar)
    has_json_poser = {k.split(":", 1)[1] for k in posers}
    out = []
    for mid, rel in sorted(models.items()):
        form = mid.split(":", 1)[1][: -len(".geo")]
        if st.top(rel) == st.jar or form in has_json_poser or form not in builtin or mid not in jar_models:
            continue
        own = jar_models[mid]
        if st.top(own, st.jar) != st.jar:
            continue
        ours = [b for b in bones(st.read(own, layer=st.jar)) if not b.startswith("locator")]
        theirs = set(bones(st.read(rel)))
        missing = [b for b in ours if b not in theirs]
        if ours and missing:
            out.append({"form": form, "pack": st.label(rel), "pack_path": rel, "cobblemon_path": own,
                        "root_missing": ours[0] in missing, "missing_parts": missing,
                        "shadow": {p: own for p in st.paths_for("models", mid) if p != own or st.top(p) != st.jar}})
    return out


def spawnable_species(instance: Path) -> dict[str, list[str]]:
    """species -> where it spawns: data/spawns.json, and implemented species in the instance's spawn pools."""
    out: dict[str, set] = {}

    def add(name, src):
        if isinstance(name, str) and name.strip():
            out.setdefault(name.split()[0].split(":")[-1].lower(), set()).add(src)

    def walk(o, top=False):
        if isinstance(o, dict):
            if isinstance(o.get("pokemon"), str):
                add(o["pokemon"], "data/spawns.json")
            elif top and isinstance(o.get("species"), str):
                add(o["species"], "data/spawns.json")
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v, top)

    if SPAWNS.is_file():
        doc = json.loads(SPAWNS.read_text(encoding="utf-8"))
        walk(doc.get("entries") or [], top=True)
        walk({k: v for k, v in doc.items() if k != "entries"})

    implemented: dict[str, bool] = {}
    pools: dict[str, set] = {}
    sources = [(m.name, z) for m, z, _ in mod_jars(instance)]
    sources.sort(key=lambda s: not s[0].startswith("Cobblemon-fabric"))  # Cobblemon's species first
    for d in sorted((instance / "datapacks").glob("*.zip")) + sorted((instance / "datapacks" / "extra").glob("*.zip")):
        try:
            sources.append((d.name, zipfile.ZipFile(d)))
        except zipfile.BadZipFile:
            continue
    for label, z in sources:
        for n in z.namelist():
            if not n.startswith("data/") or not n.endswith(".json"):
                continue
            if "/spawn_pool_world/" in n:
                d = jload(z.read(n))
                for s in (d.get("spawns") or []) if isinstance(d, dict) else []:
                    if isinstance(s, dict) and isinstance(s.get("pokemon"), str) and s["pokemon"].strip():
                        pools.setdefault(s["pokemon"].split()[0].split(":")[-1].lower(), set()).add(label)
            elif re.match(r"data/[^/]+/species/", n) or re.match(r"data/[^/]+/species_additions/", n):
                d = jload(z.read(n))
                if isinstance(d, dict) and "implemented" in d:
                    key = (d.get("target") or n.rsplit("/", 1)[1][:-5]).split(":")[-1].lower()
                    implemented[key] = bool(d["implemented"])
    for sp, srcs in pools.items():
        if implemented.get(sp):
            for s in srcs:
                out.setdefault(sp, set()).add(s)
    return {k: sorted(v) for k, v in sorted(out.items())}


def missing_faults(st: Stack, builtin: set[str], spawnable: dict) -> list[dict]:
    res = st.resolvers()
    models, posers = st.registry("models"), st.registry("posers")
    out = []
    for sp, srcs in spawnable.items():
        entries = res.get("cobblemon:" + sp)
        if not entries:
            out.append({"species": sp, "problem": ["no resolver"], "spawn_sources": srcs})
            continue
        allv = variations(entries)
        prob = []
        m, p, t = resolve(allv, set(), "model"), resolve(allv, set(), "poser"), resolve(allv, set(), "texture")
        if m is None and p is None and t is None:
            prob.append("no variation without aspects: only %s" % sorted({",".join(v.get("aspects") or []) for _, v in allv}))
        else:
            if not isinstance(m, str) or qualify(m) not in models:
                prob.append("model missing: %s" % m)
            if not isinstance(p, str) or (qualify(p) not in posers and p.split(":")[-1] not in builtin):
                prob.append("poser missing: %s" % p)
            ids = tex_ids(t)
            if t is None or (ids and any(tex_rel(i) not in st.prov for i in ids)):
                prob.append("texture missing: %s" % t)
        if prob:
            out.append({"species": sp, "problem": prob, "spawn_sources": srcs})
    return out


def uv_forms(st: Stack) -> list[dict]:
    """Every form whose effective model and texture come from different packs, with its UV match."""
    models = st.registry("models")
    seen, out = set(), []
    for sp, entries in sorted(st.resolvers().items()):
        allv = variations(entries)
        for _, v0 in allv:
            if not any(k in v0 for k in ("model", "texture")):
                continue
            aspects = set(v0.get("aspects") or [])
            m, t = resolve(allv, aspects, "model"), resolve(allv, aspects, "texture")
            ids = tex_ids(t)
            if not isinstance(m, str) or not ids or "/textures/pokemon/" not in tex_rel(ids[0]):
                continue
            mid, trel = qualify(m), tex_rel(ids[0])
            mrel = models.get(mid)
            if not mrel or trel not in st.prov or (mrel, trel) in seen:
                continue
            seen.add((mrel, trel))
            ml, tl = st.top(mrel), st.top(trel)
            if ml == tl:
                continue
            ref = st.model_in_layer(tl, mid)
            ref_layer = tl if ref else None
            if not ref:
                ref = st.registry("models", upto=tl).get(mid)
                ref_layer = st.top(ref, tl) if ref else None
            if not ref:
                continue
            mb, rb = st.read(mrel), st.read(ref, layer=ref_layer)
            rects, (tw, th) = uv_layout(mb)
            if mb == rb:
                match = 1.0
            else:
                rrects, _ = uv_layout(rb)
                match = len(rects & rrects) / len(rects) if rects else 1.0
            ts = png_size(st.read(trel))
            aspect_ok = not ts or ts[0] * th == ts[1] * tw
            out.append({"species": sp.split(":", 1)[1], "aspects": sorted(aspects), "model": mid,
                        "model_path": mrel, "model_pack": st.layers[ml].label,
                        "texture": trel, "texture_pack": st.layers[tl].label,
                        "drawn_for": ref, "drawn_for_pack": st.layers[ref_layer].label,
                        "uv_match": round(match, 3), "texture_size": list(ts) if ts else None,
                        "model_uv_space": [tw, th], "aspect_ok": aspect_ok,
                        "flagged": match < UV_THRESHOLD or not aspect_ok})
    return out


def histogram(forms):
    """Split forms by UV match; the in-between band is listed so a form drifting into the gap is seen."""
    h = {">=95%": 0, "50-95%": [], "20-50%": [], "<20%": 0, "aspect_mismatch": 0}
    for f in forms:
        m = f["uv_match"]
        if m >= 0.95:
            h[">=95%"] += 1
        elif m < 0.20:
            h["<20%"] += 1
        else:
            h["50-95%" if m >= UV_THRESHOLD else "20-50%"].append("%s %d%%" % (form_key(f), round(m * 100)))
        h["aspect_mismatch"] += not f["aspect_ok"]
    return h


def form_key(f):
    return f["species"] + ("[%s]" % ",".join(f["aspects"]) if f["aspects"] else "")


# ---------------------------------------------------------------- scan

def stack_for(instance: Path, **kw) -> Stack:
    return Stack(instance_layers(instance, **kw), "mod:" + cobblemon_jar(instance).name)


def faults(st: Stack, builtin, spawnable) -> dict:
    uv = uv_forms(st)
    return {"crash": crash_faults(st, builtin), "missing": missing_faults(st, builtin, spawnable),
            "uv_mismatch": [f for f in uv if f["flagged"]], "uv_histogram": histogram(uv), "uv_split_forms": len(uv)}


def scan(instance: Path, with_packs=()) -> dict:
    jar = zipfile.ZipFile(cobblemon_jar(instance))
    builtin = builtin_poser_forms(jar)
    spawnable = spawnable_species(instance)
    base = stack_for(instance, include_ours=False)
    eff = stack_for(instance, include_ours=True, extra=with_packs)
    fb, fe = faults(base, builtin, spawnable), faults(eff, builtin, spawnable)
    names = {"crash": lambda f: f["form"], "missing": lambda f: f["species"], "uv_mismatch": form_key}
    uncovered = {k: sorted({names[k](f) for f in fe[k]}) for k in names}
    ours = [l.label for l in eff.layers if l.label in OUR_PACKS or l.label.startswith("simulated:")]
    return {"instance": str(instance), "cobblemon": cobblemon_jar(instance).name,
            "our_packs_in_effect": ours, "packs_scanned": len(eff.layers),
            "spawnable_species": len(spawnable),
            "counts": {"flagged": {k: len({names[k](f) for f in fb[k]}) for k in names},
                       "uncovered": {k: len(v) for k, v in uncovered.items()}},
            "uv_histogram": {"without_our_packs": fb["uv_histogram"], "effective": fe["uv_histogram"]},
            "uncovered": uncovered,
            "rules": {"crash": "built-in poser (no JSON poser anywhere) whose effective model lacks a non-locator part of Cobblemon's model",
                      "missing": "spawnable species with no resolver, or whose base variation's model/poser/texture is absent",
                      "uv_mismatch": "under %d%% of the model's UV rectangles in the model its texture was drawn for, or texture aspect != model UV space" % (UV_THRESHOLD * 100)},
            "flagged": {k: fb[k] for k in names}}


# ---------------------------------------------------------------- build

def cobblemon_fixes(instance: Path):
    """dst path -> (source label, src path, bytes) for Cobblemon's own files, plus what they cover."""
    st = stack_for(instance, include_ours=False)
    jar = st.layers[st.jar]
    builtin = builtin_poser_forms(jar.zf)
    files, covered = {}, {"crash": [], "uv_mismatch": [], "uv_mismatch_left": [], "poser_kept": []}
    for f in crash_faults(st, builtin):
        for dst, src in f["shadow"].items():
            files[dst] = (jar.label, src)
        covered["crash"].append(f["form"])
    jar_posers, jar_anims = st.registry("posers", upto=st.jar), st.registry("anims", upto=st.jar)
    posers, anims = st.registry("posers"), st.registry("anims")
    res = st.resolvers()
    for f in uv_forms(st):
        if not f["flagged"]:
            continue
        # Only a texture Cobblemon drew, on its own model id, is restored with Cobblemon's files.
        if f["texture_pack"] != jar.label or f["drawn_for_pack"] != jar.label:
            covered["uv_mismatch_left"].append(form_key(f))
            continue
        for p in st.paths_for("models", f["model"]):
            if st.top(p) != st.jar:
                files[p] = (jar.label, f["drawn_for"])
        pid = resolve(variations(res["cobblemon:" + f["species"]]), set(f["aspects"]), "poser")
        pid = qualify(pid) if isinstance(pid, str) else None
        if pid in jar_posers and st.top(posers[pid]) != st.jar:
            for p in st.paths_for("posers", pid):
                if st.top(p) != st.jar:
                    files[p] = (jar.label, jar_posers[pid])
        elif pid in posers and st.top(posers[pid]) != st.jar:
            # Cobblemon poses this form with a built-in poser, and a pack's JSON poser of the same
            # name replaces it. No file can restore a built-in poser, so the pack's poser stays.
            covered["poser_kept"].append("%s: %s (%s)" % (form_key(f), posers[pid], st.label(posers[pid])))
        if pid in jar_posers:
            for g in sorted(set(GROUP_RE.findall(st.read(jar_posers[pid], layer=st.jar).decode("utf-8-sig", "replace")))):
                if g in jar_anims and g in anims and st.top(anims[g]) != st.jar:
                    for p in st.paths_for("anims", g):
                        if st.top(p) != st.jar:
                            files[p] = (jar.label, jar_anims[g])
        covered["uv_mismatch"].append(form_key(f))
    # A pack's resolver at Cobblemon's own path can still pair the restored model with textures drawn
    # for the old one (E19's Arbok snake patterns: 128x64 textures for the 1.7 model). Simulate the
    # fixes; for a species whose restored model still mismatches a pack texture, restore Cobblemon's
    # resolvers where a pack shadows them at the same path.
    restored = {f.split("[")[0] for f in covered["uv_mismatch"]}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for dst, (_, src) in files.items():
            zf.writestr(dst, st.read(src, layer=st.jar))
    sim = Stack(st.layers + [Layer("simulated:fixes", zipfile.ZipFile(buf))], jar.label)
    covered["resolver_restored"] = []
    for f in uv_forms(sim):
        if not f["flagged"] or f["species"] not in restored or f["model_pack"] != "simulated:fixes":
            continue
        for _, rel, _ in sim.resolvers().get("cobblemon:" + f["species"], []):
            if st.top(rel) not in (None, st.jar) and st.jar in st.prov.get(rel, ()):
                files[rel] = (jar.label, rel)
                if f["species"] + ": " + rel not in covered["resolver_restored"]:
                    covered["resolver_restored"].append(f["species"] + ": " + rel)
        covered["uv_mismatch"].append(form_key(f))
        if form_key(f) in covered["uv_mismatch_left"]:
            covered["uv_mismatch_left"].remove(form_key(f))
    out = {dst: (lab, src, st.read(src, layer=st.jar)) for dst, (lab, src) in files.items()}
    return out, covered


def donor_position() -> str:
    """The entry Cobbleverse puts right below ATMxMSD RP (base-pack resourcepackoverrides.json)."""
    try:
        order = json.loads(BASE_PACK_ORDER.read_text(encoding="utf-8"))["default_packs"]
        return order[order.index("file/" + DONOR_PACK) - 1]
    except (OSError, ValueError, KeyError, IndexError):
        return "cobblemon:regionbiasforms"


def donor_subset(instance: Path, layer_textures=True, no_resolver_only=False):
    """The ATMxMSD files the missing species need, simulated at ATMxMSD's Cobbleverse position.

    layer_textures=False, no_resolver_only=True reproduces the 2026-09-26 audit's list (223 paths),
    which left out the textures of resolver layers (emissive, glow) and the species that have a
    resolver but no variation without aspects."""
    donor = instance / "resourcepacks" / DONOR_PACK
    if not donor.is_file():
        raise SystemExit("donor pack not found: %s" % donor)
    jar = zipfile.ZipFile(cobblemon_jar(instance))
    builtin = builtin_poser_forms(jar)
    base = stack_for(instance, include_ours=False)
    missing = [f["species"] for f in missing_faults(base, builtin, spawnable_species(instance))
               if not no_resolver_only or f["problem"] == ["no resolver"]]
    sim = stack_for(instance, include_ours=False, insert=(donor_position(), donor))
    dl = next(i for i, l in enumerate(sim.layers) if l.path == donor)
    names = {n for n in sim.layers[dl].zf.namelist() if not n.endswith("/")}
    models, posers, anims = sim.registry("models"), sim.registry("posers"), sim.registry("anims")
    res = sim.resolvers()
    refs, unresolved, not_in_donor = set(), [], []
    for sp in missing:
        entries = res.get("cobblemon:" + sp)
        if not entries or all(sim.top(rel) != dl for _, rel, _ in entries):
            not_in_donor.append(sp)
            continue
        refs |= {rel for _, rel, _ in entries}
        for _, v in variations(entries):
            if isinstance(v.get("model"), str):
                if qualify(v["model"]) in models:
                    refs.add(models[qualify(v["model"])])
                else:
                    unresolved.append(v["model"])
            if isinstance(v.get("poser"), str):
                pid = qualify(v["poser"])
                if pid in posers:
                    refs.add(posers[pid])
                elif pid.split(":")[1] not in builtin:
                    unresolved.append(v["poser"])
            texs = tex_ids(v.get("texture"))
            if layer_textures:
                texs += [t for layer in (v.get("layers") or []) if isinstance(layer, dict)
                         for t in tex_ids(layer.get("texture"))]
            for t in texs:
                if tex_rel(t) in sim.prov:
                    refs.add(tex_rel(t))
                else:
                    unresolved.append(t)
    for rel in sorted(refs):
        if "/posers/" in rel and sim.top(rel) == dl:
            for g in GROUP_RE.findall(sim.read(rel, layer=dl).decode("utf-8-sig", "replace")):
                if g in anims:
                    refs.add(anims[g])
                else:
                    unresolved.append("animation group " + g)
    # Only paths ATMxMSD ships are its business; a resolver, model or texture another layer alone
    # provides (a ZAMegas mega resolver, say) is already on every client.
    need = sorted(r for r in refs if r in names)
    # A path a pack above ATMxMSD also ships stays with that pack, as in Cobbleverse's own order.
    left = {n: sim.label(n) for n in need if sim.top(n) != dl}
    collisions = []
    base_reg = {k: base.registry(k) for k in ("models", "posers", "anims")}
    for n in need:
        name = n.rsplit("/", 1)[-1]
        kind = "models" if "/models/" in n else "posers" if "/posers/" in n else "anims" if "/animations/" in n else None
        if kind:
            key = name[: -len(".animation.json")] if kind == "anims" else "cobblemon:" + name[: -len(".json")]
            if key in base_reg[kind] and base_reg[kind][key] != n:
                collisions.append({"path": n, "id": key, "already": base_reg[kind][key],
                                   "pack": base.label(base_reg[kind][key])})
    files = {n: (DONOR_PACK, n, sim.read(n, layer=dl)) for n in need if n not in left}
    return {"species": missing, "not_in_donor": not_in_donor, "paths": need, "unresolved": sorted(set(unresolved)),
            "left_to_stack": left, "collisions": collisions, "donor": donor, "files": files,
            "position_after": donor_position()}


def donor_credits(donor: Path) -> dict:
    z = zipfile.ZipFile(donor)
    text = z.read("readme.md").decode("utf-8", "replace") if "readme.md" in z.namelist() else ""
    people, section = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().rstrip(":")
        elif line.startswith("- ") and section:
            people.setdefault(section, []).append(line[2:].strip())
    desc = (jload(z.read("pack.mcmeta")) or {}).get("pack", {}).get("description", "")
    version = re.search(r"Version\s+([\w.]+)", desc if isinstance(desc, str) else "")
    return {"people": people, "version": version.group(1) if version else None,
            "license": z.read("LICENSE") if "LICENSE" in z.namelist() else None}


def write_zip(out: Path, entries: dict[str, bytes]):
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, entries[name])


def sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def build(instance: Path, out: Path) -> dict:
    files, covered = cobblemon_fixes(instance)
    manifest = {"cobblemon": cobblemon_jar(instance).name, "covers": covered,
                "files": {d: s for d, (_, s, _) in sorted(files.items())}}
    entries = {d: b for d, (_, _, b) in files.items()}
    entries["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT,
        "description": "Cobblers: Cobblemon 1.8 models for forms other packs break"}}, indent=1).encode()
    entries["cobblers-model-fixes.json"] = json.dumps(manifest, indent=1).encode()
    write_zip(out, entries)
    return manifest


def build_server_pack(instance: Path, out: Path, record_paths=False) -> dict:
    files, covered = cobblemon_fixes(instance)
    sub = donor_subset(instance)
    if sub["unresolved"] or sub["collisions"] or sub["not_in_donor"]:
        raise SystemExit("donor subset is not clean:\n" + json.dumps(
            {k: sub[k] for k in ("unresolved", "collisions", "not_in_donor")}, indent=1))
    recorded = json.loads(DONOR_PATHS.read_text(encoding="utf-8")) if DONOR_PATHS.is_file() else None
    derived = {"source": DONOR_PACK, "source_sha256": hashlib.sha256(sub["donor"].read_bytes()).hexdigest(),
               "derived_by": "tools/client_model_fix.py build --server-pack",
               "simulated_after": sub["position_after"], "species": sub["species"],
               "left_to_stack": sub["left_to_stack"], "paths": sub["paths"]}
    if record_paths or recorded is None:
        DONOR_PATHS.parent.mkdir(parents=True, exist_ok=True)
        DONOR_PATHS.write_text(json.dumps(derived, indent=1) + "\n", encoding="utf-8")
    elif recorded.get("paths") != derived["paths"] or recorded.get("species") != derived["species"]:
        added = sorted(set(derived["paths"]) - set(recorded.get("paths", [])))
        gone = sorted(set(recorded.get("paths", [])) - set(derived["paths"]))
        raise SystemExit("the derived ATMxMSD subset differs from %s (+%d -%d paths); review and rerun with "
                         "--record-paths\n  added: %s\n  removed: %s" % (DONOR_PATHS.relative_to(REPO), len(added),
                                                                         len(gone), added[:10], gone[:10]))
    clash = sorted(set(files) & set(sub["files"]))
    if clash:
        raise SystemExit("a Cobblemon fix and the donor subset write the same path: %s" % clash)
    cred = donor_credits(sub["donor"])
    contributors = cred["people"].get("Contributors", [])
    entries = {d: b for d, (_, _, b) in files.items()}
    entries.update({d: b for d, (_, _, b) in sub["files"].items()})
    credits = {"AllTheMons": "AllTheMons x Mega Showdown (ATMxMSD RP %s), (c) EasySqueeze & Lvnatic. Models, "
                             "animations and textures by its contributors; unaltered subset, not monetized."
                             % (cred["version"] or "?"),
               "AllTheMons contributors": contributors,
               "Cobblemon": "Cobblemon 1.8 model, poser and animation files from %s" % cobblemon_jar(instance).name}
    entries["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT,
        "description": "Cobblers client pack: an AllTheMons subset (%d species) and Cobblemon 1.8 model fixes. "
                       "AllTheMons by Lvnatic and contributors" % len(sub["species"])},
        "credits": credits}, indent=1, ensure_ascii=False).encode("utf-8")
    lines = ["# Credits", "", "This pack is a modified copy of **AllTheMons** (ATMxMSD RP %s), (c) EasySqueeze & "
             "Lvnatic, redistributed unaltered in part and without monetization. It holds only the files for the "
             "species listed in cobblers-client-pack.json." % (cred["version"] or "?"), ""]
    for section, ppl in cred["people"].items():
        lines += ["## AllTheMons: " + section, ""] + ["- " + p for p in ppl] + [""]
    lines += ["## Cobblemon", "", "Model, poser and animation files from Cobblemon 1.8 (%s), placed at the paths "
              "that override other packs." % cobblemon_jar(instance).name, ""]
    entries["CREDITS.md"] = "\n".join(lines).encode("utf-8")
    if cred["license"]:
        entries["LICENSE-AllTheMons.md"] = cred["license"]
    manifest = {"cobblemon": cobblemon_jar(instance).name, "donor": derived, "covers": covered,
                "cobblemon_files": {d: s for d, (_, s, _) in sorted(files.items())},
                "donor_files": sorted(sub["files"])}
    entries["cobblers-client-pack.json"] = json.dumps(manifest, indent=1).encode()
    write_zip(out, entries)
    digest = sha1(out)
    out.with_name(out.name + ".sha1").write_text(digest + "\n", encoding="ascii")
    manifest["sha1"] = digest
    return manifest


# ---------------------------------------------------------------- install

def install(instance: Path, zip_path: Path) -> list[str]:
    name = zip_path.name
    shutil.copy2(zip_path, instance / "resourcepacks" / name)
    opts = instance / "options.txt"
    backup = opts.with_name("options.txt.pre-cobblers-model-fixes")
    if not backup.exists():
        shutil.copy2(opts, backup)
    lines = opts.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("resourcePacks:"):
            packs = [p for p in json.loads(line.split(":", 1)[1]) if p != "file/" + name]
            packs.append("file/" + name)   # last = highest priority
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
        if name == "scan":
            s.add_argument("--with-pack", action="append", default=[], type=Path,
                           help="simulate this zip above every pack, as a server resource pack")
            s.add_argument("--full", action="store_true", help="include every flagged record, not just names")
        if name == "build":
            s.add_argument("--out", type=Path)
            s.add_argument("--server-pack", action="store_true")
            s.add_argument("--record-paths", action="store_true")
        if name == "install":
            s.add_argument("--zip", type=Path, default=Path("build/client") / PACK_NAME)
    a = p.parse_args(argv)
    if a.cmd == "scan":
        r = scan(a.instance, a.with_pack)
        if not a.full:
            r["flagged"] = {"crash": [f["form"] for f in r["flagged"]["crash"]],
                            "missing": [f["species"] for f in r["flagged"]["missing"]],
                            "uv_mismatch": ["%s (%s model, %s texture, %d%%%s)" % (
                                form_key(f), f["model_pack"], f["texture_pack"], f["uv_match"] * 100,
                                "" if f["aspect_ok"] else ", aspect %s vs %s" % (f["texture_size"], f["model_uv_space"]))
                                for f in r["flagged"]["uv_mismatch"]]}
        print(json.dumps(r, indent=1, ensure_ascii=False))
        return 1 if any(r["uncovered"].values()) else 0
    if a.cmd == "build":
        if a.server_pack:
            out = a.out or Path("build/client") / SERVER_PACK_NAME
            m = build_server_pack(a.instance, out, a.record_paths)
            print("%s: %d Cobblemon file(s) (crash %d, uv %d forms), %d ATMxMSD file(s) of %d derived for %d species"
                  % (out, len(m["cobblemon_files"]), len(m["covers"]["crash"]), len(m["covers"]["uv_mismatch"]),
                     len(m["donor_files"]), len(m["donor"]["paths"]), len(m["donor"]["species"])))
            print("left to the stack:", m["donor"]["left_to_stack"])
            print("uv_mismatch not restorable from Cobblemon:", m["covers"]["uv_mismatch_left"])
            print("pack poser kept (Cobblemon's is built in):", m["covers"]["poser_kept"])
            print("Cobblemon resolver restored:", m["covers"]["resolver_restored"])
            print("size %d bytes" % out.stat().st_size)
            print("sha1 %s  (written to %s.sha1)" % (m["sha1"], out))
            return 0
        out = a.out or Path("build/client") / PACK_NAME
        m = build(a.instance, out)
        print("%s: %d file(s); crash %s; uv %s" % (out, len(m["files"]), m["covers"]["crash"], m["covers"]["uv_mismatch"]))
        return 0
    packs = install(a.instance, a.zip)
    print("installed; top of the pack list:", packs[-3:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
