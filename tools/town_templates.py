#!/usr/bin/env python
"""Every structure template a town could be built from, what it is, and what it looks like.

Reads the templates the server can actually place (server.jar, every mod jar and its nested jars, and the
datapacks level.dat has enabled, later packs overriding earlier ones exactly as the game resolves them) plus our
own kits/structures, and for the families a town could use:

  scan     parse, measure and classify -> derived/town_templates/templates.json
  render   isometric PNG of every town-relevant template (two opposite corners side by side)
           -> build/structure_renders/<source>/<namespace>/<path>.png
  html     the browsable catalogue -> build/structure_renders/index.html

  python tools/town_templates.py scan --server-dir ../cobblers-server
  python tools/town_templates.py render
  python tools/town_templates.py html

Classes are decided in CLASS_RULES below from what a template contains (palette, trainer spawners, beds, size)
and then pinned per id after looking at the renders. Block colours are the average colour of each block's own
texture, resolved blockstate -> model -> texture from the client jar and the mod jars; a block with no texture
found falls back to a keyword table, so the renders are recognisable rather than accurate.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import pickle
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import nbt
import spawn_blocks as SB

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "derived" / "town_templates"
RENDER_DIR = ROOT / "build" / "structure_renders"
CACHE = OUT_DIR / "geometry.pickle"
STRUCT_RE = re.compile(r"^data/([^/]+)/structures?/(.+)\.nbt$")
POOL_RE = re.compile(r"^data/([^/]+)/worldgen/template_pool/(.+)\.json$")
SKIP = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:structure_void", "minecraft:jigsaw",
        "minecraft:barrier", "minecraft:light", "minecraft:structure_block", "minecraft:moving_piston"}

# ---------------------------------------------------------------- which families are town candidates
# (prefix of "namespace:path", town candidate?, family note). First match wins; anything unmatched is counted but
# not parsed and reported as not town-relevant with its family.
FAMILIES = [
    ("minecraft:village/", True, "vanilla village pieces"),
    ("minecraft:igloo/", True, "vanilla igloo"),
    ("repurposed_structures:villages/", True, "Repurposed Structures village pieces"),
    ("repurposed_structures:wells/", True, "Repurposed Structures wells"),
    ("repurposed_structures:witch_huts/", True, "Repurposed Structures witch huts"),
    ("repurposed_structures:igloos/", True, "Repurposed Structures igloos"),
    ("cobblemon:village", True, "Cobblemon village pieces (Pokemon Centers, berry farms, long paths)"),
    ("cobblemon:villages/", True, "Cobblemon Pokemon Centers injected into Repurposed Structures villages"),
    ("cobblemon:habitats/village_", True, "Cobblemon village habitat pieces"),
    ("bca:", True, "Cobblemon Additions (BCA) villages"),
    ("cobbleverse:", True, "Cobbleverse datapack structures"),
    ("beautify:", True, "Beautify botanist houses"),
    ("waystones:village/", True, "Waystones village pieces"),
    ("mega_showdown:", True, "Mega Showdown sites"),
    ("cobblers:f4/", True, "our converted donor templates"),
    ("cobblers:towns/", True, "our place-time stripped copies"),
    ("cobblers:kits/gyms/", True, "our imported prefabs"),
    ("cobblers:kits/buildings/", True, "our imported prefabs"),
    ("cobblers:kits/services/", True, "our imported prefabs"),
    ("cobblers:kits/props/", True, "our imported prefabs"),
    ("cobblers:kits/trees/", False, "our generated trees"),
    ("cobblers:foliage/", False, "our foliage objects"),
    ("cobblers:cavern/", False, "our foliage objects (cavern copy)"),
    ("cobblers:route1/", False, "our foliage objects (route 1 copy)"),
    ("cobblemon:habitats/", False, "Cobblemon habitats (wild spawn scenery)"),
    ("cobblemon:ruins/", False, "Cobblemon ruins"),
    ("cobblemon:fossils/", False, "Cobblemon fossils"),
    ("cobblemon:fishing_boats/", False, "Cobblemon fishing boats"),
    ("cobblemon:shipwreck_coves/", False, "Cobblemon shipwreck coves"),
    ("legendarymonuments:", False, "Legendary Monuments shrines and dungeons"),
    ("lumymon:", False, "LumyMon temples"),
    ("minecraft:spring/", False, "Vanilla Backport sulfur springs"),
]


def family_of(tid):
    for prefix, town, note in FAMILIES:
        if tid.startswith(prefix):
            return town, note
    ns, path = tid.split(":", 1)
    return False, "%s:%s" % (ns, path.split("/")[0])


# ---------------------------------------------------------------- sources, in load order

def source_slug(label):
    base = label.split("!")[0]
    table = [("server.jar", "vanilla"), ("Cobblemon-fabric", "cobblemon"), ("cobblemon-additions", "cobblemon-additions"),
             ("repurposed_structures", "repurposed-structures"), ("COBBLEVERSE-DP", "cobbleverse-dp"),
             ("PokeCenterPCs", "pokecenterpcs"), ("beautify", "beautify"), ("waystones", "waystones"),
             ("mega_showdown", "mega-showdown"), ("LegendaryMonuments", "legendarymonuments"), ("LumyMon", "lumymon"),
             ("VanillaBackport", "vanillabackport")]
    for key, slug in table:
        if base.startswith(key):
            return slug
    if base.startswith("kits/"):
        return "kits"
    return "server-" + base.replace(".zip", "").replace(" ", "_")


def ordered_sources(server_dir):
    """spawn_blocks.read_sources, reordered so a later entry overrides an earlier one as the game does: vanilla,
    mods, then datapacks in level.dat's Enabled order. Disabled datapacks are dropped."""
    import level_dat as L
    srcs = SB.read_sources(server_dir)
    levelname = "world"
    props = Path(server_dir) / "server.properties"
    for line in props.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("level-name="):
            levelname = line.split("=", 1)[1].strip()
    dp = L.summary(Path(server_dir) / levelname / "level.dat")["datapacks"]
    enabled = [e.replace("file/", "") for e in dp["Enabled"]]
    jars = [s for s in srcs if ".jar" in s[0]]
    packs = [s for s in srcs if ".jar" not in s[0]]
    order = {name: i for i, name in enumerate(enabled)}
    kept = sorted([s for s in packs if s[0] in order], key=lambda s: order[s[0]])
    dropped = sorted(s[0] for s in packs if s[0] not in order)
    jars.sort(key=lambda s: (0 if s[0].startswith("server.jar") else 1, s[0]))
    return jars + kept, {"enabled_datapacks": [s[0] for s in kept], "disabled_or_unlisted": dropped, "level": levelname}


def iter_templates(sources):
    for label, read, names in sources:
        for n in names:
            m = STRUCT_RE.match(n)
            if m:
                yield "%s:%s" % (m.group(1), m.group(2)), label, read, n


def pool_index(sources):
    """template id -> pools listing it; and structure start pools."""
    pools_of = defaultdict(set)
    for label, read, names in sources:
        for n in names:
            m = POOL_RE.match(n)
            if not m:
                continue
            try:
                doc = json.loads(read(n))
            except Exception:
                continue
            pid = "%s:%s" % (m.group(1), m.group(2))
            stack = [e.get("element") for e in doc.get("elements", [])]
            while stack:
                el = stack.pop()
                if not isinstance(el, dict):
                    continue
                if isinstance(el.get("elements"), list):
                    stack.extend(el["elements"])
                loc = el.get("location")
                if isinstance(loc, str):
                    pools_of[loc if ":" in loc else "minecraft:" + loc].add(pid)
    return pools_of


# ---------------------------------------------------------------- measuring one template

DECOR_POOL = re.compile(r"decor|villager|animal|cats|iron_golem|golem|berr|store_worker|worker|lamp|npc|tree|flower|"
                        r"spawner|mob|camel|sheep|bee|statue|plant|sign|garden|pile|crop|farm_animal|nurse|joy|pokemon|"
                        r"empty$|fallback|feature", re.I)


def measure(tid, data):
    _, doc = nbt.loads(data)
    size = [int(v) for v in doc["size"]]
    palettes = doc.get("palettes")
    pal = doc.get("palette") if doc.get("palette") is not None else (palettes[0] if palettes else [])
    names = [p.get("Name") for p in pal]
    props = [p.get("Properties") or {} for p in pal]
    pos, st = [], []
    hist = Counter()
    jigsaws, trainers, loot, cmd, spawners, signs = [], [], 0, 0, 0, []
    for b in doc.get("blocks") or []:
        s = b["state"]
        nm = names[s]
        n = b.get("nbt") or {}
        if nm == "minecraft:jigsaw":
            jigsaws.append({"pool": n.get("pool"), "name": n.get("name"), "target": n.get("target"),
                            "final_state": n.get("final_state"), "pos": b["pos"],
                            "orientation": props[s].get("orientation")})
        if nm in SKIP:
            continue
        hist[nm] += 1
        pos.append(b["pos"])
        st.append(s)
        if n.get("LootTable"):
            loot += 1
        if "command_block" in nm:
            cmd += 1
        if nm == "minecraft:spawner" or nm.endswith(":trial_spawner"):
            spawners += 1
        if nm == "rctmod:trainer_spawner":
            trainers.extend(n.get("TrainerIds") or [])
        if nm.endswith("_sign") and isinstance(n.get("front_text"), dict):
            msgs = [m for m in (n["front_text"].get("messages") or []) if isinstance(m, str)]
            txt = " ".join(re.sub(r'^"|"$', "", m) for m in msgs if m not in ('""', '{"text":""}', ""))
            txt = re.sub(r'\{"text":"([^"]*)"\}', r"\1", txt).strip()
            if txt:
                signs.append(txt)
    ents = Counter()
    for e in doc.get("entities") or []:
        ents[(e.get("nbt") or {}).get("id", "?")] += 1
    geo = {"size": size, "names": names, "props": props,
           "pos": np.array(pos, dtype=np.int16).reshape(-1, 3), "state": np.array(st, dtype=np.int32)}
    info = {"size": size, "blocks": int(len(pos)), "palette_variants": len(palettes) if palettes else 1,
            "histogram": dict(hist.most_common()), "jigsaws": jigsaws, "trainers": trainers,
            "loot_tables": loot, "command_blocks": cmd, "spawners": spawners, "signs": signs[:12],
            "entities": dict(ents), "sha256": hashlib.sha256(data).hexdigest()}
    return info, geo


def placement_kind(tid, info):
    """STANDALONE: a whole thing; /place template drops it in (its decoration slots stay empty).
    PIECE: a fragment that only makes sense with the pieces its jigsaws would attach."""
    structural, decor = [], []
    for j in info["jigsaws"]:
        pool = j.get("pool") or "minecraft:empty"
        if pool == "minecraft:empty" or DECOR_POOL.search(pool) or DECOR_POOL.search(j.get("name") or ""):
            if pool != "minecraft:empty":
                decor.append(pool)
        else:
            structural.append(pool)
    t = "/" + tid.split(":", 1)[1]
    # A PIECE is incomplete by itself: a street, road, path, room, basement or ladder shaft. A building whose jigsaws
    # only reach outward (a village centre that grows paths and houses around itself) is still a whole building, and
    # /place template drops it in with those connectors left as their final-state blocks.
    fragment = re.search(r"/(streets|paths|terminators|decays|roads|bits|rooms|hallways|connectors|junctions)/|"
                         r"(_road|_path|road_|path_|ladder_|/basement|/middle$|/bottom$)", t)
    kind = "PIECE" if fragment else "STANDALONE"
    return kind, sorted(set(structural)), sorted(set(decor))


# ---------------------------------------------------------------- classification

KANTO = {"kanto_brock": "Brock (Pewter, Rock)", "kanto_misty": "Misty (Cerulean, Water)",
         "kanto_ltsurge": "Lt. Surge (Vermilion, Electric)", "kanto_erika": "Erika (Celadon, Grass)",
         "kanto_koga": "Koga (Fuchsia, Poison)", "kanto_sabrina": "Sabrina (Saffron, Psychic)",
         "kanto_blaine": "Blaine (Cinnabar, Fire)", "kanto_giovanni": "Giovanni (Viridian, Ground)"}
TYPES = ["center", "mart", "gym", "house", "shop", "civic", "fence", "lamp", "signage", "prop", "not_town"]
TYPE_LABEL = {"center": "Pokemon Center", "mart": "Poke Mart", "gym": "Gym", "house": "House", "shop": "Shop / market",
              "civic": "Civic building", "fence": "Fence", "lamp": "Lamp / lighting", "signage": "Signage",
              "prop": "Prop / decoration", "not_town": "Not town-relevant"}

LIGHT = re.compile(r"lantern|lamp|torch|glowstone|sea_lantern|shroomlight|froglight|end_rod|candle|redstone_lamp|light_post")


def auto_class(tid, info):
    h = info["histogram"]
    path = tid.split(":", 1)[1]
    sx, sy, sz = info["size"]
    total = max(1, info["blocks"])
    beds = sum(v for k, v in h.items() if k.endswith("_bed"))
    healing = h.get("cobblemon:healing_machine", 0)
    leader = [KANTO[t] for t in info["trainers"] if t in KANTO]
    if leader:
        return "gym", "rctmod trainer spawner for " + ", ".join(leader)
    regional = [t for t in info["trainers"] if re.fullmatch(r"(hoenn|johto|sinnoh)_[a-z]+", t)]
    if regional:
        return "gym", "rctmod trainer spawner for %s (a %s gym; Cobbleverse uses the Italian leader names)" % (
            ", ".join(regional), regional[0].split("_")[0].title())
    if re.search(r"pokecenter|poke_center", path):
        return "center", "id names a Pokemon Center; healing machines %d" % healing
    if re.search(r"pokemart|poke_mart", path):
        return "mart", "id names a Poke Mart"
    lights = sum(v for k, v in h.items() if LIGHT.search(k))
    fences = sum(v for k, v in h.items() if re.search(r"_fence$|_wall$|fence_gate", k))
    signs = sum(v for k, v in h.items() if k.endswith("_sign") or k.endswith("_banner"))
    if sx * sz <= 9 and lights and total <= 60:
        return "lamp", "footprint %dx%d with %d light blocks" % (sx, sz, lights)
    if fences / total > 0.5:
        return "fence", "%d%% fence and wall blocks" % (100 * fences // total)
    if signs and signs / total > 0.15:
        return "signage", "%d sign/banner blocks of %d" % (signs, total)
    if beds and sy >= 5:
        return "house", "%d bed blocks" % beds
    if sy <= 4 or total < 150:
        return "prop", "low or small (%dx%dx%d, %d blocks)" % (sx, sy, sz, total)
    return "house", "a building without beds (%dx%dx%d)" % (sx, sy, sz)


# Pinned after looking at the renders (contact sheets of every rendered template, 2026-09-16). Ordered regexes on the
# template id; the first match wins over the automatic class. A rule states what the thing IS, not what it is called:
# every rule below was checked against the pictures, and where a name and a picture disagreed the picture won.
RULES: list[tuple[str, str, str]] = [
    # entity-only templates: a 1x2x1 box holding one NPC, used as a jigsaw decoration slot
    (r"^bca:stores/.*/pokemart_shopkeeper$", "mart", "entity only: one CobbleDollars merchant, the Mart clerk BCA puts in its Mart"),
    (r"^bca:stores/.*/nurse_joy$", "center", "entity only: one villager named for Nurse Joy, the NPC slot of BCA's Center"),
    (r"^bca:stores/", "shop", "entity only: one CobbleDollars merchant (a market or store clerk), no blocks"),
    (r"^bca:special_structure_spawner/", "not_town", "a 3-block spawner marker for the witch hut, not a building"),
    # the Cobbleverse and other named structures, by what the render shows
    (r"^cobbleverse:(hoenn|johto|sinnoh)_league$", "civic", "a regional Pokemon League building (Elite Four and Champion)"),
    (r"^cobbleverse:(sky_pillar|bell_tower|burned_tower|celebi_shrine|whirl_island|dyna_tree|secret_garden|crescent_isle|"
     r"fullmoon_island|flower_paradise|snowpoint_temple|spear_pillar|split_decision_temple)$", "not_town", "legendary or story site, not a town building"),
    (r"^cobbleverse:(rocket_radio_tower|eterna_building|team_galactic_hq|wind_plant)$", "not_town", "villain landmark"),
    (r"^cobbleverse:ash$", "house", "Ash and Delia's house (Pallet): a large furnished home with two RCT trainers"),
    (r"^cobbleverse:kanto_league$", "civic", "the Kanto Pokemon League: a 111x159x120 tower with the Elite Four and Champion Blue"),
    (r"^cobbleverse:team_rocket_tower", "not_town", "villain landmark: a 60-tall Team Rocket office tower with 26-27 grunts"),
    (r"^cobbleverse:(crown_|dawn_tower|dusk_tower|legendary/|mythical/)", "not_town", "legendary or mythical site, not a town building"),
    (r"^mega_showdown:observatory$", "civic", "a domed observatory building"),
    (r"^mega_showdown:", "not_town", "Mega Showdown dig site or meteor, not a town building"),
    (r"^(kits|cobblers):f4/pallet/rare_structures/lab$", "civic", "Professor Oak's laboratory (CobbleTowns donor)"),
    (r"^(kits|cobblers):f4/pallet/town_centers/sign$", "signage", "Pallet Town sign with its path junction and a tree"),
    (r"^bca:.*one_off/the_lodge", "center", "a lodge-scale Center: healing machine, PC, waystone and 60 beds in a 51x40x51 inn, not the red-roof look"),
    (r"^bca:fighting/centers/center-wyrms-rest$", "center", "a lodge-scale Center: healing machine, PC, waystone and 40 beds in a towered inn"),
    (r"^bca:dark/centers/center_the_marshlight_tavern$", "shop", "a tavern and inn (14 beds, display cases, no healer)"),
    (r"^bca:.*farmers_market", "shop", "a covered market hall with stall slots"),
    (r"^bca:.*center_the_academy$", "civic", "The Academy: a 49x60x73 school campus with a clock tower and library"),
    (r"^bca:.*department_store$", "shop", "a four-storey department store with a rooftop garden"),
    (r"^bca:.*one_off_haunted_church$", "civic", "a church with a tall spire and graveyard"),
    (r"^bca:.*one_off_the_crypt$", "prop", "a crypt and graveyard"),
    (r"^bca:.*center_battlepad$", "civic", "a battle arena: a sunken battle field with lamp posts and a path ring"),
    (r"^bca:.*center_small_village", "prop", "a town square: paved cross with a fountain and planters"),
    (r"^bca:.*(center_village_road|/paths/|fallback)", "prop", "road or path piece"),
    (r"^bca:.*battlepad", "prop", "a battle field marked out on the ground, fenced"),
    (r"^bca:general/berries/", "prop", "berry plot: a dirt block with a berry plant slot"),
    (r"^bca:general/general_decor/(berry_?stand|market_stall)", "shop", "market stall"),
    (r"^bca:general/general_decor/decor_(mid|small)_cemetary$", "prop", "a small cemetery"),
    (r"^bca:general/general_decor/(decoration_well|decorations_well)", "prop", "a roofed well"),
    (r"^bca:general/lamp_posts/", "lamp", "lamp post"),
    (r"^bca:general/general_decor/", "prop", "street furniture (bench, cart, picnic table, wagon, pump or planter)"),
    (r"^bca:special_structures/swamp_witches_hut$", "house", "a stilted swamp hut over a pond"),
    (r"^beautify:botanist_house", "house", "Beautify's botanist house: a small village house in the biome's materials"),
    (r"^waystones:village/", "prop", "a village waystone plinth"),
    (r"^cobblemon:habitats/village_", "prop", "a Pokemon habitat nook: a nest of blocks and plants that draws wild Pokemon, not a building"),
    (r"^cobblemon:.*(long_path)$", "prop", "road or path piece"),
    (r"^cobblemon:.*berry_(large|small)$", "prop", "berry farm plot"),
    # village families: vanilla and Repurposed Structures share one naming scheme
    (r"village.*/decays/", "not_town", "a grass patch used to decay abandoned villages"),
    (r"village.*/(streets|terminators)/", "prop", "road or path piece"),
    (r"village.*/(town_centers|.*meeting_point|.*fountain)", "prop", "village square: well, fountain, market canopies or a plaza"),
    (r"village.*(lamp|lantern)", "lamp", "village lamp post"),
    (r"village.*(well_bottom|/decor/decoration|accessory)", "prop", "well or small decoration"),
    (r"village.*(animal_pen|_farm|/farm_\d|/pen_?\d?$)", "prop", "farm plot or animal pen"),
    (r"village.*(temple|library)", "civic", "temple or library"),
    (r"village.*(butcher|smith|armorer|weapon|saloon)", "shop", "a workshop or shopfront building (butcher, smith, armorer)"),
    (r"village.*/decor/", "prop", "small decoration"),
    (r"igloos?/.*(ladder|basement)|^minecraft:igloo/(middle|bottom)$", "not_town", "igloo basement or ladder shaft piece"),
    (r"igloos?/.*top|^minecraft:igloo/top$", "house", "an igloo dome"),
    (r"^repurposed_structures:wells/", "prop", "a well"),
    (r"^repurposed_structures:witch_huts/", "house", "a stilted witch hut"),
    (r"village.*/houses/", "house", "a village house"),
]


def classify(tid, info):
    for pattern, cls, why in RULES:
        if re.search(pattern, tid):
            return cls, why, "pinned after viewing the render"
    c, why = auto_class(tid, info)
    return c, why, "automatic (contents)"


# ---------------------------------------------------------------- spawn blocks

def spawn_table(sources):
    spawns, tags = SB.collect(sources)
    ns_loaded = SB.loaded_namespaces(sources)
    blocks = defaultdict(set)
    for entry, uses in spawns.items():
        for b in SB.resolve(entry, tags):
            if b.split(":")[0] not in ns_loaded:
                continue
            for u in uses:
                label = (u["pokemon"] or "herd") + ("" if u["condition"] == "condition" else " (anticondition)")
                blocks[b].add((label, u["field"]))
    return {b: sorted(v) for b, v in blocks.items()}


def policy_status(block, policy):
    for s in policy.get("substitutions", []):
        if s["from"] == block:
            return "rule exists, not applied in this template -> " + s["to"]
    for w in policy.get("whitelist", []):
        if block in (w.get("blocks") or []):
            return "whitelisted (%s)" % w.get("scope", "")
    return "not covered by policy"


# ---------------------------------------------------------------- variants

def shape_key(geo):
    sx, sy, sz = geo["size"]
    occ = np.zeros((sx, sy, sz), dtype=bool)
    if len(geo["pos"]):
        p = geo["pos"].astype(int)
        occ[p[:, 0], p[:, 1], p[:, 2]] = True
    return occ


def transforms(occ):
    out = []
    a = occ
    for m in (False, True):
        b = a[::-1, :, :] if m else a
        for k in range(4):
            out.append(np.rot90(b, k, axes=(0, 2)))
    return out


def jaccard(a, b):
    if a.shape != b.shape:
        return 0.0
    inter = np.logical_and(a, b).sum()
    uni = np.logical_or(a, b).sum()
    return float(inter) / uni if uni else 1.0


def best_match(A, B, max_dy=4):
    """Jaccard of two occupancy grids under the best rotation/mirror and vertical offset (0 if footprints differ)."""
    if A.shape[1] > B.shape[1]:
        A, B = B, A
    dy = B.shape[1] - A.shape[1]
    if dy > max_dy:
        return 0.0
    j = 0.0
    for t in transforms(A):
        if t.shape[0] != B.shape[0] or t.shape[2] != B.shape[2]:
            continue
        for off in range(dy + 1):
            padded = np.zeros(B.shape, dtype=bool)
            padded[:, off:off + t.shape[1], :] = t
            j = max(j, jaccard(padded, B))
    return j


def group_variants(ids, geos, threshold=0.85):
    """Representative clustering, not union-find: a template joins a design only if it matches that design's
    representative (the first member, vanilla before mods) at Jaccard >= threshold. Chaining is what made the
    first cut merge ten different 7x7x7 cottages into one."""
    order = sorted(ids, key=lambda t: (0 if t.startswith("minecraft:") else 1 if t.startswith(("bca:", "cobbleverse:")) else 2, t))
    occ = {i: shape_key(geos[i]) for i in ids}
    reps = defaultdict(list)                        # footprint -> [(rep id, members)]
    scores = {}
    for t in order:
        sx, sy, sz = geos[t]["size"]
        foot = (min(sx, sz), max(sx, sz))
        placed = False
        for rep, members in reps[foot]:
            j = best_match(occ[rep], occ[t])
            if j >= threshold:
                members.append(t)
                scores[t] = (rep, j)
                placed = True
                break
        if not placed:
            reps[foot].append((t, [t]))
    groups = [members for lst in reps.values() for _, members in lst]
    return groups, scores


# ---------------------------------------------------------------- scan

def cmd_scan(a):
    sources, load_info = ordered_sources(a.server_dir)
    effective, shadowed, family_counts = {}, defaultdict(list), Counter()
    total_files = 0
    for tid, label, read, name in iter_templates(sources):
        total_files += 1
        if tid in effective:
            shadowed[tid].append(effective[tid][0])
        effective[tid] = (label, read, name)
    kit_files = sorted((ROOT / "kits" / "structures").rglob("*.nbt"))
    pools_of = pool_index(sources)
    rows, geos = {}, {}
    for tid, (label, read, name) in sorted(effective.items()):
        town, fam = family_of(tid)
        family_counts[(source_slug(label), fam, town)] += 1
        if not town:
            continue
        data = read(name)
        info, geo = measure(tid, data)
        kind, structural, decor = placement_kind(tid, info)
        rows[tid] = dict(id=tid, source=source_slug(label), source_file="%s!%s" % (label, name), family=fam,
                         overrides=[source_slug(s) for s in shadowed.get(tid, [])], pools=sorted(pools_of.get(tid, [])),
                         placement=kind, structural_jigsaw_pools=structural, decoration_jigsaw_pools=decor,
                         **{k: v for k, v in info.items() if k != "jigsaws"}, jigsaw_count=len(info["jigsaws"]))
        geos[tid] = geo
    # disabled regional Cobbleverse datapacks: shipped, not loaded, so /place template cannot reach them today
    for z in sorted((Path(a.server_dir) / "datapacks" / "extra").glob("COBBLEVERSE*.zip")):
        if z.name in load_info["enabled_datapacks"]:
            continue
        zz = zipfile.ZipFile(z)
        slug = z.stem.lower().replace("-dp", "") + "-dp-disabled"
        for n in zz.namelist():
            m = STRUCT_RE.match(n)
            if not m:
                continue
            tid = "%s:%s" % (m.group(1), m.group(2))
            if tid in rows:
                continue
            total_files += 1
            family_counts[(slug, "Cobbleverse regional datapack, disabled on this world", True)] += 1
            data = zz.read(n)
            info, geo = measure(tid, data)
            kind, structural, decor = placement_kind(tid, info)
            rows[tid] = dict(id=tid, source=slug, source_file="datapacks/extra/%s!%s" % (z.name, n),
                             family="Cobbleverse regional datapack, DISABLED on this world", overrides=[], pools=[],
                             placement=kind, structural_jigsaw_pools=structural, decoration_jigsaw_pools=decor,
                             disabled=True, **{k: v for k, v in info.items() if k != "jigsaws"}, jigsaw_count=len(info["jigsaws"]))
            geos[tid] = geo
    # our kits, as files in the repository (they may differ from what the server has installed)
    installed = {r["sha256"]: t for t, r in rows.items() if r["source"].startswith("server-cobblers")}
    for p in kit_files:
        rel = p.relative_to(ROOT).as_posix()
        if "/foliage/" in rel or "/trees/" in rel:
            family_counts[("kits", "our foliage and tree objects", False)] += 1
            continue
        parts = rel.split("/")
        if parts[2] == "campaign":
            tid = "kits:" + "/".join(parts[3:])[:-4]
        else:
            tid = "kits:" + "/".join(parts[2:])[:-4]
        data = p.read_bytes()
        info, geo = measure(tid, data)
        kind, structural, decor = placement_kind(tid, info)
        family_counts[("kits", "our kit library (repository)", True)] += 1
        rows[tid] = dict(id=tid, source="kits", source_file=rel, family="our kit library (repository)", overrides=[],
                         pools=[], placement=kind, structural_jigsaw_pools=structural, decoration_jigsaw_pools=decor,
                         installed_on_server_as=installed.get(info["sha256"]),
                         **{k: v for k, v in info.items() if k != "jigsaws"}, jigsaw_count=len(info["jigsaws"]))
        geos[tid] = geo
    spawn = spawn_table(sources)
    policy = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    for tid, r in rows.items():
        c, why, how = classify(tid, r)
        r.update(type=c, type_why=why, type_how=how)
        flags = []
        for b, n in r["histogram"].items():
            if b in spawn:
                flags.append({"block": b, "count": n, "spawns": sorted({s for s, _ in spawn[b]}),
                              "fields": sorted({f for _, f in spawn[b]}), "policy": policy_status(b, policy)})
        r["spawn_blocks"] = flags
        r["waystones"] = sum(n for b, n in r["histogram"].items() if b.startswith("waystones:"))
        r["concrete"] = {b: n for b, n in r["histogram"].items() if re.fullmatch(r"minecraft:\w+_concrete", b)}
        r["moarconcrete"] = {b: n for b, n in r["histogram"].items() if b.startswith("moarconcrete:")}
        r["render"] = "%s/%s.png" % (r["source"], tid.replace(":", "/"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with CACHE.open("wb") as f:
        pickle.dump(geos, f)
    doc = {"schema": "cobblers.town-templates/1", "generated": datetime.date.today().isoformat(),
           "generator": "tools/town_templates.py scan", "load_order": load_info,
           "template_files_seen": total_files, "effective_template_ids": len(effective),
           "overridden_ids": len(shadowed), "kit_files": len(kit_files),
           "families": [{"source": s, "family": f, "town_candidate": t, "templates": n}
                        for (s, f, t), n in sorted(family_counts.items(), key=lambda kv: (-kv[1], kv[0]))],
           "spawn_block_count": len(spawn), "spawn_table": {b: [list(x) for x in v] for b, v in spawn.items()},
           "templates": rows}
    (OUT_DIR / "templates.json").write_text(json.dumps(doc, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"files": total_files, "effective": len(effective), "overridden": len(shadowed),
                      "candidates": len(rows), "spawn_blocks": len(spawn),
                      "by_type": Counter(r["type"] for r in rows.values())}, indent=1))


# ---------------------------------------------------------------- colours

KEYWORD_RGB = [  # fallback when no texture resolves; first match wins
    ("water", (63, 118, 228)), ("lava", (230, 110, 20)), ("glass", (190, 220, 235)), ("leaves", (80, 140, 50)),
    ("grass", (100, 160, 70)), ("dirt", (130, 95, 65)), ("sand", (220, 205, 150)), ("snow", (245, 250, 250)),
    ("ice", (160, 190, 245)), ("cherry", (225, 160, 170)), ("birch", (215, 200, 140)), ("dark_oak", (70, 50, 30)),
    ("spruce", (110, 80, 50)), ("jungle", (160, 115, 80)), ("acacia", (170, 90, 50)), ("mangrove", (115, 55, 50)),
    ("bamboo", (200, 180, 90)), ("crimson", (120, 50, 80)), ("warped", (45, 110, 110)), ("oak", (160, 130, 80)),
    ("deepslate", (75, 75, 80)), ("blackstone", (45, 40, 45)), ("brick", (150, 90, 75)), ("quartz", (235, 230, 222)),
    ("sandstone", (215, 200, 150)), ("prismarine", (90, 160, 145)), ("copper", (190, 110, 80)), ("iron", (215, 215, 215)),
    ("gold", (240, 205, 70)), ("stone", (125, 125, 125)), ("cobble", (120, 120, 120)), ("andesite", (135, 135, 135)),
    ("granite", (150, 105, 85)), ("diorite", (190, 190, 190)), ("terracotta", (150, 95, 70)), ("wool", (220, 220, 220)),
    ("lantern", (250, 200, 110)), ("torch", (250, 200, 110)), ("lamp", (245, 210, 140)), ("hay", (200, 170, 50)),
    ("log", (110, 85, 55)), ("plank", (160, 130, 80)), ("wood", (140, 105, 70)),
]
DYES = {"white": (233, 236, 236), "orange": (240, 118, 19), "magenta": (189, 68, 179), "light_blue": (58, 175, 217),
        "yellow": (248, 197, 39), "lime": (112, 185, 25), "pink": (237, 141, 172), "light_gray": (142, 142, 134),
        "gray": (62, 68, 71), "cyan": (21, 137, 145), "purple": (121, 42, 172), "blue": (53, 57, 157),
        "brown": (114, 71, 40), "green": (84, 109, 27), "red": (160, 39, 34), "black": (20, 21, 25)}
TINT_GRASS, TINT_FOLIAGE, TINT_WATER = (145, 189, 89), (119, 171, 47), (63, 118, 228)
TINTED = re.compile(r"(^|/)(grass_block_top|short_grass|grass|tall_grass_(top|bottom)|fern|large_fern_(top|bottom)|"
                    r"vine|lily_pad|sugar_cane|(oak|jungle|acacia|dark_oak|mangrove)_leaves|"
                    r"water_still|water_flow|attached_melon_stem|melon_stem|pumpkin_stem)$")
FIXED_TINT = {"spruce_leaves": (97, 153, 97), "birch_leaves": (128, 167, 85)}


class Assets:
    """blockstate -> model -> texture lookups across the client jar and the mod jars."""

    def __init__(self, client_jar, server_dir):
        self.readers = {}
        zips = []
        if client_jar and Path(client_jar).exists():
            zips.append(zipfile.ZipFile(client_jar))
        for jar in sorted((Path(server_dir) / "mods").glob("*.jar")):
            try:
                z = zipfile.ZipFile(jar)
            except zipfile.BadZipFile:
                continue
            zips.append(z)
            for n in z.namelist():
                if n.startswith("META-INF/jars/") and n.endswith(".jar"):
                    try:
                        zips.append(zipfile.ZipFile(io.BytesIO(z.read(n))))
                    except Exception:
                        pass
        for z in zips:
            for n in z.namelist():
                if n.startswith("assets/") and (n.endswith(".json") or n.endswith(".png")):
                    self.readers.setdefault(n, z)
        self.cache = {}

    def read(self, path):
        z = self.readers.get(path)
        return z.read(path) if z else None

    def json(self, path):
        raw = self.read(path)
        if raw is None:
            return None
        try:
            return json.loads(raw.decode("utf-8-sig"))
        except Exception:
            return None

    @staticmethod
    def split(ref):
        if ":" in ref:
            return tuple(ref.split(":", 1))
        return "minecraft", ref

    def model_textures(self, ref, depth=0):
        if depth > 8:
            return {}
        ns, p = self.split(ref)
        doc = self.json("assets/%s/models/%s.json" % (ns, p))
        if doc is None:
            return {}
        tex = {}
        if doc.get("parent"):
            tex.update(self.model_textures(doc["parent"], depth + 1))
        tex.update(doc.get("textures") or {})
        return tex

    def tex_rgb(self, ref):
        from PIL import Image
        ns, p = self.split(ref)
        key = "assets/%s/textures/%s.png" % (ns, p)
        if key in self.cache:
            return self.cache[key]
        raw = self.read(key)
        rgb = None
        if raw:
            try:
                im = Image.open(io.BytesIO(raw)).convert("RGBA")
                w, h = im.size
                if h > w:
                    im = im.crop((0, 0, w, w))
                arr = np.asarray(im).reshape(-1, 4).astype(float)
                arr = arr[arr[:, 3] > 20]
                if len(arr):
                    base = arr[:, :3].mean(axis=0)
                    tint = None
                    leaf = p.rsplit("/", 1)[-1]
                    if leaf in FIXED_TINT:
                        tint = FIXED_TINT[leaf]
                    elif TINTED.search(p):
                        tint = TINT_WATER if "water" in p else (TINT_FOLIAGE if "leaves" in p or "vine" in p else TINT_GRASS)
                    rgb = tuple(float(c) * t / 255.0 for c, t in zip(base, tint)) if tint else tuple(float(c) for c in base)
            except Exception:
                rgb = None
        self.cache[key] = rgb
        return rgb

    def block_rgb(self, name, props):
        """-> (top rgb, side rgb) or None."""
        ns, p = name.split(":", 1)
        state = self.json("assets/%s/blockstates/%s.json" % (ns, p))
        model = None
        if state:
            if isinstance(state.get("variants"), dict) and state["variants"]:
                vs = state["variants"]
                chosen = None
                for k, v in vs.items():
                    conds = dict(c.split("=", 1) for c in k.split(",") if "=" in c)
                    if all(str(props.get(ck)) == cv for ck, cv in conds.items()):
                        chosen = v
                        break
                chosen = chosen if chosen is not None else next(iter(vs.values()))
                chosen = chosen[0] if isinstance(chosen, list) else chosen
                model = chosen.get("model") if isinstance(chosen, dict) else None
            elif isinstance(state.get("multipart"), list) and state["multipart"]:
                ap = state["multipart"][0].get("apply")
                ap = ap[0] if isinstance(ap, list) else ap
                model = ap.get("model") if isinstance(ap, dict) else None
        if model is None:
            model = "%s:block/%s" % (ns, p)
        tex = self.model_textures(model)

        def resolve(k):
            v, n = tex.get(k), 0
            while isinstance(v, str) and v.startswith("#") and n < 8:
                v, n = tex.get(v[1:]), n + 1
            return v if isinstance(v, str) and not v.startswith("#") else None
        top_keys = ["top", "end", "up", "all", "texture", "cross", "plant", "pattern", "wool", "side", "front", "particle"]
        side_keys = ["side", "all", "front", "north", "texture", "cross", "plant", "wool", "end", "top", "particle"]
        top = next((resolve(k) for k in top_keys if resolve(k)), None)
        side = next((resolve(k) for k in side_keys if resolve(k)), None)
        if top is None and side is None:
            any_tex = [resolve(k) for k in tex if resolve(k)]
            top = side = any_tex[0] if any_tex else None
        t = self.tex_rgb(top) if top else None
        s = self.tex_rgb(side) if side else None
        if t is None and s is None:
            return None
        return (t or s, s or t)


def keyword_rgb(name):
    p = name.split(":", 1)[1]
    for dye, rgb in sorted(DYES.items(), key=lambda kv: -len(kv[0])):
        if p.startswith(dye + "_"):
            return rgb
    for k, rgb in KEYWORD_RGB:
        if k in p:
            return rgb
    h = hashlib.md5(name.encode()).digest()
    return (110 + h[0] % 90, 100 + h[1] % 90, 90 + h[2] % 90)


# ---------------------------------------------------------------- shapes

FLAT = re.compile(r"carpet$|pressure_plate$|_rail$|^rail$|lily_pad|redstone_wire|leaf_litter|pink_petals|tripwire$|"
                  r"_button$|^lever$|frogspawn|glow_lichen|sculk_vein")
THIN = re.compile(r"_fence$|_wall$|_pane$|iron_bars|^chain$|torch|lantern$|end_rod|lightning_rod|candle|"
                  r"_sign$|_banner$|sapling|flower$|tulip|poppy|dandelion|orchid|allium|bluet|daisy|cornflower|lily_of|"
                  r"^short_grass$|^tall_grass$|fern$|dead_bush|sweet_berry_bush|^ladder$|^vine$|_head$|_skull$|flower_pot|"
                  r"potted_|^red_mushroom$|^brown_mushroom$|^bamboo$|sugar_cane|_coral$|_coral_fan$|seagrass|^kelp|"
                  r"fence_gate$|_rod$|lamp_post")


def shape_boxes(name, props):
    """-> list of (x0, y0, z0, x1, y1, z1) inside the unit cell."""
    p = name.split(":", 1)[1]
    if p.endswith("_slab"):
        t = props.get("type", "bottom")
        return [(0, 0, 0, 1, 1, 1)] if t == "double" else ([(0, 0.5, 0, 1, 1, 1)] if t == "top" else [(0, 0, 0, 1, 0.5, 1)])
    if p.endswith("_trapdoor"):
        if props.get("open") == "true":
            return [(0.4, 0, 0.4, 0.6, 1, 0.6)]
        return [(0, 0.8, 0, 1, 1, 1)] if props.get("half") == "top" else [(0, 0, 0, 1, 0.2, 1)]
    if p == "snow" and props.get("layers"):
        return [(0, 0, 0, 1, int(props["layers"]) / 8.0, 1)]
    if name.startswith("minecraft:") and FLAT.search(p):
        return [(0, 0, 0, 1, 0.12, 1)]
    if FLAT.search(p) and "carpet" in p:
        return [(0, 0, 0, 1, 0.12, 1)]
    if THIN.search(p):
        if p.endswith("_wall"):
            return [(0.25, 0, 0.25, 0.75, 1, 0.75)]
        if "torch" in p or "lantern" in p or "candle" in p:
            return [(0.35, 0, 0.35, 0.65, 0.6, 0.65)]
        return [(0.35, 0, 0.35, 0.65, 1, 0.65)]
    return [(0, 0, 0, 1, 1, 1)]


# ---------------------------------------------------------------- the renderer

def render_view(geo, colours, full, scale, flip):
    from PIL import Image, ImageDraw
    sx, sy, sz = geo["size"]
    pos = geo["pos"].astype(int)
    st = geo["state"]
    if flip:
        pos = pos.copy()
        pos[:, 0] = sx - 1 - pos[:, 0]
        pos[:, 2] = sz - 1 - pos[:, 2]
    s = scale
    m = 6
    W = int((sx + sz) * s) + 2 * m
    H = int((sx + sz) * s / 2 + sy * s) + 2 * m
    img = Image.new("RGB", (W, H), (250, 250, 247))
    d = ImageDraw.Draw(img)

    def proj(x, y, z):
        return (m + (x - z + sz) * s, m + (x + z) * s / 2.0 + (sy - y) * s)
    d.polygon([proj(0, 0, 0), proj(sx, 0, 0), proj(sx, 0, sz), proj(0, 0, sz)], fill=(232, 232, 226), outline=(200, 200, 192))
    solid = set()
    for (x, y, z), k in zip(pos.tolist(), st.tolist()):
        if full[k]:
            solid.add((x, y, z))
    order = np.argsort(pos[:, 0] + pos[:, 1] + pos[:, 2], kind="stable")
    for i in order.tolist():
        x, y, z = pos[i].tolist()
        k = int(st[i])
        if full[k] and (x + 1, y, z) in solid and (x, y + 1, z) in solid and (x, y, z + 1) in solid:
            continue
        top, side = colours[k]
        right = tuple(int(c * 0.62) for c in side)
        left = tuple(int(c * 0.82) for c in side)
        topc = tuple(int(c) for c in top)
        for (x0, y0, z0, x1, y1, z1) in geo["boxes"][k]:
            X0, Y0, Z0, X1, Y1, Z1 = x + x0, y + y0, z + z0, x + x1, y + y1, z + z1
            d.polygon([proj(X1, Y0, Z0), proj(X1, Y1, Z0), proj(X1, Y1, Z1), proj(X1, Y0, Z1)], fill=right)
            d.polygon([proj(X0, Y0, Z1), proj(X1, Y0, Z1), proj(X1, Y1, Z1), proj(X0, Y1, Z1)], fill=left)
            d.polygon([proj(X0, Y1, Z0), proj(X1, Y1, Z0), proj(X1, Y1, Z1), proj(X0, Y1, Z1)], fill=topc)
    return img


def render_template(geo, assets, rgb_cache, out_path, width=1400):
    from PIL import Image, ImageDraw
    colours, full, boxes = [], [], []
    for name, props in zip(geo["names"], geo["props"]):
        props = props or {}
        key = (name, tuple(sorted(props.items())))
        if key not in rgb_cache:
            got = assets.block_rgb(name, props) if assets else None
            rgb_cache[key] = got if got is not None else ("fallback", keyword_rgb(name))
        got = rgb_cache[key]
        colours.append((got[1], got[1]) if got[0] == "fallback" else got)
        b = shape_boxes(name, props)
        boxes.append(b)
        full.append(b == [(0, 0, 0, 1, 1, 1)] and not re.search(r"glass|leaves|door|stairs|slab|ice$", name))
    geo = dict(geo, boxes=boxes)
    sx, sy, sz = geo["size"]
    scale = max(2.0, min(18.0, (width / 2 - 20) / float(sx + sz)))
    a = render_view(geo, colours, full, scale, False)
    b = render_view(geo, colours, full, scale, True)
    out = Image.new("RGB", (a.width + b.width + 10, max(a.height, b.height) + 18), (250, 250, 247))
    out.paste(a, (0, 18))
    out.paste(b, (a.width + 10, 18))
    dr = ImageDraw.Draw(out)
    dr.text((6, 3), "from the +x +z corner (south-east)", fill=(90, 90, 90))
    dr.text((a.width + 16, 3), "from the -x -z corner (north-west)", fill=(90, 90, 90))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, optimize=True)


def find_client_jar():
    for c in [Path.home() / "AppData/Roaming/.minecraft/versions/1.21.1/1.21.1.jar",
              Path.home() / "curseforge/minecraft/Install/versions/1.21.1/1.21.1.jar"]:
        if c.exists():
            return c
    return None


def cmd_render(a):
    doc = json.loads((OUT_DIR / "templates.json").read_text(encoding="utf-8"))
    with CACHE.open("rb") as f:
        geos = pickle.load(f)
    client = a.client_jar or find_client_jar()
    assets = Assets(client, a.server_dir)
    rgb_cache = {}
    pat = re.compile(a.only) if a.only else None
    done = 0
    for tid, r in doc["templates"].items():
        if pat and not pat.search(tid):
            continue
        if not pat and not r.get("render_wanted"):
            continue
        if not a.force and not pat and (RENDER_DIR / r["render"]).exists():
            continue
        render_template(geos[tid], assets, rgb_cache, RENDER_DIR / r["render"])
        done += 1
    missing = sorted({k[0] for k, v in rgb_cache.items() if v[0] == "fallback"})
    print(json.dumps({"rendered": done, "client_jar": str(client), "block_names_without_texture": len(missing),
                      "examples": missing[:60]}, indent=1))


SAME_DESIGN = [
    # (keep, other, why): merges the geometry test cannot make, decided by looking at the renders. Each Cobbleverse
    # region builds its gyms from one shell and recolours it; roof trim and footprint differ by a block or two, which
    # is enough to drop the occupancy match under 85%.
    ("cobbleverse:brock", "cobbleverse:blaine", "Kanto gym shell (blaine, erika and ltsurge are 23 deep, the rest 24)"),
] + [("cobbleverse:petra", "cobbleverse:" + x, "Hoenn gym shell, recoloured")
     for x in ("rudi", "walter", "fiammetta", "norman", "tell_pat", "alice")] +     [("cobbleverse:valerio", "cobbleverse:" + x, "Johto gym shell, recoloured")
     for x in ("raffaello", "chiara", "angelo", "furio", "jasmine", "alfredo", "sandra")] +     [("cobbleverse:pedro", "cobbleverse:" + x, "Sinnoh gym shell, recoloured")
     for x in ("gardenia", "marzia", "omar", "fannie", "corrado", "bianca", "ferruccio")]
NPC_ONLY = re.compile(r"/(villagers|animals|mobs|piglins|cats|iron_golem|camel_spawn)(/|$)|/common/animals/|special_structure_spawner/")


def cmd_classify(a):
    """Classes, what to render, and design-variant groups. Re-runnable without re-reading the jars."""
    path = OUT_DIR / "templates.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    with CACHE.open("rb") as f:
        geos = pickle.load(f)
    rows = doc["templates"]
    for r in rows.values():
        for k in ("design", "design_members", "design_match", "render_note", "identical_copies"):
            r.pop(k, None)
    piece_seen = Counter()
    for tid, r in sorted(rows.items()):
        r["placement"] = placement_kind(tid, {"jigsaws": []})[0]
        c, why, how = classify(tid, r)
        if NPC_ONLY.search("/" + tid.split(":", 1)[1]) and r["blocks"] < 40 and how.startswith("automatic"):
            c, why, how = "not_town", "an NPC or animal spawn marker for a village pool (%d blocks)" % r["blocks"], "automatic (contents)"
        r.update(type=c, type_why=why, type_how=how)
        r["decayed"] = "/zombie/" in tid
        want = c != "not_town" and not r["decayed"] and r["blocks"] > 0
        if re.search(r"^bca:general/berries/berry_(?!1$)", tid):
            want, r["render_note"] = False, "berry plot: bca:general/berries/berry_1 is rendered for all 73"
        if tid.startswith("cobbleverse:") or tid.startswith("mega_showdown:"):
            want = r["blocks"] > 0                      # shown even when not a town building: the owner asked what these are
        if want and r["placement"] == "PIECE":
            parent = tid.rsplit("/", 1)[0]
            piece_seen[parent] += 1
            want = piece_seen[parent] <= 2 or c in ("center", "mart", "gym", "civic", "shop", "house")
            r["render_note"] = "representative jigsaw piece" if want else "jigsaw piece not rendered (family has a representative)"
        r["render_wanted"] = want
    # spawn-block flags against the policy as it is now (another session may have changed it since the scan)
    policy = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    spawn = {b: [tuple(x) for x in v] for b, v in doc.get("spawn_table", {}).items()}
    for tid, r in rows.items():
        r["spawn_blocks"] = [{"block": b, "count": n, "spawns": sorted({s for s, _ in spawn[b]}),
                              "fields": sorted({f for _, f in spawn[b]}), "policy": policy_status(b, policy)}
                             for b, n in r["histogram"].items() if b in spawn]
    # the same bytes in two places (a server copy of a kit template): render once
    by_sha = defaultdict(list)
    for tid, r in rows.items():
        by_sha[r["sha256"]].append(tid)
    for sha, ids in by_sha.items():
        ids.sort(key=lambda t: (not t.startswith("kits:"), t))
        for t in ids:
            rows[t]["identical_copies"] = [x for x in ids if x != t]
        for t in ids[1:]:
            if rows[t]["render_wanted"]:
                rows[t]["render_wanted"] = False
                rows[t]["render"] = rows[ids[0]]["render"]
                rows[t]["render_note"] = "byte-identical to %s; its render is shown" % ids[0]
    # design variants: same occupied cells under some rotation/mirror, across every non-trivial candidate
    for tid, r in rows.items():
        g = geos[tid]
        r["waystones"] = int(sum(1 for k in g["state"].tolist() if g["names"][k].startswith("waystones:")
                                 and (g["props"][k] or {}).get("half", "lower") == "lower"))
    ids = [t for t, r in rows.items() if r["type"] != "not_town" and r["blocks"] >= 1 and len(set(rows[x]["sha256"] for x in [t])) and
           t == sorted(by_sha[r["sha256"]], key=lambda x: (not x.startswith("kits:"), x))[0]]
    groups, scores = group_variants(ids, geos, threshold=a.threshold)
    # merges the geometry test cannot make, decided by looking: same building, footprint one block different
    where = {t: gi for gi, g in enumerate(groups) for t in g}
    for keep, other, why in SAME_DESIGN:
        if keep in where and other in where and where[keep] != where[other]:
            gi, go = where[keep], where[other]
            groups[gi].extend(groups[go])
            for t in groups[go]:
                where[t] = gi
            groups[go] = []
    groups = [g for g in groups if g]
    for g in groups:
        g.sort(key=lambda t: ("/zombie/" in t, t))
        gid = g[0]
        for t in g:
            rows[t]["design"] = gid
            rows[t]["design_members"] = len(g)
            if t in scores:
                rows[t]["design_match"] = round(scores[t][1], 3)
    for tid, r in rows.items():
        if "design" not in r:
            first = sorted(by_sha[r["sha256"]], key=lambda x: (not x.startswith("kits:"), x))[0]
            r["design"] = rows[first].get("design", tid)
            r["design_members"] = rows[first].get("design_members", 1)
    path.write_text(json.dumps(doc, indent=1, default=str) + "\n", encoding="utf-8")
    types = Counter(r["type"] for r in rows.values())
    print(json.dumps({"by_type": types, "render_wanted": sum(1 for r in rows.values() if r["render_wanted"]),
                      "design_groups": len(groups)}, indent=1))


# ---------------------------------------------------------------- decorative blocks the pack registers

BLOCK_DIR = RENDER_DIR / "blocks"
BLOCK_USE = [  # (group, regex on the colour/wood-folded id, e.g. "cobblefurnies:*_sofa"); first match wins
    ("building materials", r"^(rechiseled|carved_wood|moarconcrete):|_(corner|pillar)_trim$|tumblestone"),
    ("not dressing", r"spawner|_ore$|ore_|budding|_crop$|stem$|_gem_(cluster|block)$|^cobblemon:.*(fossil|restoration_tank|"
                     r"incubator|pasture|nest)|^(toms_storage|sophisticatedstorage|sophisticatedbackpacks|ironchest|tmcraft|rctmod|"
                     r"cobblemonbattlepositions|mega_showdown|legendarymonuments|waystones):|furnicrafter|portal|summon_|altar|"
                     r"^lumymon:.*(anchor|trigger|crystal|cocoon)|meteor|shard|energy_root|dormant|habitat_block|"
                     r"potion|heal$|elixir|ether$|restore$|^cobblemon:(x_|dire_hit|guard_spec|antidote|awakening|burn_heal|"
                     r"ice_heal|paralyze_heal|revival_herb|full_|max_|hyper_|super_|potion)|_policy$|_tag$|_type_gem$|seeds$|"
                     r"medicinal_leek|revival|bugwort|big_root|vivichoke|hearty_grain|galarica|_stone_block$|dawn_stone|dusk_stone"),
    ("service machines", r"^cobblemon:(pc|healing_machine|monitor|damaged_monitor|display_case)$|tm_machine|ticket_machine"),
    ("statues, fountains and monuments", r"statue|figurine|trophy|monument|bust|shrine|totem|obelisk|pedestal|plinth|idol|"
                                         r"fountain|topiary"),
    ("Pokemon-themed decor", r"pokedoll|plush|poke_?ball|pokeball|poke_wool|pokemon|gilded_chest|fishbowl|^pokeblocks:|gacha|"
                             r"mosaic|poke_(cake|snack)|calyrex_crown|applin_basket|head_pile|gimmighoul|relic_coin"),
    ("lighting", r"lamp|lantern|chandelier|candle|torch|sconce|light_bulb|glow"),
    ("signage", r"_sign$|signboard|_board$|banner|poster|notice|placard|chalkboard|plaque|picture_frame"),
    ("fences and walls", r"_fence$|fence_gate$|_wall$|railing|balustrade|hedge|trellis|lattice|_bars$"),
    ("plants and planters", r"planter|flower_?pot|_pot$|potted|plant|flower|vase|bush|sapling|leaves|apricorn$|_berry$|garden|"
                            r"moss|vine|ivy|hanging_basket|bonsai|cactus|fern|pothos|mint$|eyeblossom|dry_grass|leaf_litter"),
    ("floors and paving", r"floor|tiles?$|parquet|paving|carpet|rug|_mat$|terrazzo|checker"),
    ("market and shop fixtures", r"counter|register|shelf|shelves|showcase|cash|stall|vending|crate|market|shop|cabinetry|kiosk|"
                                 r"fridge|freezer|^cobblemon:tv$|^[a-z_]+:tv$"),
    ("furniture", r"chair|table|sofa|couch|_bed$|desk|stool|bench|cabinet|drawer|nightstand|wardrobe|dresser|curtain|sink|"
                  r"stove|cupboard|clock|bookcase|bookshelf|bookstack|stackable_book|oven|bath|toilet|mirror|piano|hammock|"
                  r"sleeping_bag|pillow|cushion|seat|throne|chest|trough|kitchen|fireplace|chimney|blinds|shutter|lectern|"
                  r"telescope|zaisu|cup$|plate$|bowl$|crockery|jar$|campfire_pot|dye_vat|workbench|elevator|hood"),
    ("building materials", r"planks|bricks?|stairs|slab|_block$|stone|log|wood|pillar|beam|glass|panel|concrete|siding|roof|"
                           r"shingle|thatch|wallpaper|plaster|porcelain|ceramic|resin|cinnabar|sulfur|slathered|wall_support|"
                           r"_door$|trapdoor|button|pressure_plate|grass_block|geostone|heatstone|tatami|saddle_block"),
]
COLOURS = sorted(list(DYES) + ["light_grey"], key=len, reverse=True)
WOODS = ["dark_oak", "oak", "spruce", "birch", "jungle", "acacia", "mangrove", "cherry", "bamboo", "crimson", "warped",
         "pale_oak", "saccharine", "apricorn", "stripped"]


def base_name(name):
    """Fold colour and wood variants: cobblefurnies:black_sofa and cobblefurnies:red_sofa -> cobblefurnies:*_sofa."""
    ns, p = name.split(":", 1)
    parts = p.split("_")
    out, changed = [], False
    i = 0
    while i < len(parts):
        hit = None
        for token in COLOURS + WOODS:
            tp = token.split("_")
            if parts[i:i + len(tp)] == tp:
                hit = tp
                break
        if hit:
            out.append("*")
            i += len(hit)
            changed = True
        else:
            out.append(parts[i])
            i += 1
    folded = "_".join(out)
    while "*_*" in folded:
        folded = folded.replace("*_*", "*")
    return "%s:%s" % (ns, folded) if changed else name


def model_parts(assets, ref, depth=0):
    """-> (elements, textures) following parents: elements from the nearest model that defines them."""
    if depth > 10:
        return None, {}
    ns, p = assets.split(ref)
    if p.startswith("builtin/"):
        return None, {}
    doc = assets.json("assets/%s/models/%s.json" % (ns, p))
    if doc is None:
        return None, {}
    elements, tex = None, {}
    if doc.get("parent"):
        elements, tex = model_parts(assets, doc["parent"], depth + 1)
        tex = dict(tex)
    tex.update(doc.get("textures") or {})
    if doc.get("elements"):
        elements = doc["elements"]
    return elements, tex


def texture_image(assets, ref):
    from PIL import Image
    ns, p = assets.split(ref)
    raw = assets.read("assets/%s/textures/%s.png" % (ns, p))
    if not raw:
        return None
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:
        return None
    w, h = im.size
    meta = assets.read("assets/%s/textures/%s.png.mcmeta" % (ns, p))
    if h > w and (meta or h % w == 0):
        im = im.crop((0, 0, w, w))
    return im


def region_rgb(im, uv):
    w, h = im.size
    u0, v0, u1, v1 = uv
    box = [int(min(u0, u1) * w / 16), int(min(v0, v1) * h / 16), int(max(u0, u1) * w / 16), int(max(v0, v1) * h / 16)]
    box[2], box[3] = max(box[2], box[0] + 1), max(box[3], box[1] + 1)
    arr = np.asarray(im.crop(box)).reshape(-1, 4).astype(float)
    arr = arr[arr[:, 3] > 20]
    if not len(arr):
        return None
    return tuple(arr[:, :3].mean(axis=0))


def draw_model(assets, elements, tex, size=96):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 34.0

    def proj(x, y, z):
        return (size / 2 + (x - z) * s, size * 0.30 + (x + z) * s / 2 - y * s + 12 * s)

    def resolve(ref):
        n = 0
        while isinstance(ref, str) and ref.startswith("#") and n < 8:
            ref, n = tex.get(ref[1:]), n + 1
        return ref
    cache = {}
    boxes = []
    for el in elements:
        f, t = el.get("from"), el.get("to")
        if not (isinstance(f, list) and isinstance(t, list)):
            continue
        faces = el.get("faces") or {}
        cols = {}
        for face in ("up", "east", "south", "north", "west", "down"):
            fd = faces.get(face)
            if not fd:
                continue
            ref = resolve(fd.get("texture"))
            if not isinstance(ref, str):
                continue
            if ref not in cache:
                cache[ref] = texture_image(assets, ref)
            im = cache[ref]
            if im is None:
                continue
            uv = fd.get("uv") or [0, 0, 16, 16]
            c = region_rgb(im, uv)
            if c is not None:
                cols[face] = c
        if not cols:
            continue
        any_c = next(iter(cols.values()))
        top = cols.get("up", any_c)
        east = cols.get("east", cols.get("west", any_c))
        south = cols.get("south", cols.get("north", any_c))
        boxes.append((f, t, top, east, south))
    boxes.sort(key=lambda b: (b[0][0] + b[1][0]) / 2 + (b[0][1] + b[1][1]) / 2 + (b[0][2] + b[1][2]) / 2)
    for (f, t, top, east, south) in boxes:
        x0, y0, z0 = f
        x1, y1, z1 = t
        d.polygon([proj(x1, y0, z0), proj(x1, y1, z0), proj(x1, y1, z1), proj(x1, y0, z1)], fill=tuple(int(c * 0.62) for c in east) + (255,))
        d.polygon([proj(x0, y0, z1), proj(x1, y0, z1), proj(x1, y1, z1), proj(x0, y1, z1)], fill=tuple(int(c * 0.82) for c in south) + (255,))
        d.polygon([proj(x0, y1, z0), proj(x1, y1, z0), proj(x1, y1, z1), proj(x0, y1, z1)], fill=tuple(int(c) for c in top) + (255,))
    return img if boxes else None


def block_thumbnail(assets, ns, name, out_path):
    """Item model first (what a player sees in the inventory), else the blockstate's model."""
    from PIL import Image
    refs = []
    item = assets.json("assets/%s/models/item/%s.json" % (ns, name))
    if item is not None:
        refs.append("%s:item/%s" % (ns, name))
    state = assets.json("assets/%s/blockstates/%s.json" % (ns, name))
    if state:
        if isinstance(state.get("variants"), dict) and state["variants"]:
            v = next(iter(state["variants"].values()))
            v = v[0] if isinstance(v, list) else v
            if isinstance(v, dict) and v.get("model"):
                refs.append(v["model"])
        elif isinstance(state.get("multipart"), list):
            for part in state["multipart"]:
                ap = part.get("apply")
                ap = ap[0] if isinstance(ap, list) else ap
                if isinstance(ap, dict) and ap.get("model"):
                    refs.append(ap["model"])
                    break
    for ref in refs:
        elements, tex = model_parts(assets, ref)
        if tex.get("layer0") and not elements:
            im = texture_image(assets, tex["layer0"])
            if im is not None:
                im = im.resize((64, 64), Image.NEAREST)
                canvas = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
                canvas.paste(im, (16, 16), im)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                canvas.save(out_path)
                return "sprite"
        if elements:
            im = draw_model(assets, elements, tex)
            if im is not None:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                im.save(out_path)
                return "model"
    return None


def cmd_blocks(a):
    client = a.client_jar or find_client_jar()
    assets = Assets(client, a.server_dir)
    vanilla_states = set()
    if client:
        vanilla_states = {n for n in zipfile.ZipFile(client).namelist() if n.startswith("assets/minecraft/blockstates/")}
    # which jar registers each namespace's blockstates (for the source column)
    owner = {}
    lang = {}
    for jar in sorted((Path(a.server_dir) / "mods").glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except zipfile.BadZipFile:
            continue
        zs = [(jar.name, z)]
        for n in z.namelist():
            if n.startswith("META-INF/jars/") and n.endswith(".jar"):
                try:
                    zs.append(("%s!%s" % (jar.name, n.split("/")[-1]), zipfile.ZipFile(io.BytesIO(z.read(n)))))
                except Exception:
                    pass
        for label, zz in zs:
            for n in zz.namelist():
                parts = n.split("/")
                if len(parts) == 4 and parts[0] == "assets" and parts[2] == "blockstates" and n.endswith(".json"):
                    if parts[1] == "minecraft" and n in vanilla_states:
                        continue
                    owner.setdefault("%s:%s" % (parts[1], parts[3][:-5]), label)
                if len(parts) == 4 and parts[0] == "assets" and parts[2] == "lang" and parts[3] == "en_us.json":
                    try:
                        lang.update(json.loads(zz.read(n).decode("utf-8-sig")))
                    except Exception:
                        pass
    sources, _ = ordered_sources(a.server_dir)
    spawn = spawn_table(sources)
    rows = []
    for bid, label in sorted(owner.items()):
        ns, name = bid.split(":", 1)
        group = next((g for g, rx in BLOCK_USE if re.search(rx, base_name(bid))), "other")
        thumb = BLOCK_DIR / ns / (name + ".png")
        kind = block_thumbnail(assets, ns, name, thumb) if (a.force or not thumb.exists()) else "cached"
        rows.append({"id": bid, "name": lang.get("block.%s.%s" % (ns, name)) or lang.get("item.%s.%s" % (ns, name)),
                     "jar": label, "group": group, "base": base_name(bid),
                     "thumbnail": ("blocks/%s/%s.png" % (ns, name)) if (kind or thumb.exists()) else None,
                     "spawns": sorted({s for s, _ in spawn.get(bid, [])})})
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = {"schema": "cobblers.pack-blocks/1", "generated": datetime.date.today().isoformat(),
           "generator": "tools/town_templates.py blocks",
           "method": "every assets/<ns>/blockstates/<name>.json in the server's mod jars (nested jars included), minus "
                     "the vanilla 1.21.1 client jar's own; display names from assets/<ns>/lang/en_us.json",
           "blocks": rows}
    (OUT_DIR / "blocks.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"blocks": len(rows), "by_group": Counter(r["group"] for r in rows),
                      "by_namespace": Counter(r["id"].split(":")[0] for r in rows),
                      "no_thumbnail": sum(1 for r in rows if not r["thumbnail"]),
                      "spawn_conditioned": sum(1 for r in rows if r["spawns"])}, indent=1))


def esc(x):
    import html
    return html.escape(str(x), quote=True)


GYM_ORDER = ["kanto_brock", "kanto_misty", "kanto_ltsurge", "kanto_erika", "kanto_koga", "kanto_sabrina", "kanto_blaine",
             "kanto_giovanni"]
SECTION_ORDER = ["center", "mart", "gym", "house", "shop", "civic", "fence", "lamp", "signage", "prop"]
QUIET_WHITELIST = ("whitelisted",)


def usable(r):
    """Counted as a template a builder can drop in: a whole thing, with blocks, not a decayed (zombie) copy."""
    return r["placement"] == "STANDALONE" and r["blocks"] > 0 and not r["decayed"] and not r.get("disabled")


def source_family(tid, r):
    if r["source"] == "kits" or tid.startswith("cobblers:"):
        return "our kits"
    if r.get("disabled"):
        return "Cobbleverse regional datapack (disabled)"
    if tid.startswith("bca:"):
        return "Cobblemon Additions" + (" (Cobbleverse copy)" if r["source"] == "cobbleverse-dp" else "")
    if tid.startswith("minecraft:village"):
        return "vanilla villages"
    if tid.startswith("repurposed_structures:"):
        return "Repurposed Structures"
    if tid.startswith("cobblemon:"):
        return "Cobblemon" + (" (PokeCenterPCs override)" if r["source"] == "pokecenterpcs" else "")
    return {"cobbleverse": "Cobbleverse datapack", "beautify": "Beautify", "waystones": "Waystones",
            "mega_showdown": "Mega Showdown", "minecraft": "vanilla"}.get(tid.split(":")[0], r["source"])


def flag_html(r):
    out = []
    if r.get("trainers"):
        out.append('<span class="tag info">RCT trainers: %s</span>' % esc(", ".join(sorted(set(r["trainers"])))[:160]))
    if r.get("waystones"):
        out.append('<span class="tag bad">waystone x%d in the template</span>' % r["waystones"])
    if r.get("command_blocks"):
        out.append('<span class="tag warn">%d command blocks</span>' % r["command_blocks"])
    if r.get("spawners"):
        out.append('<span class="tag warn">%d mob spawners</span>' % r["spawners"])
    if r.get("loot_tables"):
        out.append('<span class="tag">%d loot-table containers</span>' % r["loot_tables"])
    for f in r.get("spawn_blocks", []):
        cls = "bad" if f["policy"].startswith("not covered") or f["policy"].startswith("rule exists") else "quiet"
        out.append('<span class="tag %s" title="%s">%s x%d: %s</span>' % (
            cls, esc(f["policy"]), esc(f["block"].replace("minecraft:", "")), f["count"], esc(", ".join(f["spawns"][:4]))))
    return " ".join(out)


def card(tid, r, used, big=False):
    img = r.get("render")
    has = img and (RENDER_DIR / img).exists()
    pic = ('<a href="%s"><img loading="lazy" src="%s" alt="%s"></a>' % (esc(img), esc(img), esc(tid))) if has else \
        '<div class="noimg">%s</div>' % ("entity only, no blocks" if r["blocks"] == 0 else "not rendered")
    note = r.get("render_note") or ""
    return """<div class="card%s"><div class="pic">%s</div><div class="meta">
<div class="id">%s%s</div>
<div>%s &middot; %s &middot; %s blocks &middot; <b class="%s">%s</b>%s</div>
<div class="why">%s</div>
<div class="flags">%s</div>%s</div></div>""" % (
        " big" if big else "", pic, esc(tid) + (' <span class="tag bad">datapack disabled</span>' if r.get("disabled") else ""), ' <span class="tag used">placed in data/placements.json</span>' if tid in used else "",
        esc(source_family(tid, r)), "&times;".join(str(v) for v in r["size"]), r["blocks"],
        "ok" if r["placement"] == "STANDALONE" else "piece", "standalone" if r["placement"] == "STANDALONE" else "jigsaw piece",
        " &middot; decayed copy" if r["decayed"] else "",
        esc(r["type_why"]), flag_html(r), ('<div class="note">%s</div>' % esc(note)) if note else "")


def cmd_html(a):
    doc = json.loads((OUT_DIR / "templates.json").read_text(encoding="utf-8"))
    rows = doc["templates"]
    blocks_doc = json.loads((OUT_DIR / "blocks.json").read_text(encoding="utf-8")) if (OUT_DIR / "blocks.json").exists() else None
    used = set()
    pl = ROOT / "data" / "placements.json"
    if pl.exists():
        used = {p.get("template") for p in json.loads(pl.read_text(encoding="utf-8")).get("placements", [])}
    # designs per type, over usable templates only
    designs = defaultdict(lambda: defaultdict(list))
    for tid, r in rows.items():
        if r["type"] != "not_town" and usable(r):
            designs[r["type"]][r["design"]].append(tid)
    summary = []
    for t in SECTION_ORDER:
        ds = designs.get(t, {})
        n_templates = sum(len(v) for v in ds.values())
        srcs = Counter(source_family(d, rows[d]) for d in ds)
        off = {rows[x]["design"] for x, r in rows.items() if r["type"] == t and r.get("disabled") and r["blocks"] > 0} - set(ds)
        summary.append((t, len(ds), n_templates, srcs, len(off)))
    parts = []
    parts.append("""<title>Town structure catalogue</title>
<style>
:root{--bg:#fbfbf8;--fg:#1d1d1b;--mute:#6b6b66;--line:#dcdcd4;--card:#fff;--bad:#a4261c;--badbg:#fbe9e7;--warn:#8a5a00;--warnbg:#fff4dc;
--ok:#1d6b35;--info:#1f4f8a;--infobg:#e8f0fb;--quiet:#77776f;--quietbg:#f1f1ec}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#1a1a18;--fg:#e8e8e2;--mute:#a3a39b;--line:#3a3a36;--card:#232321;
--bad:#ff8a7a;--badbg:#3a1f1b;--warn:#f2c46b;--warnbg:#3a2f18;--ok:#7fd49a;--info:#9cc1f2;--infobg:#1c2a3d;--quiet:#a3a39b;--quietbg:#2b2b28}}
:root[data-theme="dark"]{--bg:#1a1a18;--fg:#e8e8e2;--mute:#a3a39b;--line:#3a3a36;--card:#232321;--bad:#ff8a7a;--badbg:#3a1f1b;--warn:#f2c46b;
--warnbg:#3a2f18;--ok:#7fd49a;--info:#9cc1f2;--infobg:#1c2a3d;--quiet:#a3a39b;--quietbg:#2b2b28}
a{color:var(--info)}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0;padding:1rem clamp(16px,3vw,40px) 4rem}
h1{margin:.2rem 0 .2rem;font-size:1.6rem}h2{margin:2.2rem 0 .6rem;border-bottom:1px solid var(--line);padding-bottom:.3rem}
h3{margin:1.4rem 0 .4rem;font-size:1.05rem}p{max-width:75ch}.mute{color:var(--mute)}
table{border-collapse:collapse;margin:.6rem 0}td,th{border:1px solid var(--line);padding:.25rem .55rem;text-align:left;vertical-align:top}
th{background:var(--card)}.tablewrap{overflow-x:auto}
nav a{margin-right:.8rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:.8rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:6px;overflow:hidden;display:flex;flex-direction:column}
.card.big{grid-column:1/-1}
.pic img{width:100%;height:auto;display:block;background:#fafaf7}.noimg{padding:1.2rem;color:var(--mute);text-align:center}
.meta{padding:.45rem .6rem;font-size:13px}.id{font-family:ui-monospace,Consolas,monospace;font-weight:600;word-break:break-all}
.why{color:var(--mute)}.note{color:var(--mute);font-style:italic}
.tag{display:inline-block;font-size:11.5px;padding:0 .35rem;border-radius:3px;margin:.12rem .1rem 0 0;background:var(--quietbg);color:var(--quiet)}
.tag.bad{background:var(--badbg);color:var(--bad)}.tag.warn{background:var(--warnbg);color:var(--warn)}
.tag.info{background:var(--infobg);color:var(--info)}.tag.used{background:var(--infobg);color:var(--info)}
b.ok{color:var(--ok)}b.piece{color:var(--warn)}
details{margin:.4rem 0}summary{cursor:pointer;font-weight:600}
.design{border-left:3px solid var(--line);padding-left:.7rem;margin:1rem 0}
.members{font-family:ui-monospace,Consolas,monospace;font-size:12px;color:var(--mute);word-break:break-all}
.bgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:.5rem}
.bcard{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:.35rem .45rem;font-size:12px}
.bcard .thumbs img{width:48px;height:48px;image-rendering:pixelated}
.bcard .bname{font-weight:600}.bcard .bid{font-family:ui-monospace,Consolas,monospace;color:var(--mute);word-break:break-all}
.gap{color:var(--bad);font-weight:600}
</style>""")
    parts.append("<h1>Town structure catalogue</h1>")
    parts.append('<p class="mute">Generated %s by <code>tools/town_templates.py</code> from the server at <code>%s</code> (level <code>%s</code>) '
                 'and <code>kits/structures</code>. Findings and method: <code>docs/world-building/STRUCTURE_INVENTORY.md</code>. '
                 'Each render shows the template from two opposite corners; colours are texture averages, not textures.</p>'
                 % (esc(doc["generated"]), esc(a.server_dir if hasattr(a, "server_dir") else ""), esc(doc["load_order"]["level"])))
    parts.append('<nav>' + " ".join('<a href="#%s">%s</a>' % (t, esc(TYPE_LABEL[t])) for t in SECTION_ORDER)
                 + ' <a href="#unused">Unused Cobbleverse</a> <a href="#landmarks">Landmarks</a> <a href="#blocks">Decorative blocks</a></nav>')
    # summary
    parts.append("<h2 id=\"summary\">Summary</h2>")
    parts.append("<p>Counts are over <b>standalone</b> templates with blocks, excluding decayed (zombie-village) copies and "
                 "entity-only NPC boxes. A <b>design</b> is a group of templates whose occupied cells match at 85% or more "
                 "under some rotation or mirror (vertical offset up to 4): the same building in other materials counts once.</p>")
    parts.append('<div class="tablewrap"><table><tr><th>Type</th><th>Distinct designs</th><th>Placeable templates</th><th>More designs in disabled datapacks</th><th>Designs by source</th></tr>')
    for t, nd, nt, srcs, noff in summary:
        parts.append("<tr><td><a href=\"#%s\">%s</a></td><td%s>%d</td><td>%d</td><td>%s</td><td>%s</td></tr>" % (
            t, esc(TYPE_LABEL[t]), ' class="gap"' if nd == 0 else "", nd, nt, noff or "",
            esc(", ".join("%s %d" % (k, v) for k, v in srcs.most_common())) or '<span class="gap">none: an authoring gap</span>'))
    parts.append("</table></div>")
    # what Cobbleverse ships that the campaign has not placed
    parts.append('<h2 id="unused">Shipped by Cobbleverse and not placed by us</h2>')
    parts.append("<p>Placed means named in <code>data/placements.json</code>. Everything in this table is unplaced. "
                 "Standalone means <code>/place template</code> drops in the whole building; its jigsaw decoration "
                 "slots (NPC clerks, berry plants, lamp posts) stay empty unless placed separately.</p>")
    parts.append('<div class="tablewrap"><table><tr><th>What</th><th>Templates</th><th>Loaded on this world</th><th>Kind</th><th>Notes</th></tr>')
    kanto = [t for t, r in sorted(rows.items()) if r["type"] == "gym" and not r.get("disabled") and t.startswith("cobbleverse:")]
    regional = [t for t, r in sorted(rows.items()) if r["type"] == "gym" and r.get("disabled")]
    leagues = [t for t, r in sorted(rows.items()) if re.search(r"_league$", t)]
    svc = [t for t, r in sorted(rows.items()) if r["type"] in ("center", "mart") and t.split(":")[0] in ("bca", "cobblemon") and r["blocks"] > 0]
    npc = [t for t, r in sorted(rows.items()) if t.startswith("bca:stores/") and r["blocks"] == 0]
    bca_houses = [t for t, r in rows.items() if t.startswith("bca:") and r["type"] == "house"]
    rows_u = [
        ("Kanto gyms (8 leaders)", kanto, "yes (COBBLEVERSE-DP-v31)", "standalone",
         "one shell recoloured for Brock, Lt. Surge, Erika, Koga, Sabrina, Blaine, Giovanni; Misty's is a different "
         "building on a floating island. Each carries its leader's RCT trainer spawner and vanilla concrete."),
        ("Hoenn, Johto, Sinnoh gyms", regional, "no: the three regional datapacks are disabled in level.dat", "standalone",
         "one shell per region, recoloured; Hoenn adds a floating-island gym (adriano) and a mossy one (alice)"),
        ("League buildings", leagues, "Kanto yes; Hoenn, Johto, Sinnoh no", "standalone", "Elite Four and Champion trainer spawners inside"),
        ("Pokemon Centers and Marts", svc, "yes", "standalone", "BCA's red-roof Center and blue Mart (Cobbleverse ships its own "
         "copies, which override BCA's), two lodge-scale Centers, and 19 village Centers overridden by PokeCenterPCs"),
        ("Shop clerks and Nurse Joy", npc, "yes", "entity-only template",
         "1x2x1 boxes holding one CobbleDollars merchant (or a villager for Nurse Joy); this is what makes a BCA Mart "
         "or market functional, and it is not placed by placing the building"),
        ("BCA custom villages", bca_houses, "yes", "worldgen jigsaw villages; every house template is standalone",
         "9 worldgen structures (default, dark, fighting at small/mid/large, plus the witch hut)"),
    ]
    for what, ids_, loaded, kind, note in rows_u:
        parts.append("<tr><td>%s</td><td>%d<div class=\"members\">%s</div></td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            esc(what), len(ids_), esc(", ".join(i.split(":", 1)[1] for i in ids_[:40]) + (" ..." if len(ids_) > 40 else "")),
            esc(loaded), esc(kind), esc(note)))
    parts.append("</table></div>")
    # sections
    for t in SECTION_ORDER:
        parts.append('<h2 id="%s">%s</h2>' % (t, esc(TYPE_LABEL[t])))
        ids = [tid for tid, r in rows.items() if r["type"] == t]
        if not ids:
            parts.append('<p class="gap">No template of this type exists in the pack or our kits.</p>')
            continue
        if t == "gym":
            by_leader = defaultdict(list)
            for tid in ids:
                leaders = [x for x in rows[tid]["trainers"] if x in KANTO or re.fullmatch(r"(hoenn|johto|sinnoh)_[a-z]+", x)] or ["?"]
                by_leader[leaders[0]].append(tid)
            for leader in GYM_ORDER + sorted(k for k in by_leader if k not in GYM_ORDER):
                if leader not in by_leader:
                    parts.append('<h3>%s</h3><p class="gap">no template</p>' % esc(KANTO.get(leader, leader)))
                    continue
                label = KANTO.get(leader) or ("%s (%s, datapack disabled on this world)" % (leader, leader.split("_")[0].title()))
                parts.append("<h3>%s</h3><div class=\"grid\">" % esc(label))
                for tid in sorted(by_leader[leader], key=lambda x: (not rows[x].get("render_wanted"), x)):
                    if not rows[tid].get("render_wanted") and rows[tid].get("identical_copies"):
                        continue
                    parts.append(card(tid, rows[tid], used))
                parts.append("</div>")
            continue
        groups = defaultdict(list)
        for tid in ids:
            groups[rows[tid]["design"]].append(tid)
        ordered = sorted(groups.items(), key=lambda kv: (not any(usable(rows[x]) for x in kv[1]), source_family(kv[0], rows[kv[0]]), kv[0]))
        fam_of = defaultdict(list)
        for rep, members in ordered:
            fam_of[source_family(rep, rows[rep])].append((rep, members))
        for fam, lst in fam_of.items():
            n_use = sum(1 for rep, m in lst if any(usable(rows[x]) for x in m))
            collapsed = t in ("prop",) or (t == "house" and fam in ("Repurposed Structures",))
            parts.append('<details%s><summary>%s: %d designs (%d placeable)</summary>' % ("" if collapsed else " open", esc(fam), len(lst), n_use))
            for rep, members in lst:
                members.sort(key=lambda x: (rows[x]["decayed"], not rows[x].get("render_wanted"), x))
                shown = [m for m in members if rows[m].get("render_wanted") or (m == members[0])]
                rest = [m for m in members if m not in shown]
                label = "design of %d template%s" % (len(members), "s" if len(members) != 1 else "")
                parts.append('<div class="design"><div class="mute">%s</div><div class="grid">' % label)
                for m in shown[:12]:
                    parts.append(card(m, rows[m], used))
                parts.append("</div>")
                if rest or len(shown) > 12:
                    more = rest + shown[12:]
                    parts.append('<div class="members">also: %s</div>' % esc(", ".join(
                        "%s%s" % (x, " (decayed)" if rows[x]["decayed"] else "") for x in more)))
                parts.append("</div>")
            parts.append("</details>")
    # landmarks: Cobbleverse and Mega Showdown structures that are not town buildings
    parts.append('<h2 id="landmarks">Landmarks and other shipped structures (not town buildings)</h2><div class="grid">')
    for tid, r in sorted(rows.items()):
        if r["type"] == "not_town" and r.get("render_wanted"):
            parts.append(card(tid, r, used))
    parts.append("</div>")
    # decorative blocks
    if blocks_doc:
        parts.append('<h2 id="blocks">Decorative blocks the pack already registers</h2>')
        parts.append("<p>Every block with a blockstate in the server's mod jars that the vanilla 1.21.1 client jar does not "
                     "have. Variants that differ only by colour or wood are folded into one card (hover a thumbnail for its id). "
                     "Thumbnails are drawn from each block's item or block model. A red tag means a loaded Cobblemon spawn "
                     "condition names the block.</p>")
        order = ["furniture", "statues, fountains and monuments", "Pokemon-themed decor", "service machines",
                 "market and shop fixtures", "lighting", "signage", "fences and walls", "plants and planters",
                 "floors and paving", "other", "building materials", "not dressing"]
        by_group = defaultdict(lambda: defaultdict(list))
        for b in blocks_doc["blocks"]:
            by_group[b["group"]][b["base"]].append(b)
        parts.append('<div class="tablewrap"><table><tr><th>Group</th><th>Cards (folded)</th><th>Blocks</th><th>Namespaces</th></tr>')
        for g in order:
            bases = by_group.get(g, {})
            nss = Counter(x["id"].split(":")[0] for v in bases.values() for x in v)
            parts.append("<tr><td><a href=\"#blk-%s\">%s</a></td><td>%d</td><td>%d</td><td>%s</td></tr>" % (
                re.sub(r"\W+", "-", g), esc(g), len(bases), sum(len(v) for v in bases.values()),
                esc(", ".join("%s %d" % kv for kv in nss.most_common()))))
        parts.append("</table></div>")
        for g in order:
            bases = by_group.get(g, {})
            collapsed = g in ("building materials", "not dressing")
            parts.append('<details%s id="blk-%s"><summary>%s (%d)</summary><div class="bgrid">' % (
                "" if collapsed else " open", re.sub(r"\W+", "-", g), esc(g), sum(len(v) for v in bases.values())))
            for base, members in sorted(bases.items(), key=lambda kv: kv[0]):
                members.sort(key=lambda x: x["id"])
                thumbs = "".join('<img loading="lazy" src="%s" title="%s" alt="">' % (esc(m["thumbnail"]), esc(m["id"]))
                                 for m in members[:12] if m["thumbnail"])
                spawns = sorted({s for m in members for s in m["spawns"]})
                name = members[0]["name"] or members[0]["id"]
                parts.append('<div class="bcard"><div class="thumbs">%s</div><div class="bname">%s%s</div><div class="bid">%s</div>%s</div>' % (
                    thumbs or '<span class="mute">no thumbnail</span>', esc(name),
                    (" <span class=\"mute\">+%d variants</span>" % (len(members) - 1)) if len(members) > 1 else "",
                    esc(base), ('<span class="tag bad">spawn condition: %s</span>' % esc(", ".join(spawns[:6]))) if spawns else ""))
            parts.append("</div></details>")
    out = RENDER_DIR / "index.html"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(json.dumps({"out": str(out), "bytes": out.stat().st_size,
                      "summary": {t: {"designs": nd, "templates": nt, "disabled_designs": noff} for t, nd, nt, _, noff in summary}}, indent=1))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--server-dir", required=True)
    s = sub.add_parser("classify")
    s.add_argument("--threshold", type=float, default=0.85)
    s = sub.add_parser("render")
    s.add_argument("--only", default=None, help="regex on template id")
    s.add_argument("--client-jar", default=None)
    s.add_argument("--force", action="store_true", help="re-render PNGs that already exist")
    s.add_argument("--server-dir", default=str(ROOT.parent.parent / "cobblers-server"))
    s = sub.add_parser("blocks")
    s.add_argument("--client-jar", default=None)
    s.add_argument("--force", action="store_true")
    s.add_argument("--server-dir", default=str(ROOT.parent.parent / "cobblers-server"))
    s = sub.add_parser("html")
    s.add_argument("--server-dir", default=str(ROOT.parent.parent / "cobblers-server"))
    a = p.parse_args(argv)
    {"scan": cmd_scan, "classify": cmd_classify, "render": cmd_render, "blocks": cmd_blocks, "html": cmd_html}[a.cmd](a)


if __name__ == "__main__":
    main()
