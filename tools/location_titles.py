#!/usr/bin/env python
"""Location titles: a title on screen when a player enters a region or a settlement. Regions and settlements only,
not sub-regions or routes.

How it works, in vanilla datapack terms (advancements and functions, no mod):

  in_<id>   an advancement with a `minecraft:location` trigger, true when the player is in the overworld inside
            any of the place's boxes. Its reward function shows the title and revokes out_<id>.
  out_<id>  true when the player is NOT inside the place's boxes grown by a margin. Its reward revokes in_<id>.

The location trigger is tested about once a second, and only for advancements the player does not yet have, so a
player inside a place costs nothing until they leave: entering grants in_ (the title shows once), leaving grants
out_ and re-arms in_. The margin is hysteresis: walking along a border does not re-title at every step. Neither
advancement has a display, so no toast and nothing in the advancement screen.

  regions      data/regions.json land regions (21), their polygons rasterised to boxes on a 32-block grid
               (tools/subregion_boxes.py); title = the region's display_name
  settlements  every data/towns.json place that is not a landmark tree, and every data/placements.json settlement
               (the Route 1 mansion); its box is the settlement plan's footprint rect when it has one, else its
               towns.json footprint. The Displaced City's box is its cavern, from the cavern floor to its ceiling
               (derived/cavern/plan.json), so the summit over it is not "in" it. Title = the settlement's name,
               subtitle = the region it stands in
  names        tools/signposts.place_names(): data/towns.json display_name once set, else the working name in
               data/signposts.json. Signs and titles read the same list, so a real name lands on both

A region's title is not shown while the player is inside a settlement (predicate in_any_settlement): arriving in
Pallet at spawn shows "Pallet", not "Pallet Fields" over it.

  python tools/location_titles.py                 # writes build/datapacks/cobblers_titles, reports counts
  python tools/location_titles.py --check         # every titled place has a name and a box; exit 1 if not

Not verifiable without a player: the pack's loading is checked on a server (the log names any advancement it
rejects), the titles themselves need somebody to walk in.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
OUT = ROOT / "build" / "datapacks" / "cobblers_titles"
NS = "cobblers"
GRID = 32                  # region raster, blocks
MARGIN_REGION = 24         # leave a region only this far past its edge
MARGIN_SETTLEMENT = 16
TIMES = (10, 60, 20)       # fade in, stay, fade out, ticks


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def regions():
    """[{id, name, boxes}] for the land regions."""
    import subregion_boxes as SB
    out = []
    for r in load("regions.json")["regions"]:
        out.append({"id": r["id"], "name": r["display_name"], "polygons": r["polygons"],
                    "boxes": [(b[0], b[2], b[1], b[3]) for b in SB.boxes_for(r["polygons"], grid=GRID)]})
    return out


def region_of(x, z, regs):
    import subregion_boxes as SB
    for r in regs:
        if any(SB.point_in_polygon(x, z, poly) for poly in r["polygons"]):
            return r
    return None


def settlements(regs):
    """[{id, name, box (x0, z0, x1, z1), y (lo, hi) or None, region name or None}]."""
    import signposts
    names = signposts.place_names()
    towns = {t["id"]: t for t in load("towns.json")["towns"]}
    doc = load("placements.json")
    ids = [t for t, v in towns.items() if v.get("kind") != "landmark_tree"]
    ids += [s for s in doc["settlements"] if s not in towns]
    out = []
    for sid in ids:
        plan = (doc["settlements"].get(sid) or {}).get("plan") or {}
        rect = (plan.get("footprint") or {}).get("rect")
        if not rect:
            fp = towns.get(sid, {}).get("footprint") or {}
            rect = [fp.get("min_x"), fp.get("min_z"), fp.get("max_x"), fp.get("max_z")] if fp else None
        y = None
        if sid == "displaced_city":
            cp = json.loads((ROOT / "derived" / "cavern" / "plan.json").read_text(encoding="utf-8"))
            y = (cp["floor_y"]["min"] - 2, cp["ceiling_y"]["max"])
        cx, cz = ((rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0) if rect else (None, None)
        reg = region_of(cx, cz, regs) if rect else None
        if reg is None:                        # a centre on the coast, just off its region's polygon: towns.json says
            reg = next((r for r in regs if r["id"] == towns.get(sid, {}).get("region")), None)
        out.append({"id": sid, "name": names.get(sid), "box": tuple(rect) if rect else None, "y": y,
                    "region": reg["name"] if reg else None})
    return out


def _range(lo, hi):
    return {"min": lo, "max": hi}


def _inside(boxes, y=None, grow=0):
    """A loot condition: the player (this) inside any of the boxes, grown by `grow` blocks."""
    terms = []
    for x0, z0, x1, z1 in boxes:
        pos = {"x": _range(x0 - grow, x1 + 1 + grow), "z": _range(z0 - grow, z1 + 1 + grow)}
        if y:
            pos["y"] = _range(y[0] - (grow and 4), y[1] + (grow and 4))
        terms.append({"condition": "minecraft:entity_properties", "entity": "this",
                      "predicate": {"location": {"position": pos}}})
    return terms[0] if len(terms) == 1 else {"condition": "minecraft:any_of", "terms": terms}


OVERWORLD = {"condition": "minecraft:entity_properties", "entity": "this",
             "predicate": {"location": {"dimension": "minecraft:overworld"}}}


def advancement(player, reward):
    return {"criteria": {"here": {"trigger": "minecraft:location", "conditions": {"player": player}}},
            "rewards": {"function": reward}}


def text(s, **style):
    return json.dumps(dict({"text": s}, **style), ensure_ascii=False)


def build(out=OUT):
    regs = regions()
    sets = settlements(regs)
    missing = [s["id"] for s in sets if not s["name"] or not s["box"]]
    if missing:
        raise SystemExit("no name or no box for: %s (data/signposts.json names, data/towns.json)" % missing)
    if out.exists():
        shutil.rmtree(out)
    adv = out / "data" / NS / "advancement" / "titles"
    fn = out / "data" / NS / "function" / "titles"
    pred = out / "data" / NS / "predicate" / "titles"
    for d in (adv, fn, pred):
        d.mkdir(parents=True)
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                     "Cobblers: location titles for regions and settlements (tools/location_titles.py)"}}) + "\n",
                                     encoding="utf-8")

    def w(path, obj):
        path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    in_any = [_inside([s["box"]], s["y"]) for s in sets]
    w(pred / "in_any_settlement.json", {"condition": "minecraft:any_of", "terms": in_any})
    times = "title @s times %d %d %d" % TIMES
    for r in regs:
        key = "region_%s" % r["id"]
        w(adv / ("in_%s.json" % key), advancement([OVERWORLD, _inside(r["boxes"])], "%s:titles/enter_%s" % (NS, key)))
        w(adv / ("out_%s.json" % key), advancement([OVERWORLD, {"condition": "minecraft:inverted",
                                                                "term": _inside(r["boxes"], grow=MARGIN_REGION)}],
                                                   "%s:titles/leave_%s" % (NS, key)))
        show = "execute unless predicate %s:titles/in_any_settlement run " % NS
        (fn / ("enter_%s.mcfunction" % key)).write_text("\n".join([
            "# entering %s (tools/location_titles.py); no title over a settlement's own" % r["name"],
            "advancement revoke @s only %s:titles/out_%s" % (NS, key),
            show + times,
            show + "title @s subtitle " + text(""),
            show + "title @s title " + text(r["name"], color="gold")]) + "\n", encoding="utf-8")
        (fn / ("leave_%s.mcfunction" % key)).write_text(
            "advancement revoke @s only %s:titles/in_%s\n" % (NS, key), encoding="utf-8")
    for s in sets:
        key = "place_%s" % s["id"]
        w(adv / ("in_%s.json" % key), advancement([OVERWORLD, _inside([s["box"]], s["y"])], "%s:titles/enter_%s" % (NS, key)))
        w(adv / ("out_%s.json" % key), advancement([OVERWORLD, {"condition": "minecraft:inverted",
                                                                "term": _inside([s["box"]], s["y"], grow=MARGIN_SETTLEMENT)}],
                                                   "%s:titles/leave_%s" % (NS, key)))
        (fn / ("enter_%s.mcfunction" % key)).write_text("\n".join([
            "# entering %s (tools/location_titles.py)" % s["name"],
            "advancement revoke @s only %s:titles/out_%s" % (NS, key),
            times,
            "title @s subtitle " + text(s["region"] or "", color="gray"),
            "title @s title " + text(s["name"])]) + "\n", encoding="utf-8")
        (fn / ("leave_%s.mcfunction" % key)).write_text(
            "advancement revoke @s only %s:titles/in_%s\n" % (NS, key), encoding="utf-8")
    return regs, sets


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true", help="only check every titled place has a name and a box")
    a = p.parse_args(argv)
    if a.check:
        regs = regions()
        sets = settlements(regs)
        bad = [s["id"] for s in sets if not s["name"] or not s["box"]] + [r["id"] for r in regs if not r["name"] or not r["boxes"]]
        print("%d regions, %d settlements; %s" % (len(regs), len(sets), "missing: %s" % bad if bad else "all named and boxed"))
        return 1 if bad else 0
    regs, sets = build()
    print("wrote %s: %d regions (%d boxes), %d settlements" % (OUT, len(regs), sum(len(r["boxes"]) for r in regs), len(sets)))
    for s in sets:
        print("  %-22s %-22s in %s" % (s["id"], s["name"], s["region"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
