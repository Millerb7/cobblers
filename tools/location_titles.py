#!/usr/bin/env python
"""Location titles: a title on screen when a player enters a Nuzlocke catch zone or a settlement.

The owner, 2026-10-06: "make the location titles pop up in game so a player knows when they have entered a new one".
The zones are data/nuzlocke_zones.json (tools/nuzlocke_zones.py: one zone per distinct encounter table); before
2026-10-06 this pack titled the 21 land regions, which are not catch zones (a region holds two to five tables).

How it works, in vanilla datapack terms (advancements, functions, scoreboards; no mod):

  in_<key>   an advancement with a `minecraft:location` trigger, true when the player is in the overworld inside any
             of the place's boxes. Its reward function shows the title and revokes out_<key>.
  out_<key>  true when the player is NOT inside the place's boxes grown by a margin. Its reward revokes in_<key>.

The location trigger is tested once a second (every 20 player ticks), and only for advancements the player does not
hold, so a player inside a place costs nothing until they leave: entering grants in_ (the title shows once), leaving
grants out_ and re-arms in_. The margin is hysteresis: walking along a border does not re-title at every step. No
advancement has a display, so no toast and nothing in the advancement screen.

  zones        land: the sub-region's polygons on a 32-block raster (tools/subregion_boxes.py), the raster the spawn
               compile uses; sea: tools/compile_spawns.py marine_bands, the boxes the sea bands spawn in; waterway:
               tools/waterways.py boxes_by_segment; cave (Victory Road): a box of +-range_of_influence round every
               placed Habitat Block of the zone's pools, and only where the player cannot see the sky. A site zone (the
               Route 1 mansion) is titled by its settlement. Title = the zone's name, subtitle = its region.
  settlements  every data/towns.json place that is not a landmark tree, and every data/placements.json settlement;
               its box is the settlement plan's footprint rect when it has one, else its towns.json footprint. The
               Displaced City's box is its cavern, floor to ceiling (derived/cavern/plan.json). Title = the
               settlement's name (tools/signposts.place_names(), the list the signs read), subtitle = its region.

Five rules keep it from going quiet or spamming. "Hold" keeps in_ granted (no title until the player leaves);
"retry" revokes in_ again so the location check a second later asks once more:

  1. A land, sea or waterway title is not shown inside a settlement or a Victory Road cave (predicate in_enclosure):
     retry, so it shows on stepping out. Before 2026-10-06 the region's in_ was granted silently inside the settlement
     and HELD: a player who started in Pallet never saw "Pallet Fields" on leaving it.
  2. Cooldown (the gate function, game time, no tick): the title the screen last showed, shown under COOLDOWN ticks
     ago, is held; the one before it (A -> B -> A on a border) is retried, so it shows once the cooldown has run out
     if the player is still there. At most one title per place per COOLDOWN, and the screen is right in the end.
  3. Re-arm on joining: advancements persist in the player's file, so a player who logged out inside a place held its
     in_ forever and was never told where they were; and a title fired in the player's first second can land under
     the loading screen. REARM_DELAY ticks after every join (first join included) every in_ is revoked and the
     cooldown forgotten, so the place the player stands in titles once they can see it. Before that: retry.
  4. Leaving a place re-arms every place, so stepping out of a creek, a town or a zone's corner back into the zone
     around it titles that zone again (through the gate) instead of leaving the last, wrong, title on the screen.
  5. Hysteresis: a place is left only MARGIN blocks past its edge.

  python tools/location_titles.py                 # writes build/datapacks/cobblers_titles, reports counts
  python tools/location_titles.py --check         # every titled place has a name and a box; exit 1 if not

Not verifiable without a player: the pack's loading is checked on a server (the log names any advancement or
function it rejects), the titles themselves need somebody to walk in.
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
ZONES = ROOT / "data" / "nuzlocke_zones.json"
NS = "cobblers"
GRID = 32                  # land raster, blocks: compile_spawns.SUBREGION_GRID
MARGIN_ZONE = 8            # leave a zone only this far past its edge (the cooldown, not the margin, stops spam)
MARGIN_SETTLEMENT = 8
MARGIN_CAVE = 4
TIMES = (10, 60, 20)       # fade in, stay, fade out, ticks
COOLDOWN = 600             # ticks: one of the last two titles is not shown again sooner than this (30 s)
REARM_DELAY = 100          # ticks after a join before the current place is titled (5 s, past the loading screen)
SCORES = ("cob_t_seen", "cob_t_left", "cob_t_wait", "cob_t_id", "cob_t_l1", "cob_t_l2", "cob_t_t1", "cob_t_t2",
          "cob_t_now", "cob_t_d", "cob_t_ok")


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def regions():
    """[{id, name, polygons}] for the land regions: a settlement's subtitle."""
    return [{"id": r["id"], "name": r["display_name"], "polygons": r["polygons"]} for r in load("regions.json")["regions"]]


def region_of(x, z, regs):
    import subregion_boxes as SB
    for r in regs:
        if any(SB.point_in_polygon(x, z, poly) for poly in r["polygons"]):
            return r
    return None


def _xz(b):
    """(minX, maxX, minZ, maxZ) -> a title box (x0, z0, x1, z1, None, None)."""
    return (b[0], b[2], b[1], b[3], None, None)


def zones():
    """[{zone, kind, name, subtitle, boxes, sky}] for every titled zone of data/nuzlocke_zones.json; a box is
    (x0, z0, x1, z1, ylo, yhi) inclusive, y None for a full column. A site zone is left to its settlement."""
    import subregion_boxes as SB
    doc = json.loads(ZONES.read_text(encoding="utf-8"))
    subs = {s["id"]: s for s in load("regions.json")["subregions"]}
    ways = {w["id"]: w for w in load("waterways.json")["waterways"]}
    blocks = load("habitat_blocks.json")["blocks"]
    bands = None
    out = []
    for z in doc["zones"]:
        kind, sky = z["kind"], None
        if kind == "site":
            continue
        if kind == "land":
            boxes = [_xz(b) for b in SB.boxes_for(subs[z["zone"]]["polygons"], grid=GRID)]
        elif kind == "sea":
            if bands is None:
                bands = _marine_bands()
            boxes = [_xz(b) for b in bands.get(z["zone"], [])]
        elif kind == "waterway":
            import waterways as W
            import compile_spawns as CS
            w = ways[z["zone"]]
            boxes = [_xz(b) for _, _, bs in W.boxes_by_segment(w["polyline"], w["half_width"], CS.WATERWAY_GRID) for b in bs]
        elif kind == "cave":
            pools = {"cobblers:" + p for p in z["pools"]}
            boxes = []
            for b in blocks:
                if b["pool"] in pools and b.get("status") == "placed":
                    p, r = b["position"], int(b["range_of_influence"])
                    boxes.append((p["x"] - r, p["z"] - r, p["x"] + r, p["z"] + r, p["y"] - r, p["y"] + r))
            sky = False
        else:
            raise SystemExit("data/nuzlocke_zones.json: zone %s has unknown kind %r" % (z["zone"], kind))
        out.append({"zone": z["zone"], "kind": kind, "name": z["name"], "subtitle": z["subtitle"],
                    "boxes": sorted(boxes, key=lambda b: tuple(-1 << 30 if v is None else v for v in b)), "sky": sky})
    return out


def _marine_bands():
    """The sea bands' boxes exactly as tools/compile_spawns.py main() computes them for the spawn pack."""
    import compile_spawns as CS
    import waterways as W
    water = []
    for w in load("waterways.json")["waterways"]:
        for _, _, bs in W.boxes_by_segment(w["polyline"], w["half_width"], CS.WATERWAY_GRID):
            water.extend(bs)
    return CS.marine_bands(load("spawns.json"), load("regions.json"), load("routes.json"), water)


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


def _inside(boxes, grow=0, sky=None):
    """A loot condition: the player (this) inside any of the boxes (x0, z0, x1, z1, ylo, yhi), grown by `grow`."""
    terms = []
    for x0, z0, x1, z1, ylo, yhi in boxes:
        pos = {"x": _range(x0 - grow, x1 + 1 + grow), "z": _range(z0 - grow, z1 + 1 + grow)}
        if ylo is not None:
            pos["y"] = _range(ylo - grow, yhi + 1 + grow)
        loc = {"position": pos}
        if sky is not None:
            loc["can_see_sky"] = sky
        terms.append({"condition": "minecraft:entity_properties", "entity": "this", "predicate": {"location": loc}})
    return terms[0] if len(terms) == 1 else {"condition": "minecraft:any_of", "terms": terms}


def settlement_boxes(s):
    x0, z0, x1, z1 = s["box"]
    return [(x0, z0, x1, z1, s["y"][0], s["y"][1]) if s["y"] else (x0, z0, x1, z1, None, None)]


OVERWORLD = {"condition": "minecraft:entity_properties", "entity": "this",
             "predicate": {"location": {"dimension": "minecraft:overworld"}}}


def advancement(player, reward):
    return {"criteria": {"here": {"trigger": "minecraft:location", "conditions": {"player": player}}},
            "rewards": {"function": reward}}


def text(s, **style):
    return json.dumps(dict({"text": s}, **style), ensure_ascii=False)


def _show(n, key, title, subtitle, colour=None, sub_colour="gray"):
    """The lines that title the player through the cooldown gate, as place number n: cob_t_ok 1 shows, 0 holds
    (the screen already says this), 2 retries (in_ revoked, so the check a second later asks again)."""
    ok = "execute if score @s cob_t_ok matches 1 run "
    return ["scoreboard players set @s cob_t_id %d" % n,
            "function %s:titles/gate" % NS,
            "execute if score @s cob_t_ok matches 2 run return run advancement revoke @s only %s:titles/in_%s" % (NS, key),
            ok + "title @s times %d %d %d" % TIMES,
            ok + "title @s subtitle " + text(subtitle or "", color=sub_colour),
            ok + "title @s title " + (text(title, color=colour) if colour else text(title))]


def _leave(key):
    """Leaving a place re-arms every place (rule 5): the one the player is still in titles again, through the gate.
    Only on a real leave (in_ held): out_ also fires once for every place a joining player is outside."""
    return ["execute if entity @s[advancements={%s:titles/in_%s=true}] run function %s:titles/rearm_places" % (NS, key, NS),
            "advancement revoke @s only %s:titles/in_%s" % (NS, key)]


def build(out=OUT):
    regs = regions()
    sets = settlements(regs)
    zs = zones()
    missing = [s["id"] for s in sets if not s["name"] or not s["box"]] + [z["zone"] for z in zs if not z["name"] or not z["boxes"]]
    if missing:
        raise SystemExit("no name or no box for: %s (data/signposts.json names, data/towns.json, data/nuzlocke_zones.json)"
                         % missing)
    if out.exists():
        shutil.rmtree(out)
    adv = out / "data" / NS / "advancement" / "titles"
    fn = out / "data" / NS / "function" / "titles"
    pred = out / "data" / NS / "predicate" / "titles"
    tags = out / "data" / "minecraft" / "tags" / "function"
    for d in (adv, fn, pred, tags):
        d.mkdir(parents=True)
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                     "Cobblers: location titles for the Nuzlocke catch zones and settlements "
                                     "(tools/location_titles.py)"}}) + "\n", encoding="utf-8")

    def w(path, obj):
        path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    def f(name, lines):
        (fn / ("%s.mcfunction" % name)).write_text("\n".join(lines) + "\n", encoding="utf-8")

    caves = [b for z in zs if z["kind"] == "cave" for b in z["boxes"]]
    enclosure = [_inside(settlement_boxes(s)) for s in sets]
    if caves:
        enclosure.append(_inside(caves, sky=False))
    w(pred / "in_enclosure.json", {"condition": "minecraft:any_of", "terms": enclosure})

    keys = []
    n = 0
    for z in zs:
        n += 1
        key = "zone_%s" % z["zone"]
        keys.append(key)
        margin = MARGIN_CAVE if z["kind"] == "cave" else MARGIN_ZONE
        w(adv / ("in_%s.json" % key), advancement([OVERWORLD, _inside(z["boxes"], sky=z["sky"])], "%s:titles/enter_%s" % (NS, key)))
        w(adv / ("out_%s.json" % key), advancement([OVERWORLD, {"condition": "minecraft:inverted",
                                                                "term": _inside(z["boxes"], grow=margin)}],
                                                   "%s:titles/leave_%s" % (NS, key)))
        lines = ["# entering %s, a Nuzlocke catch zone (data/nuzlocke_zones.json, tools/location_titles.py)" % z["name"],
                 "advancement revoke @s only %s:titles/out_%s" % (NS, key)]
        if z["kind"] != "cave":
            # inside a settlement or a cave: no title, and armed again so it shows on stepping out
            lines.append("execute if predicate %s:titles/in_enclosure run return run advancement revoke @s only %s:titles/in_%s"
                         % (NS, NS, key))
        f("enter_" + key, lines + _show(n, key, z["name"], z["subtitle"], colour="gold"))
        f("leave_" + key, _leave(key))
    for s in sets:
        n += 1
        key = "place_%s" % s["id"]
        keys.append(key)
        w(adv / ("in_%s.json" % key), advancement([OVERWORLD, _inside(settlement_boxes(s))], "%s:titles/enter_%s" % (NS, key)))
        w(adv / ("out_%s.json" % key), advancement([OVERWORLD, {"condition": "minecraft:inverted",
                                                                "term": _inside(settlement_boxes(s), grow=MARGIN_SETTLEMENT)}],
                                                   "%s:titles/leave_%s" % (NS, key)))
        f("enter_" + key, ["# entering %s (tools/location_titles.py)" % s["name"],
                           "advancement revoke @s only %s:titles/out_%s" % (NS, key)] + _show(n, key, s["name"], s["region"]))
        f("leave_" + key, _leave(key))

    # the cooldown gate: cob_t_ok 1 when place cob_t_id may title now; remembers the last two shown (l1, l2) and when
    f("gate", ["# rule 2: not one of the last two titles again within %d ticks; rule 3: nothing before the re-arm" % COOLDOWN,
               "execute unless score @s cob_t_l1 matches -2147483648..2147483647 run function %s:titles/init" % NS,
               "execute store result score @s cob_t_now run time query gametime",
               # joining: nothing yet, ask again (the re-arm clears everything anyway)
               "execute if score @s cob_t_wait matches 1.. run return run scoreboard players set @s cob_t_ok 2",
               # the last title shown, recently: the screen already said it, hold
               "scoreboard players operation @s cob_t_d = @s cob_t_now",
               "scoreboard players operation @s cob_t_d -= @s cob_t_t1",
               "execute if score @s cob_t_id = @s cob_t_l1 if score @s cob_t_d matches ..%d run return run "
               "scoreboard players set @s cob_t_ok 0" % (COOLDOWN - 1),
               # the one before it, recently (A -> B -> A on a border): not now, but ask again until the cooldown ends
               "scoreboard players operation @s cob_t_d = @s cob_t_now",
               "scoreboard players operation @s cob_t_d -= @s cob_t_t2",
               "execute if score @s cob_t_id = @s cob_t_l2 if score @s cob_t_d matches ..%d run return run "
               "scoreboard players set @s cob_t_ok 2" % (COOLDOWN - 1),
               "scoreboard players set @s cob_t_ok 1",
               "execute unless score @s cob_t_id = @s cob_t_l1 run function %s:titles/shift" % NS,
               "scoreboard players operation @s cob_t_l1 = @s cob_t_id",
               "scoreboard players operation @s cob_t_t1 = @s cob_t_now"])
    f("shift", ["scoreboard players operation @s cob_t_l2 = @s cob_t_l1",
                "scoreboard players operation @s cob_t_t2 = @s cob_t_t1"])
    f("init", ["scoreboard players set @s cob_t_l1 0", "scoreboard players set @s cob_t_l2 0",
               "scoreboard players set @s cob_t_t1 -1000000", "scoreboard players set @s cob_t_t2 -1000000"])
    # rule 3: the re-arm after every join
    f("load", ["# tools/location_titles.py: the scores the titles keep per player"]
      + ["scoreboard objectives add %s %s" % (s, "minecraft.custom:minecraft.leave_game" if s == "cob_t_left" else "dummy")
         for s in SCORES])
    f("tick", ["# rule 3: a join (first ever, or back after leaving) starts the wait; the wait ends in a re-arm",
               "execute as @a unless score @s cob_t_seen matches 1 run function %s:titles/joined" % NS,
               "execute as @a[scores={cob_t_left=1..}] run function %s:titles/joined" % NS,
               "execute as @a[scores={cob_t_wait=1..}] run function %s:titles/wait" % NS])
    f("joined", ["scoreboard players set @s cob_t_seen 1", "scoreboard players set @s cob_t_left 0",
                 "scoreboard players set @s cob_t_wait 1"])
    f("wait", ["scoreboard players add @s cob_t_wait 1",
               "execute if score @s cob_t_wait matches %d.. run function %s:titles/rearm" % (REARM_DELAY, NS)])
    f("rearm", ["# after a join: the cooldown forgotten and every place re-armed, so the one the player stands in titles",
                "scoreboard players set @s cob_t_wait 0",
                "scoreboard players set @s cob_t_l1 0",
                "scoreboard players set @s cob_t_l2 0",
                "function %s:titles/rearm_places" % NS])
    f("rearm_places", ["# every place's in_ revoked: the location check a second later grants the ones the player is in"]
      + ["advancement revoke @s only %s:titles/in_%s" % (NS, k) for k in keys])
    w(tags / "load.json", {"values": ["%s:titles/load" % NS]})
    w(tags / "tick.json", {"values": ["%s:titles/tick" % NS]})
    return zs, sets


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true", help="only check every titled place has a name and a box")
    a = p.parse_args(argv)
    if a.check:
        sets = settlements(regions())
        zs = zones()
        bad = [s["id"] for s in sets if not s["name"] or not s["box"]] + [z["zone"] for z in zs if not z["name"] or not z["boxes"]]
        print("%d zones, %d settlements; %s" % (len(zs), len(sets), "missing: %s" % bad if bad else "all named and boxed"))
        return 1 if bad else 0
    zs, sets = build()
    by = {}
    for z in zs:
        by[z["kind"]] = by.get(z["kind"], 0) + 1
    print("wrote %s: %d zones %s (%d boxes), %d settlements" % (OUT, len(zs), by, sum(len(z["boxes"]) for z in zs), len(sets)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
