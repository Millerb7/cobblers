#!/usr/bin/env python
"""Every container we place is a Lootr container with a loot table that exists on the server.

Why (the owner, 2026-10-21): opening a chest whose LootTable names a table the server does not have prints a red error
under Lootr. Pallet's eight cobblemoncitytowns chests did (a mod we do not run), and the first fix, `minecraft:empty`,
is rejected the same way. The owner then asked for every chest to be instanced if it can be, with fun loot for every
stage of the game. This tool finds the containers, decides each one's table, writes data/loot_fixes.json, writes the
RCON command list that repairs the world that already exists, and is the mapping the placers use so a rebuild does not
bring the errors back.

  python tools/loot_fix.py plan                 counts only (harvests: needs the heightmap and the server's mods/ and datapacks/)
  python tools/loot_fix.py fixes                writes data/loot_fixes.json
  python tools/loot_fix.py commands [--out F] [--area N] [--no-guard]
                                                writes the RCON list from data/loot_fixes.json, grouped by area, each area
                                                bracketed by forceload add / forceload remove
  python tools/loot_fix.py tables [--out DIR]   writes data/cobblers/loot_table/chests/<stage>/<kind>.json from
                                                data/stage_loot.json (and nothing when that file is absent)
  python tools/loot_fix.py check                every new table exists, no position twice, no minecraft:empty

What it harvests, and how each world position is computed (the placing tool's own function, never a second copy):
  - towns: tools/place_town.py build(), which reports every container it seats (template_info() lists them, world_xz()
    and `rotate` turn them, oy is the origin's Y). tools/place_town.py calls resolve_container() below for the same
    containers while it writes the town function, so the repair and the rebuild cannot disagree;
  - donors and adopted sites: tools/place_donor.py transform() (mirror then rotation about the placement position) at the
    record's position, for every `pack_template` record, and for an adopted site that no placement record schedules
    (tools/adopted_sites.where()).

What it does NOT cover (CLAUDE.md "Our list is not the world"):
  - anything a mod's own worldgen placed (Repurposed Structures, Cobblemon, Lumymon villages): not ours;
  - a container a generator writes by `setblock` (dungeon vaults, portals, fossil seams, data/rewards.json caches): see
    data/loot_remap.json not_touched for why each is left alone;
  - a container only a player or a mod places in play;
  - Y of a town building on a LEVELLED lot when derived/towns/<settlement>_plan.json is absent (it is gitignored and
    built by prepare): x, z and facing are exact then, Y is the heightmap's, and the record says y_basis. The commands
    are guarded (`execute if block`), so a wrong Y does nothing rather than damage.

data/stage_loot.json (written by the trainer-balance designer) is read when it exists. The shape this tool reads:
  {"stages": {"<stage id>": {"tiers": [1, 2], "sigil": 1 | true | {"band": 1, "chance": 0.08, "kinds": [...]},
                              "kinds": {"<kind>": {"rolls": 2 | [1, 3],
                                                   "entries": [{"item": "cobblemon:poke_ball", "weight": 10,
                                                                "count": 3 | [1, 4]}],
                                                   "pools": [<raw vanilla pools>]}}}}}
  `stages` may also be a list of objects with an "id". A stage without "tiers" takes the default ladder
  (data/loot_remap.json default_stage_ladder) by its position in the list.
That shape is this tool's reading, written before the file existed: reconcile it with the real file.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

REMAP = ROOT / "data" / "loot_remap.json"
STAGE_LOOT = ROOT / "data" / "stage_loot.json"
FIXES = ROOT / "data" / "loot_fixes.json"
NS = "cobblers"
SERVER_DIR = "C:/Users/wnd/Documents/github/cobblers-server"
DIRS = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}
BY_VEC = {v: k for k, v in DIRS.items()}

_cache: dict = {}
SKIPPED: list = []          # settlements place_town.build() refused in this checkout, with its words


def remap():
    if "remap" not in _cache:
        _cache["remap"] = json.loads(REMAP.read_text(encoding="utf-8"))
    return _cache["remap"]


def stage_doc():
    """The stages of data/stage_loot.json as {id: stage dict}, or {} when the file does not exist."""
    if "stages" not in _cache:
        out = {}
        if STAGE_LOOT.is_file():
            raw = json.loads(STAGE_LOOT.read_text(encoding="utf-8")).get("stages") or {}
            if isinstance(raw, dict):
                out = {k: dict(v) for k, v in raw.items()}
            else:
                out = {s["id"]: dict(s) for s in raw}
        _cache["stages"] = out
    return _cache["stages"]


def stage_ids():
    ladder = remap()["default_stage_ladder"]
    return list(stage_doc()) or list(ladder["ids"])


def tier_to_stage():
    """{tier int: stage id}: the stage file's own `tiers`, else the default ladder spread over the stages it names."""
    ladder = remap()["default_stage_ladder"]
    sd = stage_doc()
    if not sd:
        return {int(k): v for k, v in ladder["tier_to_stage"].items()}
    out, ids = {}, list(sd)
    for sid, s in sd.items():
        for t in s.get("tiers") or []:
            out[int(t)] = sid
    if out:
        return out
    base = {int(k): ladder["ids"].index(v) for k, v in ladder["tier_to_stage"].items()}
    top = max(base.values()) or 1
    return {t: ids[min(len(ids) - 1, round(i * (len(ids) - 1) / top))] for t, i in base.items()}


def tier_at(x, z):
    """(tier, basis): the encounter tier of the sub-region that holds (x, z) in data/regions.json, else of the nearest one."""
    if "subs" not in _cache:
        import subregion_boxes as SB
        regions = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
        tables = json.loads((ROOT / "data" / "encounter_design.json").read_text(encoding="utf-8"))["tables"]
        subs = []
        for s in regions["subregions"]:
            tier = (tables.get(s["id"]) or {}).get("tier")
            if tier is not None and s.get("polygons"):
                subs.append((s["id"], int(tier), s["polygons"]))
        _cache["subs"], _cache["pip"] = subs, SB.point_in_polygon
    pip = _cache["pip"]
    best = None
    for sid, tier, polys in _cache["subs"]:
        for poly in polys:
            if pip(x + 0.5, z + 0.5, poly):
                return tier, "inside %s" % sid
            d = min((px - x) ** 2 + (pz - z) ** 2 for px, pz in poly)
            if best is None or d < best[0]:
                best = (d, tier, sid)
    if best is None:
        return 1, "no sub-region has a tier: stage 1"
    return best[1], "nearest %s (%d blocks)" % (best[2], int(best[0] ** 0.5))


def existing_tables():
    if "tables" not in _cache:
        import loot_tables_existing as LT
        _cache["tables"], _cache["sources"] = LT.existing()
    return _cache["tables"]


def stage_tables():
    """The cobblers:chests/<stage>/<kind> ids data/stage_loot.json defines (empty while the file is absent)."""
    out = set()
    for sid, s in stage_doc().items():
        for kind in s.get("kinds") or {}:
            out.add("%s:chests/%s/%s" % (NS, sid, kind))
    out |= {site_table_id(k) for k in site_overrides()}
    return out


def known_tables():
    return existing_tables() | stage_tables()


# ------------------------------------------------------------------------------------------------- container reading


def container_block(name):
    """The Lootr block for a template block, or None when Lootr has no block for it."""
    lb = remap()["lootr_blocks"]
    if name.endswith("shulker_box"):
        return lb["minecraft:shulker_box"]
    return lb.get(name) if name in ("minecraft:chest", "minecraft:trapped_chest", "minecraft:barrel") else None


def template_containers(doc):
    """[{pos, name, lootr, props, table, items}] for every container in a loaded template that Lootr can instance."""
    pal = doc["palette"] if "palette" in doc else doc["palettes"][0]
    out = []
    for b in doc["blocks"]:
        p = pal[b["state"]]
        lootr = container_block(p["Name"])
        if not lootr:
            continue
        n = b.get("nbt") or {}
        out.append({"pos": list(b["pos"]), "name": p["Name"], "lootr": lootr, "props": dict(p.get("Properties") or {}),
                    "table": n.get("LootTable") or None, "items": bool(n.get("Items"))})
    return out


def turn_facing(facing, rot, mirror="none"):
    """A facing after `/place template`'s mirror (left_right negates z, front_back negates x) then rotation."""
    if facing not in DIRS:
        return facing
    x, z = DIRS[facing]
    if mirror == "left_right":
        z = -z
    elif mirror == "front_back":
        x = -x
    x, z = {"none": (x, z), "clockwise_90": (-z, x), "180": (-x, -z), "counterclockwise_90": (z, -x)}[rot]
    return BY_VEC[(x, z)]


def kept_props(c, rot, mirror):
    keep = remap()["lootr_blocks"]["kept_properties"][c["lootr"]]
    props = {k: v for k, v in c["props"].items() if k in keep}
    if "facing" in props:
        props["facing"] = turn_facing(props["facing"], rot, mirror)
    if mirror != "none" and props.get("type") in ("left", "right"):
        props["type"] = "right" if props["type"] == "left" else "left"
    return props


# ------------------------------------------------------------------------------------------------- the decision


def kind_of(placement, template_id, old_table):
    """The kind of a container: the first rule of data/loot_remap.json kind_rules whose any pattern field matches."""
    values = {"placement_id": placement.get("id") or "", "template": template_id or "", "old_table": old_table or "",
              "placement_kind": placement.get("kind") or ""}
    for r in remap()["kind_rules"]["rules"]:
        fields = [k for k in values if k in r]
        if fields and any(re.search(r[k], values[k]) for k in fields):
            return r["kind"]
    return remap()["kind_rules"]["default"]


def stage_of(x, z, placement):
    """(stage id, tier, basis): the League's own stage by placement kind, else the stage of the area's encounter tier."""
    ladder = remap()["default_stage_ladder"]
    pk = placement.get("kind") or ""
    if pk in ladder["placement_kind_overrides"]:
        return ladder["placement_kind_overrides"][pk], None, "placement kind %s" % pk
    tier, basis = tier_at(x, z)
    t2s = tier_to_stage()
    below = [k for k in t2s if k <= tier]
    stage = t2s[tier] if tier in t2s else (t2s[max(below)] if below else t2s[min(t2s)])
    return stage, tier, basis


def placeholder_table(kind, old_table, template_id):
    rm = remap()
    if kind == "house":
        for word, t in rm["placeholder_house_flavours"].items():
            if word != "why" and re.search(word, "%s %s" % (old_table or "", template_id or "")):
                return t
    if kind == "smith":
        for word, t in rm["placeholder_smith_flavours"].items():
            if re.search(word, "%s %s" % (old_table or "", template_id or "")):
                return t
    return rm["placeholder_by_kind"][kind]


def stage_table(stage, kind):
    """cobblers:chests/<stage>/<kind> when data/stage_loot.json defines it (falling back to the stage's other, then house)."""
    kinds = (stage_doc().get(stage) or {}).get("kinds") or {}
    for k in (kind, "other", "house"):
        if k in kinds:
            return "%s:chests/%s/%s" % (NS, stage, k)
    return None


def resolve_container(c, world, rot, mirror, placement, source, template_id, stripped=False):
    """The record for one container: where it is, what it names, what it should name, and why.

    c: an entry of template_containers(); world: (x, y, z) of the block; stripped: the placer removed the template's table
    (tools/place_town.py did for every town container, `clear_loot` donors do), so the world holds an empty plain container
    whatever the template says."""
    x, y, z = world
    kind = kind_of(placement, template_id, c["table"])
    stage, tier, basis = stage_of(x, z, placement)
    old = c["table"]
    new, why, placeholder = None, "", False
    if c["items"] and not old:
        return {"action": "skip_items", "why": "the template stocks this container with literal items: left alone",
                "kind": kind, "stage": stage, "tier": tier, "stage_basis": basis, "new_table": None, "placeholder": False}
    st = stage_table(stage, kind) if stage_doc() else None
    if st:
        new, why = st, "stage %s, kind %s (data/stage_loot.json)" % (stage, kind)
        action = "restage"
    else:
        placeholder = True
        gate = None
        if kind == "legendary_site" and old and old in existing_tables():
            body = table_text(old)
            gate = re.search(remap()["forbidden_in_instanced_loot"]["item_regex"], body or "")
        if old and old in existing_tables() and not stripped and not gate:
            new, action = old, "keep"
            why = "the template's own table exists on the server (%s)" % old
        elif gate:
            new, action = placeholder_table(kind, old, template_id), "replace_gate_table"
            why = "%s can hand out a gate item (%s) and this is a legendary site: no feather, summon item or key in an instanced chest" % (old, gate.group(0))
        else:
            new = placeholder_table(kind, old, template_id)
            if old and old == "minecraft:empty":
                action, why = "fix_empty", "minecraft:empty is rejected by Lootr; the %s kind's placeholder instead" % kind
            elif old and old not in existing_tables():
                action, why = "fix_missing", "table %s is not on the server (mod not installed)" % old
            elif old:
                action, why = "restore_stripped", "the placer strips the template's table; the world holds an empty container"
            else:
                action, why = "add_table", "an empty container with no table: given one so it holds something"
    return {"action": action, "kind": kind, "stage": stage, "tier": tier, "stage_basis": basis, "new_table": new,
            "placeholder": placeholder, "why": why}


def build_record(c, world, rot, mirror, placement, source, template_id, stripped, y_basis):
    r = resolve_container(c, world, rot, mirror, placement, source, template_id, stripped)
    props = kept_props(c, rot, mirror)
    r.update({"placement": placement.get("id"), "source": source, "template": template_id, "template_pos": c["pos"],
              "block": c["name"], "lootr_block": c["lootr"], "pos": list(world), "facing": props.get("facing"),
              "properties": props, "old_table": c["table"], "world_state": "stripped" if stripped else "as_template",
              "y_basis": y_basis, "chunk": [world[0] >> 4, world[2] >> 4]})
    return r


def block_state(r):
    props = ",".join("%s=%s" % kv for kv in sorted(r["properties"].items()))
    return "%s%s{LootTable:\"%s\"}" % (r["lootr_block"], "[%s]" % props if props else "", r["new_table"])


def source_commands(r):
    """The lines a placer writes right after `place template`: nothing for a record that keeps its own table or skips."""
    if r["action"] in ("keep", "skip_items") or not r.get("new_table"):
        return []
    x, y, z = r["pos"]
    return ["setblock %d %d %d %s" % (x, y, z, block_state(r))]


def fix_commands(r, guard=True):
    """The repair for a world that already exists: guarded so a wrong Y places nothing."""
    if r["action"] in ("keep", "skip_items") or not r.get("new_table"):
        return []
    x, y, z = r["pos"]
    cmd = "setblock %d %d %d %s" % (x, y, z, block_state(r))
    if not guard:
        return [cmd]
    return ["execute if block %d %d %d %s run %s" % (x, y, z, b, cmd) for b in (r["block"], r["lootr_block"])]


# ------------------------------------------------------------------------------------------------- harvesting


def reward_positions():
    d = json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))
    return {tuple(r["container"]["at"]) for r in d.get("rewards") or [] if (r.get("container") or {}).get("at")}


def harvest_towns(server_dir=None):
    """Every container place_town.build() seats, from its own report (it calls resolve_container)."""
    import ground as G
    import place_town
    from terrain import env_source_root
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    legs_p = ROOT / "derived" / "routes" / "critical_legs.json"
    legs = json.loads(legs_p.read_text(encoding="utf-8")) if legs_p.exists() else None
    out = []
    names = sorted({q["settlement"] for q in doc["placements"] if q.get("file")})
    tmp = Path(tempfile.mkdtemp(prefix="loot_fix_"))
    for s in names:
        try:
            ground_at = G.for_settlement(s, env_source_root(), doc)
            _cmds, report = place_town.build(s, doc, ground_at, legs, tmp / s, buildings_only=True)
        except SystemExit as exc:
            # a settlement whose ground needs a derived plan this checkout lacks (the cavern's): named, never silent
            SKIPPED.append((s, str(exc)[:160]))
            continue
        plan = ROOT / "derived" / "towns" / ("%s_plan.json" % s)
        for rec in report.get("containers") or []:
            rec["y_basis"] = "heightmap and derived plan" if plan.is_file() else "heightmap only (derived/towns/%s_plan.json absent)" % s
            out.append(rec)
    return out


def harvest_donors(server_dir=SERVER_DIR):
    import adopted_sites
    import place_donor
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    out = []
    for p in place_donor.records(doc):
        _n, tdoc = place_donor.load_template(server_dir, p["pack_template"])
        out += donor_records(p, tdoc, "place_donor")
    scheduled = {q.get("scheduled_as") for q in adopted_sites.sites() if q.get("scheduled_as")}
    for s in adopted_sites.sites():
        if s.get("scheduled_as") in scheduled and s.get("scheduled_as"):
            continue
        w = adopted_sites.where(s)
        p = {"id": s["id"], "kind": "donor", "pack_template": s["template"],
             "position": {"x": w["corner"][0], "y": w["y"], "z": w["corner"][1]}, "rotation": w["rotation"], "mirror": w["mirror"]}
        _n, tdoc = place_donor.load_template(server_dir, s["template"])
        out += donor_records(p, tdoc, "adopted_sites (not scheduled in data/placements.json)")
    return out


def donor_records(p, tdoc, source):
    import place_donor
    rot, mirror = p.get("rotation") or "none", p.get("mirror") or "none"
    pos = p["position"]
    out = []
    for c in template_containers(tdoc):
        tx, ty, tz = c["pos"]
        rx, rz = place_donor.transform(tx, tz, rot, mirror)
        world = (pos["x"] + rx, pos["y"] + ty, pos["z"] + rz)
        out.append(build_record(c, world, rot, mirror, p, source, p["pack_template"], bool(p.get("clear_loot")),
                                "record position (absolute y)"))
    return out


def donor_source_commands(p, tdoc):
    """The lines tools/place_donor.py writes after the paste of one record: every container's repair, from here."""
    return [line for r in donor_records(p, tdoc, "place_donor") for line in source_commands(r)]


def harvest(server_dir=SERVER_DIR):
    recs = harvest_towns(server_dir) + harvest_donors(server_dir)
    rewards = reward_positions()
    kept, dropped = [], []
    for r in recs:
        (dropped if tuple(r["pos"]) in rewards else kept).append(r)
    seen, dups = {}, []
    for r in kept:
        k = tuple(r["pos"])
        if k in seen:
            dups.append((k, seen[k], r["placement"]))
        seen[k] = r["placement"]
    return kept, dropped, dups


def legendary_items(server_dir=SERVER_DIR):
    """Every item stocked in the legendary towers' containers, nested storage included, flagged when it is a gate item."""
    import adopted_sites
    import place_donor
    rx = re.compile(remap()["forbidden_in_instanced_loot"]["item_regex"])
    out = []

    def walk(v, found):
        if isinstance(v, dict):
            i = v.get("id")
            if isinstance(i, str) and ":" in i and ("count" in v or "Count" in v):
                found.append(i)
            for x in v.values():
                walk(x, found)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x, found)

    import nbt as N
    for s in adopted_sites.sites():
        tid = s["template"]
        if "legendary/" not in tid and "tower" not in tid and "spire" not in tid and "temple" not in tid:
            continue
        _n, doc = place_donor.load_template(server_dir, tid)
        pal = doc["palette"]
        for b in doc["blocks"]:
            nb = b.get("nbt")
            if not nb:
                continue
            found = []
            walk(nb, found)
            if found:
                out.append({"site": s["id"], "template": tid, "block": pal[b["state"]]["Name"], "template_pos": list(b["pos"]),
                            "items": dict(Counter(found)), "gate_items": sorted({i for i in found if rx.search(i)})})
    return out


# ------------------------------------------------------------------------------------------------- the tables


def sigil_entry(band):
    """The loot entry for a dungeon band's sigil, from tools/dungeon.py's own item definition (sigil_recipe): the same
    item, id and components the crafting recipe makes. Never a look-alike."""
    import dungeon
    doc = dungeon.load()
    x = next(s for s in dungeon.sigils(doc) if s["band"] == int(band))
    res = dungeon.sigil_recipe(x, doc)["result"]
    return {"type": "minecraft:item", "name": res["id"],
            "functions": [{"function": "minecraft:set_components", "components": res["components"]}]}


def _count(c):
    if isinstance(c, list):
        return {"type": "minecraft:uniform", "min": c[0], "max": c[1]}
    return c


def table_json(stage_id, stage, kind, spec):
    pools = []
    if spec.get("pools"):
        pools += spec["pools"]
    elif spec.get("entries"):
        entries = []
        for e in spec["entries"]:
            ent = {"type": "minecraft:item", "name": e["item"], "weight": e.get("weight", 1)}
            fn = []
            if e.get("count") is not None:
                fn.append({"function": "minecraft:set_count", "count": _count(e["count"])})
            if e.get("components"):
                fn.append({"function": "minecraft:set_components", "components": e["components"]})
            if fn:
                ent["functions"] = fn
            entries.append(ent)
        rolls = spec.get("rolls", 2)
        pools.append({"rolls": {"type": "minecraft:uniform", "min": rolls[0], "max": rolls[1]} if isinstance(rolls, list) else rolls,
                      "entries": entries})
    sg = stage.get("sigil")
    if sg:
        sg = {"band": sg} if isinstance(sg, int) and not isinstance(sg, bool) else ({} if sg is True else dict(sg))
        band = sg.get("band")
        if band is None:
            band = (stage_ids().index(stage_id) + 1)
        if not sg.get("kinds") or kind in sg["kinds"]:
            pools.append({"rolls": 1, "conditions": [{"condition": "minecraft:random_chance", "chance": sg.get("chance", 0.08)}],
                          "entries": [sigil_entry(band)]})
    return {"type": "minecraft:chest", "pools": pools}


def site_overrides():
    """{site id: (stage id, extra entries)} from data/stage_loot.json site_overrides: a legendary site's own table is its
    stage's legendary_site entries plus these themed ones (the owner, 2026-10-21: 'give the player something cool')."""
    f = ROOT / "data" / "stage_loot.json"
    if not f.exists():
        return {}
    ov = json.loads(f.read_text(encoding="utf-8")).get("site_overrides") or {}
    return {k: (v["stage"], v.get("add") or []) for k, v in ov.items()
            if isinstance(v, dict) and v.get("stage") and v.get("add")}


def site_table_id(site):
    stage, _ = site_overrides()[site]
    return "%s:chests/%s/legendary_%s" % (NS, stage, site)


def write_tables(out):
    n = 0
    docs = stage_doc()
    if docs:
        mc = Path(out) / "pack.mcmeta"
        mc.parent.mkdir(parents=True, exist_ok=True)
        mc.write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                           "Cobblers: staged chest loot (tools/loot_fix.py, data/stage_loot.json)"}},
                                 indent=2) + "\n", encoding="utf-8")
    for sid, st in docs.items():
        for kind, spec in (st.get("kinds") or {}).items():
            p = Path(out) / "data" / NS / "loot_table" / "chests" / sid / (kind + ".json")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(table_json(sid, st, kind, spec), indent=1) + "\n", encoding="utf-8")
            n += 1
    for site, (stage, add) in site_overrides().items():
        st = docs.get(stage)
        if not st or "legendary_site" not in (st.get("kinds") or {}):
            continue
        spec = dict(st["kinds"]["legendary_site"])
        spec["entries"] = list(spec.get("entries") or []) + list(add)
        p = Path(out) / "data" / NS / "loot_table" / "chests" / stage / ("legendary_%s.json" % site)
        p.write_text(json.dumps(table_json(stage, st, "legendary_site", spec), indent=1) + "\n", encoding="utf-8")
        n += 1
    return n


# ------------------------------------------------------------------------------------------------- reports and checks


def problems(recs):
    bad = []
    known = known_tables()
    seen = Counter(tuple(r["pos"]) for r in recs)
    for r in recs:
        t = r.get("new_table")
        if r["action"] == "skip_items":
            continue
        if not t or t == "minecraft:empty" or t not in known:
            bad.append("%s %s: new table %r is not an existing table" % (r["placement"], r["pos"], t))
    for k, n in seen.items():
        if n > 1:
            bad.append("position %s appears %d times" % (list(k), n))
    # the forbidden items must not be reachable from any table we hand out at a legendary site
    rx = re.compile(remap()["forbidden_in_instanced_loot"]["item_regex"])
    for t in sorted({r["new_table"] for r in recs if r["kind"] == "legendary_site" and r.get("new_table")}):
        body = table_text(t)
        if body is not None and rx.search(body):
            bad.append("table %s at a legendary site can hand out a gate item (%s)" % (t, rx.search(body).group(0)))
    return bad


def table_text(tid):
    """The JSON text of an existing table in the server's packs, or of one of ours; None when not found."""
    import glob
    import zipfile
    ns, rel = tid.split(":", 1)
    names = ["data/%s/loot_table/%s.json" % (ns, rel), "data/%s/loot_tables/%s.json" % (ns, rel)]
    if ns == NS and stage_doc():
        sid, kind = rel.split("/")[1:3]
        st = stage_doc().get(sid)
        if st and kind in (st.get("kinds") or {}):
            return json.dumps(table_json(sid, st, kind, st["kinds"][kind]))
    for path in sorted(glob.glob(SERVER_DIR + "/datapacks/*.zip")) + sorted(glob.glob(SERVER_DIR + "/mods/*.jar")) + \
            glob.glob(SERVER_DIR + "/versions/*/*.jar") + glob.glob(SERVER_DIR + "/*.jar"):
        try:
            with zipfile.ZipFile(path) as z:
                for n in names:
                    if n in z.namelist():
                        return z.read(n).decode("utf-8", "replace")
        except (zipfile.BadZipFile, OSError):
            continue
    return None


def summary(recs):
    c = lambda key: dict(sorted(Counter(r[key] for r in recs).items(), key=lambda kv: -kv[1]))
    return {"containers": len(recs), "templates": len({r["template"] for r in recs}),
            "placements": len({r["placement"] for r in recs}), "by_action": c("action"), "by_kind": c("kind"),
            "by_stage": c("stage"), "by_source": c("source"), "by_block": c("block"),
            "bad_old_tables": dict(Counter(r["old_table"] for r in recs if r["action"] in ("fix_missing", "fix_empty"))),
            "areas_64": len({(r["chunk"][0] // 4, r["chunk"][1] // 4) for r in recs if r["action"] not in ("keep", "skip_items")})}


def load_fixes():
    return json.loads(FIXES.read_text(encoding="utf-8"))


def write_commands(doc, out, area=4, guard=True):
    """Sections of area x area chunks: forceload add, the repairs, forceload remove. Returns (lines, containers)."""
    groups = defaultdict(list)
    for r in doc["containers"]:
        if fix_commands(r, guard):
            groups[(r["chunk"][0] // area, r["chunk"][1] // area)].append(r)
    lines, n = ["# Generated by tools/loot_fix.py commands from data/loot_fixes.json. Run one section at a time over RCON."], 0
    for (gx, gz), rs in sorted(groups.items()):
        x0, z0, x1, z1 = gx * area * 16, gz * area * 16, (gx + 1) * area * 16 - 1, (gz + 1) * area * 16 - 1
        lines += ["", "# area %d,%d: %d containers" % (gx, gz, len(rs)), "forceload add %d %d %d %d" % (x0, z0, x1, z1)]
        for r in sorted(rs, key=lambda q: tuple(q["pos"])):
            lines += fix_commands(r, guard)
            n += 1
        lines.append("forceload remove %d %d %d %d" % (x0, z0, x1, z1))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(groups), n


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    sub.add_parser("fixes")
    c = sub.add_parser("commands")
    c.add_argument("--out", default=str(ROOT / "build" / "loot_fix" / "loot_fix.rcon.txt"))
    c.add_argument("--area", type=int, default=4, help="chunks per side of a forceload section")
    c.add_argument("--no-guard", action="store_true")
    t = sub.add_parser("tables")
    t.add_argument("--out", default=str(ROOT / "build" / "datapacks" / "cobblers_loot"))
    sub.add_parser("check")
    a = p.parse_args(argv)
    if a.cmd in ("plan", "fixes"):
        recs, dropped, dups = harvest()
        print(json.dumps(summary(recs), indent=1))
        for name, why in SKIPPED:
            print("NOT HARVESTED: settlement %s: %s" % (name, why))
        print("excluded as data/rewards.json caches:", len(dropped), "| duplicate positions:", len(dups))
        bad = problems(recs)
        print("problems:", len(bad))
        for b in bad[:20]:
            print("  ", b)
        if a.cmd == "fixes":
            doc = {"schema": "cobblers.loot_fixes/1", "generated_by": "python tools/loot_fix.py fixes",
                   "stage_mode": "stage_loot" if stage_doc() else "placeholder (data/stage_loot.json absent)",
                   "counts": summary(recs), "legendary_items": legendary_items(),
                   "not_covered": __doc__.split("What it does NOT cover")[1].split("data/stage_loot.json")[0].strip(),
                   "containers": sorted(recs, key=lambda r: (r["chunk"], r["pos"]))}
            FIXES.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
            print("wrote", FIXES)
        return 1 if bad else 0
    if a.cmd == "commands":
        groups, n = write_commands(load_fixes(), a.out, a.area, not a.no_guard)
        print("%d containers in %d areas -> %s" % (n, groups, a.out))
        return 0
    if a.cmd == "tables":
        n = write_tables(a.out)
        print("%d tables -> %s%s" % (n, a.out, "" if n else " (data/stage_loot.json absent: nothing to write)"))
        return 0
    bad = problems(load_fixes()["containers"])
    print("check: %d problems" % len(bad))
    for b in bad[:30]:
        print("  ", b)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
