#!/usr/bin/env python
"""What a player actually meets, table by table, read from the COMPILED spawn pack -- never from data/spawns.json.

The owner, 2026-10-02, after playing: every lake is Magikarp, Goldeen and Barraskewda; Victory Road has Quagsire and
Excadrill; nothing escalates and exploring rewards nothing. This tool measures those complaints so a rebuild can be
judged against numbers rather than impressions.

What it reads, and why each source is independent of the authored intent:

  build/datapacks/cobblers_spawns   the pack tools/compile_spawns.py emits, byte-identical to the one installed on
                                    staging-2026-10-01 (checked 2026-10-02: 164 of 164 files). A route file's spawn
                                    id carries the sub-region the corridor box took the entry from, so the corridor
                                    and the wilderness of one sub-region are reported apart.
  data/habitat_blocks.json          which habitat pools a placed block actually serves (a pool no block uses is
                                    unreachable, however good its roster).
  derived/availability.json         tools/availability.py's placement of each pool on the gym sequence: the leg a
                                    player first meets it on (route N's corridor is leg N; Victory Road is leg 9).
  the Cobblemon 1.8.0 jar           evolution chains and base stats (tools/battle_sim.py find_jar/load_pack).

A table is split by CONTEXT, because a land spawn never competes with a water one: "land" is grounded, "water" is
surface, submerged and seafloor. Within a context the chance of one species is

    P(bucket) * weight / (sum of weights in that bucket and context)

with P(bucket) from Cobbleverse's best-spawner-config (common 88.5, uncommon 10, rare 1.2, ultra-rare 0.3),
renormalised over the buckets the context actually holds. That renormalisation is an ASSUMPTION about how Cobblemon
1.8.0 treats a bucket with no candidate at a position; it is what makes a table's shares sum to one. Biome, time and
depth conditions are reported, not modelled: a species limited to night or to one biome is over-counted by day or in
another biome.

Hearts (docs/mechanics/ENCOUNTER_DESIGN.md section 10) are reported as their own tables, kind "hearts": the base
roster plus the heart's own spawns, with the heart's area share (a summit's measured on tools/ground.py when the
heightmap is reachable), its Chebyshev gap to the nearest route box and the share of its spawn chance above the cap.
The cap is the table's tier's, read from data/encounter_design.json's tier ladder.

Measures per table: the stage of each species in its family (base, middle, final, or single), the probability-
weighted base-stat total, the share of the table that is an evolved form, and the share whose family the player
could not have met on an earlier leg (novelty).

  python tools/encounter_audit.py                         # summary to stdout
  python tools/encounter_audit.py --json derived/encounter_audit.json --md docs/research/ENCOUNTER_AUDIT.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
PACK = ROOT / "build" / "datapacks" / "cobblers_spawns"
AVAIL = ROOT / "derived" / "availability.json"
BUCKETS = {"common": 88.5, "uncommon": 10.0, "rare": 1.2, "ultra-rare": 0.3}
WATER = {"surface", "submerged", "seafloor"}
ROUTE_LEG = {"route_0%d" % n: n for n in range(1, 9)}

# This tool decides nowhere anything goes; it reads no world.
WORLD_READS = set()


def species_index(jar=None):
    """{species id: {"bst", "types", "stage", "stages", "family", "evolves_by"}} from the jar.

    stage counts from 1 along the longest pre-evolution chain; stages is the family's longest chain. A regional or
    alternate form ("sandshrew alolan") is looked up by its base species for the chain and by its form for stats.
    """
    import battle_sim
    species, _, _ = battle_sim.load_pack(jar or battle_sim.find_jar())
    pre = {}
    edges = defaultdict(list)
    for k, sp in species.items():
        for ev in sp.get("evolutions") or []:
            res = battle_sim.key((ev.get("result") or "").split()[0])
            if res in species and res != k:
                lv = next((r.get("minLevel") for r in ev.get("requirements") or [] if r.get("variant") == "level"), None)
                method = "level" if ev.get("variant") == "level_up" and lv is not None and len(ev.get("requirements") or []) == 1 else "other"
                edges[k].append((res, method, lv))
                pre.setdefault(res, k)

    def root(k):
        seen = set()
        while k in pre and k not in seen:
            seen.add(k)
            k = pre[k]
        return k

    def depth(k):
        d, seen = 1, set()
        while k in pre and k not in seen:
            seen.add(k)
            k, d = pre[k], d + 1
        return d

    def longest(k, seen=()):
        return 1 + max((longest(r, seen + (k,)) for r, _, _ in edges.get(k, []) if r not in seen), default=0)

    out = {}
    for k, sp in species.items():
        b = sp.get("baseStats") or {}
        r = root(k)
        out[k] = {"bst": sum(b.values()), "types": [t for t in (sp.get("primaryType"), sp.get("secondaryType")) if t],
                  "stage": depth(k), "stages": longest(r), "family": r,
                  "evolves_by": sorted({m for _, m, _ in edges.get(k, [])})}
        for f in sp.get("forms") or []:
            fb = f.get("baseStats")
            if fb:
                fk = k + battle_sim.key(f.get("name") or "")
                out.setdefault(fk, dict(out[k], bst=sum(fb.values())))
    return out


def lookup(idx, name):
    import battle_sim
    parts = name.split()
    regional = {"alolan": "alola", "galarian": "galar", "hisuian": "hisui", "paldean": "paldea"}
    if len(parts) > 1 and parts[1] in regional and battle_sim.key(parts[0] + regional[parts[1]]) in idx:
        return idx[battle_sim.key(parts[0] + regional[parts[1]])]
    k = battle_sim.key(name.replace(" ", ""))
    if k in idx:
        return idx[k]
    if parts and battle_sim.key(parts[0]) in idx:
        return idx[battle_sim.key(parts[0])]
    return None


def stage_label(info):
    if not info:
        return "unknown"
    if info["stages"] == 1:
        return "single"
    if info["stage"] == 1:
        return "base"
    return "final" if info["stage"] == info["stages"] else "middle"


def lvl(text):
    a, _, b = str(text).partition("-")
    return int(a), int(b or a)


def table(entries, idx):
    """[{species, context, p, bucket, lo, hi, stage, bst, conditions}] for one table, shares within each context."""
    by_ctx = defaultdict(lambda: defaultdict(dict))
    for e in entries:
        ctx = "water" if e["spawnablePositionType"] in WATER else "land"
        # keyed by species, level AND origin: inside a heart one species can come twice, the base roster's and the
        # heart's own, and both apply there, so they are never folded into one; everywhere else a species has one
        # level per table and the key is the species as before
        origin = "heart" if HEART_ID.search(e.get("id", "")) else ""
        rec = by_ctx[ctx][e["bucket"]].setdefault((e["pokemon"], str(e.get("level") or e.get("levelRange")), origin),
                                                  {"w": 0.0, "lo": 999, "hi": 0, "cond": set(), "n": 0})
        rec["w"] = max(rec["w"], float(e["weight"]))  # one box's weight: the same entry repeats per box
        lo, hi = lvl(e.get("level") or e.get("levelRange"))
        rec["lo"], rec["hi"] = min(rec["lo"], lo), max(rec["hi"], hi)
        c = e.get("condition") or {}
        for key in ("timeRange", "maxY", "minY", "neededNearbyBlocks", "biomes"):
            if c.get(key) is not None:
                rec["cond"].add("%s=%s" % (key, c[key] if key != "biomes" else ",".join(x.split(":")[-1] for x in c[key])))
        if e.get("timeRange"):
            rec["cond"].add("timeRange=%s" % e["timeRange"])
    rows = []
    for ctx, buckets in by_ctx.items():
        total_b = sum(BUCKETS.get(b, 0) for b in buckets)
        for b, sp in buckets.items():
            tw = sum(r["w"] for r in sp.values()) or 1
            for (name, _lvl, origin), r in sp.items():
                info = lookup(idx, name)
                rows.append({"species": name, "context": ctx, "bucket": b, "heart": bool(origin),
                             "p": round(BUCKETS.get(b, 0) / total_b * r["w"] / tw, 5) if total_b else 0,
                             "lo": r["lo"], "hi": r["hi"], "stage": stage_label(info),
                             "family": info["family"] if info else name, "bst": info["bst"] if info else None,
                             "conditions": sorted(r["cond"])})
    rows.sort(key=lambda r: (r["context"], -r["p"]))
    return rows


def above_cap(r, cap):
    """The share of a row's levels above the cap, every level in its range taken as equally likely (an assumption
    about Cobblemon 1.8.0's level draw)."""
    if cap is None:
        return 0.0
    return max(0, r["hi"] - max(r["lo"], cap + 1) + 1) / float(r["hi"] - r["lo"] + 1)


def measures(rows, earlier_families, cap=None):
    out = {}
    for ctx in ("land", "water"):
        rs = [r for r in rows if r["context"] == ctx]
        if not rs:
            continue
        p = sum(r["p"] for r in rs) or 1
        known = [r for r in rs if r["bst"]]
        pk = sum(r["p"] for r in known) or 1
        out[ctx] = {"species": len({r["species"] for r in rs}),
                    "above_cap_share": round(sum(r["p"] * above_cap(r, cap) for r in rs) / p, 4),
                    "top3_share": round(sum(sorted((r["p"] for r in rs), reverse=True)[:3]) / p, 3),
                    "evolved_share": round(sum(r["p"] for r in rs if r["stage"] in ("middle", "final")) / p, 3),
                    "final_or_single_share": round(sum(r["p"] for r in rs if r["stage"] in ("final", "single")) / p, 3),
                    "mean_bst": round(sum(r["p"] * r["bst"] for r in known) / pk),
                    "novel_share": round(sum(r["p"] for r in rs if r["family"] not in earlier_families) / p, 3),
                    "level": [min(r["lo"] for r in rs), max(r["hi"] for r in rs)]}
    return out


HEART_ID = re.compile(r"_h\d{4}_")


def load_pack(pack):
    """{(kind, id, subregion or None): [spawn details]}. A route detail is split by the sub-region in its id.

    A sub-region's heart (docs/mechanics/ENCOUNTER_DESIGN.md section 10; compiled ids <sub>_h<n>_<species>) is
    reported as its own table, kind "hearts": what a player meets INSIDE the heart, which is the sub-region's base
    roster there plus the heart's own spawns. The sub-region's own table is its base roster alone."""
    pools = defaultdict(list)
    base = pack / "data" / "cobblers"
    subs = sorted((p.stem for p in (base / "spawn_pool_world" / "subregions").glob("*.json")), key=len, reverse=True)
    regions = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    subs = sorted({s["id"] for s in regions["subregions"]} | set(subs), key=len, reverse=True)
    for f in sorted((base / "spawn_pool_world").rglob("*.json")):
        kind = f.parent.name
        heart = []
        for s in json.loads(f.read_text(encoding="utf-8"))["spawns"]:
            sub = None
            if kind == "routes":
                sub = next((x for x in subs if "_%s_" % x in s["id"]), "?")
            if kind == "subregions" and HEART_ID.search(s["id"]):
                heart.append(s)
                continue
            pools[(kind, f.stem, sub)].append(s)
        if heart:
            pools[("hearts", f.stem, None)] = pools[(kind, f.stem, None)] + heart
    for f in sorted((base / "habitat_pools").glob("*.json")):
        for s in json.loads(f.read_text(encoding="utf-8"))["spawns"]:
            pools[("habitat", f.stem, None)].append(dict(s, pokemon=s["species"]))
    return pools


def legs(avail, pools, blocks):
    """{(kind, id, sub): (leg, placement)} -- leg 1..8 for a gym's approach, 9 for Victory Road, None if unplaced."""
    first = {}
    for g, rows in sorted(avail["gyms"].items(), key=lambda t: int(t[0])):
        for r in rows:
            first.setdefault(r["pool"], (int(g), "near the path" if r.get("off_corridor") else "on the path"))
    placed = defaultdict(int)
    for b in blocks:
        if b.get("status") == "placed":
            placed[b["pool"].split(":")[-1]] += 1
    out = {}
    for key in pools:
        kind, pid, sub = key
        if kind == "routes":
            out[key] = (ROUTE_LEG.get(pid[:8], 9), "the corridor")
        elif pid in first:
            out[key] = first[pid]
        elif pid in avail.get("off_route", {}):
            nr = avail["off_route"][pid]["nearest_route"]
            out[key] = (ROUTE_LEG.get(nr[:8], 9), "off the path (%d blocks from %s)" % (avail["off_route"][pid]["gap"], nr))
        elif kind == "habitat":
            if pid.startswith("vrc_"):
                out[key] = (9, "Victory Road (%d blocks placed)" % placed[pid])
            else:
                out[key] = (None, "habitat, %d blocks placed" % placed[pid])
        elif kind == "marine":
            out[key] = (None, "open sea")
        else:
            out[key] = (None, "unplaced")
    return out, placed


def audit(pack=PACK, avail_path=AVAIL, jar=None, ground_fn=None):
    idx = species_index(jar)
    pools = load_pack(pack)
    avail = json.loads(Path(avail_path).read_text(encoding="utf-8"))
    blocks = json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]
    where, placed = legs(avail, pools, blocks)
    tables = {}
    for key, entries in pools.items():
        tables[key] = table(entries, idx)
    # families met by leg: a family on a leg-N table is known from leg N on
    met = defaultdict(set)
    for key, rows in tables.items():
        lg = where[key][0]
        if lg:
            met[lg] |= {r["family"] for r in rows}
    caps = tier_caps()
    geo = heart_geometry(pack, pools, ground_fn)
    out = []
    for key, rows in sorted(tables.items(), key=lambda t: (where[t[0]][0] or 99, t[0][0], t[0][1], t[0][2] or "")):
        lg, placement = where[key]
        earlier = set().union(*(met[g] for g in range(1, lg))) if lg else set()
        if key[0] == "habitat" and not placed.get(key[1]) and not key[1].startswith("vrc_"):
            placement = "habitat pool, no block placed"
        cap = caps["tables"].get(key[1]) if key[0] in ("subregions", "hearts") else (
            caps["leg"].get(lg) if key[0] in ("routes", "habitat") and lg else None)
        rec = {"kind": key[0], "pool": key[1], "subregion": key[2], "leg": lg, "placement": placement, "cap": cap,
               "measures": measures(rows, earlier, cap), "rows": rows}
        if key[0] == "hearts":
            rec["heart"] = geo.get(key[1])
        out.append(rec)
    return out


def tier_caps():
    """{"tables": {table id: cap}, "leg": {leg: cap}} from data/encounter_design.json's tier ladder (the cap a player
    carries on each leg, ENCOUNTER_DESIGN.md section 2). The one input this report takes from the design: a table's
    cap is its tier's, and an off-path tier is raised by the design with a written reason."""
    d = json.loads((ROOT / "data" / "encounter_design.json").read_text(encoding="utf-8"))
    tiers = {int(k): v["cap"] for k, v in d["rules"]["tiers"].items()}
    return {"tables": {k: tiers[t["tier"]] for k, t in d["tables"].items()}, "leg": tiers}


def heart_geometry(pack, pools, ground_fn=None):
    """{sub-region: {...}} for every heart, measured on the compiled boxes.

    area_share         heart columns over the sub-region's compiled columns. A focus heart's columns are its boxes;
                       a summit heart's are the columns of its boxes whose ground (tools/ground.py, the canonical
                       heightmap) is at or above its minY, and without the heightmap only the boxes are reported.
    min_gap_to_route   the smallest Chebyshev gap between a heart box and any route file's box: section 1 calls a
                       place within 128 blocks of a route "near the path", and the heart must keep out of that band.
    """
    route_boxes = []
    for (kind, _pid, _sub), spawns in pools.items():
        if kind == "routes":
            route_boxes += [(c["minX"], c["maxX"], c["minZ"], c["maxZ"]) for c in (s["condition"] for s in spawns) if "minX" in c]
    route_boxes = sorted(set(route_boxes))
    out = {}
    for (kind, pid, _sub), spawns in pools.items():
        if kind != "hearts":
            continue
        hb = sorted({(c["minX"], c["maxX"], c["minZ"], c["maxZ"]) for c in
                     (s["condition"] for s in spawns if HEART_ID.search(s.get("id", ""))) if "minX" in c})
        bb = sorted({(c["minX"], c["maxX"], c["minZ"], c["maxZ"]) for c in
                     (s["condition"] for s in spawns if not HEART_ID.search(s.get("id", ""))) if "minX" in c})
        miny = {s["condition"].get("minY") for s in spawns if HEART_ID.search(s.get("id", ""))} - {None}
        area = sum((b[1] - b[0] + 1) * (b[3] - b[2] + 1) for b in bb)
        harea = sum((b[1] - b[0] + 1) * (b[3] - b[2] + 1) for b in hb)
        rec = {"kind": "summit" if miny else "focus", "boxes": len(hb), "box_area": harea, "area": area,
               "min_gap_to_route": min((max(0, b[0] - r[1], r[0] - b[1], b[2] - r[3], r[2] - b[3])
                                        for b in hb for r in route_boxes), default=None)}
        if miny:
            rec["minY"] = min(miny)
            if ground_fn is not None:
                rec["columns_at_or_above"] = int(sum(int((ground_fn(b) >= rec["minY"]).sum()) for b in hb))
                rec["area_share"] = round(rec["columns_at_or_above"] / float(area), 4)
            else:
                rec["area_share"] = None
                rec["note"] = "no heightmap (COBBLERS_SOURCE_ROOT): the summit's share is not measured"
        else:
            rec["area_share"] = round(harea / float(area), 4)
        out[pid] = rec
    return out


def load_ground():
    """A box -> ground array function from tools/ground.py, or None when the heightmap is not reachable."""
    import ground
    import terrain
    try:
        g = ground.load()
    except terrain.TerrainUnavailable:  # no heightmap here: the report says the summit areas were not measured
        return None
    return lambda b: g.box(b[0], b[2], b[1], b[3])


def lake_overlap(tables):
    """Pairwise share of the water tables' probability that two lakes give to the same species."""
    water = {}
    for t in tables:
        if t["kind"] == "subregions":
            w = {r["species"]: r["p"] for r in t["rows"] if r["context"] == "water"}
            if w:
                s = sum(w.values())
                water[t["pool"]] = {k: v / s for k, v in w.items()}
    pairs = []
    names = sorted(water)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            pairs.append((round(sum(min(water[a].get(k, 0), water[b].get(k, 0)) for k in set(water[a]) | set(water[b])), 3), a, b))
    return water, sorted(pairs, reverse=True)


def leg_summary(tables):
    """Per leg, over the land tables a player meets on or near the path (the corridor and on/near sub-regions)."""
    out = {}
    for lg in range(1, 10):
        ts = [t for t in tables if t["leg"] == lg and "land" in t["measures"] and not t["placement"].startswith("off")
              and t["kind"] != "hearts"]
        if not ts:
            continue
        n = len(ts)
        out[lg] = {k: round(sum(t["measures"]["land"][k] for t in ts) / n, 3)
                   for k in ("evolved_share", "final_or_single_share", "mean_bst", "novel_share")}
        out[lg]["tables"] = n
    return out


def render(tables, overlap):
    water, pairs = overlap
    lines = ["# Encounter audit: what a player meets, per sub-region", "",
             "Generated by `tools/encounter_audit.py` from the compiled spawn pack. Shares are within a context (land",
             "or water); see the tool's docstring for the bucket assumption and what is not modelled.", ""]
    lines += ["## By leg (on or near the path, land tables, unweighted mean of tables)", "",
              "| Leg | Tables | Evolved share | Final/single share | Mean BST | Novel family share |", "|---|---|---|---|---|---|"]
    for lg, m in leg_summary(tables).items():
        lines.append("| %s | %d | %.2f | %.2f | %d | %.2f |" % (lg if lg < 9 else "VR", m["tables"], m["evolved_share"],
                                                            m["final_or_single_share"], m["mean_bst"], m["novel_share"]))
    hearts = [t for t in tables if t["kind"] == "hearts"]
    if hearts:
        lines += ["", "## Hearts (ENCOUNTER_DESIGN.md section 10): inside the heart, the base roster plus the heart's own", "",
                  "Area share is the heart's columns over the sub-region's compiled columns (a summit's: columns at or "
                  "above its minY, canonical heightmap). Gap is the nearest route box, Chebyshev. Above cap is the share "
                  "of the heart's spawn chance whose level is over the table's cap, levels in a range taken as equally "
                  "likely.", "",
                  "| Heart | Kind | Cap | Area share | Gap to route | Land above cap | Water above cap | Top level |",
                  "|---|---|---|---|---|---|---|---|"]
        for t in sorted(hearts, key=lambda t: (t["leg"] or 99, t["pool"])):
            g = t.get("heart") or {}
            m = t["measures"]
            lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                t["pool"], g.get("kind", "?") + (" y%s" % g["minY"] if g.get("minY") is not None else ""), t["cap"],
                "%.1f%%" % (100 * g["area_share"]) if g.get("area_share") is not None else "not measured",
                g.get("min_gap_to_route"),
                "%.1f%%" % (100 * m["land"]["above_cap_share"]) if "land" in m else "-",
                "%.1f%%" % (100 * m["water"]["above_cap_share"]) if "water" in m else "-",
                max(r["hi"] for r in t["rows"])))
    lines += ["", "## Lakes: the most alike water tables (share of probability on the same species)", "",
              "| Overlap | A | B |", "|---|---|---|"]
    lines += ["| %.2f | %s | %s |" % p for p in pairs[:15]]
    lines += ["", "## Every table", ""]
    for t in tables:
        name = t["pool"] + (" / " + t["subregion"] if t["subregion"] else "")
        lines += ["### %s (%s) -- leg %s, %s" % (name, t["kind"], t["leg"] if t["leg"] else "-", t["placement"]), ""]
        for ctx, m in t["measures"].items():
            lines.append("- **%s**: %d species, levels %d-%d, evolved %.2f, final/single %.2f, mean BST %d, novel %.2f, top 3 %.2f%s"
                         % (ctx, m["species"], m["level"][0], m["level"][1], m["evolved_share"], m["final_or_single_share"],
                            m["mean_bst"], m["novel_share"], m["top3_share"],
                            (", above cap %d: %.3f" % (t["cap"], m["above_cap_share"])) if t.get("cap") else ""))
        lines.append("")
        lines.append("| Context | Species | Chance | Bucket | Levels | Stage | BST | Conditions |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for r in t["rows"]:
            lines.append("| %s | %s | %.1f%% | %s | %d-%d | %s | %s | %s |" % (
                r["context"], r["species"] + (" (heart)" if r.get("heart") else ""), 100 * r["p"], r["bucket"], r["lo"], r["hi"], r["stage"], r["bst"] or "?",
                "; ".join(r["conditions"]).replace("|", "/")))
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--availability", default=str(AVAIL))
    ap.add_argument("--json")
    ap.add_argument("--md")
    a = ap.parse_args(argv)
    tables = audit(Path(a.pack), a.availability, ground_fn=load_ground())
    ov = lake_overlap(tables)
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps({"tables": tables, "legs": leg_summary(tables),
                                            "lake_overlap": ov[1]}, indent=1) + "\n", encoding="utf-8")
    if a.md:
        Path(a.md).write_text(render(tables, ov), encoding="utf-8", newline="\n")
    print("tables %d" % len(tables))
    for lg, m in leg_summary(tables).items():
        print("leg %s: %s" % (lg, m))
    print("most alike lakes:", ov[1][:5])
    for t in sorted((t for t in tables if t["kind"] == "hearts"), key=lambda t: (t["leg"] or 99, t["pool"])):
        g, m = t.get("heart") or {}, t["measures"]
        print("heart %s: %s, cap %s, area share %s, gap to route %s, above cap %s, top level %d" % (
            t["pool"], g.get("kind"), t["cap"], g.get("area_share"), g.get("min_gap_to_route"),
            {c: m[c]["above_cap_share"] for c in m}, max(r["hi"] for r in t["rows"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
