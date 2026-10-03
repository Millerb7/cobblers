#!/usr/bin/env python
"""Shrew Station, audited offline: the emitted pack replayed block by block against the plan, re-derived.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). audit() never imports tools/research_station.py or
tools/water_mask.py; main() calls the generator's placement_steps() only to obtain the step list, which is one of the
outputs being checked (tools/lopunny_house_audit.py's arrangement). It reads data/research_station.json, the canonical heightmap (tools/ground.py), the sea's
level in data/world.json and every lake's basin and level in data/landmarks.json (with its own point-in-polygon test: a
column a lake holds is not the sea's), data/habitat_blocks.json, data/spawns.json,
data/rewards.json, data/quests.json, data/dialogue.json, data/spawn_blocks.json and data/spawn_block_policy.json,
derives what it expects with its own arithmetic, then REPLAYS the generated build functions into a block model and
compares. The only things taken from the generator are its outputs (the pack, and the re-application steps it hands
tools/reapply.py), which are what is being checked. Mutating the generator (a deck a block high, a lantern left out,
an altar turned, a post cut short, the switch tag added while held, an earning advancement shipped while held) fails
a named check here with the data untouched; tests/test_research_station.py does exactly that.

What is checked, each from the data and the heightmap, never from the pack:

  site       the water's level (data/world.json for the sea, data/landmarks.json for a lake) is the record's level_y;
             the shrine's centre is over shrine.min_depth or more; every land building's ground is at least
             rules.land_above_level over the water's level
  depth      every walk column is the site's water at least its kind's min_depth deep, or (a landfall kind) dry ground
             exactly at the deck's level; every land building stands on dry columns (own polygon test)
  footprint  no write lands outside the walks, the buildings (and their roof lip and door steps), the plaza, the
             signs and the mast; nothing is written into the water but a deck at the level, a post, or the
             hydrophone's waterlogged hatch; nothing below ground but the plaza's paving and a landfall deck
  decks      every walk column has a solid deck at the level, except the dive opening, where nothing is written; a
             post stands under every wet corner from the bed to the deck; a railed deck's open edges are railed
  seat       a land building's floor is max(ground under it) + 1 and solid, with foundation down to the ground; a deck
             building's floor is the level; walls, roof and the door as recorded; the door opens onto a standing place
  shrine     the Latias and Latios altars, facing as recorded, and the anchor, on a solid dais at level + 1 with air over
             them; the altar blocks are the ones the record names (LumyMon's, VERIFIED in the jar)
  blocks     every written block is in blocks.ids; none is a spawn condition unless a policy entry scoped to
             research_station allows it; no chest, no bed, and no water written
  light      block light flooded from every replayed lantern (15, one less a step, through air, water and what does
             not stop light) reaches every standing place on the decks, the plaza, the dais and the buildings' floors
             at min_light or more
  clear      every clear box starts above the water's surface (a #replaceable fill at the surface would take water)
  npc        each station NPC's data/rewards.json npc_grant and data/quests.json npc_at is the spot derived here, with
             two blocks of air and a floor under it, and one npc_grant per quest
  habitat    data/habitat_blocks.json station_study_pool: activated, its pool the record's, at the middle of the post
             derived here (ground + 1 .. level - 1), which the replay writes and R9E replaces; its spawn box holds at
             least max_spawns columns of water; the pool is study_pool.species alone, at levels inside the band
             study_pool.band_from names in data/spawns.json (a marine band or a sub-region), the pool record's
             level_band is that band, the species is already in that band's roster, and it spawns in water
  hold       THE SWITCH. The tick function removes the issuing tags while economy.issuing is false and adds them only
             when it is true (the crown's only with post_champion_cap >= 70, the Eon dews' only with eon_issuing
             true as well); no earning advancement and no `give` is shipped while held; every station transition
             that gives an item or runs a function, and every option that runs one, requires the issuing tag, in the
             data AND in the compiled dialogue; a transition or compiled option that gives a held item checks EVERY
             tag that holds it (HELD_BY: the crown its own, the dews the one switch and their own); no other quest
             gives an altar item
  steps      the re-application holds each zone's written chunks, runs its build, releases; each function passes
             tools/function_limits.py

NOT checked, and it needs a running server (data/research_station.json probes): that the fills land, that the altars
render and answer, that the study pool's Horsea spawn, that the NPCs render, that the tick function removes a tag added by hand.

  python tools/research_station_audit.py [--pack build/datapacks/cobblers_research_station] [--source-root R]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / "cobblers_research_station"
FN_DIR = "data/cobblers/function/research_station"
ZONES = ("strand", "crossing", "platform", "study_pool")
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace (\S+))?$")
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S.*?)(?: replace)?$")
FORCELOAD = re.compile(r"^forceload (add|remove) (-?\d+) (-?\d+) (-?\d+) (-?\d+)$")
SIDES = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}
# what light and a body pass through (doors and trapdoors are their own case for a body)
LIGHT_THROUGH = {"minecraft:air", "minecraft:glass", "minecraft:glass_pane", "minecraft:spruce_fence", "minecraft:lantern",
                 "minecraft:chain", "minecraft:spruce_sign", "minecraft:red_banner", "minecraft:blue_banner",
                 "minecraft:cyan_wall_banner", "minecraft:light_gray_carpet", "minecraft:cyan_carpet",
                 "minecraft:red_carpet", "minecraft:spruce_door", "minecraft:spruce_trapdoor", "minecraft:ladder"}
WALK_THROUGH = {"minecraft:air", "minecraft:light_gray_carpet", "minecraft:cyan_carpet", "minecraft:red_carpet",
                "minecraft:spruce_door", "minecraft:spruce_sign", "minecraft:chain"}
ALTAR_ITEMS = {"lumymon:thunder_feather", "lumymon:glacier_feather", "lumymon:ember_feather", "lumymon:calyrex_crown",
               "lumymon:ruby_dew", "lumymon:sapphire_dew", "lumymon:origin_fossil"}
QUESTS = ("evt_station_director", "evt_station_courier", "evt_station_archive", "evt_station_eon_shrine")
# Which switch tags (economy.tags keys) hold each item, stated here and not read from the generator: the feathers sit
# behind the one switch; the crown behind its own tag (added only with post_champion_cap >= 70); the Eon dews behind
# BOTH the one switch and their own (economy.eon_issuing), because the owner's decision of 2026-10-02 names the three
# feathers only and throwing the one switch must not issue the dews.
HELD_BY = {"lumymon:thunder_feather": ("issuing",), "lumymon:ember_feather": ("issuing",),
           "lumymon:glacier_feather": ("issuing",), "lumymon:calyrex_crown": ("issuing_crown",),
           "lumymon:ruby_dew": ("issuing", "issuing_eon"), "lumymon:sapphire_dew": ("issuing", "issuing_eon")}


class Report:
    def __init__(self):
        self.errors, self.notes = [], []

    def err(self, check, msg):
        self.errors.append("%s: %s" % (check, msg))


def base(state):
    return state.split("[")[0].split("{")[0]


def prop(state, key):
    m = re.search(r"[\[,]%s=([a-z0-9_]+)" % key, state)
    return m.group(1) if m else None


def load_json(name, root=DATA):
    return json.loads((root / name).read_text(encoding="utf-8"))


def in_rect(x, z, r):
    return r[0] <= x <= r[2] and r[1] <= z <= r[3]


def cells(r):
    return [(x, z) for x in range(r[0], r[2] + 1) for z in range(r[1], r[3] + 1)]


# ------------------------------------------------------------------------------------------------ the water, re-derived
def _in_poly(x, z, poly):
    """Even-odd ray cast on the column's centre; written here, not taken from tools/water_mask.py."""
    px, pz = x + 0.5, z + 0.5
    inside = False
    n = len(poly)
    for i in range(n):
        (x1, z1), (x2, z2) = poly[i], poly[(i + 1) % n]
        if (z1 > pz) != (z2 > pz):
            xi = x1 + (pz - z1) * (x2 - x1) / (z2 - z1)
            if px < xi:
                inside = not inside
    return inside


class Water:
    """The site's water (site.water: "sea" or a lake's landmark id), read from data/world.json and data/landmarks.json
    with this file's own polygon test. The sea is water where the ground is under vertical.sea_level and no lake basin
    holds the column (a lake's water there is the lake's, not the sea's); a lake is water where the ground is under its
    level_y inside its basin_polygons."""

    def __init__(self, rec, g, data=DATA):
        self.body = rec["site"]["water"]
        self.lakes = []
        for l in load_json("landmarks.json", data)["landmarks"]:
            wb = l.get("water_body") or {}
            if wb.get("level_y") is None or not wb.get("basin_polygons"):
                continue
            pts = [q for ring in wb["basin_polygons"] for q in ring]
            box = (min(q[0] for q in pts), min(q[1] for q in pts), max(q[0] for q in pts), max(q[1] for q in pts))
            self.lakes.append((l["id"], int(wb["level_y"]), wb["basin_polygons"], box))
        if self.body == "sea":
            self.level = int(load_json("world.json", data)["vertical"]["sea_level"])
            self.polys = None
        else:
            hit = [k for k in self.lakes if k[0] == self.body]
            if not hit:
                raise SystemExit("data/landmarks.json has no water body %s" % self.body)
            self.level, self.polys = hit[0][1], hit[0][2]
        self.g = g
        self._cache = {}

    def _in_lake(self, x, z, h):
        return any(h < lv and b[0] <= x <= b[2] and b[1] <= z <= b[3] and any(_in_poly(x, z, p) for p in polys)
                   for _lid, lv, polys, b in self.lakes)

    def depth(self, x, z):
        k = (x, z)
        if k not in self._cache:
            h = self.g(x, z)
            if self.polys is None:
                wet = h < self.level and not self._in_lake(x, z, h)
            else:
                wet = h < self.level and any(_in_poly(x, z, p) for p in self.polys)
            self._cache[k] = (self.level - h) if wet else None
        return self._cache[k]


# ------------------------------------------------------------------------------------------------ the replay
class Replay:
    def __init__(self):
        self.blocks, self.zone_of, self.clears, self.order = {}, {}, [], {}
        self.n = 0

    def run(self, zone, lines, rep):
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("forceload"):
                continue
            m = FILL.match(line)
            if m:
                x0, y0, z0, x1, y1, z1 = (int(v) for v in m.groups()[:6])
                st, tag = m.group(7), m.group(8)
                if tag:
                    self.clears.append((zone, (x0, y0, z0, x1, y1, z1), tag))
                    continue
                for x in range(min(x0, x1), max(x0, x1) + 1):
                    for y in range(min(y0, y1), max(y0, y1) + 1):
                        for z in range(min(z0, z1), max(z0, z1) + 1):
                            self._set((x, y, z), st, zone)
                continue
            m = SETBLOCK.match(line)
            if m:
                self._set((int(m.group(1)), int(m.group(2)), int(m.group(3))), m.group(4), zone)
                continue
            rep.err("replay", "%s: a command the replay does not model: %s" % (zone, line[:80]))

    def _set(self, k, st, zone):
        self.blocks[k] = st
        self.zone_of[k] = zone
        self.n += 1
        self.order[k] = self.n


class Expect:
    """What the data and the heightmap say, derived here."""

    def __init__(self, rec, g, lake):
        self.rec, self.g, self.lake = rec, g, lake
        self.L = lake.level
        self.walks = {w["id"]: w for w in rec["walks"]}
        self.walk_of = {}
        for w in rec["walks"]:
            for c in cells(w["rect"]):
                self.walk_of[c] = w["id"]
        d = rec["dive"]
        (cx, cz), n = d["at"], d["half"]
        self.hole = {(x, z) for x in range(cx - n, cx + n + 1) for z in range(cz - n, cz + n + 1)}
        self.buildings = {b["id"]: b for b in rec["buildings"]}
        self.floor = {}
        for b in rec["buildings"]:
            if b["on"] == "deck":
                self.floor[b["id"]] = self.L
            else:
                self.floor[b["id"]] = max(g(x, z) for x, z in cells(b["rect"])) + 1
        self.under_deck_buildings = {c for b in rec["buildings"] if b["on"] == "deck" for c in cells(b["rect"])}
        self.land_rects = [b["rect"] for b in rec["buildings"] if b["on"] == "land"]

    def door(self, b):
        x0, z0, x1, z1 = b["rect"]
        side, at = b["door"]["side"], b["door"]["at"]
        if side in ("north", "south"):
            return (at, z0 if side == "north" else z1)
        return (x0 if side == "west" else x1, at)

    def npc_spot(self, n):
        x, z = n["at"]
        if n["in"] in self.floor:
            return (x, self.floor[n["in"]] + 1, z)
        return (x, self.L + 1, z)

    def habitat(self):
        x, z = self.rec["study_pool"]["habitat_post"]
        gy = self.g(x, z)
        return (x, gy + 1 + (self.L - gy - 1) // 2, z)


# ------------------------------------------------------------------------------------------------ checks
def check_site(R, rec, lake):
    if lake.level != rec["site"]["level_y"]:
        R.err("site", "data/world.json or data/landmarks.json gives %s level y%d; the record says y%d"
              % (rec["site"]["water"], lake.level, rec["site"]["level_y"]))
    sh = rec["shrine"]["centre"]
    d = lake.depth(*sh)
    need = rec["shrine"]["min_depth"]
    if d is None or d < need:
        R.err("site", "the shrine's centre %s stands over %s of water; shrine.min_depth is %d" % (sh, d, need))
    above = rec["rules"]["land_above_level"]
    for b in rec["buildings"]:
        if b["on"] == "land":
            low = [c for c in cells(b["rect"]) if lake.g(*c) < lake.level + above]
            if low:
                R.err("site", "land building %s has ground under y%d (the water's level + rules.land_above_level) at %s"
                      % (b["id"], lake.level + above, low[:3]))


def check_depth(R, E):
    md = E.rec["rules"]["min_depth"]
    land = set(E.rec["rules"]["landfall_kinds"])
    for w in E.rec["walks"]:
        bad = []
        for x, z in cells(w["rect"]):
            d = E.lake.depth(x, z)
            if d is None:
                if w["kind"] not in land or E.g(x, z) != E.L:
                    bad.append((x, z, "dry y%d" % E.g(x, z)))
            elif d < md[w["kind"]]:
                bad.append((x, z, "%d deep" % d))
        if bad:
            R.err("depth", "walk %s (%s, min %d): %d column(s) break the rule, e.g. %s" % (w["id"], w["kind"], md[w["kind"]], len(bad), bad[:3]))
    for b in E.rec["buildings"]:
        if b["on"] == "land":
            wet = [c for c in cells(b["rect"]) if E.lake.depth(*c) is not None]
            if wet:
                R.err("depth", "building %s stands in the water at %s" % (b["id"], wet[:3]))


def allowed_columns(E):
    cols = set(E.walk_of)
    for b in E.rec["buildings"]:
        x0, z0, x1, z1 = b["rect"]
        cols |= set(cells((x0 - 1, z0 - 1, x1 + 1, z1 + 1)))
        if b["on"] == "land":
            dx, dz = SIDES[b["door"]["side"]]
            ox, oz = E.door(b)
            cols |= {(ox + dx * k, oz + dz * k) for k in range(1, 6)}
    cols |= set(cells(E.rec["plaza"]["rect"]))
    cols |= {tuple(s["at"]) for s in E.rec["signs"]}
    return cols


def check_footprint(R, E, W):
    cols = allowed_columns(E)
    outside = [k for k in W.blocks if (k[0], k[2]) not in cols]
    if outside:
        R.err("footprint", "%d write(s) outside the station's columns, e.g. %s" % (len(outside), outside[:3]))
    pr = E.rec["plaza"]["rect"]
    into_lake, below = [], []
    for (x, y, z), st in W.blocks.items():
        d = E.lake.depth(x, z)
        gy = E.g(x, z)
        if d is not None and y <= E.L:
            post = base(st) == "minecraft:stripped_spruce_log" and prop(st, "axis") == "y" and gy < y < E.L
            deck = y == E.L and (x, z) in E.walk_of
            if not (post or deck):
                into_lake.append(((x, y, z), st[:40]))
        if d is None and y <= gy:
            paving = y == gy and in_rect(x, z, pr) and not any(in_rect(x, z, r) for r in E.land_rects)
            landfall = y == gy == E.L and (x, z) in E.walk_of
            if not (paving or landfall):
                below.append(((x, y, z), st[:40]))
    if into_lake:
        R.err("footprint", "%d write(s) into the water that are neither a deck at the level nor a post: %s" % (len(into_lake), into_lake[:3]))
    if below:
        R.err("footprint", "%d write(s) at or below the ground that are neither paving nor a landfall deck: %s" % (len(below), below[:3]))


def solid(st):
    """A block a body stands on and a wall is made of (glass counts; a fence, a pane or a sign does not)."""
    if st is None:
        return False
    return base(st) == "minecraft:glass" or base(st) not in LIGHT_THROUGH


def check_decks(R, E, W):
    missing, holed = [], []
    for (x, z), wid in E.walk_of.items():
        st = W.blocks.get((x, E.L, z))
        if (x, z) in E.hole:
            if any((x, y, z) in W.blocks for y in range(E.g(x, z) + 1, E.L + 1)):
                holed.append((x, z))
            continue
        if st is None or base(st) == "minecraft:air":
            missing.append((x, z, wid))
    if missing:
        R.err("decks", "%d walk column(s) with no deck at y%d, e.g. %s" % (len(missing), E.L, missing[:3]))
    if holed:
        R.err("decks", "the dive opening has writes in its water at %s" % holed[:3])
    # a post under every wet corner, from the bed to the deck
    short = []
    for w in E.rec["walks"]:
        x0, z0, x1, z1 = w["rect"]
        for x, z in ((x0, z0), (x0, z1), (x1, z0), (x1, z1)):
            if (x, z) in E.hole or E.lake.depth(x, z) is None:
                continue
            for y in range(E.g(x, z) + 1, E.L):
                st = W.blocks.get((x, y, z))
                if st is None or base(st) != "minecraft:stripped_spruce_log":
                    short.append((x, y, z, w["id"]))
                    break
    if short:
        R.err("decks", "%d corner post(s) do not reach from the bed to the deck, e.g. %s" % (len(short), short[:3]))
    # railed decks: every open edge railed
    others = set(E.walk_of)
    rects = [b["rect"] for b in E.rec["buildings"]]
    unrailed = []
    for w in E.rec["walks"]:
        if not w.get("rails"):
            continue
        x0, z0, x1, z1 = w["rect"]
        mine = set(cells(w["rect"]))
        for x, z in cells(w["rect"]):
            if (x, z) in E.hole or (x, z) in E.under_deck_buildings:
                continue
            for s, (dx, dz) in SIDES.items():
                n = (x + dx, z + dz)
                if n in mine:
                    continue
                if n in others or any(in_rect(n[0], n[1], r) for r in rects):
                    continue
                st = W.blocks.get((x, E.L + 1, z))
                if st is None or base(st) != "minecraft:spruce_fence":
                    unrailed.append((x, z, w["id"]))
                break
    if unrailed:
        R.err("decks", "%d open edge cell(s) of a railed deck have no rail, e.g. %s" % (len(unrailed), unrailed[:3]))


def check_seat(R, E, W):
    for b in E.rec["buildings"]:
        f = E.floor[b["id"]]
        x0, z0, x1, z1 = b["rect"]
        H = b["height"]
        bad = [c for c in cells(b["rect"]) if not solid(W.blocks.get((c[0], f, c[1])))
               and base(W.blocks.get((c[0], f, c[1])) or "") != "minecraft:spruce_trapdoor"]
        if bad:
            R.err("seat", "%s: the floor at y%d is not solid at %s" % (b["id"], f, bad[:3]))
        if b["on"] == "land":
            gap = [(x, y, z) for x, z in cells(b["rect"]) for y in range(E.g(x, z) + 1, f) if not solid(W.blocks.get((x, y, z)))]
            if gap:
                R.err("seat", "%s: the foundation has gaps under the floor at %s" % (b["id"], gap[:3]))
        roof = [c for c in cells(b["rect"]) if not solid(W.blocks.get((c[0], f + H + 1, c[1])))]
        if roof:
            R.err("seat", "%s: the roof at y%d is open at %s" % (b["id"], f + H + 1, roof[:3]))
        dx, dz = E.door(b)
        lo, up = W.blocks.get((dx, f + 1, dz)), W.blocks.get((dx, f + 2, dz))
        if not (lo and up and base(lo) == base(up) == "minecraft:spruce_door" and prop(lo, "half") == "lower" and prop(up, "half") == "upper"):
            R.err("seat", "%s: no door at (%d, %d, %d)" % (b["id"], dx, f + 1, dz))
        ring = [(x, z) for x, z in cells(b["rect"]) if (x in (x0, x1) or z in (z0, z1)) and (x, z) != (dx, dz)]
        holes = [(x, y, z) for x, z in ring for y in (f + 1, f + H) if not solid(W.blocks.get((x, y, z)))]
        if holes:
            R.err("seat", "%s: the wall is open at %s" % (b["id"], holes[:3]))


def check_shrine(R, E, W):
    s = E.rec["shrine"]
    L = E.L
    for key in ("latias", "latios"):
        a = s[key]
        x, z = a["at"]
        st = W.blocks.get((x, L + 2, z))
        if not st or base(st) != a["block"] or prop(st, "facing") != a["facing"]:
            R.err("shrine", "%s: expected %s[facing=%s] at (%d, %d, %d), found %s" % (key, a["block"], a["facing"], x, L + 2, z, st))
        if not solid(W.blocks.get((x, L + 1, z))):
            R.err("shrine", "%s's altar has no dais under it" % key)
        if W.blocks.get((x, L + 3, z), "minecraft:air") != "minecraft:air":
            R.err("shrine", "%s's altar is covered" % key)
    an = s["anchor"]
    x, z = an["at"]
    if base(W.blocks.get((x, L + 2, z)) or "") != an["block"]:
        R.err("shrine", "no %s at (%d, %d, %d)" % (an["block"], x, L + 2, z))
    for y in (L + 3, L + 4):
        if W.blocks.get((x, y, z), "minecraft:air") != "minecraft:air":
            R.err("shrine", "the anchor has no room over it at y%d" % y)
    for key, item in (("latias", "lumymon:ruby_dew"), ("latios", "lumymon:sapphire_dew")):
        if s[key]["activation_item"] != item:
            R.err("shrine", "%s's activation item is %s; LumyMon's class names %s" % (key, s[key]["activation_item"], item))


def check_blocks(R, E, W, data=DATA):
    ids = set(E.rec["blocks"]["ids"])
    sb = set(load_json("spawn_blocks.json", data)["blocks"])
    pol = load_json("spawn_block_policy.json", data)["whitelist"]
    seen = {base(st) for st in W.blocks.values()}
    out = sorted(seen - ids)
    if out:
        R.err("blocks", "written blocks outside blocks.ids: %s" % out)
    cond = sorted(b for b in seen & sb if not any(b in w["blocks"] and "research_station" in (w.get("scope") or "") for w in pol))
    if cond:
        R.err("blocks", "written spawn conditions (data/spawn_blocks.json) no policy entry allows here: %s" % cond)
    for bad in ("minecraft:chest", "minecraft:water"):
        if bad in seen:
            R.err("blocks", "%s is written" % bad)
    if any(b.endswith("_bed") for b in seen):
        R.err("blocks", "a bed is written")
    wl = [k for k, st in W.blocks.items() if prop(st, "waterlogged") == "true"
          and not (E.lake.depth(k[0], k[2]) is not None and k[1] == E.L)]
    if wl:
        R.err("blocks", "waterlogged blocks out of the water's surface: %s" % wl[:3])


def check_light(R, E, W):
    lanterns = [k for k, st in W.blocks.items() if base(st) == "minecraft:lantern"]
    if not lanterns:
        R.err("light", "no lantern is written")
        return
    xs = [k[0] for k in W.blocks]
    zs = [k[2] for k in W.blocks]
    box = (min(xs) - 16, min(zs) - 16, max(xs) + 16, max(zs) + 16)

    def through(k):
        st = W.blocks.get(k)
        if st is not None:
            return base(st) in LIGHT_THROUGH
        x, y, z = k
        return y > E.g(x, z)

    dist = {k: 0 for k in lanterns}
    q = deque(lanterns)
    while q:
        k = q.popleft()
        d = dist[k]
        if d >= 15:
            continue
        x, y, z = k
        for n in ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1)):
            if n in dist or not (box[0] <= n[0] <= box[2] and box[1] <= n[2] <= box[3]) or not through(n):
                continue
            dist[n] = d + 1
            q.append(n)
    need = E.rec["rules"]["min_light"]

    def light(k):
        return 15 - dist[k] if k in dist else 0

    places = []
    for (x, z) in E.walk_of:
        if (x, z) not in E.hole and (x, z) not in E.under_deck_buildings:
            places.append((x, E.L + 1, z))
    pr = E.rec["plaza"]["rect"]
    for x, z in cells(pr):
        if E.lake.depth(x, z) is None and not any(in_rect(x, z, r) for r in E.land_rects):
            places.append((x, E.g(x, z) + 1, z))
    for b in E.rec["buildings"]:
        x0, z0, x1, z1 = b["rect"]
        for x, z in cells((x0 + 1, z0 + 1, x1 - 1, z1 - 1)):
            places.append((x, E.floor[b["id"]] + 1, z))
    cx, cz = E.rec["shrine"]["centre"]
    n = E.rec["shrine"]["dais_half"]
    places += [(x, E.L + 2, z) for x, z in cells((cx - n, cz - n, cx + n, cz + n))]
    dark = []
    for k in places:
        if W.blocks.get(k, "minecraft:air") != "minecraft:air":
            continue
        below = W.blocks.get((k[0], k[1] - 1, k[2]))
        if not solid(below):
            continue
        if light(k) < need:
            dark.append((k, light(k)))
    if dark:
        R.err("light", "%d standing place(s) below light %d, e.g. %s" % (len(dark), need, dark[:4]))
    R.notes.append("light: %d lanterns, %d standing places checked" % (len(lanterns), len(places)))


def check_clear(R, E, W):
    low = [c for c in W.clears if c[1][1] <= E.L or c[1][4] <= E.L]
    if low:
        R.err("clear", "%d clear box(es) reach the water's surface y%d: %s" % (len(low), E.L, low[:2]))
    for w in E.rec["walks"]:
        x0, z0, x1, z1 = w["rect"]
        if not any(t == "#minecraft:replaceable" and b[0] <= x0 and b[2] <= z0 and b[3] >= x1 and b[5] >= z1 and b[1] == E.L + 1
                   for _z, b, t in W.clears):
            R.err("clear", "walk %s is not cleared of plants from y%d" % (w["id"], E.L + 1))


def check_npcs(R, E, W, data=DATA):
    rw = load_json("rewards.json", data)["rewards"]
    qs = {q["id"]: q for q in load_json("quests.json", data)["quests"]}
    conv = {c["id"]: c for c in load_json("dialogue.json", data)["conversations"]}
    for n in E.rec["npcs"]:
        spot = E.npc_spot(n)
        c = conv.get(n["conversation"])
        if not c:
            R.err("npc", "%s: no conversation %s" % (n["id"], n["conversation"]))
            continue
        grants = [r for r in rw if r.get("kind") == "npc_grant" and r.get("quest") == c["quest_id"]]
        if len(grants) != 1:
            R.err("npc", "%s: %d npc_grant records for %s, not 1" % (n["id"], len(grants), c["quest_id"]))
            continue
        if tuple(grants[0]["npc_at"]) != spot:
            R.err("npc", "%s: data/rewards.json npc_at %s; derived here %s" % (n["id"], grants[0]["npc_at"], spot))
        q = qs.get(c["quest_id"])
        if q is None or tuple(q.get("npc_at") or ()) != spot:
            R.err("npc", "%s: data/quests.json npc_at %s; derived here %s" % (n["id"], q and q.get("npc_at"), spot))
        x, y, z = spot
        for yy in (y, y + 1):
            if W.blocks.get((x, yy, z), "minecraft:air") != "minecraft:air":
                R.err("npc", "%s's spot %s is not air at y%d: %s" % (n["id"], spot, yy, W.blocks[(x, yy, z)][:40]))
        if not solid(W.blocks.get((x, y - 1, z))):
            R.err("npc", "%s's spot %s has no floor" % (n["id"], spot))
        if n["in"] in E.buildings:
            reach_door(R, E, W, E.buildings[n["in"]], spot, n["id"])


def reach_door(R, E, W, b, spot, who):
    """A body (two blocks high) walks from outside the door to the NPC's side, through the door, inside the building."""
    f = E.floor[b["id"]]
    x0, z0, x1, z1 = b["rect"]
    dx, dz = SIDES[b["door"]["side"]]
    ox, oz = E.door(b)
    start = (ox + dx, oz + dz)

    def ok(x, z):
        return all(base(W.blocks.get((x, y, z), "minecraft:air")) in WALK_THROUGH for y in (f + 1, f + 2))
    if not ok(*start):
        R.err("npc", "%s: the door of %s opens onto a blocked place %s" % (who, b["id"], start))
        return
    seen, q = {start}, deque([start])
    while q:
        x, z = q.popleft()
        for ddx, ddz in SIDES.values():
            n = (x + ddx, z + ddz)
            if n in seen or not in_rect(n[0], n[1], (x0, z0, x1, z1)) or not ok(*n):
                continue
            seen.add(n)
            q.append(n)
    tx, _ty, tz = spot
    if not any(abs(tx - x) + abs(tz - z) == 1 for x, z in seen):
        R.err("npc", "%s cannot be reached from the door of %s" % (who, b["id"]))


def check_habitat(R, E, W, data=DATA):
    want = E.habitat()
    sp_rec = E.rec["study_pool"]
    hb = {b["id"]: b for b in load_json("habitat_blocks.json", data)["blocks"]}
    b = hb.get(sp_rec["habitat_block"])
    if not b:
        R.err("habitat", "data/habitat_blocks.json has no %s" % sp_rec["habitat_block"])
        return
    pos = (b["position"]["x"], b["position"]["y"], b["position"]["z"])
    if pos != want:
        R.err("habitat", "the block is at %s; the post's middle is %s" % (pos, want))
    if b.get("style") != "activated" or b.get("pool") != "cobblers:%s" % sp_rec["habitat_block"]:
        R.err("habitat", "the block is not the record's activated pool")
    st = W.blocks.get(want)
    if not st or base(st) != base(b.get("mimic") or ""):
        R.err("habitat", "the pack writes %s at %s, not the post the block mimics (%s)" % (st, want, b.get("mimic")))
    x, z = want[0], want[2]
    for y in range(E.g(x, z) + 1, E.L):
        s2 = W.blocks.get((x, y, z))
        if not s2 or base(s2) != "minecraft:stripped_spruce_log":
            R.err("habitat", "the post under the study deck is broken at y%d" % y)
            break
    a = b.get("activated") or {}
    r = a.get("spawn_range", 0)
    water = sum(1 for xx in range(x - r, x + r + 1) for zz in range(z - r, z + r + 1) if E.lake.depth(xx, zz))
    if water < a.get("max_spawns", 1):
        R.err("habitat", "the spawn box holds %d water columns, fewer than max_spawns" % water)
    sp = load_json("spawns.json", data)
    pool = next((h for h in sp["habitats"] if h["id"] == sp_rec["habitat_block"]), None)
    ents = [e for e in sp["entries"] if e.get("scope") == sp_rec["habitat_block"] and e.get("mechanism") == "habitat_block"]
    if not pool or {e["species"] for e in ents} != {sp_rec["species"]}:
        R.err("habitat", "the pool is not %s alone: %s" % (sp_rec["species"], sorted({e["species"] for e in ents})))
        return
    # the band the pool's water lies in, read from data/spawns.json (a land sub-region or a marine zone's band)
    src = sp_rec["band_from"]
    if "subregion" in src:
        band = next((s["level_band"] for s in sp["subregions"] if s["id"] == src["subregion"]), None)
    else:
        zone = next((m for m in sp.get("marine_zones") or [] if m["id"] == src["marine_zone"]), {})
        band = next((bd["level_band"] for bd in zone.get("bands") or [] if bd["id"] == src["band"]), None)
    if band is None:
        R.err("habitat", "data/spawns.json has no band %s" % src)
        return
    for e in ents:
        lo, hi = (int(v) for v in e["level"].split("-"))
        if lo < band["minimum"] or hi > band["maximum"]:
            R.err("habitat", "the pool's %s levels %d-%d are outside %s's band %d-%d"
                  % (e["species"], lo, hi, src, band["minimum"], band["maximum"]))
    if pool.get("level_band") != {"minimum": band["minimum"], "maximum": band["maximum"]}:
        R.err("habitat", "the pool record's level_band %s is not %s's %s" % (pool.get("level_band"), src, band))
    # the species must already live in that band, so the roster round the station is unchanged
    if "band" in src:
        here = {e["species"] for e in sp["entries"] if e.get("scope") == src["band"]}
    else:
        here = {e["species"] for e in sp["entries"] if e.get("scope") == src["subregion"]}
    if sp_rec["species"] not in here:
        R.err("habitat", "%s is not already in %s's roster: the study pool would add a species" % (sp_rec["species"], src))
    if any(e.get("spawnable_position") not in ("submerged", "surface") for e in ents):
        R.err("habitat", "a pool entry does not spawn in water: %s" % [(e["species"], e.get("spawnable_position")) for e in ents])


def _conds(c):
    out = [c]
    for k in ("conditions",):
        for x in c.get(k) or []:
            out += _conds(x)
    if c.get("condition"):
        out += _conds(c["condition"])
    return out


def _requires_tag(conds, tags):
    return any(c.get("kind") == "player_tag" and c.get("tag") in tags for c in conds)


def check_hold(R, E, pack, data=DATA):
    eco = E.rec["economy"]
    t = eco["tags"]
    issuing = bool(eco["issuing"])
    cap = eco.get("post_champion_cap")
    crown = issuing and isinstance(cap, int) and cap >= 70
    eon = issuing and eco.get("eon_issuing") is True
    tick = (pack / FN_DIR / "tick.mcfunction")
    lines = [l.strip() for l in tick.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")] if tick.is_file() else []
    for tag, on in ((t["issuing"], issuing), (t["issuing_crown"], crown), (t["issuing_eon"], eon)):
        add = "tag @a[tag=!%s] add %s" % (tag, tag)
        rem = "tag @a[tag=%s] remove %s" % (tag, tag)
        if on and add not in lines:
            R.err("hold", "the tick function does not add %s, and the record says it is issued" % tag)
        if not on and (rem not in lines or any((" add %s" % tag) in l for l in lines)):
            R.err("hold", "HELD, but the tick function does not remove %s (or adds it)" % tag)
    tagf = pack / "data/minecraft/tags/function/tick.json"
    if not tagf.is_file() or "cobblers:research_station/tick" not in json.loads(tagf.read_text(encoding="utf-8")).get("values", []):
        R.err("hold", "the tick function is not in #minecraft:tick")
    advs = sorted(pack.glob("data/*/advancement/**/*.json"))
    if not issuing and advs:
        R.err("hold", "HELD, but the pack ships %d advancement(s): %s" % (len(advs), [a.name for a in advs]))
    if issuing and len(advs) != 4:
        R.err("hold", "issuing, but the pack ships %d earning advancement(s), not 4" % len(advs))
    for f in pack.rglob("*.mcfunction"):
        text = f.read_text(encoding="utf-8")
        if not issuing and re.search(r"(^|\s)give\s", text, re.M):
            R.err("hold", "HELD, but %s gives an item" % f.name)
        for item in ALTAR_ITEMS:
            if item in text:
                R.err("hold", "%s names %s" % (f.name, item))
    co = pack / FN_DIR / "crown_offering.mcfunction"
    first = [l for l in co.read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")][:1] if co.is_file() else []
    if first != ["execute unless entity @s[tag=%s] run return 0" % t["issuing_crown"]]:
        R.err("hold", "crown_offering does not first return unless %s: %s" % (t["issuing_crown"], first))
    # the data: every station transition that gives or runs, and every option that runs one, requires the tag
    qs = {q["id"]: q for q in load_json("quests.json", data)["quests"]}
    tagset = {t["issuing"], t["issuing_crown"]}
    for qid in QUESTS:
        q = qs.get(qid)
        if not q:
            R.err("hold", "no quest %s" % qid)
            continue
        for tr in q["transitions"]:
            gives = [e for e in tr["effects"] if e["kind"] in ("grant_reward_once", "give_item", "function", "consume_held_item")]
            conds = [x for c in tr["conditions"] for x in _conds(c)]
            if gives and not _requires_tag(conds, tagset):
                R.err("hold", "%s.%s gives or takes without requiring %s" % (qid, tr["id"], sorted(tagset)))
            # per item: a transition that grants a held item requires EVERY tag that holds it (HELD_BY), so the crown
            # cannot ride the one switch alone and the dews cannot be issued with the feathers
            rewards = {r["id"]: [c["item"] for c in r.get("contents") or []] for r in q.get("rewards") or []}
            items = [e["item"] for e in tr["effects"] if e["kind"] == "give_item"]
            items += [i for e in tr["effects"] if e["kind"] == "grant_reward_once" for i in rewards.get(e["reward"], [])]
            have = {c.get("tag") for c in conds if c.get("kind") == "player_tag"}
            for item in items:
                for key in HELD_BY.get(item, ()):
                    if t[key] not in have:
                        R.err("hold", "%s.%s grants %s without requiring %s" % (qid, tr["id"], item, t[key]))
    for c in load_json("dialogue.json", data)["conversations"]:
        if c["quest_id"] not in QUESTS:
            continue
        q = qs[c["quest_id"]]
        trs = {tr["id"]: tr for tr in q["transitions"]}
        for nd in c["nodes"]:
            for r in nd.get("responses") or []:
                runs = [a["transition"] for a in r.get("actions") or [] if a["kind"] == "quest_transition"]
                if any(trs[x]["id"] != "start" for x in runs):
                    vis = _conds(r.get("visible_when") or {})
                    if not _requires_tag(vis, tagset | {t["harvest_paid"]}):
                        R.err("hold", "%s %s runs %s and is visible without the issuing tag" % (c["id"], r["id"], runs))
    # no other quest gives an altar item (data/adopted_legendary_sites.json a_dead_altar_must_not_block)
    for q in qs.values():
        if q["id"] in QUESTS:
            continue
        s = json.dumps(q)
        named = [i for i in ALTAR_ITEMS if i in s]
        if named:
            R.err("hold", "quest %s names %s" % (q["id"], named))
    # the compiled dialogue: every give of an altar item sits behind the tag, in the option and in its action
    try:
        import compile_dialogue as CD
        for c in load_json("dialogue.json", data)["conversations"]:
            if c["quest_id"] not in QUESTS:
                continue
            files = CD.build(c["id"], data)
            page_doc = files["data/cobblers/dialogues/%s.json" % c["id"]]
            if isinstance(page_doc, str):
                page_doc = json.loads(page_doc)
            for page in page_doc["pages"]:
                inp = page.get("input")
                if not isinstance(inp, dict):
                    continue
                for o in inp.get("options") or []:
                    act = o.get("action", "")
                    i = act.find("give @s ")
                    j = act.find("function cobblers:research_station/")
                    k = min(v for v in (i, j) if v >= 0) if (i >= 0 or j >= 0) else -1
                    if k < 0:
                        continue
                    if "has_tag('cobblers_station_issuing" not in act[:k]:
                        R.err("hold", "compiled %s %s gives before any issuing check" % (c["id"], o.get("value")))
                    if "has_tag('cobblers_station_issuing" not in o.get("isVisible", "") and "cobblers_station_harvest_paid" not in o.get("isVisible", ""):
                        R.err("hold", "compiled %s %s is visible without the issuing tag" % (c["id"], o.get("value")))
                    # per item, as in the data: every tag that holds a given item is checked before its give
                    for item, keys in HELD_BY.items():
                        g = act.find("give @s %s " % item)
                        if g < 0:
                            continue
                        for key in keys:
                            if "has_tag('%s')" % t[key] not in act[:g]:
                                R.err("hold", "compiled %s %s gives %s before checking %s"
                                      % (c["id"], o.get("value"), item, t[key]))
    except SystemExit as e:
        R.err("hold", "the station's conversations do not compile: %s" % e)


def check_steps(R, rec, W, pack, steps):
    import function_limits
    if steps is None:
        return
    want = []
    for zone in ZONES:
        want.append(zone)
    fns = [v for k, v in steps if k == "fn"]
    if fns != ["cobblers:research_station/build_%s" % z for z in ZONES]:
        R.err("steps", "the step runs %s, not the four zones in order" % fns)
    held = []
    for i, (k, v) in enumerate(steps):
        if k == "cmd" and v.startswith("forceload add"):
            held.append(tuple(int(t) for t in v.split()[2:6]))
    if len(held) != len(ZONES):
        R.err("steps", "the step holds %d boxes, not one per zone" % len(held))
        return
    for zone, (x0, z0, x1, z1) in zip(ZONES, held):
        out = [k for k, zn in W.zone_of.items() if zn == zone and not (x0 <= k[0] <= x1 and z0 <= k[2] <= z1)]
        if out:
            R.err("steps", "zone %s writes outside the chunks its step holds: %s" % (zone, out[:3]))
        f = pack / FN_DIR / ("build_%s.mcfunction" % zone)
        if f.is_file():
            bad = function_limits.check_lines(f.read_text(encoding="utf-8").splitlines(), f.name)
            if bad:
                R.err("steps", "%s: %s" % (f.name, bad[:2]))


def audit(rec, g, pack, steps=None, data=DATA):
    R = Report()
    pack = Path(pack)
    lake = Water(rec, g, data)
    E = Expect(rec, g, lake)
    W = Replay()
    for zone in ZONES:
        f = pack / FN_DIR / ("build_%s.mcfunction" % zone)
        if not f.is_file():
            R.err("replay", "no %s" % f)
            continue
        W.run(zone, f.read_text(encoding="utf-8").splitlines(), R)
    check_site(R, rec, lake)
    check_depth(R, E)
    check_footprint(R, E, W)
    check_decks(R, E, W)
    check_seat(R, E, W)
    check_shrine(R, E, W)
    check_blocks(R, E, W, data)
    check_light(R, E, W)
    check_clear(R, E, W)
    check_npcs(R, E, W, data)
    check_habitat(R, E, W, data)
    check_hold(R, E, pack, data)
    check_steps(R, rec, W, pack, steps)
    R.notes.append("replayed %d blocks in %d writes" % (len(W.blocks), W.n))
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--source-root")
    ap.add_argument("--no-steps", action="store_true", help="skip the re-application step check (it imports the generator's step builder)")
    a = ap.parse_args(argv)
    import ground as G
    rec = load_json("research_station.json")
    g = G.load(a.source_root)
    steps = None
    if not a.no_steps:
        import research_station as RS   # its OUTPUT (the step list) is what is checked, as tools/lopunny_house_audit.py does
        steps = RS.placement_steps(RS.load(), g)
    rep = audit(rec, g, a.pack, steps)
    for n in rep.notes:
        print("note: " + n)
    for e in rep.errors:
        print("PROBLEM " + e)
    print("research_station_audit: %d problem(s)" % len(rep.errors))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
