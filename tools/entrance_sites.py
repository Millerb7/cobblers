#!/usr/bin/env python
"""The six caves and mines as the player site shows them (docs/player/region-map.html: a map layer and the "Caves and
mines" section): where each entrance is, how deep it goes, which town to ask, whether a trail leads to it.

Every figure is read, none typed:
  entrances   data/cave_systems.json `mouths` and data/mine_networks.json `adits` (x, z); the surface y is
              tools/ground.py's rounded heightmap ground at that column
  depth       a cave system: data/cave_systems.json rules.levels (the four levels' y); a mine: the first level's floor
              is the ground at its first adit and each deeper level is data/mine_networks.json geometry.level_gap lower
              (docs/world-building/MINE_NETWORKS.md: the Old Craters Drift 101 down to -11 is 101 - 16 x 7)
  towns       data/entrance_trails.json: `trails` name the town (or route) a trail starts from, `guides` the town whose
              resident marks an entrance; names from data/towns.json display_name
  levels      the wild levels of the encounter areas the entrances stand in, passed in by the map generator (its
              areas: the same tables the page lists)

What this does NOT say, on purpose (tests/test_player_site_leaks.py): the guides' names or seats, their dialogue, or any
quest id: they are in the story files, which the public site must not repeat. It does not say what lives underground:
no underground spawn table is authored for these places in the data this reads.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def levels_at(areas, x, z):
    """(low, high, [area names]) of the land and route areas whose boxes hold (x, z); None when none does. `areas` are
    the map generator's model areas: {kind, name, boxes: [[x0, x1, z0, z1], ...], rows: [{lv: [lo, hi]}]}."""
    lo, hi, names = None, None, []
    for a in areas:
        if a["kind"] not in ("land", "route") or not a["rows"]:
            continue
        if any(b[0] <= x <= b[1] and b[2] <= z <= b[3] for b in a["boxes"]):
            lo = min([v for v in [lo] if v is not None] + [r["lv"][0] for r in a["rows"]])
            hi = max([v for v in [hi] if v is not None] + [r["lv"][1] for r in a["rows"]])
            names.append(a["name"])
    return (lo, hi, names) if lo is not None else None


def sites(ground, areas=None):
    """[{id, name, kind, entrances: [{id, x, y, z}], depth, town, trail, guide, levels}] for the six systems, in the
    order data/entrance_trails.json lists them (caves west to east by file, then mines)."""
    caves = _load("cave_systems.json")
    mines = _load("mine_networks.json")
    et = _load("entrance_trails.json")
    towns = {t["id"]: t for t in _load("towns.json")["towns"]}
    signs = _load("signposts.json")
    routes = signs["route_labels"]
    tname = lambda tid: towns[tid].get("display_name") or signs["names"].get(tid) or tid
    out = []
    for s in caves["systems"]:
        lv = caves["rules"]["levels"]
        ys = ", ".join("y%d" % l["y"] for l in lv[:-1]) + " and y%d" % lv[-1]["y"]
        out.append({"id": s["id"], "name": s["name"], "kind": "cave",
                    "entrances": [{"id": m["id"], "x": m["x"], "z": m["z"], "y": ground(m["x"], m["z"])} for m in s["mouths"]],
                    "depth": "%d levels, about %s" % (len(lv), ys)})
    gap = mines["geometry"]["level_gap"]
    for n in mines["networks"]:
        ent = [{"id": a["id"], "x": a["portal"][0], "z": a["portal"][1], "y": ground(a["portal"][0], a["portal"][1])} for a in n["adits"]]
        top = ent[0]["y"]
        out.append({"id": n["id"], "name": n["name"], "kind": "mine", "entrances": ent,
                    "depth": "%d levels, floors from y%d down to y%d" % (n["levels"], top, top - gap * (n["levels"] - 1))})
    for s in out:
        s["trails"] = []
        for t in et["trails"]:
            if t["system"] == s["id"]:
                start = tname(t["from_town"]) if t.get("from_town") else routes[t["from_route"]]
                s["trails"].append({"from": start, "to": t["to"], "from_route": bool(t.get("from_route"))})
        g = next((g for g in et["guides"] if g["system"] == s["id"]), None)
        s["guide_town"] = tname(g["town"]) if g else None
        s["guide_to"] = g["goes_to"] if g else None
        if areas is not None:
            got = [levels_at(areas, e["x"], e["z"]) for e in s["entrances"]]
            got = [g_ for g_ in got if g_]
            s["levels"] = (min(g_[0] for g_ in got), max(g_[1] for g_ in got)) if got else None
        else:
            s["levels"] = None
    return out
