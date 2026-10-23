#!/usr/bin/env python
"""Nest rooms (the owner, 2026-10-22: "I would also like some random room to be added where we have habitat blocks spawning a
nest or something"): the Habitat Block and pool records for the rooms tools/cave_systems.py and tools/mine_networks.py site
off a side branch of their passages. This module holds only what the two share; each generator sites and carves its own
rooms and records their geometry in its own data file (data/cave_systems.json systems[].nest_rooms, data/mine_networks.json
networks[].nest_rooms).

  the block   ONE activated Habitat Block per room, in the floor cell under the room's middle, placed by the existing
              machinery: a record in data/habitat_blocks.json, written into the world by tools/habitat_blocks.py at step
              R9E, AFTER the carve steps R9CS and R9MN (tools/reapply.py lists them in that order). Activated, so the
              setblock carries the whole block entity after the mimic is set first (docs/STATE.md, "Never switch a placed
              Habitat Block's style with data merge"); nothing here ever writes `data merge` or `data modify` to a
              Habitat Block, and nothing reads one back by force-loading its chunk (the 2026-10-20 crash: a force-loaded
              Habitat Block with no player ticking it, its spawner uninitialised). Verify only from a stopped world copy.
  the pool    data/spawns.json habitats[] plus its flat entries[], in the shape tools/caves.py pool_records writes
              (mechanism habitat_block, scope = the pool id). Levels: the band of the sub-region the room is in
              (data/regions.json polygons, data/spawns.json subregions), staged by data/spawns.json evolution_policy: a
              stage spawns from the level it evolves at (or the band's floor) to four past its next LEVEL evolution (or
              the band's top), and not at all if that range is empty; the final stage takes (tier - 3) / 6 of the family's
              weight, held to [0.2, 0.9]. Evolutions that are not by level alone are not walked (conservative: no stage
              reached by an item, a trade, friendship or a biome is spawned). Species come from a Cobblemon jar
              (tools/battle_sim.py load_pack): a family root the jar does not have fails closed.

What this does NOT cover: whether an activated block inside a sealed underground room fills only that room (HB-1 in
docs/mechanics/LEGENDARY_HOMES.md is unmeasured); spawn positions inside the room in a running game; the levels
Cobbleverse may rescale. Nothing here touches a world.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HABITATS = ROOT / "data" / "habitat_blocks.json"
SPAWNS = ROOT / "data" / "spawns.json"
REGIONS = ROOT / "data" / "regions.json"

ACTIVATED = {"chance": 1.0, "trigger": "TICK", "max_spawns_per_activation": 2, "max_spawns": 5}


class NestError(Exception):
    pass


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(p, doc):
    Path(p).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def block_id(room_id):
    return room_id + "_block"


def pool_id(room_id):
    return room_id + "_pool"


def stone_for(y):
    return "minecraft:deepslate" if y < 0 else "minecraft:stone"


# ------------------------------------------------------------------ where a room is: its sub-region's band

def point_in_polygon(x, z, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x0, z0 = poly[i]
        x1, z1 = poly[(i + 1) % n]
        if (z0 > z) != (z1 > z):
            if x < x0 + (z - z0) * (x1 - x0) / (z1 - z0):
                inside = not inside
    return inside


def band_of(x, z, spawns=None, regions=None):
    """(sub-region id, band min, band max, tier) of a point, or (None, None, None, None)."""
    regs = (regions or jload(REGIONS))["subregions"]
    bands = {s["id"]: s for s in (spawns or jload(SPAWNS))["subregions"]}
    for r in regs:
        if r["id"] in bands and any(point_in_polygon(x, z, poly) for poly in r["polygons"]):
            b = bands[r["id"]]["level_band"]
            return r["id"], int(b["minimum"]), int(b["maximum"]), b.get("tier")
    return None, None, None, None


# ------------------------------------------------------------------ the pool: stages from the jar

def load_species(jar):
    import battle_sim
    sp, _, _ = battle_sim.load_pack(jar)
    return sp


def _key(name):
    import battle_sim
    return battle_sim.key(name)


def stages(species, root, band):
    """[(species key, lo, hi, why)] for a family root inside band (lo, hi), walking LEVEL-only evolutions forward."""
    k = _key(root)
    if k not in species:
        raise NestError("%s is not a species in the jar" % root)
    chain = [(k, None)]
    seen = {k}
    while True:
        cur = chain[-1][0]
        nxt = None
        for ev in species[cur].get("evolutions") or []:
            req = ev.get("requirements") or []
            if ev.get("variant") == "level_up" and len(req) == 1 and req[0].get("variant") == "level" and req[0].get("minLevel"):
                r = _key((ev.get("result") or "").split()[0])
                if r in species and r not in seen:
                    nxt = (r, int(req[0]["minLevel"]))
                    break
        if not nxt:
            break
        chain.append(nxt)
        seen.add(nxt[0])
    out = []
    for i, (sp, at) in enumerate(chain):
        nl = chain[i + 1][1] if i + 1 < len(chain) else None
        lo = max(band[0], at or 1)
        hi = band[1] if nl is None else min(band[1], nl + 4)
        if lo > hi:
            continue
        why = []
        why.append("evolves from %s at %d" % (chain[i - 1][0], at) if at else "the family's first stage")
        why.append("evolves at %d (spawns to four past it)" % nl if nl else "no further level evolution")
        out.append((sp, lo, hi, "; ".join(why) + " (Cobblemon jar species data, data/spawns.json evolution_policy)"))
    return out


def pool_records(room, theme, species, spawns=None, regions=None):
    """(habitat pool record, [flat entry]) for one room."""
    x, y, z = room["block"]
    sub, bmin, bmax, tier = band_of(x, z, spawns, regions)
    if sub is None:
        raise NestError("%s: the room at (%d, %d) is in no sub-region with a level band" % (room["id"], x, z))
    pid = pool_id(room["id"])
    f_final = min(0.9, max(0.2, ((tier or 0) - 3) / 6.0))
    rec_entries, flat = [], []
    for fam in theme["families"]:
        st = stages(species, fam["root"], (bmin, bmax))
        if not st:
            continue
        shares = [1.0] if len(st) == 1 else [(1 - f_final) / (len(st) - 1)] * (len(st) - 1) + [f_final]
        for (sp, lo, hi, why), share in zip(st, shares):
            lvl = "%d-%d" % (lo, hi) if lo != hi else "%d" % lo
            w = round(fam["weight"] * share, 2)
            name = (species[sp].get("name") or sp)
            rec_entries.append({"species": name, "pokemon": sp, "family": _key(fam["root"]), "family_priority": fam["bucket"],
                                "ambient": True, "eligibility_reason": why, "level": lvl, "bucket": fam["bucket"],
                                "weight": w, "conditions": {}})
            flat.append({"id": "habitat.%s.%s" % (pid, sp), "species": sp, "bucket": fam["bucket"], "level": lvl, "weight": w,
                         "ambient": True, "scope": pid, "mechanism": "habitat_block", "conditions": {},
                         "eligibility_reason": why, "spawnable_position": "grounded"})
    if not rec_entries:
        raise NestError("%s: no family of theme %s has a stage in %d-%d" % (room["id"], theme["theme"], bmin, bmax))
    lo = min(int(e["level"].split("-")[0]) for e in rec_entries)
    hi = max(int(e["level"].split("-")[-1]) for e in rec_entries)
    hab = {"id": pid, "display_name": theme["name"],
           "intended_location": "%s at x%d z%d (%s): one activated Habitat Block, %s in data/habitat_blocks.json, in the floor of a "
                                "nest room %s across off a side branch" % (room["place"], x, z, room["owner_file"], block_id(room["id"]),
                                                                           room["across"]),
           "mechanism": "habitat_block", "replace_spawns": False, "level_band": {"minimum": lo, "maximum": hi},
           "level_band_why": "the band of %s (%d-%d, tier %s), the sub-region the room is in (data/regions.json polygons, data/spawns.json "
                             "subregions), staged by data/spawns.json evolution_policy" % (sub, bmin, bmax, tier),
           "why": theme["why"], "entries": rec_entries,
           "placement_status": "authored: data/habitat_blocks.json %s, status planned (%s)" % (block_id(room["id"]), room["generated_by"])}
    return hab, flat


def habitat_record(room):
    x, y, z = room["block"]
    act = dict(ACTIVATED, spawn_range=int(room["spawn_range"]), cancel_range=int(room["cancel_range"]))
    return {"id": block_id(room["id"]), "place": "%s (%s): the floor cell under the middle of the nest room %s" % (room["place"], room["owner_file"], room["id"]),
            "pool": "cobblers:%s" % pool_id(room["id"]), "style": "activated", "replace_spawns": False,
            "position": {"x": int(x), "y": int(y), "z": int(z)}, "mimic": stone_for(int(y)),
            "activated": {k: act[k] for k in ("spawn_range", "chance", "trigger", "cancel_range", "max_spawns_per_activation", "max_spawns")},
            "status": "planned", "generated_by": room["generated_by"],
            "why": "A nest room (the owner, 2026-10-22: 'some random room ... where we have habitat blocks spawning a nest'): one ACTIVATED "
                   "block in the floor under the room's middle keeps up to %d of the theme alive, %d refilled at a time, TICK at chance 1. "
                   "spawn_range %d keeps the spawner's box inside the room (the generator and its audit check that no other carved cell "
                   "is in it); cancel_range %d cancels the pack's natural spawns in the room and not in the passage the spur leaves. The "
                   "mimic is the rock the floor is (deepslate under y0). Carved by %s, which runs BEFORE R9E; never data-merged or "
                   "read back by force-loading (docs/STATE.md, the 2026-10-20 crash)."
                   % (act["max_spawns"], act["max_spawns_per_activation"], act["spawn_range"], act["cancel_range"], room["step"])}


# ------------------------------------------------------------------ writing and checking the records

def sync(rooms, themes, species, prefix):
    """Write every room's block record and pool (replacing the records whose ids start with `prefix`, keeping all others)."""
    hb = jload(HABITATS)
    hb["blocks"] = [b for b in hb["blocks"] if not str(b.get("id", "")).startswith(prefix)] + [habitat_record(r) for r in rooms]
    sp = jload(SPAWNS)
    habs, ents = [], []
    regions = jload(REGIONS)
    for r in rooms:
        h, e = pool_records(r, themes[r["theme"]], species, sp, regions)
        habs.append(h)
        ents += e
    sp["habitats"] = [h for h in sp["habitats"] if not str(h.get("id", "")).startswith(prefix)] + habs
    sp["entries"] = [e for e in sp["entries"] if not str(e.get("scope", "")).startswith(prefix)] + ents
    dump(HABITATS, hb)
    dump(SPAWNS, sp)
    return habs, ents


def record_problems(rooms, prefix):
    """The records the rooms imply must be in data/ as written (a moved room or a hand edit is drift: fail closed)."""
    out = []
    blocks = {b["id"]: b for b in jload(HABITATS)["blocks"]}
    want_ids = {block_id(r["id"]) for r in rooms}
    for r in rooms:
        want = habitat_record(r)
        got = blocks.get(want["id"])
        if got is None:
            out.append("data/habitat_blocks.json lacks %s" % want["id"])
        elif got != want:
            out.append("data/habitat_blocks.json %s differs from the room's geometry" % want["id"])
    for bid in blocks:
        if bid.startswith(prefix) and bid not in want_ids:
            out.append("data/habitat_blocks.json carries %s, which no recorded room has" % bid)
    habs = {h["id"]: h for h in jload(SPAWNS)["habitats"]}
    for r in rooms:
        h = habs.get(pool_id(r["id"]))
        if h is None:
            out.append("data/spawns.json habitats lacks %s" % pool_id(r["id"]))
        elif not h.get("entries"):
            out.append("data/spawns.json habitats %s has no entries" % pool_id(r["id"]))
    return out
