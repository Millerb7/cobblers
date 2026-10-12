#!/usr/bin/env python
"""Three optional dungeon rooms (unit RT-B, 2026-10-10): `fishing_room`, `egg_room`, `fossil_chamber`.

The owner's "Next phase" (docs/mechanics/DUNGEON_PASS2.md): more room types, to tell whole dungeons apart. Researched in
docs/research/notes/dungeon-room-mechanisms.md (sections 1-3); this module builds on its verdicts and says below which of
its ASSUMED items it still rests on. Rung: **datapack plus generator** (functions, loot tables, NPC classes and dialogues,
one spawn-pool file); the earlier rungs (Cobblemon native, addon, config) have no say over a room in a custom dimension,
and nothing here needed a scripting layer or a mod. Registered into the room kit (`dungeon_rooms.EXTENSION_MODULES`).

  kind `fishing_room`   params.pool_length (odd, 5..9, default 9), params.pool_width (3..9, 7), params.species (a key of
                        data/dungeon_extras2.json fishing.species; default the dungeon's theme)
  kind `egg_room`       params.offers (a dict like data eggs.offers) and params.clock_s_by_band override the data
  kind `fossil_chamber` params.fossils_by_band override the data's fossils.by_band

FISHING. A trench pool one deep (the walk check's wading depth), a pier, lantern posts, seagrass and sea pickles. The fish are
a boxed `spawn_pool_world` file (pack_files): `spawnablePositionType: fishing`, `dimensions: [cobblers:pocket]`, the dungeon's
four slot rows as minX..maxZ, and `neededNearbyBlocks: [<band marker>]`. A spawn entry cannot see the entrant's band and the
pool must differ by band, so three cells of the pool bed (under the pier, invisible) hold a marker block that the slot
reset sets from `dg.band`; each band's entries require their marker (a FishingSpawningCondition field, read from the jar).
A Habitat Block was the research's first choice and is not used: it is a block entity a command-placed shell activates only
after a chunk reload (EXP-021), its fishing influence is untested (data/spawn_suppression.json), and it cannot see the band
either. The wanted species (starters among them) stand in the `common` bucket (83% of rolls); every band has one species in
each bucket. A rod is lent (a marked Poke Rod, taken back wherever the rift pick is: `patch_functions`). A catch is weighed
as a nest catch (tools/dungeon_greed.py CATCH_ALIAS): GREED counts every catch in a live run, by the room the catcher
stands in.

EGGS. A non-battling NPC vendor (class and dialogue per slot and band, `pack_files`) stands behind a counter. Each offer's
button runs `take_b<band>_<k>` as the player: it refuses outside a live run, after the run's one egg, and when fewer than
`min_left_s` of the clock would remain; otherwise it charges the band's price in CLOCK SECONDS (data eggs.price.why: the
engine's own currency, the vault's), weighs the egg as a nest catch through greed/add, and runs
`givepokemonegg @s <species>` as the player (Cobbreeding 2.3.0 registers the literal with `player` and `properties`
arguments, read from the jar; the recipient is the executor). One per run: the holder `#s<g>r<i>e` is 0 at entry and the reset
and 1 once bought.

FOSSILS. No brushing (impossible in adventure mode; research section 3). A bay of dig blocks against the north wall; ONE
fossil block (calcite) hides in the middle layer at one of 8 spots rolled by `random value` at the first step in; the rift
pick may break the dig block and calcite exactly as it breaks a seam (`pick_blocks` gains them through PICK_EXTRA_FNS). The
mined stat of calcite is GREED's count (data/dungeon_greed.json blocks); the room's tick sees the cell turn to air and gives
the fossil from a per-band loot table (the 15 ids of cobblemon:fossils). Dust drifts in front of the face over the fossil.
Solid behind every breakable block: the bay is closed by a frame and a lintel of the theme's wall block, and the back layer
sits against the hull wall.

UNPROVEN IN GAME (experiments/EXP-089-dungeon-fish-egg-fossil): that a PokeBobber in one-deep water spawns from a spawn pool
whose entries carry a box, `dimensions` and `neededNearbyBlocks` together; that a spawn_pool_world file inside the dungeon
pack loads on a datapack reload and not only at boot; that `givepokemonegg` run as the player from a function gives an egg and
hatches it; that a non-battling NPC class with a dialogue interaction opens its dialogue in the pocket; that calcite mined
under can_break in adventure raises minecraft.mined and drops; the lent rod's use. The offline model is
tests/test_dungeon_extras2.py.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dungeon_grid as G  # noqa: E402
import dungeon_rooms as R  # noqa: E402
from dungeon_rooms import fill, setb  # noqa: E402

DATA_PATH = ROOT / "data" / "dungeon_extras2.json"
SCHEMA = "cobblers.dungeon_extras2/1"
LOADED = "# chunks-loaded-by: the member standing in the room (its chunks are loaded)"
NS = "cobblers"
KINDS = ("fishing_room", "egg_room", "fossil_chamber")
BUCKETS = ("common", "uncommon", "rare", "ultra-rare")
NPC_TAG = "dg.egg."                      # + the room slug: the vendor of that room (and the slot's own tag)
ROD_KEY = "cobblers_lent_rod"
SLUG = re.compile(r"[^a-z0-9_]")
SPECIES = re.compile(r"^[a-z0-9_]+$")
PRICE_MARGIN_S = 60


# ------------------------------------------------------------------------------------------------- data


_DATA = {}


def load(path=DATA_PATH):
    key = str(path)
    if key not in _DATA:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if doc.get("schema") != SCHEMA:
            raise R.RoomError("%s: schema must be %s" % (path, SCHEMA))
        _DATA[key] = doc
    return _DATA[key]


def bands_of(doc):
    return [b["band"] for b in doc["engine"]["bands"]]


def lower_cap(doc, band):
    return min(next(b for b in doc["engine"]["bands"] if b["band"] == band)["caps"])


def U(doc):
    """Clock units a second at x1 (a pass is period_ticks of them: tenth-ticks since unit GREED)."""
    return doc["engine"]["clock"]["units_per_tick"] * 20


def slug(room_id):
    return SLUG.sub("_", room_id.lower())


def dim_of(doc):
    return doc["engine"]["pocket"]["dimension"]


def level_range(doc, band):
    hi = lower_cap(doc, band)
    lo = max(5, hi - 10)
    return lo, hi


class Ctl:
    """What one built room needs to write its blocks and functions."""

    def __init__(self, doc, d, slot, room):
        self.doc, self.d, self.slot, self.room = doc, d, slot, room
        self.p = room["params"]
        self.H = R.state_holder(slot, room)
        self.dim = dim_of(doc)
        self.fy = room["floor_in"]
        self.g = slot["g"]
        self.lab = "%s room %s (%s)" % (d["id"], room["id"], room["kind"])

    def fn(self, name):
        return R.room_fn(self.d, self.room, self.slot, name)

    def holder(self, tag):
        return self.H + tag

    def inn(self, line):
        return "execute in %s run %s" % (self.dim, line)

    def fail(self, msg):
        raise R.RoomError("%s: %s" % (self.lab, msg))

    def theme_id(self):
        return self.d.get("theme")

    def safe(self, theme):
        return theme["safe"]


def at(pos):
    return "%d %d %d" % tuple(int(v) for v in pos)


def bar(msg, colour="gray"):
    return "title @s actionbar %s" % R.text(msg, colour)


def say(msg, colour="gray"):
    return "tellraw @s %s" % R.text(msg, colour)


def sound(name, vol=1, pitch=1):
    return "playsound %s master @s ~ ~ ~ %s %s" % (name, vol, pitch)


# ------------------------------------------------------------------------------------------------- the fishing room


def fishing_cfg():
    return load()["fishing"]


def lent_rod_item():
    r = fishing_cfg()["rod"]
    return ("%s[minecraft:custom_data={%s:1b},minecraft:item_name=%s]"
            % (r["id"], ROD_KEY, "'%s'" % R.text(r["name"], r["colour"])))


def lent_rod_match():
    return "%s[minecraft:custom_data~{%s:1b}]" % (fishing_cfg()["rod"]["id"], ROD_KEY)


def pool_species_key(room, d):
    return (room.get("params") or {}).get("species") or d.get("theme")


def fishing_geometry(c):
    """The pool, pier and post cells of a fishing room (x/z are absolute). Fails with a message when the room is too small."""
    r, p = c.room, c.p
    cfg = fishing_cfg()["pool"]
    L = int(p.get("pool_length", cfg["length"]))
    W = int(p.get("pool_width", cfg["width"]))
    if L % 2 == 0 or not 5 <= L <= 9:
        c.fail("params.pool_length must be odd, 5..9 (is %d): every bobber must be within 4 blocks of the centre marker" % L)
    if not 3 <= W <= 9:
        c.fail("params.pool_width must be 3..9 (is %d)" % W)
    ix0, ix1, iz0, iz1, fy = r["ix0"], r["ix1"], r["iz0"], r["iz1"], c.fy
    cx = (ix0 + ix1) // 2
    if cx - L // 2 < ix0 + 3 or cx + L // 2 > ix1 - 3:
        c.fail("the room is %d long: a %d-long pool needs 6 more" % (r["length"], L))
    if r["height"] < 5:
        c.fail("a fishing room needs a height of at least 5")
    line = (r["z_in"] + r["z_out"]) / 2.0
    zc = (iz0 + iz1) / 2.0
    side = "north" if line >= zc else "south"
    if side == "north":
        z0 = iz0 + 2
        z1 = z0 + W - 1
        edge = z1                                  # the pool's edge nearest the room's middle; the pier runs toward z0
        gap = min(r["z_in"], r["z_out"], line) - z1
        pier_z = [edge - k for k in range(5)]
    else:
        z1 = iz1 - 2
        z0 = z1 - W + 1
        edge = z0
        gap = z0 - max(r["z_in"], r["z_out"], line)
        pier_z = [edge + k for k in range(5)]
    if gap < 4:
        c.fail("the pool (z %d..%d, %s side) is %d from the doors' line; it needs 4: widen the room" % (z0, z1, side, gap))
    if abs(zc - (z1 if side == "north" else z0)) < 3:
        c.fail("the pool reaches the room's middle: widen the room")
    zm = (z0 + z1) // 2
    return {"cx": cx, "L": L, "W": W, "x0": cx - L // 2, "x1": cx + L // 2, "z0": z0, "z1": z1, "edge": edge, "side": side,
            "pier_z": pier_z, "zm": zm, "marker": [(cx - 2, zm), (cx, zm), (cx + 2, zm)]}


def kind_fishing(doc, d, slot, room, theme):
    c = Ctl(doc, d, slot, room)
    cfg = fishing_cfg()
    g = fishing_geometry(c)
    fy, cx = c.fy, g["cx"]
    safe = theme["safe"]
    theme_id = c.theme_id()
    bed = cfg["bed"].get(theme_id)
    if bed is None:
        c.fail("data/dungeon_extras2.json fishing.bed has no block for theme %r" % theme_id)
    markers = {int(k): v for k, v in cfg["markers"].items() if k.isdigit()}
    bands = bands_of(doc)
    for b in bands:
        if b not in markers:
            c.fail("fishing.markers has no block for band %d" % b)
    x0, x1, z0, z1 = g["x0"], g["x1"], g["z0"], g["z1"]
    rg = R.rng(d, room, "fishing")
    ops = [fill((x0, fy - 2, z0, x1, fy - 2, z1), bed),                 # the bed (BED_UNDER: one under the floor course)
           fill((x0, fy - 1, z0, x1, fy - 1, z1), "minecraft:water"),
           fill((x0, fy, z0, x1, fy + 3, z1), "minecraft:air")]
    for z in g["pier_z"]:
        ops.append(setb((cx, fy - 1, z), safe["counter"]))
    for (mx, mz) in g["marker"]:
        ops.append(setb((mx, fy - 2, mz), markers[bands[0]]))
    pier_set = {(cx, z) for z in g["pier_z"]}
    # the two corners `expect` reads as plain water are never decor (PLACE-ROOMS, 2026-10-11: a jungle seed put seagrass
    # on one and the room failed its own check)
    water = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)
             if (x, z) not in pier_set and abs(x - cx) >= 1 and (x, z) not in ((x0, z0), (x1, z1))]
    rg.shuffle(water)
    decor = []
    for (x, z) in water[:int(cfg["decor"]["seagrass"])]:
        ops.append(setb((x, fy - 1, z), "minecraft:seagrass"))
        decor.append(((x, fy - 1, z), "minecraft:seagrass"))
    for (x, z) in water[int(cfg["decor"]["seagrass"]):int(cfg["decor"]["seagrass"]) + int(cfg["decor"]["sea_pickles"])]:
        ops.append(setb((x, fy - 1, z), "minecraft:sea_pickle[pickles=3,waterlogged=true]"))
        decor.append(((x, fy - 1, z), "minecraft:sea_pickle"))
    lights = []
    ground = c.room
    zlo, zhi = min(z0, z1) - 1, max(z0, z1) + 1
    for px in (x0 - 1, x1 + 1):
        for pz in (zlo, zhi):
            if ground["ix0"] <= px <= ground["ix1"] and ground["iz0"] <= pz <= ground["iz1"]:
                ops += [setb((px, fy, pz), safe["post"]), setb((px, fy + 1, pz), safe["lantern"])]
                lights.append((px, fy + 1, pz))
    end_z = g["pier_z"][-1]
    shore_z = g["edge"] + (2 if g["side"] == "north" else -2)
    yaw = 180 if g["side"] == "north" else 0
    reserve = (x0 - 2, fy - 2, max(ground["iz0"], zlo - 1), x1 + 2, fy + 3, min(ground["iz1"], zhi + 1))
    reset = ["# the pool's band marker (under the pier, three cells): the entrant's band's block, set by the slot reset as the",
             "# entrant (dg.band frozen at the rip). The shell wrote band 1's. The lent rod is taken from anyone still carrying one"]
    for b in bands:
        for (mx, mz) in g["marker"]:
            reset.append("execute in %s if score @s dg.band matches %d run setblock %d %d %d %s" % (c.dim, b, mx, fy - 2, mz, markers[b]))
    reset.append("clear @s %s" % lent_rod_match())
    enter = [bar(cfg["messages"]["enter"], "aqua"), "give @s %s 1" % lent_rod_item(), sound("minecraft:entity.fishing_bobber.splash", 0.5, 1.2)]
    expect = ([((x0, fy - 1, z0), "minecraft:water"), ((x1, fy - 1, z1), "minecraft:water"), ((x0, fy - 2, z0), bed)]
              + [((cx, fy - 1, z), safe["counter"]) for z in g["pier_z"]]
              + [((mx, fy - 2, mz), markers[bands[0]]) for (mx, mz) in g["marker"]] + decor)
    return {"blocks": ops, "lights": lights, "reserve": [reserve],
            "anchors": {"pier": [[cx, fy, end_z, yaw]], "shore": [[cx, fy, shore_z, yaw]]},
            "functions": {"enter": enter, "reset": reset},
            "meta": {"fishing": g, "expect": expect, "attached": [], "bed": bed, "markers": markers, "extra_drop": 1,
                     "marker_cells": [(mx, fy - 2, mz) for (mx, mz) in g["marker"]]}}


def fishing_rooms(doc, d):
    return [r for r in R.all_records(d) if r.get("kind") == "fishing_room"]


def dungeon_slots(doc, d):
    import dungeon as DG
    return [s for s in DG.slots(doc) if s["dungeon"]["id"] == d["id"]]


def spawn_entries(doc, d, species_key=None):
    """[spawn detail] for a dungeon's fishing pool: bands x buckets, boxed to the dungeon's slot rows, keyed to the band marker."""
    cfg = fishing_cfg()
    key = species_key or d.get("theme")
    table = cfg["species"][key]
    sl = dungeon_slots(doc, d)
    eng = doc["engine"]["slots"]
    z_lo = min(s["z0"] for s in sl)
    z_hi = max(s["z0"] for s in sl) + int(eng["strip_width_max"]) - 1
    x_lo = int(eng["origin_x"])
    x_hi = x_lo + int(eng["strip_length"]) - 1
    out = []
    n = 0
    for band in bands_of(doc):
        lo, hi = level_range(doc, band)
        marker = cfg["markers"][str(band)]
        for bucket in BUCKETS:
            for sp, w in table[str(band)][bucket]:
                n += 1
                out.append({
                    "id": "dg_%s_fish_b%d_%02d" % (d["short"], band, n),
                    "pokemon": sp, "type": "pokemon", "spawnablePositionType": "fishing",
                    "bucket": bucket, "level": "%d-%d" % (lo, hi), "weight": float(w),
                    "condition": {"dimensions": [dim_of(doc)], "minX": x_lo, "maxX": x_hi, "minZ": z_lo, "maxZ": z_hi,
                                  "neededNearbyBlocks": [marker]}})
    return out


def spawn_pool_path(d):
    return "data/cobblemon/spawn_pool_world/cobblers_dg_%s_fishing.json" % d["short"]


def spawn_pool(doc, d, species_key=None):
    return {"enabled": True, "neededInstalledMods": [], "neededUninstalledMods": [], "spawns": spawn_entries(doc, d, species_key)}


# ------------------------------------------------------------------------------------------------- the egg room


def egg_cfg():
    return load()["eggs"]


def offers_of(room, band):
    p = room.get("params") or {}
    src = p.get("offers") or egg_cfg()["offers"]
    return src[str(band)]


def price_s(doc, room, band):
    p = room.get("params") or {}
    src = p.get("clock_s_by_band") or egg_cfg()["price"]["clock_s_by_band"]
    return int(src[str(band)])


def nest_cp(doc, band):
    import dungeon_greed as DGR
    return DGR.catch_cp(DGR.load(), egg_cfg()["price"]["greed"], band, doc)


def vendor_class(d, room, g, band):
    return "dg_%s_egg_%s_s%d_b%d" % (d["short"], slug(room["id"]), g, band)


def npc_class(d, room, g, band, theme_id):
    v = egg_cfg()["vendor"][theme_id]
    return {"hitbox": "player", "names": [v["name"]], "resourceIdentifier": egg_cfg()["skin"],
            "interaction": {"type": "dialogue", "dialogue": "%s:%s" % (NS, vendor_class(d, room, g, band))},
            "canDespawn": False, "isInvulnerable": True, "isMovable": False, "isLeashable": False,
            "allowProjectileHits": False,
            "ai": [{"type": "apply_behaviours", "presets": ["cobblemon:looks_at_players"]}]}


def take_fn_name(band, k):
    return "take_b%d_%d" % (band, k)


def dialogue(doc, d, room, g, band, theme_id):
    """The vendor's dialogue for one slot and band: one page, the offers as lines (name and its one-line description)
    and one button each; a button runs the slot's take function as the player and closes."""
    cfg = egg_cfg()
    offers = offers_of(room, band)
    cost = price_s(doc, room, band)
    lines = ["%s (%d s of your clock; one egg a run)" % (cfg["intro"], cost)]
    lines += ["%s: %s" % (o["name"], o["desc"]) for o in offers]
    options = []
    for k, o in enumerate(offers):
        fn = R.room_fn(d, room, {"g": g}, take_fn_name(band, k))
        options.append({"text": "Take the %s egg" % o["name"], "value": "take%d" % k,
                        "action": ["q.run_command('execute as ' + q.player.uuid + ' at @s run function %s');" % fn, "q.dialogue.close();"]})
    options.append({"text": "Not now", "value": "cancel", "action": ["q.dialogue.close();"]})
    v = cfg["vendor"][theme_id]
    return {"speakers": {"vendor": {"name": v["name"]}},
            "pages": [{"id": "offer", "speaker": "vendor", "lines": lines, "input": {"type": "option", "vertical": True, "options": options}}]}


def room_tag(room):
    return NPC_TAG + slug(room["id"])


def kind_egg(doc, d, slot, room, theme):
    c = Ctl(doc, d, slot, room)
    cfg = egg_cfg()
    theme_id = c.theme_id()
    if theme_id not in cfg["vendor"]:
        c.fail("data/dungeon_extras2.json eggs.vendor has no entry for theme %r" % theme_id)
    safe = theme["safe"]
    fy, iz0 = c.fy, room["iz0"]
    cx = (room["ix0"] + room["ix1"]) // 2
    if room["ix1"] - room["ix0"] < 18 or room["iz1"] - room["iz0"] < 12 or room["height"] < 5:
        c.fail("an egg room needs a room at least 19 long, 13 wide and 5 high (is %d x %d x %d)" % (room["length"], room["width"], room["height"]))
    hz = iz0 + 1                                            # the vendor's row, behind the counter
    ops = [fill((cx - 3, fy, hz + 1, cx + 3, fy, hz + 1), safe["counter"]),
           fill((cx - 3, fy + 1, hz + 1, cx + 3, fy + 1, hz + 1), safe["counter_top"]),
           fill((cx - 3, fy, hz + 2, cx + 3, fy, hz + 3), safe["rug"])]
    lights = []
    for px in (cx - 5, cx + 5):
        ops += [setb((px, fy, hz + 1), safe["post"]), setb((px, fy + 1, hz + 1), safe["lantern"])]
        lights.append((px, fy + 1, hz + 1))
    bands = bands_of(doc)
    for b in bands:
        offs = offers_of(room, b)
        if not 1 <= len(offs) <= 5:
            c.fail("band %d: 1 to 5 offers (is %d)" % (b, len(offs)))
    H, he = c.H, c.holder("e")
    tag = room_tag(room)
    gtag = "dg.s%d" % c.g
    npc_sel = "@e[type=cobblemon:npc,tag=%s,tag=%s]" % (tag, gtag)
    import dungeon as DG
    npc_at = DG.F("npc_at")
    enter = [LOADED, "scoreboard players set %s dg.rs 0" % he, bar("An egg-seller keeps a stall here.", "gold"),
             "execute in %s run kill %s" % (c.dim, npc_sel)]
    for b in bands:
        enter.append("execute if score @s dg.band matches %d in %s run function %s {x:\"%.1f\",y:\"%d\",z:\"%.1f\",cls:\"%s:%s\",level:\"1\"}"
                     % (b, c.dim, npc_at, cx + 0.5, fy, hz + 0.5, NS, vendor_class(d, room, c.g, b)))
    enter.append("execute in %s positioned %.1f %d %.1f as @e[type=cobblemon:npc,tag=!%s,distance=..1.5,sort=nearest,limit=1] run function %s"
                 % (c.dim, cx + 0.5, fy, hz + 0.5, DG.TAGS["npc"], c.fn("vendor_bind")))
    fns = {"enter": enter,
           "vendor_bind": [LOADED, "function %s" % DG.F("slot/s%d/bind" % c.g), "tag @s add %s" % tag],
           "reset": ["# the stall: the vendor gone, the egg unsold (the next entry spawns a vendor of the entrant's band)",
                     "execute in %s run kill %s" % (c.dim, npc_sel), "scoreboard players set %s dg.rs 0" % he]}
    u = U(doc)
    msgs = cfg["messages"]
    for b in bands:
        cost = price_s(doc, room, b)
        need = (cost + int(cfg["price"]["min_left_s"])) * u
        for k, o in enumerate(offers_of(room, b)):
            cp = nest_cp(doc, b)
            fns[take_fn_name(b, k)] = [
                LOADED, "# As the player, from the vendor's dialogue (band %d, offer %d: %s)." % (b, k, o["species"]),
                "execute unless score @s dg.st matches 3 run return 0",
                "execute unless score @s dg.band matches %d run return 0" % b,
                "execute if score %s dg.rs matches 1 run return run %s" % (he, say(msgs["already"], "gray")),
                "execute unless score @s dg.clock matches %d.. run return run %s" % (need, say(msgs["short"], "gray")),
                "scoreboard players set %s dg.rs 1" % he,
                "scoreboard players remove @s dg.clock %d" % (cost * u),
                "execute as @s run givepokemonegg @s %s" % o["species"],
                "scoreboard players set #gv dg.t %d" % cp,
                "function %s" % DG.F("greed/add"),
                say(msgs["got"], "gold"), sound("minecraft:entity.chicken.egg", 1, 1)]
    anchors = {"vendor": [[cx, fy, hz, 0]], "stall": [[cx, fy, hz + 3, 180]]}
    expect = [((cx, fy + 1, hz + 1), safe["counter_top"]), ((cx - 3, fy, hz + 1), safe["counter"])]
    return {"blocks": ops, "lights": lights, "reserve": [(cx - 6, fy, iz0, cx + 6, fy + 3, hz + 5)], "anchors": anchors,
            "functions": fns,
            "meta": {"egg": True, "expect": expect, "attached": [], "vendor": [cx, fy, hz], "npc_tag": tag}}


def egg_rooms_of_slot(doc, d, slot):
    return [r for r in R.layout(doc, d, slot) if r["kind"] == "egg_room"]


def egg_files(doc):
    out = {}
    for d in doc["dungeons"]:
        if not R.has_rooms(d):
            continue
        for s in dungeon_slots(doc, d):
            for r in egg_rooms_of_slot(doc, d, s):
                for b in bands_of(doc):
                    name = vendor_class(d, r, s["g"], b)
                    out["data/%s/npcs/%s.json" % (NS, name)] = json.dumps(npc_class(d, r, s["g"], b, d["theme"]), indent=2) + "\n"
                    out["data/%s/dialogues/%s.json" % (NS, name)] = json.dumps(dialogue(doc, d, r, s["g"], b, d["theme"]), indent=2) + "\n"
    return out


# ------------------------------------------------------------------------------------------------- the fossil chamber


def fossil_cfg():
    return load()["fossils"]


def fossils_of(room, band):
    p = room.get("params") or {}
    src = p.get("fossils_by_band") or fossil_cfg()["by_band"]
    keys = sorted(int(k) for k in src)
    ok = [k for k in keys if k <= band]
    return src[str(ok[-1])] if ok else []


def fossil_table_id(d, room, band):
    return "%s:dungeons/fossil/%s/%s/b%d" % (NS, d["id"], room["id"], band)


def fossil_table(entries):
    pool = {"rolls": 1, "entries": [{"type": "minecraft:item", "name": item, "weight": int(w),
                                     "functions": [{"function": "minecraft:set_count", "count": 1}]} for item, w in entries]}
    return {"type": "minecraft:chest", "pools": [pool]}


def fossil_geometry(c):
    r = c.room
    bay = fossil_cfg()["bay"]
    W, rows, depth, K = int(bay["width"]), int(bay["rows"]), int(bay["depth"]), int(bay["variants"])
    ix0, ix1, iz0, iz1, fy = r["ix0"], r["ix1"], r["iz0"], r["iz1"], c.fy
    cx = (ix0 + ix1) // 2
    if ix1 - ix0 < 20 or iz1 - iz0 < 10 or r["height"] < rows + 3:
        c.fail("a fossil chamber needs a room at least 21 long, 11 wide and %d high (is %d x %d x %d)" % (rows + 3, r["length"], r["width"], r["height"]))
    half = W // 2
    cells = [(cx + dx, fy + dy, iz0 + 1) for dy in range(rows) for dx in range(-(half - 1), half)]       # the middle layer, away from the frame
    rg = R.rng(c.d, r, "fossil")
    rg.shuffle(cells)
    spots = cells[:K]
    return {"cx": cx, "W": W, "rows": rows, "depth": depth, "x0": cx - half, "x1": cx + half, "spots": spots, "K": len(spots)}


def pick_extra(d, themes=None):
    """PICK_EXTRA_FNS: the dig block of the theme and the fossil block, when the dungeon has a fossil chamber."""
    if not R.has_rooms(d) or not any(r.get("kind") == "fossil_chamber" for r in R.all_records(d)):
        return []
    cfg = fossil_cfg()
    dig = cfg["dig"].get(d.get("theme"))
    return ([dig] if dig else []) + [cfg["block"]]


def kind_fossil(doc, d, slot, room, theme):
    c = Ctl(doc, d, slot, room)
    cfg = fossil_cfg()
    theme_id = c.theme_id()
    dig = cfg["dig"].get(theme_id)
    if dig is None:
        c.fail("data/dungeon_extras2.json fossils.dig has no block for theme %r" % theme_id)
    g = fossil_geometry(c)
    fy, iz0, cx = c.fy, room["iz0"], g["cx"]
    wall = theme["hull"]["wall"]
    block = cfg["block"]
    x0, x1, rows, depth = g["x0"], g["x1"], g["rows"], g["depth"]
    spots = g["spots"]
    first = spots[0]
    ops = [fill((x0, fy, iz0, x1, fy + rows, iz0 + depth - 1), wall),                       # the frame and the lintel
           fill((x0 + 1, fy, iz0, x1 - 1, fy + rows - 1, iz0 + depth - 1), dig),            # every breakable cell
           setb(first, block)]
    H = c.H
    hf = c.holder("f")
    f = {}
    for j, cell in enumerate(spots):
        body = [LOADED]
        if j:
            body.append("setblock %s %s" % (at(first), dig))
            body.append("setblock %s %s" % (at(cell), block))
        f["v%d" % j] = body
    enter = [LOADED, bar(cfg["messages"]["enter"], "gold"), "execute store result score %s dg.rs run random value 0..%d" % (hf, g["K"] - 1)]
    enter += ["execute if score %s dg.rs matches %d run function %s" % (hf, j, c.fn("v%d" % j)) for j in range(g["K"])]
    front = iz0 + depth
    tick = [LOADED, "execute unless score %s dg.rs matches 1 run return 0" % H]
    tick += ["execute if score %s dg.rs matches %d unless block %s %s run return run function %s"
             % (hf, j, at(cell), block, c.fn("got")) for j, cell in enumerate(spots)]
    for j, (sx, sy, _sz) in enumerate(spots):
        tick.append("execute if score %s dg.rs matches %d positioned %d.5 %d.5 %d.3 if entity @s[distance=..14] run particle %s ~ ~ ~ 0.25 0.25 0.1 0.01 2"
                    % (hf, j, sx, sy, front, cfg["particle"]))
    bands = bands_of(doc)
    got = [LOADED, "function %s" % c.fn("clear")]
    for b in bands:
        got.append("execute if score @s dg.band matches %d run loot give @s loot %s" % (b, fossil_table_id(d, room, b)))
    got += [bar(cfg["messages"]["got"], "gold"), sound("minecraft:block.amethyst_block.break", 1, 0.8),
            "particle minecraft:happy_villager ~ ~1 ~ 0.4 0.5 0.4 0 10"]
    reset = ["# the bay: every dig cell back, the fossil at variant 0 (the next entry rolls again), the room's state clear",
             c.inn("fill %s %s" % (" ".join(str(v) for v in (x0 + 1, fy, iz0, x1 - 1, fy + rows - 1, iz0 + depth - 1)), dig)),
             c.inn("setblock %s %s" % (at(first), block)), "scoreboard players set %s dg.rs 0" % hf]
    n_cells = (x1 - x0 - 1) * rows * depth
    anchors = {"dig_at": [[cx, fy, front + 1, 180]]}
    expect = [(first, block), ((x0 + 1, fy + rows - 1, iz0 + depth - 1), dig), ((x0, fy, iz0), wall), ((x1, fy + rows, iz0), wall)]
    return {"blocks": ops, "reserve": [(x0 - 3, fy, iz0, x1 + 3, fy + rows + 1, front + 3)], "anchors": anchors,
            "functions": dict(f, enter=enter, tick=tick, got=got, reset=reset),
            "meta": {"fossil": g, "expect": expect, "attached": [], "breakable_extra": n_cells, "dig": dig, "block": block,
                     "dig_cells": n_cells}}


def fossil_rooms(doc, d):
    return [r for r in R.all_records(d) if r.get("kind") == "fossil_chamber"]


def fossil_files(doc):
    out = {}
    for d in doc["dungeons"]:
        if not R.has_rooms(d):
            continue
        seen = set()
        for r in fossil_rooms(doc, d):
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            for b in bands_of(doc):
                out["data/%s/loot_table/dungeons/fossil/%s/%s/b%d.json" % (NS, d["id"], r["id"], b)] = \
                    json.dumps(fossil_table(fossils_of(r, b)), indent=2) + "\n"
    return out


# ------------------------------------------------------------------------------------------------- the pack


def pack_files(doc):
    """{path: text}: the fishing spawn pools, the vendors' NPC classes and dialogues, the fossil loot tables (tools/dungeon.py build())."""
    out = {}
    for d in doc["dungeons"]:
        if R.has_rooms(d) and fishing_rooms(doc, d):
            keys = {pool_species_key(r, d) for r in fishing_rooms(doc, d)}
            if len(keys) == 1:
                out[spawn_pool_path(d)] = json.dumps(spawn_pool(doc, d, keys.pop()), indent=2) + "\n"
    out.update(egg_files(doc))
    out.update(fossil_files(doc))
    return out


def has_fishing(doc):
    return any(R.has_rooms(d) and fishing_rooms(doc, d) for d in doc["dungeons"])


def patch_functions(doc, fns):
    """After every line that takes the rift pick back (a run's end, the far and back rips, the keeper's stale pass) the same
    line for the lent rod. Only when a dungeon has a fishing room."""
    if not has_fishing(doc):
        return
    import dungeon as DG
    pick = DG.pick_match(doc)
    lent = lent_rod_match()
    for name, lines in list(fns.items()):
        if not any(pick in ln and "clear @s" in ln for ln in lines):
            continue
        out = []
        for ln in lines:
            out.append(ln)
            if pick in ln and "clear @s" in ln:
                out.append(ln.replace(pick, lent))
        fns[name] = out


# ------------------------------------------------------------------------------------------------- checks


_SPECIES = {}


def jar_species():
    """{id: labels} from the Cobblemon jar, or None when the jar is not on this machine."""
    jar = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar")
    if not jar.is_file():
        return None
    if "s" not in _SPECIES:
        import zipfile
        out, pre = {}, {}
        with zipfile.ZipFile(jar) as z:
            for n in z.namelist():
                if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                    try:
                        j = json.loads(z.read(n))
                    except ValueError:
                        continue
                    name = n.rsplit("/", 1)[1][:-5]
                    out[name] = set(j.get("labels", []))
                    if j.get("preEvolution"):
                        pre[name] = j["preEvolution"].split(":")[-1]
        for name, labels in out.items():            # a line carries its first stage's label: wartortle is of the starter line
            root_ = name
            while root_ in pre and pre[root_] in out:
                root_ = pre[root_]
            if "starter" in out[root_]:
                labels.add("starter_line")
        _SPECIES["s"] = out
    return _SPECIES["s"]


NOT_FISHABLE = {"legendary", "mythical", "ultra_beast", "paradox", "fossil"}
NOT_AN_EGG = {"legendary", "mythical", "ultra_beast", "paradox"}


def data_problems(doc, species=None):
    """The data file against the engine: every band and bucket covered, levels under the band's lower cap, species ids that
    exist and are not a legendary (or, for fishing, a fossil Pokemon: the fossil chamber is their source), prices that can
    never end a run, fossil ids in the 15-id tag, one marker per band."""
    bad = []
    data = load()
    bands = bands_of(doc)
    fish = data["fishing"]
    seen_markers = set()
    for b in bands:
        m = fish["markers"].get(str(b))
        if not m:
            bad.append("fishing.markers: no block for band %d" % b)
        elif m in seen_markers:
            bad.append("fishing.markers: %s is used for two bands" % m)
        seen_markers.add(m)
    for theme, t in fish["species"].items():
        for b in bands:
            row = t.get(str(b))
            if row is None:
                bad.append("fishing.species.%s: no pool for band %d" % (theme, b))
                continue
            for bucket in BUCKETS:
                if not row.get(bucket):
                    bad.append("fishing.species.%s band %d: bucket %s is empty (a rolled empty bucket may spawn nothing)" % (theme, b, bucket))
                for sp, w in row.get(bucket, []):
                    if not SPECIES.match(sp) or not (isinstance(w, (int, float)) and w > 0):
                        bad.append("fishing.species.%s band %d: bad entry %r" % (theme, b, [sp, w]))
                    elif species is not None:
                        if sp not in species:
                            bad.append("fishing.species.%s band %d: %s is not a Cobblemon 1.8.0 species" % (theme, b, sp))
                        elif species[sp] & NOT_FISHABLE:
                            bad.append("fishing.species.%s band %d: %s carries label %s" % (theme, b, sp, sorted(species[sp] & NOT_FISHABLE)))
            commons = {sp for sp, _w in row.get("common", [])}
            if species is not None and not any(species.get(sp, set()) & {"starter", "starter_line"} for sp in commons):
                bad.append("fishing.species.%s band %d: no starter in the common bucket" % (theme, b))
    eggs = data["eggs"]
    for b in bands:
        offs = eggs["offers"].get(str(b))
        if not offs:
            bad.append("eggs.offers: no offers for band %d" % b)
            continue
        for o in offs:
            if not SPECIES.match(o["species"]) or not o.get("name") or not o.get("desc"):
                bad.append("eggs.offers band %d: %r needs species, name and desc" % (b, o))
            elif len(o["desc"]) > 90:
                bad.append("eggs.offers band %d: %s's description is over 90 characters" % (b, o["species"]))
            elif species is not None:
                if o["species"] not in species:
                    bad.append("eggs.offers band %d: %s is not a Cobblemon 1.8.0 species" % (b, o["species"]))
                elif species[o["species"]] & NOT_AN_EGG:
                    bad.append("eggs.offers band %d: %s is a legendary" % (b, o["species"]))
        cost = eggs["price"]["clock_s_by_band"].get(str(b))
        clock = min((int(d["clock_s_by_band"][str(b)]) for d in doc["dungeons"] if d.get("clock_s_by_band")), default=int(next(x for x in doc["engine"]["bands"] if x["band"] == b)["clock_s"]))
        if not isinstance(cost, int) or cost < 1 or cost + eggs["price"]["min_left_s"] >= clock:
            bad.append("eggs.price band %d: %r s is not under the shortest clock (%d s) less the margin" % (b, cost, clock))
    ids = {"cobblemon:" + n for n in ("helix_fossil", "dome_fossil", "old_amber_fossil", "root_fossil", "claw_fossil", "skull_fossil", "armor_fossil",
                                       "cover_fossil", "plume_fossil", "jaw_fossil", "sail_fossil", "fossilized_bird", "fossilized_fish",
                                       "fossilized_drake", "fossilized_dino")}
    for b in bands:
        row = data["fossils"]["by_band"].get(str(b))
        if not row:
            bad.append("fossils.by_band: nothing for band %d" % b)
            continue
        for item, w in row:
            if item not in ids or not (isinstance(w, int) and w > 0):
                bad.append("fossils.by_band band %d: %r is not one of the 15 fossil ids with a positive weight" % (b, [item, w]))
    return bad


def check(doc, d, slot):
    """EXTRA_CHECKS: the data file (once, on the first slot), the rooms' params, that nothing overwrote a room's own blocks,
    that the markers, the dig block and calcite stand nowhere else, that the pool is wading depth over a solid bed, and the
    fossil bay is closed (solid behind every breakable block)."""
    bad = []
    kinds = {r["kind"] for r in R.layout(doc, d, slot)}
    if not kinds & set(KINDS):
        return bad
    first = next(x for x in doc["dungeons"] if R.has_rooms(x) and any(r.get("kind") in KINDS for r in R.all_records(x)))
    if first["id"] == d["id"] and slot.get("k", 1) == 1:
        bad += data_problems(doc, jar_species())
    fish_rooms = [r for r in R.layout(doc, d, slot) if r["kind"] == "fishing_room"]
    if len({pool_species_key(r, d) for r in fish_rooms}) > 1:
        bad.append("%s: fishing rooms of one dungeon must share one species table (their spawn entries share one box)" % d["id"])
    for r in fish_rooms:
        if pool_species_key(r, d) not in fishing_cfg()["species"]:
            bad.append("%s room %s: params.species %r is not a table of fishing.species" % (d["id"], r["id"], pool_species_key(r, d)))
    markers = set(fishing_cfg()["markers"][k] for k in fishing_cfg()["markers"] if k.isdigit())
    own = {"fishing_room": markers, "fossil_chamber": {fossil_cfg()["block"]} | set(fossil_cfg()["dig"].values())}
    for b in R.slot_build(doc, d, slot):
        r = b.room
        lab = "%s room %s (%s)" % (d["id"], r["id"], r["kind"])
        g = b.grid
        for pos, want in b.meta.get("expect", []):
            got = G.base(g.block_at(*pos))
            if got != G.base(want):
                bad.append("%s: %s at %s is %s (dressing or a bug overwrote it)" % (lab, G.base(want), list(pos), got))
        names = {G.base(n) for n in g.names()}
        for kind, blocks in own.items():
            if r["kind"] != kind and names & blocks:
                bad.append("%s: holds %s, which only a %s may place" % (lab, sorted(names & blocks), kind))
        if r["kind"] == "fishing_room":
            m = b.meta["fishing"]
            fy = r["floor_in"]
            cls = g.cls()
            for x in range(m["x0"], m["x1"] + 1):
                for z in range(m["z0"], m["z1"] + 1):
                    if (x, z) in {(m["cx"], pz) for pz in m["pier_z"]}:
                        continue
                    if g.block_at(x, fy - 2, z) in ("minecraft:air",) or cls[g.local(x, fy - 2, z)] != G.SOLID:
                        bad.append("%s: the pool bed at (%d, %d, %d) is not solid" % (lab, x, fy - 2, z))
                        break
                    hull = R.load_themes()["themes"][d["theme"]]["hull"]
                    lamps = {G.base(hull["light"]), G.base((hull.get("tall_lights") or {}).get("block", hull["light"]))}
                    if G.base(g.block_at(x, fy - 1, z)) not in {"minecraft:water", "minecraft:seagrass", "minecraft:sea_pickle"} | lamps:
                        # a flooded ruin sets a sea lantern into the floor course every few blocks, under standing water too
                        bad.append("%s: the pool cell (%d, %d, %d) is %s, not wading-depth water" % (lab, x, fy - 1, z, g.block_at(x, fy - 1, z)))
                        break
                    if G.classify(g.block_at(x, fy, z)) != G.PASS or G.classify(g.block_at(x, fy + 1, z)) != G.PASS:
                        bad.append("%s: the pool cell (%d, %d) has something over the water" % (lab, x, z))
                        break
        if r["kind"] == "fossil_chamber":
            m = b.meta["fossil"]
            fy = r["floor_in"]
            cls = g.cls()
            iz0 = r["iz0"]
            for x in range(m["x0"] + 1, m["x1"]):
                for y in range(fy, fy + m["rows"]):
                    # solid behind the back layer (the hull's wall column) and over and under the bay
                    if cls[g.local(x, y, iz0 - 1)] != G.SOLID:
                        bad.append("%s: nothing solid behind the dig cell (%d, %d, %d)" % (lab, x, y, iz0))
                        break
                if cls[g.local(x, fy + m["rows"], iz0)] != G.SOLID:
                    bad.append("%s: nothing solid over the dig cell (%d, %d)" % (lab, x, iz0))
            for dx in (m["x0"], m["x1"]):
                for y in range(fy, fy + m["rows"]):
                    for z in range(iz0, iz0 + m["depth"]):
                        if cls[g.local(dx, y, z)] != G.SOLID:
                            bad.append("%s: the bay's frame is open at (%d, %d, %d)" % (lab, dx, y, z))
    return bad


R.EXTRA_CHECKS.append(check)
if pick_extra not in R.PICK_EXTRA_FNS:
    R.PICK_EXTRA_FNS.append(pick_extra)

R.register("fishing_room", kind_fishing, dress="light")
R.register("egg_room", kind_egg, dress="light")
R.register("fossil_chamber", kind_fossil, dress="light")
