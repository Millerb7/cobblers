#!/usr/bin/env python
"""RELICS: the rewards behind the secrets (pass 2, unit DG2-RELICS, 2026-10-10).

The owner's replayability choice 2 (docs/mechanics/DUNGEON_PASS2.md): "a lore note or a relic piece per secret, a set
collected across runs (a scoreboard or advancement per piece)". The room kit builds the secrets' geometry and a `secret`
anchor (the relic spot, walk-checked WITH the trick and refused WITHOUT it); this module puts something to find there.
Mechanism rung: datapack plus generator (CLAUDE.md principle 6: nothing here needs a mod or a scripting layer; an
advancement, a scoreboard objective and merged room hooks are all it takes).

THE RECORD (written by the dungeon's author; nothing else is needed):
  room.params.relic        an id, [a-z][a-z0-9_]{1,31}, unique in the dungeon
  room.params.lore         one or two sentences of the dungeon's story, at most `lore_max` (160) characters, ASCII
  room.params.relic_name   OPTIONAL display name (<= `name_max`); default: the id, underscores to spaces, title case
  A room with TWO secrets gives each its own `relic` / `lore` / `relic_name` inside the secret record instead.

WHAT IS BUILT, per secret (the dress op `relics`, listed last in each theme's dress, data/dungeon_themes.json):
  * a PEDESTAL beside the relic spot (a themed plinth one block high with an `armed` block on it: a lit lantern, a
    froglight), in the secret's own chamber or alcove; the spot stays walkable, so the walk check still proves the
    secret reachable WITH its trick and not without it. Where the pedestal stands is the first of the spot's neighbours
    that is air, open to the ceiling, with a solid floor, nearest the secret's wall.
  * the room's `tick` (each keeper pass the member is in the room, clock running) gains one line per relic: a member
    within `trigger_radius` (1.6) of the pedestal's centre runs the relic's own function `relic_<id>` as themselves;
    while the pedestal is armed a thin particle marks it (only for a member within 14; a sealed chamber hides it).
  * `relic_<id>`: a member who already holds the relic is told so and nothing else happens. Otherwise: the criterion
    <id> of the dungeon's advancement is granted, their count (dg.rl_<short>) goes up, the relic is given as an item
    (named, lored, with a glint, tagged cobblers_relic:"<id>"), a title, the lore in chat, the count, a chime, and the
    pedestal's `armed` block becomes its `taken` block for the rest of this run.
  * the room's `reset` (the slot's reset) puts the armed block back and the room's state holder to 0. That is the
    DISPLAY. It never revokes an advancement and never touches a score: the player's record is theirs.

THE COLLECTION: one advancement per dungeon, cobblers:dungeons/relics/<short>, one `minecraft:impossible` criterion per
relic (the union over every variant, so a relic only a swapped room carries still counts) and every one required. The
last criterion completes it: the toast, the chat line, a goal frame. The count objective dg.rl_<short> is the display.

THE RUN BOARD: the board is one text entity every member reads, so it carries a static line (how many relics are
hidden). The per-player line lives beside it: on arrival the member gets a chat line "Relics of <dungeon>: n/N", and
while they stand within 5 blocks of the board in the entry room (before the clock starts) the same sits in their
action bar.

NO ECONOMY: the relic's base item comes from the theme's `items` list in data/dungeon_relics.json and must be priced
nowhere (the CobbleDollars bank, data/markets.json, data/traders.json, data/produce_buyer.json): tests/test_dungeon_relics.py
checks it. It is a keepsake and pays nothing.

UNPROVEN IN GAME: the selector form `advancements={cobblers:dungeons/relics/<short>={<id>=true}}` (the documented
wiki form, not yet run here), `advancement grant @s only <adv> <criterion>` on an impossible criterion (the sigil
advancements use the same trigger), a lore line's SNBT, `enchantment_glint_override`, the sound and particle ids
(particle checked against the 1.21.1 jar), a goal-frame root advancement showing as a tab of its own, and that a co-op
member sees the pedestal's `taken` state although they have not taken theirs (they are still given theirs by walking up).
"""
from __future__ import annotations

import json
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dungeon_grid as G  # noqa: E402
import dungeon_rooms as R  # noqa: E402
from dungeon_rooms import setb  # noqa: E402

DATA_PATH = ROOT / "data" / "dungeon_relics.json"
SCHEMA = "cobblers.dungeon_relics/1"
ID_RE = re.compile(r"[a-z][a-z0-9_]{1,31}")
LORE_RE = re.compile(r"[ -~]+")           # printable ASCII: the function files and the default font
BOARD_RADIUS = 5                           # the action bar shows within this of the board, in the entry room (the arrival message is read first)
PARTICLE_RADIUS = 14
CUSTOM_KEY = "cobblers_relic"
OBJ_ROOM = "dg.rs"                         # the kit's state objective; holder #s<g>r<i>l<j> here: 0/unset armed, 1 taken this run
TRIGGER_RE = re.compile(r"positioned (-?\d+)\.5 (-?\d+) (-?\d+)\.5 if entity @s\[distance=\.\.([0-9.]+)\] run function")
MIN_TRIGGER = 1.0                          # the spot beside the pedestal is one block from its centre

_DATA = {}


def data(path=DATA_PATH):
    key = str(path)
    if key not in _DATA:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if doc.get("schema") != SCHEMA:
            raise R.RoomError("%s: schema must be %s" % (path, SCHEMA))
        _DATA[key] = doc
    return _DATA[key]


# ------------------------------------------------------------------------------------------------- the record


def title_case(rid):
    return " ".join(w.capitalize() for w in rid.split("_"))


def relic_specs(room):
    """[{secret, type, relic, lore, name}] for the room's secrets (None fields where the author wrote nothing). The
    room-level params.relic / lore / relic_name belong to a room with exactly ONE secret."""
    secs = room.get("secrets") or []
    prm = room.get("params") or {}
    out = []
    for s in secs:
        rid, lore, name = s.get("relic"), s.get("lore"), s.get("relic_name")
        if len(secs) == 1:
            rid = rid if rid is not None else prm.get("relic")
            lore = lore if lore is not None else prm.get("lore")
            name = name if name is not None else prm.get("relic_name")
        out.append({"secret": s.get("id"), "type": s.get("type", "cracked"), "relic": rid, "lore": lore,
                    "name": name if name else (title_case(rid) if isinstance(rid, str) else None)})
    return out


def variants_of(doc, d):
    """The dungeon record as every variant builds it (a dungeon without variants: itself)."""
    if not d.get("variants"):
        return [d]
    return [R.resolve(doc, d, {"k": i + 1}) for i in range(len(d["variants"]))]


def catalog(doc, d):
    """([relic], [problem]): every relic of the dungeon over every variant, in first-seen order, and what is wrong with
    the record: a missing or malformed id or lore, a name too long, an id used twice with a different lore, a relic on
    a room with no secret, a secret without a relic once the dungeon has any."""
    cfg = data()
    found = {}
    order = []
    bad = []
    missing = []
    for rd in variants_of(doc, d):
        for r in R._walk_records(rd.get("rooms", [])):
            lab = "%s room %s" % (d["id"], r["id"])
            prm = r.get("params") or {}
            if (prm.get("relic") is not None or prm.get("lore") is not None) and not (r.get("secrets") or []):
                bad.append("%s: params.relic / lore on a room with no secret (a relic is placed at a secret's spot)" % lab)
            for sp in relic_specs(r):
                sl = "%s secret %s" % (lab, sp["secret"])
                rid, lore = sp["relic"], sp["lore"]
                if rid is None and lore is None:
                    missing.append(sl)
                    continue
                if not isinstance(rid, str) or not ID_RE.fullmatch(rid):
                    bad.append("%s: relic %r is not an id (lowercase letters, digits and underscores, starting with a letter, 2-32)" % (sl, rid))
                    continue
                if not isinstance(lore, str) or not lore.strip():
                    bad.append("%s: relic %s has no lore" % (sl, rid))
                    continue
                if len(lore) > cfg["lore_max"]:
                    bad.append("%s: relic %s's lore is %d characters, over the limit %d" % (sl, rid, len(lore), cfg["lore_max"]))
                if not LORE_RE.fullmatch(lore):
                    bad.append("%s: relic %s's lore holds a character outside printable ASCII" % (sl, rid))
                if len(sp["name"]) > cfg["name_max"]:
                    bad.append("%s: relic %s's name is %d characters, over the limit %d" % (sl, rid, len(sp["name"]), cfg["name_max"]))
                if rid in found:
                    # the same relic in the same room under another variant is one relic; in another room, or with other
                    # words, it is a second one under the same id
                    prev = found[rid]
                    if prev["room"] != r["id"]:
                        bad.append("%s: relic id %s is also in room %s (ids are unique in the dungeon)" % (sl, rid, prev["room"]))
                    elif prev["lore"] != lore or prev["name"] != sp["name"]:
                        bad.append("%s: relic id %s has different lore or name in another variant" % (sl, rid))
                    continue
                found[rid] = {"id": rid, "name": sp["name"], "lore": lore, "room": r["id"], "secret": sp["secret"],
                              "type": sp["type"]}
                order.append(rid)
    if found and missing:
        for sl in dict.fromkeys(missing):
            bad.append("%s: no relic or lore, in a dungeon whose collection has %d relic(s)" % (sl, len(found)))
    return [found[i] for i in order], list(dict.fromkeys(bad)), sorted(dict.fromkeys(missing))


def has_relics(doc, d):
    return R.has_rooms(d) and bool(catalog(doc, d)[0])


def adv_id(d):
    return "cobblers:dungeons/relics/%s" % d["short"]


def obj_of(d):
    return "dg.rl_%s" % d["short"]


def theme_cfg(d):
    cfg = data()["themes"].get(d.get("theme"))
    if cfg is None:
        raise R.RoomError("%s: data/dungeon_relics.json has no entry for theme %r" % (d["id"], d.get("theme")))
    return cfg


def item_of(d, relics, rid):
    items = theme_cfg(d)["items"]
    idx = [r["id"] for r in relics].index(rid)
    return items[idx % len(items)]


# ------------------------------------------------------------------------------------------------- text


def jtext(msg, colour="gray", italic=False):
    return json.dumps({"text": msg, "color": colour, "italic": italic}, ensure_ascii=False)


def snbt_str(s):
    return "'%s'" % s.replace("\\", "\\\\").replace("'", "\\'")


def lore_lines(lore):
    return textwrap.wrap(lore, data()["lore_wrap"])


def item_stack(d, relics, rel):
    """The relic as a give-able item: named, lored, glinting, tagged."""
    cfg = theme_cfg(d)
    lines = [jtext(x, "gray") for x in lore_lines(rel["lore"])]
    lines.append(jtext(d["name"], "dark_gray"))
    return ("%s[minecraft:item_name=%s,minecraft:lore=[%s],minecraft:custom_data={%s:\"%s\"},minecraft:enchantment_glint_override=true]"
            % (item_of(d, relics, rel["id"]), snbt_str(jtext(rel["name"], cfg["colour"])), ",".join(snbt_str(x) for x in lines),
               CUSTOM_KEY, rel["id"]))


def count_component(d, total, prefix):
    return json.dumps([{"text": prefix, "color": "gray"}, {"score": {"name": "@s", "objective": obj_of(d)}, "color": "gold"},
                       {"text": "/%d" % total, "color": "gray"}], ensure_ascii=False)


# ------------------------------------------------------------------------------------------------- the room

def holder(slot, room, j):
    return "#s%dr%dl%d" % (slot["g"], room["i"], j)


def neighbours(secret):
    """The cells beside the relic spot, nearest the secret's own wall first: a cracked chamber's wall is north or south,
    a balcony's alcove ends east."""
    if secret["type"] == "balcony":
        return [(1, 0), (0, -1), (0, 1), (-1, 0)]
    toward = -1 if secret.get("side") == "north" else 1
    return [(0, toward), (-1, 0), (1, 0), (0, -toward)]


def place_pedestal(ctx, secret, cfg):
    """(px, py, pz) of the pedestal placed in the grid, or None when no neighbour of the spot takes one."""
    sx, sy, sz = secret["anchor"][:3]
    g = ctx.grid
    for dx, dz in neighbours(secret):
        px, pz = sx + dx, sz + dz
        room = ctx.room
        if not (room["ix0"] <= px <= room["ix1"] and room["iz0"] <= pz <= room["iz1"]):
            continue        # (the outline's `open` is False inside a secret's rock: the chamber is carved from it)
        if not (g.inside(px, sy - 1, pz) and g.inside(px, sy + 2, pz)):
            continue
        if G.classify(g.block_at(px, sy - 1, pz)) != G.SOLID:
            continue
        if any(G.classify(g.block_at(px, y, pz)) != G.PASS or g.block_at(px, y, pz) != "minecraft:air" for y in (sy, sy + 1, sy + 2)):
            continue
        ctx.add(setb((px, sy, pz), cfg["pedestal"]))
        ctx.add(setb((px, sy + 1, pz), cfg["armed"]))
        return (px, sy, pz)
    return None


def touch_lines(doc, d, relics, rel, slot, room, j, ped):
    """The function relic_<id>: run as a member who stands at the pedestal."""
    cfg = data()
    tcfg = theme_cfg(d)
    adv, obj, rid = adv_id(d), obj_of(d), rel["id"]
    px, py, pz = ped
    H = holder(slot, room, j)
    has = "execute if entity @s[advancements={%s={%s=true}}]" % (adv, rid)
    total = len(relics)
    return [
        R.HEAD, R.LOADED,
        "# relic %s of %s, slot %d room %s: as the member at the pedestal. Once per player, ever (the advancement criterion)" % (rid, d["id"], slot["g"], room["id"]),
        "%s run title @s actionbar %s" % (has, json.dumps([{"text": "You already hold ", "color": "gray"},
                                                          {"text": rel["name"], "color": tcfg["colour"]}], ensure_ascii=False)),
        "%s run return 0" % has,
        "scoreboard players set %s %s 1" % (H, OBJ_ROOM),
        "advancement grant @s only %s %s" % (adv, rid),
        "scoreboard players add @s %s 1" % obj,
        "give @s %s" % item_stack(d, relics, rel),
        "setblock %d %d %d %s" % (px, py + 1, pz, tcfg["taken"]),
        "playsound %s master @s ~ ~ ~ 1 1.2" % cfg["sound_found"],
        "particle %s %d.5 %d %d.5 0.3 0.4 0.3 0.05 20" % (cfg["particle"], px, py + 1, pz),
        "title @s times 10 90 30",
        "title @s subtitle %s" % json.dumps([{"text": "Relic ", "color": "gray"}, {"score": {"name": "@s", "objective": obj}, "color": "gold"},
                                              {"text": " of %d" % total, "color": "gray"}], ensure_ascii=False),
        "title @s title %s" % jtext(rel["name"], tcfg["colour"]),
        "tellraw @s %s" % json.dumps([{"text": "%s: " % rel["name"], "color": tcfg["colour"]}, {"text": rel["lore"], "color": "gray", "italic": True}],
                                      ensure_ascii=False),
        "tellraw @s %s" % count_component(d, total, "Relics of %s: " % d["name"]),
        "execute if entity @s[advancements={%s=true}] run tellraw @s %s" % (adv, jtext("Every relic of %s is yours." % d["name"], "gold")),
        "execute if entity @s[advancements={%s=true}] run playsound %s master @s ~ ~ ~ 1 1" % (adv, cfg["sound_done"]),
    ]


def dress_relics(ctx, spec):
    """The dress op: pedestals, pickups and resets for the room's secrets."""
    room, b, d = ctx.room, ctx.built, ctx.d
    metas = b.meta.get("secrets") or []
    if not metas:
        return
    cfg = theme_cfg(d)
    relics, _bad, _miss = catalog(ctx.doc, d)
    specs = relic_specs(room)
    mine = b.meta.setdefault("relics", [])
    tick, reset = [], []
    cdata = data()
    for j, (m, sp) in enumerate(zip(metas, specs)):
        if sp["relic"] is None or sp["lore"] is None or sp["relic"] not in [r["id"] for r in relics]:
            continue            # problems()/warnings() name it
        rel = next(r for r in relics if r["id"] == sp["relic"])
        ped = place_pedestal(ctx, m, cfg)
        if ped is None:
            mine.append({"id": rel["id"], "secret": sp["secret"], "pedestal": None})
            continue
        px, py, pz = ped
        name = "relic_%s" % rel["id"]
        b.functions[name] = touch_lines(ctx.doc, d, relics, rel, ctx.slot, room, j, ped)
        H = holder(ctx.slot, room, j)
        tick.append("execute positioned %d.5 %d %d.5 if entity @s[distance=..%g] run function %s"
                    % (px, py, pz, cdata["trigger_radius"], R.room_fn(d, room, ctx.slot, name)))
        tick.append("execute unless score %s %s matches 1.. positioned %d.5 %d.5 %d.5 if entity @s[distance=..%d] run particle %s ~ ~ ~ 0.15 0.2 0.15 0.005 1"
                    % (H, OBJ_ROOM, px, py + 1, pz, PARTICLE_RADIUS, cdata["particle"]))
        reset.append("scoreboard players set %s %s 0" % (H, OBJ_ROOM))
        reset.append("setblock %d %d %d %s" % (px, py + 1, pz, cfg["armed"]))
        mine.append({"id": rel["id"], "secret": sp["secret"], "type": sp["type"], "pedestal": [px, py, pz], "spot": list(m["anchor"][:3]),
                     "holder": H, "function": name})
    if tick:
        b.functions["tick"] = tick + b.functions.get("tick", [])
    if reset:
        b.functions["reset"] = b.functions.get("reset", []) + reset


# ------------------------------------------------------------------------------------------------- the pack


def relic_dungeons(doc):
    import dungeon as DG
    return [d for d in DG.dungeons(doc) if has_relics(doc, d)]


def functions(doc):
    """{name under cobblers:dungeons/: lines}: the objectives (relic/load) and, per dungeon, the arrival line and the
    action bar line."""
    import dungeon as DG
    out = {}
    ds = relic_dungeons(doc)
    if not ds:
        return out
    out["relic/load"] = [DG.HEAD, "# The relic counts, one objective per dungeon (tools/dungeon_relics.py). A player's record is an advancement and a",
                         "# score on THEM: no reset of the slot or the run touches either."] + \
                        ["scoreboard objectives add %s dummy" % obj_of(d) for d in ds]
    for d in ds:
        relics = catalog(doc, d)[0]
        total = len(relics)
        init = "execute unless score @s %s matches -2147483648.. run scoreboard players set @s %s 0" % (obj_of(d), obj_of(d))
        out["relic/%s/show" % d["short"]] = [
            DG.HEAD, "# As a member arriving at %s: how many of its %d relics they hold" % (d["name"], total), init,
            "tellraw @s %s" % count_component(d, total, "Relics of %s: " % d["name"])]
        out["relic/%s/bar" % d["short"]] = [
            DG.HEAD, "# As a member in %s's entry room near the board: the same in the action bar" % d["name"], init,
            "title @s actionbar %s" % count_component(d, total, "Relics of %s: " % d["name"])]
    return out


def load_entries(doc):
    return [R.F("relic/load")] if relic_dungeons(doc) else []


def patch_functions(doc, fns):
    """The arrival chat line and the lobby's action bar, appended to the engine's own functions."""
    import dungeon as DG
    for slot in DG.slots(doc):
        d = slot["dungeon"]
        if not has_relics(doc, d):
            continue
        g = slot["g"]
        fns["slot/s%d/arrive" % g].append("function %s" % R.F("relic/%s/show" % d["short"]))
        bx, by, bz = DG.points(doc, slot)["board"]
        fns["slot/s%d/lobby" % g].append("execute if score @s %s matches %d positioned %.1f %.1f %.1f if entity @s[distance=..%d] run function %s"
                              % (DG.OBJ["slot"], g, bx, by, bz, BOARD_RADIUS, R.F("relic/%s/bar" % d["short"])))


def pack_files(doc):
    """{path: text}: the collection advancement of each dungeon with relics."""
    out = {}
    cfg = data()["collection"]
    for d in relic_dungeons(doc):
        relics = catalog(doc, d)[0]
        crit = [r["id"] for r in relics]
        adv = {"display": {"icon": {"id": item_of(d, relics, relics[0]["id"])},
                           "title": {"text": cfg["title"] % {"name": d["name"]}, "color": cfg["colour"]},
                           "description": {"text": cfg["description"] % {"name": d["name"]}},
                           "background": cfg["background"], "frame": cfg["frame"], "show_toast": True, "announce_to_chat": True},
               "criteria": {c: {"trigger": "minecraft:impossible"} for c in crit},
               "requirements": [[c] for c in crit]}
        out["data/cobblers/advancement/dungeons/relics/%s.json" % d["short"]] = json.dumps(adv, indent=2) + "\n"
    return out


def board_line(doc, d):
    """The static line of the run board, or None."""
    if not has_relics(doc, d):
        return None
    n = len(catalog(doc, d)[0])
    return "Relics hidden here: %d. Find one and it is yours for good; your count is in your chat and beside this board." % n


# ------------------------------------------------------------------------------------------------- the checks


def reach_ok(b, ped, radius):
    """The standable cells within the trigger's radius that a player reaches WITHOUT the secret's trick (the walk from the
    room's door in, jumps only where the kind allows them). It must be empty: else the relic is no secret. The with-trick
    walk is the kit's `_secret_walks` over the same grid, which the pedestal is already in. A cell counts by the nearest
    point of its footprint, and by a body that may be a block off the cell's level (a jump), so the bound is the
    pessimistic one."""
    r = b.room
    g = b.grid
    fl = R.flags_of(r["kind"])
    s_local = g.local(*R.room_start(r))
    x0, y0, z0 = g.box[:3]
    plain = G.walk(g, [s_local], jumps=fl["jumps"])
    px, py, pz = ped
    hit = []
    for (lx, ly, lz) in plain:
        x, y, z = lx + x0, ly + y0, lz + z0
        dh = max(0.0, abs(x - px) - 0.5), max(0.0, abs(z - pz) - 0.5)
        # a body standing on the cell has its feet at the cell's level; a jump lifts them by at most 1.25, which only
        # brings a cell BELOW the pedestal's level closer
        dy = float(y - py) if y >= py else max(0.0, float(py - y) - 1.25)
        if (dh[0] ** 2 + dh[1] ** 2 + dy ** 2) ** 0.5 <= radius:
            hit.append((x, y, z))
    return hit


def problems(doc, d, slot):
    """EXTRA_CHECKS: the record (once, on slot 1) and every pedestal the slot built."""
    bad = []
    if not R.has_rooms(d):
        return bad
    relics, rec_bad, _missing = catalog(doc, d)
    if slot.get("k", 1) == 1:
        bad += rec_bad
    if not relics:
        return bad
    try:
        theme_cfg(d)
    except R.RoomError as e:
        return bad + [str(e)]
    rids = {r["id"] for r in relics}
    for b in R.slot_build(doc, d, slot):
        room = b.room
        metas = b.meta.get("relics") or []
        secrets = b.meta.get("secrets") or []
        specs = relic_specs(room)
        lab = "%s room %s relics" % (d["id"], room["id"])
        want = [sp for sp in specs if sp["relic"] in rids]
        if len(metas) != len(want):
            bad.append("%s: %d relic(s) declared and %d built" % (lab, len(want), len(metas)))
        for m in metas:
            if m.get("pedestal") is None:
                bad.append("%s: relic %s finds no place for its pedestal beside the secret's spot" % (lab, m["id"]))
                continue
            px, py, pz = m["pedestal"]
            tcfg = theme_cfg(d)
            g = b.grid
            if g.block_at(px, py, pz) != tcfg["pedestal"] or g.block_at(px, py + 1, pz) != tcfg["armed"]:
                bad.append("%s: relic %s's pedestal is not in the shell at (%d, %d, %d)" % (lab, m["id"], px, py, pz))
            if list(m["spot"]) == [px, py, pz]:
                bad.append("%s: relic %s's pedestal stands on its own spot" % (lab, m["id"]))
            # the trigger is read back from the GENERATED tick line (centre and radius), not from the data it was made from
            line = next((ln for ln in b.functions.get("tick", []) if ln.endswith("/" + m["function"])), None)
            t = TRIGGER_RE.search(line) if line else None
            if t is None:
                bad.append("%s: relic %s has no trigger line in the room's tick" % (lab, m["id"]))
                continue
            cx, cy, cz, radius = int(t.group(1)), int(t.group(2)), int(t.group(3)), float(t.group(4))
            if (cx, cy, cz) != (px, py, pz):
                bad.append("%s: relic %s's trigger is centred on (%d, %d, %d), not its pedestal (%d, %d, %d)" % (lab, m["id"], cx, cy, cz, px, py, pz))
            hit = reach_ok(b, (cx, cy, cz), radius)
            if hit:
                bad.append("%s: relic %s's trigger (radius %g) reaches %d cell(s) a player stands on without the secret's trick, "
                           "first %s" % (lab, m["id"], radius, len(hit), list(sorted(hit)[0])))
            if radius < MIN_TRIGGER:
                bad.append("%s: relic %s's trigger radius %g cannot reach the spot beside its pedestal (needs %g)" % (lab, m["id"], radius, MIN_TRIGGER))
        if len(secrets) != len(specs):
            bad.append("%s: %d secrets planned and %d in the record" % (lab, len(secrets), len(specs)))
    return bad


def warnings(doc):
    """A secret with no relic in a dungeon that has none anywhere builds without a reward; say so."""
    import dungeon as DG
    out = []
    for d in DG.dungeons(doc):
        if not R.has_rooms(d):
            continue
        relics, _bad, missing = catalog(doc, d)
        if missing and not relics:
            out.append("%s: %d secret(s) carry no params.relic / lore (%s): they build with no reward" % (d["id"], len(missing), ", ".join(missing[:3])))
    return out


def report(doc):
    import dungeon as DG
    lines = []
    for d in DG.dungeons(doc):
        if not R.has_rooms(d):
            continue
        relics, bad, missing = catalog(doc, d)
        lines.append("%s: %d relic(s) %s, %d secret(s) without one%s" % (d["id"], len(relics), [r["id"] for r in relics], len(missing),
                                                                         ("; PROBLEMS: " + "; ".join(bad)) if bad else ""))
    return lines


def register():
    if __name__ != "dungeon_relics":
        return       # a mutant copy exec'd by a test must not take the dress op over
    R.register_dress("relics", dress_relics, "light")
    if problems not in R.EXTRA_CHECKS:
        R.EXTRA_CHECKS.append(problems)


register()


def main(argv=None):
    import dungeon as DG
    doc = DG.load()
    print("\n".join(report(doc) + ["WARNING: " + w for w in warnings(doc)]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
