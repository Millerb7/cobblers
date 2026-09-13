#!/usr/bin/env python
"""Inventory every structure and value-carrying worldgen feature the server's pack expects.

Reads the same jars and datapacks as tools/spawn_biomes.py (vanilla, mods with
nested jars, loaded datapacks) and, for each structure:

  - where it comes from and what type it is
  - the biomes it may generate in, resolved to loaded biome IDs, and its dimension
  - its structure set: placement type, spacing, separation, set-mates and weight
  - footprint: start template size, jigsaw depth and max distance from centre
  - what is inside, from its templates: loot tables, spawners, entities,
    non-vanilla blocks, jigsaw pools reached
  - what depends on it: spawn entries whose condition or anticondition names the
    structure (directly, through a structure tag, or through a spawn preset),
    and advancements that mention it

With --world it also reads a saved world's region files and reports structure
starts found inside and outside the authored bounds from data/world.json.

It classifies nothing. Classes are an authored decision recorded in the docs.

  python tools/structure_inventory.py --server-dir ../cobblers-server \\
      --world ../cobblers-server/erosion-land-8k --out derived/structures/inventory.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import nbt
import spawn_biomes as SB

ROOT = Path(__file__).resolve().parent.parent

STRUCTURE_RE = re.compile(r"^data/([^/]+)/worldgen/structure/(.+)\.json$")
SET_RE = re.compile(r"^data/([^/]+)/worldgen/structure_set/(.+)\.json$")
POOL_RE = re.compile(r"^data/([^/]+)/worldgen/template_pool/(.+)\.json$")
TEMPLATE_RE = re.compile(r"^data/([^/]+)/structures?/(.+)\.nbt$")
STAG_RE = re.compile(r"^data/([^/]+)/tags/worldgen/structure/(.+)\.json$")
PRESET_RE = re.compile(r"^data/([^/]+)/spawn_detail_presets/(.+)\.json$")
ADV_RE = re.compile(r"^data/([^/]+)/advancements?/(.+)\.json$")
PLACED_RE = re.compile(r"^data/([^/]+)/worldgen/placed_feature/(.+)\.json$")
CONFIGURED_RE = re.compile(r"^data/([^/]+)/worldgen/configured_feature/(.+)\.json$")

# Structure types whose layout is generated in code, not from templates.
CODE_TYPES = {
    "minecraft:buried_treasure", "minecraft:desert_pyramid", "minecraft:end_city", "minecraft:fortress",
    "minecraft:igloo", "minecraft:jungle_temple", "minecraft:mineshaft", "minecraft:nether_fossil",
    "minecraft:ocean_monument", "minecraft:ocean_ruin", "minecraft:ruined_portal", "minecraft:shipwreck",
    "minecraft:stronghold", "minecraft:swamp_hut", "minecraft:woodland_mansion",
}


def ident(m):
    return "%s:%s" % m.groups()


class Index:
    def __init__(self, packs):
        self.packs = packs
        self.structures, self.structure_src = {}, defaultdict(list)
        self.sets, self.pools, self.templates, self.presets = {}, {}, {}, {}
        self.stags, self.advancements = {}, {}
        self.placed, self.configured = {}, {}
        for pk in packs:
            for path in pk.files:
                for rx, table, src in ((STRUCTURE_RE, self.structures, self.structure_src), (SET_RE, self.sets, None),
                                       (POOL_RE, self.pools, None), (PRESET_RE, self.presets, None),
                                       (STAG_RE, self.stags, None), (ADV_RE, self.advancements, None),
                                       (PLACED_RE, self.placed, None), (CONFIGURED_RE, self.configured, None)):
                    m = rx.match(path)
                    if m:
                        key = ident(m)
                        table[key] = (pk, path)
                        if src is not None:
                            src[key].append(pk.name)
                        break
                else:
                    m = TEMPLATE_RE.match(path)
                    if m:
                        self.templates[ident(m)] = (pk, path)
        self._tcache = {}

    def json(self, table, key):
        pk, path = table[key]
        try:
            return pk.read_json(path)
        except ValueError:
            return None

    def structure_tag_members(self):
        """structure id -> set of structure tags that contain it (resolved, nested)."""
        raw = {}
        for key, (pk, path) in self.stags.items():
            doc = pk.read_json(path)
            raw["#" + key] = [v if isinstance(v, str) else v["id"] for v in doc.get("values", [])]

        def expand(tag, seen=()):
            out = set()
            for v in raw.get(tag, []):
                if v.startswith("#"):
                    if v not in seen:
                        out |= expand(v, seen + (tag,))
                else:
                    out.add(v)
            return out
        member_of = defaultdict(set)
        for tag in raw:
            for s in expand(tag):
                member_of[s].add(tag)
        return member_of

    def template(self, tid):
        """Summary of a structure template: size, loot tables, spawners, entities, modded blocks, jigsaw pools."""
        if tid in self._tcache:
            return self._tcache[tid]
        if tid not in self.templates:
            self._tcache[tid] = None
            return None
        pk, path = self.templates[tid]
        try:
            _, root = nbt.loads(pk.files[path]())
        except Exception as exc:  # a corrupt template is reported, not fatal
            self._tcache[tid] = {"error": str(exc)}
            return self._tcache[tid]
        palette = root.get("palette") or (root.get("palettes") or [[]])[0]
        names = [p.get("Name", "") for p in palette]
        info = {"size": root.get("size"), "loot_tables": Counter(), "spawners": Counter(),
                "entities": Counter(), "modded_blocks": Counter(), "jigsaw_pools": set(), "block_entities": Counter(),
                "trainers": Counter(), "commands": Counter(), "required_advancements": Counter()}
        for i, name in enumerate(names):
            if name and not name.startswith("minecraft:"):
                info["modded_blocks"][name] += 0
        for b in root.get("blocks") or []:
            name = names[b.get("state", 0)] if b.get("state", 0) < len(names) else ""
            if name and not name.startswith("minecraft:"):
                info["modded_blocks"][name] += 1
            tag = b.get("nbt")
            if not tag:
                continue
            bid = tag.get("id")
            if bid:
                info["block_entities"][bid] += 1
            if tag.get("LootTable"):
                info["loot_tables"][tag["LootTable"]] += 1
            for tr in tag.get("TrainerIds") or []:
                info["trainers"][tr] += 1
            if tag.get("Command"):
                info["commands"][tag["Command"][:160]] += 1
            if tag.get("requiredAdvancement"):
                info["required_advancements"][tag["requiredAdvancement"]] += 1
            if name == "minecraft:jigsaw" and tag.get("pool"):
                info["jigsaw_pools"].add(tag["pool"])
            if "SpawnData" in tag or "spawn_data" in tag:
                sd = tag.get("SpawnData") or tag.get("spawn_data") or {}
                ent = (sd.get("entity") or {}).get("id") or "unspecified"
                info["spawners"][ent] += 1
        for e in root.get("entities") or []:
            en = e.get("nbt") or {}
            eid = en.get("id", "?")
            species = en.get("Pokemon", {}).get("Species") if isinstance(en.get("Pokemon"), dict) else None
            info["entities"][eid + (" (%s)" % species if species else "")] += 1
        self._tcache[tid] = info
        return info

    def pool_elements(self, pool_id):
        if pool_id not in self.pools:
            return []
        doc = self.json(self.pools, pool_id) or {}
        out = []

        def walk(el):
            et = el.get("element_type", "")
            if et.endswith("list_pool_element"):
                for sub in el.get("elements", []):
                    walk(sub)
            elif "location" in el:
                out.append(("template", el["location"]))
            elif "feature" in el:
                out.append(("feature", el["feature"]))
        for entry in doc.get("elements", []):
            walk(entry.get("element", {}))
        return out


def structure_record(ix, sid, biomes, tags, dims, member_of_tags, set_of, spawn_deps, adv_deps):
    doc = ix.json(ix.structures, sid) or {}
    raw_biomes = doc.get("biomes")
    refs = [raw_biomes] if isinstance(raw_biomes, str) else list(raw_biomes or [])
    # IDs without a namespace default to minecraft:, as in the game
    refs = [("#" if r.startswith("#") else "") + (r.lstrip("#") if ":" in r else "minecraft:" + r.lstrip("#")) for r in refs]
    resolved = set()
    for r in refs:
        resolved |= SB.resolve(r, biomes, tags)
    dim = [name for name, members in dims.items() if resolved & members]
    rec = {
        "id": sid, "defined_by": ix.structure_src[sid][-1], "overridden_from": ix.structure_src[sid][:-1],
        "type": doc.get("type"), "step": doc.get("step"), "terrain_adaptation": doc.get("terrain_adaptation"),
        "biomes_raw": raw_biomes, "biomes_resolved": sorted(resolved),
        "dimension": dim[0] if len(dim) == 1 else ("+".join(dim) if dim else "unresolved"),
        "spawn_overrides": sorted((doc.get("spawn_overrides") or {}).keys()),
        "structure_sets": set_of.get(sid, []),
        "generates": bool(set_of.get(sid)),
        "structure_tags": sorted(member_of_tags.get(sid, [])),
        "jigsaw": None, "footprint": None, "contents": None,
        "spawn_dependencies": spawn_deps.get(sid, {"entries": 0, "species": []}),
        "advancements": adv_deps.get(sid, []),
        "referenced_by": {},
        "signals": [],
    }
    if doc.get("type") in CODE_TYPES or (doc.get("type") and not doc.get("start_pool")):
        rec["footprint"] = {"kind": "code-generated", "note": "layout is produced in code; size not read from data"}
        return rec
    start = doc.get("start_pool")
    rec["jigsaw"] = {"start_pool": start, "size": doc.get("size"), "max_distance_from_center": doc.get("max_distance_from_center"),
                     "start_height": doc.get("start_height"), "project_start_to_heightmap": doc.get("project_start_to_heightmap")}
    # traverse pools reachable from the start pool
    seen_pools, queue, templates = set(), [start], []
    start_templates = []
    while queue and len(seen_pools) < 400:
        pid = queue.pop()
        if not pid or pid in seen_pools or pid == "minecraft:empty":
            continue
        seen_pools.add(pid)
        for kind, loc in ix.pool_elements(pid):
            if kind != "template":
                continue
            if pid == start:
                start_templates.append(loc)
            if loc in templates:
                continue
            templates.append(loc)
            t = ix.template(loc)
            if t and "jigsaw_pools" in t:
                queue.extend(p for p in t["jigsaw_pools"] if p not in seen_pools)
    agg = {"loot_tables": Counter(), "spawners": Counter(), "entities": Counter(), "modded_blocks": Counter(),
           "block_entities": Counter(), "trainers": Counter(), "commands": Counter(), "required_advancements": Counter()}
    missing = []
    for loc in templates:
        t = ix.template(loc)
        if not t or "error" in t:
            missing.append(loc)
            continue
        for k in agg:
            agg[k].update(t[k])
    sizes = [ix.template(t)["size"] for t in start_templates if ix.template(t) and ix.template(t).get("size")]
    multi = len(templates) > len(start_templates) or (doc.get("size") or 1) > 1 and len(seen_pools) > 1
    rec["footprint"] = {
        "kind": "jigsaw" if multi else "single_template",
        "start_template_size_xyz": sizes[0] if len(sizes) == 1 else (sizes[:4] if sizes else None),
        "bound_if_jigsaw": (2 * (doc.get("max_distance_from_center") or 0)) if multi else None,
        "pools": len(seen_pools), "templates": len(templates), "templates_missing": missing[:10],
    }
    rec["contents"] = {k: dict(v.most_common(12 if k != "commands" else 30)) for k, v in agg.items()}
    rec["signals"] = signals(agg)
    return rec


SIGNAL_BLOCKS = {
    "altar": re.compile(r"_altar$|_shrine$|mew_shrine|calyrex_statue|summon_(trigger|anchor)|stark_forge|eternatus_cocoon|pokemon_trial_spawner|mega_stone_crystal|keystone_ore|wishing_star_crystal"),
    "trainer": re.compile(r"trainer_spawner|trainer_(pokemon|stand)_position"),
    "healing": re.compile(r"healing_machine|:pc$"),
    "fossil": re.compile(r"fossil|restoration_tank"),
    "habitat_spawner": re.compile(r"habitat_block"),
    "treasure": re.compile(r"gilded_chest|gimmighoul_chest|relic_coin"),
}


def signals(agg):
    """Plain flags for what a structure carries, from its blocks, entities and commands."""
    names = set(agg["modded_blocks"]) | set(agg["block_entities"]) | set(agg["entities"])
    out = sorted({k for k, rx in SIGNAL_BLOCKS.items() for n in names if rx.search(n)})
    if agg["loot_tables"]:
        out.append("loot")
    if agg["spawners"] or "minecraft:trial_spawner" in agg["block_entities"] or "minecraft:mob_spawner" in agg["block_entities"]:
        out.append("mob_spawner")
    if "minecraft:brushable_block" in agg["block_entities"]:
        out.append("archaeology")
    if "minecraft:vault" in agg["block_entities"]:
        out.append("vault")
    if agg["commands"]:
        out.append("command_blocks")
        if any("pokespawn" in c for c in agg["commands"]):
            out.append("scripted_pokemon_spawn")
        if any("advancements=" in c for c in agg["commands"]):
            out.append("advancement_gate")
    if agg["required_advancements"]:
        out.append("advancement_gate")
    if any("cobblemon:pokemon" in e for e in agg["entities"]):
        out.append("placed_pokemon")
    return sorted(set(out))


def spawn_structure_deps(ix, packs, installed, member_of_tags):
    """structure id -> {entries, species} from spawn conditions and presets."""
    preset_structs = {}
    for key, (pk, path) in ix.presets.items():
        doc = pk.read_json(path)
        cond = doc.get("condition") or {}
        if cond.get("structures"):
            preset_structs[key.split(":", 1)[1]] = list(cond["structures"])
    entries, _ = SB.collect_entries(packs, "pack", installed)
    # collect_entries drops conditions other than biomes; reread the structures field
    pools = {}
    for pk in packs:
        for path in pk.files:
            if SB.SPAWN_RE.match(path):
                pools[path] = pk
    out = defaultdict(lambda: {"entries": 0, "anti_entries": 0, "species": set(), "via": set()})
    tag_members = defaultdict(set)
    for s, tagset in member_of_tags.items():
        for t in tagset:
            tag_members[t].add(s)
    for path, pk in pools.items():
        doc = pk.read_json(path)
        if doc.get("enabled") is False:
            continue
        for sp in doc.get("spawns") or []:
            names = SB.species_of(sp)
            for field, key in (("condition", "entries"), ("anticondition", "anti_entries")):
                refs = list((sp.get(field) or {}).get("structures") or [])
                via = {}
                if field == "condition":
                    for pr in sp.get("presets") or []:
                        for r in preset_structs.get(pr, []):
                            refs.append(r)
                            via[r] = "preset:" + pr
                for r in refs:
                    targets = tag_members.get(r, set()) if r.startswith("#") else {r}
                    for t in targets:
                        o = out[t]
                        o[key] += 1
                        if key == "entries":
                            o["species"].update(names)
                        o["via"].add(via.get(r, r))
    return {k: {"entries": v["entries"], "anti_entries": v["anti_entries"], "species": sorted(v["species"]),
                "via": sorted(v["via"])} for k, v in out.items()}


def data_references(packs, structure_ids, member_of_tags):
    """structure id -> {category: [file ids]} for every JSON file that names the structure or one of its tags.

    Catches advancements (location predicates), loot tables (explorer maps),
    villager and map-trader trades, recipes for locator items, and anything else.
    Structure definitions, sets, pools and structure tags themselves are skipped.
    """
    skip = re.compile(r"/worldgen/(structure|structure_set|template_pool)/|/tags/worldgen/structure/")
    names = {sid: [sid] + sorted(member_of_tags.get(sid, [])) for sid in structure_ids}
    needles = defaultdict(set)
    for sid, ns in names.items():
        for n in ns:
            needles[n].add(sid)
    rx = re.compile(r'"(#?[a-z0-9_.\-]+:[a-z0-9_./\-]+)"')
    out = defaultdict(lambda: defaultdict(set))
    for pk in packs:
        for path in pk.files:
            if not path.endswith(".json") or skip.search(path) or not path.startswith("data/"):
                continue
            raw = pk.files[path]().decode("utf-8", "replace")
            if "structure" not in raw and "#" not in raw and "map" not in raw:
                continue
            hits = set()
            for m in rx.findall(raw):
                hits |= needles.get(m, set())
            if not hits:
                continue
            parts = path.split("/")
            category = parts[2] if len(parts) > 3 else "other"
            fid = "%s:%s" % (parts[1], "/".join(parts[3:])[:-5])
            for sid in hits:
                out[sid][category].add(fid)
    return {sid: {c: sorted(v) for c, v in cats.items()} for sid, cats in out.items()}


def valuable_features(ix):
    """Placed features from mods whose configured feature places ores, fossils, trees, berries or waystones."""
    out = []
    for key, (pk, path) in sorted(ix.placed.items()):
        if key.startswith("minecraft:"):
            continue
        doc = pk.read_json(path)
        feat = doc.get("feature")
        cf = ix.json(ix.configured, feat) if isinstance(feat, str) and feat in ix.configured else (feat if isinstance(feat, dict) else None)
        blob = json.dumps(cf) if cf else ""
        blocks = sorted(set(re.findall(r'"Name":\s*"([a-z0-9_\-.]+:[a-z0-9_/\-.]+)"', blob)))
        out.append({"placed_feature": key, "source": pk.name, "configured_feature": feat if isinstance(feat, str) else "inline",
                    "type": (cf or {}).get("type"), "blocks": [b for b in blocks if not b.startswith("minecraft:")][:8],
                    "placement": [p.get("type") for p in doc.get("placement") or []]})
    return out


def scan_world(world_dir, bounds):
    region = Path(world_dir) / "region"
    inside, outside = Counter(), Counter()
    statuses = {"inside": Counter(), "outside": Counter()}
    starts = []
    for fn in sorted(os.listdir(region)):
        m = re.match(r"r\.(-?\d+)\.(-?\d+)\.mca$", fn)
        if not m:
            continue
        rx, rz = int(m.group(1)), int(m.group(2))
        for cx, cz, ch in nbt.region_chunks(region / fn):
            bx, bz = (rx * 32 + cx) * 16, (rz * 32 + cz) * 16
            where = "inside" if (bounds["min_x"] <= bx <= bounds["max_x"] and bounds["min_z"] <= bz <= bounds["max_z"]) else "outside"
            statuses[where][ch.get("Status")] += 1
            for k, v in ((ch.get("structures") or {}).get("starts") or {}).items():
                if v.get("id") != "INVALID":
                    (inside if where == "inside" else outside)[k] += 1
                    starts.append({"structure": k, "chunk_x": bx + 8, "chunk_z": bz + 8, "where": where})
    _, level = nbt.load(Path(world_dir) / "level.dat")
    wg = level["Data"].get("WorldGenSettings", {})
    over = (wg.get("dimensions") or {}).get("minecraft:overworld", {})
    return {
        "world": str(world_dir),
        "generate_features": wg.get("generate_features"),
        "overworld_generator": (over.get("generator") or {}).get("type"),
        "overworld_settings": (over.get("generator") or {}).get("settings"),
        "border_size": level["Data"].get("BorderSize"),
        "chunk_status": {k: dict(v) for k, v in statuses.items()},
        "starts_inside": dict(inside.most_common()), "starts_outside": dict(outside.most_common()),
        "starts": starts,
    }


def _short_biomes(r):
    res = r["biomes_resolved"]
    if not res:
        return "`%s` (none loaded)" % r["biomes_raw"]
    names = [b.replace("minecraft:", "") for b in res]
    return ", ".join(names[:4]) + (" +%d" % (len(names) - 4) if len(names) > 4 else "")


def _footprint(r):
    f = r["footprint"] or {}
    if f.get("kind") == "code-generated":
        return "code-generated"
    size = f.get("start_template_size_xyz")
    if size and isinstance(size[0], list):
        size = size[0]
    base = "%sx%sx%s" % tuple(size) if size else "?"
    if f.get("kind") == "jigsaw":
        bound = f.get("bound_if_jigsaw")
        return "%s start, jigsaw depth %s%s" % (base, (r["jigsaw"] or {}).get("size"),
                                                 ", up to %s wide" % bound if bound else ", extent not in data")
    return base


def markdown(result, dimension="overworld"):
    rows = ["<!-- generated by tools/structure_inventory.py -->", "",
            "| Structure | Source | Biomes (loaded) | Set spacing / separation (chunks) | Footprint x·y·z | Spawn entries (species) | Referenced by | Carries |",
            "|---|---|---|---|---|---|---|---|"]
    for r in result["structures"]:
        if dimension and r["dimension"] != dimension:
            continue
        sets = "; ".join("%s/%s%s" % (s["spacing"], s["separation"], "" if s["set_size"] == 1 else " (1 of %d)" % s["set_size"])
                         for s in r["structure_sets"]) or "none"
        sd = r["spawn_dependencies"]
        spawn = "%d (%d)" % (sd["entries"], len(sd["species"])) if sd["entries"] else ""
        refs = ", ".join("%s %d" % (c, len(v)) for c, v in sorted(r["referenced_by"].items()))
        if r["advancements"]:
            refs = ("advancement %d" % len(r["advancements"])) + (", " + refs if refs else "")
        src = r["defined_by"].split("-fabric")[0].split("-1.")[0].replace(".jar", "").replace(".zip", "")
        rows.append("| `%s` | %s | %s | %s | %s | %s | %s | %s |" % (
            r["id"], src, _short_biomes(r), sets, _footprint(r), spawn, refs, ", ".join(r["signals"])))
    return "\n".join(rows) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--server-dir", default=os.environ.get("COBBLERS_SERVER_DIR"))
    p.add_argument("--world", default=None, help="saved world to scan for structure starts")
    p.add_argument("--world-config", default=str(ROOT / "data" / "world.json"))
    p.add_argument("--out", default=str(ROOT / "derived" / "structures" / "inventory.json"))
    p.add_argument("--markdown", default=None, help="also write the overworld table here")
    p.add_argument("--markdown-all", default=None, help="also write a table of every dimension here")
    a = p.parse_args(argv)
    if not a.server_dir:
        raise SystemExit("--server-dir or COBBLERS_SERVER_DIR is required")

    packs = SB.discover(a.server_dir)
    ix = Index(packs)
    installed = SB.mod_ids(packs)
    biomes, tags, _ = SB.build_registry(packs)
    dims = {name: SB.resolve(tag, biomes, tags) for name, tag in SB.DIMENSION_TAGS}
    member_of_tags = ix.structure_tag_members()

    set_of = defaultdict(list)
    for key in ix.sets:
        doc = ix.json(ix.sets, key) or {}
        pl = doc.get("placement") or {}
        members = doc.get("structures") or []
        total = sum(m.get("weight", 1) for m in members) or 1
        for m in members:
            set_of[m["structure"]].append({
                "set": key, "placement": pl.get("type"), "spacing": pl.get("spacing"), "separation": pl.get("separation"),
                "distance": pl.get("distance"), "count": pl.get("count"), "frequency": pl.get("frequency"),
                "weight_share": round(m.get("weight", 1) / total, 3), "set_size": len(members)})

    spawn_deps = spawn_structure_deps(ix, packs, installed, member_of_tags)
    refs = data_references(packs, list(ix.structures), member_of_tags)
    adv_deps = {sid: cats.get("advancement", []) + cats.get("advancements", []) for sid, cats in refs.items()}
    records = [structure_record(ix, sid, biomes, tags, dims, member_of_tags, set_of, spawn_deps, adv_deps)
               for sid in sorted(ix.structures)]
    for r in records:
        r["referenced_by"] = {c: v for c, v in refs.get(r["id"], {}).items() if c not in ("advancement", "advancements")}
    unknown_refs = sorted(s for s in spawn_deps if s not in ix.structures)

    result = {
        "schema": "cobblers.derived.structure_inventory/1",
        "server_dir": str(a.server_dir),
        "structures": records,
        "spawn_references_to_undefined_structures": {s: spawn_deps[s] for s in unknown_refs},
        "valuable_features": valuable_features(ix),
        "counts": {
            "structures": len(records),
            "by_dimension": dict(Counter(r["dimension"] for r in records)),
            "generating": sum(1 for r in records if r["generates"]),
        },
    }
    if a.world:
        bounds = json.loads(Path(a.world_config).read_text(encoding="utf-8"))["bounds"]
        result["world_scan"] = scan_world(a.world, bounds)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, default=list), encoding="utf-8")
    if a.markdown:
        Path(a.markdown).write_text(markdown(result), encoding="utf-8")
    if a.markdown_all:
        Path(a.markdown_all).write_text(markdown(result, dimension=None), encoding="utf-8")
    print("%d structures (%s), %d generate via structure sets -> %s"
          % (len(records), result["counts"]["by_dimension"], result["counts"]["generating"], out))
    if a.world:
        ws = result["world_scan"]
        print("world: starts inside bounds %d, outside %d" % (sum(ws["starts_inside"].values()), sum(ws["starts_outside"].values())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
