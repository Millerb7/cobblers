#!/usr/bin/env python
"""The hidden prize (dungeons pass 3, unit KIT3; DUNGEON_ROOMS.md 1b).

The owner (2026-10-10): "I want them and legendaries and ultra beasts to be the prize of a dungeon, but not as easily
found." And: "Early dungeons can't really have legendaries, so maybe it would just be a cool random Gabite or something to
catch, and then late game, after gym 6, the player gets Beast Balls and can go get real mons."

Mechanism rung: datapack plus generator. A score rolled with vanilla `random value`, a wild Pokemon spawned by the fight
rooms' own macro (`spawnpokemonat`, EXP-046) and bound with the slot's claim, the Beast Ball key's entity tag
(tools/key_ball.py, EXP-064), the board's text_display rewritten with `data merge`. Nothing needs a mod or a scripting layer.

THE RECORD: a `habitat` room's `params.prize` {rare_by_band?, legendary_by_band?, rare_pool_by_band?,
legendary_pool_by_band?, roster?, chance_by_band?, rumour?}; the defaults are data/dungeons.json `engine.prize`
(legendary_from_band, GREED's: gym 6's cap; chance_by_band; rumour; level). POOLS (PRIZE-POOLS, 2026-10-11): a band's
prize is a pool (pool_at): the single form, then the room's own `*_pool_by_band` list, then, when `roster` names a
dungeon id and data/dungeon_prize_roster.json exists, that entry's `rare_pool_by_band` / `legendary_pool_by_band` (unit
COVERAGE's file; roster_entry reads {"dungeons": {id: entry}}, {"dungeons": [{"id": ...}]} or {id: entry}). Absent file:
the room's own pools stand alone, so a prize naming `roster` builds before COVERAGE lands; present file without the
entry: a problem. One member is rolled per run at the threshold, only when the prize is present, into the room's
species holder #s<g>r<i>ps (member 1 is every other value, so an unrolled holder still spawns one). THE RUMOUR NAMES NO
SPECIES (the owner: "not as easily found"; co-op partners read the same board): it is the room's or the engine's line.

PER RUN (members_max is 1: one entrant a slot, so one roll a run):
  slot/s<g>/start   (the threshold: the sigil is spent, so re-entering cannot re-roll for free) rolls `random value
                    1..100` for each prize room against the entrant's band's chance; `#s<g>r<i>p dg.rs` 1 = present.
                    Present: the board's text gains the rumour line, the member is told it in chat.
  slot/s<g>/arrive  puts the board's text back (a stale rumour never greets the next entrant).
  room enter        present: spawns the band's rolled pool member at the anchor `prize` (fixed, no_ai), bound by
                    prize/bind (from legendary_from_band: the key tag, Beast Ball only), prize/bind_native (the same for
                    an Ultra Beast: also the native tag, so the key's x5 does not stack on the jar's, key_ball.py) or
                    prize/rare_bind (any ball).
  room reset        discards it (the slot's free and the keeper's stale-run pass discard every wild Pokemon of the slot
                    already: tools/dungeon_fights.py patch_functions, through meta "wild").

THE LEVEL CAP. The prize is spawned at the band's LOWER cap, so no entrant of the band is over-capped by it and the level
cap's refusal (tools/levelcap_pack.py: a ball at a Pokemon strictly over the thrower's cap breaks free) never fires. A
prize above the cap would need that callback to exempt it, which reopens the trap the owner closed on 2026-09-28 (rctmod
refuses every trainer battle while a party member is over the cap): an owner decision, not taken here.

THE BEAST BALL. data/key_ball.json names this tool as a boss tool (data/dungeon_prize.json the record: its `species` is
the REFERENCE prize). key_ball's check builds build(load()) and demands every bind.mcfunction adds the tag: the binds of
every authored legendary prize, or, while no dungeon authors one, the reference's, so the generator is always checked.

What it does NOT cover: whether a fixed no_ai legendary accepts a battle (DG-FIGHTS' unproven habitat assumption); the
held-catch ledger (DUNGEON_CATCHES.md, not built: nothing removes a catch today); anchor_species() lists the legendary
prizes for it. GREED weighs a catch in a habitat as catches.habitat (8 / 20 points).
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dungeon_rooms as R  # noqa: E402

DATA = ROOT / "data" / "dungeon_prize.json"
ROSTER = ROOT / "data" / "dungeon_prize_roster.json"
POOL_MAX = 16
JAR = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar")
PRIZE_TAG = "dg.prize"
SPECIES = re.compile(r"^[a-z0-9_]+$")
# the jar's labels that make a species a Beast Ball (legendary-pool) prize. `paradox` joined at COVERAGE's finding
# (2026-10-11): the jar labels 20 paradoxes, none of them legendary or mythical, so without it a paradox was refused in a
# legendary pool and accepted as a band-1 rare prize
LEGEND_LABELS = {"legendary", "mythical", "ultra_beast", "paradox"}
RESTRICTED = "restricted"           # the jar's box legendaries: band 6 only (COVERAGE's rule, the roster's rules)
RUMOUR_MAX = 120


def _D():
    import dungeon as D       # lazy: tools/dungeon.py imports the room kit, which imports this module
    return D


def _DF():
    import dungeon_fights as DF
    return DF


def load():
    """The doc key_ball's boss check builds from (data/dungeons.json)."""
    return _D().load()


def record(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def prize_of(room):
    return (room.get("params") or {}).get("prize")


def cfg(doc):
    return doc["engine"]["prize"]


def legendary_from(doc):
    return int(cfg(doc)["legendary_from_band"])


def band_rows(doc):
    return doc["engine"]["bands"]


def chance(doc, room, band):
    own = (prize_of(room) or {}).get("chance_by_band") or {}
    if str(band) in own:
        return int(own[str(band)])
    return int(cfg(doc)["chance_by_band"][band - 1])


def rumour(doc, room):
    return (prize_of(room) or {}).get("rumour") or cfg(doc)["rumour"]


_ROSTER = {}


def roster(path=None):
    """data/dungeon_prize_roster.json (unit COVERAGE), or None when it is not there. Read once a path."""
    path = Path(path) if path is not None else ROSTER
    key = str(path)
    if key not in _ROSTER:
        _ROSTER[key] = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    return _ROSTER[key]


def roster_entry(name, doc_roster=None):
    """The roster's record for dungeon `name`, or None. Accepted shapes (COVERAGE writes it in parallel, so the reader
    is lenient and the CHECK is strict): {"dungeons": {id: entry}}, {"dungeons": [{"id"|"dungeon": id, ...}]}, or
    {id: entry} at the top level."""
    r = doc_roster if doc_roster is not None else roster()
    if not isinstance(r, dict):
        return None
    ds = r.get("dungeons", r)
    if isinstance(ds, dict):
        e = ds.get(name)
        return e if isinstance(e, dict) else None
    if isinstance(ds, list):
        for e in ds:
            if isinstance(e, dict) and (e.get("id") == name or e.get("dungeon") == name):
                return e
    return None


def _roster_pools(pz):
    """{"rare": {band: [..]}, "legendary": {band: [..]}} the roster adds to a prize naming `roster`, else empty."""
    name = pz.get("roster")
    e = roster_entry(name) if isinstance(name, str) else None
    if not e:
        return {"rare": {}, "legendary": {}}
    return {"rare": e.get("rare_pool_by_band") or {}, "legendary": e.get("legendary_pool_by_band") or {}}


def pool_at(doc, room, band):
    """([species, ...], legendary) the prize can be at `band` (one is rolled per run at the threshold), or None.

    The band's pool is, in this order and without repeats: the single form (`rare_by_band` / `legendary_by_band`), the
    room's own pool (`rare_pool_by_band` / `legendary_pool_by_band`), then -- when the prize names `roster` (a dungeon
    id) and data/dungeon_prize_roster.json is present -- that roster entry's pool of the same name. Rare below
    engine.prize.legendary_from_band, legendary from it."""
    pz = prize_of(room) or {}
    leg = band >= legendary_from(doc)
    kind = "legendary" if leg else "rare"
    out = []
    one = (pz.get("%s_by_band" % kind) or {}).get(str(band))
    for sp in ([one] if one else []) + list((pz.get("%s_pool_by_band" % kind) or {}).get(str(band)) or []) \
            + list(_roster_pools(pz)[kind].get(str(band)) or []):
        if sp not in out and not model_gated(doc, sp):
            out.append(sp)
    return (out, leg) if out else None


def model_gate(sp):
    """The model gate data/dungeon_prize_roster.json `species.<sp>.model_gate` names ("atm_subset"), or None. No roster:
    None (the gate is the roster's knowledge; a species a record names directly is not gated without it)."""
    r = roster()
    v = (((r or {}).get("species") or {}).get(sp) or {}).get("model_gate") if isinstance(r, dict) else None
    if not v:
        return None
    return v.split(":", 1)[0].strip() if isinstance(v, str) else "true"


def model_gated(doc, sp):
    """True when `sp`'s model gate is not in engine.prize.models_delivered: it is dropped from every prize pool."""
    g = model_gate(sp)
    return g is not None and g not in (cfg(doc).get("models_delivered") or [])


def species_at(doc, room, band, k=1):
    """(species, legendary) pool member k (1-based) of the prize at `band`, or None (no prize that band)."""
    got = pool_at(doc, room, band)
    if not got:
        return None
    pool, leg = got
    return (pool[(k - 1) % len(pool)], leg)


def pool_size(doc, room, band):
    got = pool_at(doc, room, band)
    return len(got[0]) if got else 0


def level_at(doc, band):
    """The band's LOWER cap (engine.prize.level "lower_cap"): never over any entrant of the band's cap."""
    row = [b for b in band_rows(doc) if b["band"] == band][0]
    return int(row["caps"][0])


def holder(slot, room):
    return R.state_holder(slot, room) + "p"


def prize_tag(room):
    return "dg.pz.%s" % _DF().room_slug(room)


def anchor_species(doc):
    """Every legendary or Ultra Beast an authored prize can be: DUNGEON_CATCHES.md 3.6's anchor list (never at stake)."""
    out = set()
    for d in doc["dungeons"]:
        if not R.has_rooms(d):
            continue
        for r in R.all_records(d):
            if not prize_of(r):
                continue
            for b in band_rows(doc):
                got = pool_at(doc, r, b["band"])
                if got and got[1]:
                    out.update(got[0])
    return sorted(out)


# ------------------------------------------------------------------------------------------------- the jar


_LABELS = {}


def jar_labels():
    """{species: set(labels)} from the Cobblemon 1.8.0 jar, or None when the jar is not on this machine."""
    if "x" in _LABELS:
        return _LABELS["x"]
    if not JAR.is_file():
        _LABELS["x"] = None
        return None
    out = {}
    with zipfile.ZipFile(JAR) as z:
        for n in z.namelist():
            if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                try:
                    j = json.loads(z.read(n))
                except ValueError:
                    continue
                out[n.rsplit("/", 1)[1][:-5]] = set(j.get("labels") or [])
    _LABELS["x"] = out
    return out


# ------------------------------------------------------------------------------------------------- the functions


def bind_lines(doc, g, room, legendary, pos, species=None):
    """As the prize just spawned: the slot's claim, the prize's tags, (from legendary_from_band) the Beast Ball key's
    tags for `species` (key_ball.bind_tag_lines: the key tag, and for an Ultra Beast the native tag that keeps the
    key's x5 off the jar's own), fixed in place."""
    import key_ball
    x, y, z, yaw = pos
    lines = [_D().HEAD, "# As the hidden prize room %s has just spawned: the slot's claim, the prize's tags%s, fixed" % (
        room["id"], ", the Beast Ball key's tag (only a Beast Ball catches it, tools/key_ball.py)" if legendary else ""),
        "function %s" % _D().F("wild/s%d/bind" % g),
        "tag @s add %s" % PRIZE_TAG,
        "tag @s add %s" % prize_tag(room)]
    if legendary:
        lines += key_ball.bind_tag_lines(species) if species else ["tag @s add %s" % key_ball.boss_tag()]
    lines += ["data merge entity @s {NoAI:1b}", "tp @s %.1f %d %.1f %d 0" % (x + 0.5, y, z + 0.5, yaw)]
    return lines


def bind_name(doc, species, legendary):
    """The bind a prize of `species` uses: prize/rare_bind (any ball), prize/bind (the key), prize/bind_native (the key,
    an Ultra Beast)."""
    import key_ball
    if not legendary:
        return "prize/rare_bind"
    return "prize/bind_native" if len(key_ball.bind_tag_lines(species)) > 1 else "prize/bind"


def spawn_name(bn, k):
    return "prize/spawn_b%d" % bn if k == 1 else "prize/spawn_b%d_%d" % (bn, k)


def species_holder(slot, room):
    return holder(slot, room) + "s"


def species_cond(Hs, k, n):
    """The execute clause (trailing space) for pool member k of n: member 1 also takes any other value of the holder."""
    if n <= 1:
        return ""
    if k == 1:
        return "unless score %s dg.rs matches 2..%d " % (Hs, n)
    return "if score %s dg.rs matches %d " % (Hs, k)


def prize_functions(doc, d, slot, room):
    """{name: lines} of the prize room's own functions (spawns and binds), its enter lines, and the spawns' record
    {band: [[species, level, legendary], ...]} (pool order). The kind and key_sweep_files both build from this."""
    DF = _DF()
    g = slot["g"]
    dim = doc["engine"]["pocket"]["dimension"]
    F = _D().F
    fn = lambda name: R.room_fn(d, room, slot, name)  # noqa: E731
    H, Hs = holder(slot, room), species_holder(slot, room)
    pos = prize_pos(room, room.get("params") or {})
    x, y, z, _yaw = pos
    fns, enter, spawns = {}, [], {}
    binds = {}
    for b in band_rows(doc):
        bn = b["band"]
        got = pool_at(doc, room, bn)
        if got is None:
            continue
        pool, leg = got
        lv = level_at(doc, bn)
        props = DF.props_of(lv, False, True)
        for k, sp in enumerate(pool, 1):
            bname = bind_name(doc, sp, leg)
            binds.setdefault(bname, sp)
            fns[spawn_name(bn, k)] = [
                _D().HEAD, "# As the member, the room's first pass, the prize present this run: band %d's %s (pool member %d of %d), "
                "level %d (the band's lower cap)" % (bn, sp, k, len(pool), lv),
                "execute in %s run function %s %s" % (dim, F("wild_at"), DF.macro_args(
                    x="%.1f" % (x + 0.5), y=str(y), z="%.1f" % (z + 0.5), species=sp, props=props)),
                "execute in %s positioned %.1f %d %.1f as @e[type=cobblemon:pokemon,tag=!%s,distance=..%g,sort=nearest,limit=1] "
                "run function %s" % (dim, x + 0.5, y, z + 0.5, DF.keep_tag(doc), DF.BIND_RADIUS, fn(bname))]
            enter.append("execute if score %s dg.rs matches 1 if score @s %s matches %d %srun function %s"
                         % (H, _D().OBJ["band"], bn, species_cond(Hs, k, len(pool)), fn(spawn_name(bn, k))))
        spawns[bn] = [[sp, lv, leg] for sp in pool]
    for bname, sp in binds.items():
        fns[bname] = bind_lines(doc, g, room, bname != "prize/rare_bind", pos, sp)
    return fns, enter, spawns, pos


def prize_pos(room, params):
    a = R.default_anchors(room, params)
    has_res = bool(_DF().is_wild_room(room))
    p = list(a["center"] if has_res else a["legendary"])
    while len(p) < 4:
        p.append(90)
    return tuple(int(v) for v in p[:4])


def _wrap_habitat():
    import dungeon_fights  # noqa: F401  (registers habitat first)
    base = R.KINDS.get("habitat")
    if base is None or getattr(base, "_dg_prize", False):
        return
    flags = dict(R.FLAGS["habitat"])

    def kind_habitat_prize(doc, d, slot, room, theme):
        res = base(doc, d, slot, room, theme)
        pz = prize_of(room)
        if not pz:
            return res
        bad = room_problems(doc, d, room)
        if bad:
            raise R.RoomError("; ".join(bad))
        DF = _DF()
        g = slot["g"]
        H = holder(slot, room)
        res = dict(res)
        fns = {k: list(v) for k, v in (res.get("functions") or {}).items()}
        own, enter, pools, pos = prize_functions(doc, d, slot, room)
        fns.update(own)
        spawns = {bn: lst[0] for bn, lst in pools.items()}
        enter.append("execute if score %s dg.rs matches 1 run title @s actionbar %s" % (H, R.text("Something rare is here.", "light_purple")))
        fns["enter"] = fns.get("enter", []) + enter
        fns["reset"] = fns.get("reset", []) + [
            "execute as @e[type=cobblemon:pokemon,tag=%s,tag=%s] run runmolang \"q.entity.discard;\"" % (DF.slot_tag(g), prize_tag(room)),
            "scoreboard players set %s dg.rs 0" % H,
            "scoreboard players set %s dg.rs 1" % species_holder(slot, room)]
        res["functions"] = fns
        anchors = dict(res.get("anchors") or {})
        anchors["prize"] = list(pos)
        res["anchors"] = anchors
        meta = dict(res.get("meta") or {})
        meta.pop("placeholder", None)
        meta["wild"] = True
        meta["prize"] = {"holder": H, "spawns": spawns, "pools": pools, "species_holder": species_holder(slot, room), "pos": list(pos),
                         "chance": {b["band"]: chance(doc, room, b["band"]) for b in band_rows(doc)},
                         "assumed": "random value at the threshold; a fixed no_ai prize accepts a battle and a ball (DG-FIGHTS' habitat "
                                    "assumption); the Beast Ball key (EXP-064, unrun)"}
        res["meta"] = meta
        return res

    kind_habitat_prize._dg_prize = True
    R.register("habitat", kind_habitat_prize, **flags)


# ------------------------------------------------------------------------------------------------- the slot's lines


def prize_rooms(doc, slot):
    d = slot["dungeon"]
    if not R.has_rooms(d):
        return []
    return [r for r in R.layout(doc, d, slot) if prize_of(r)]


def board_sel(doc, slot):
    D = _D()
    st = "%s.%s%d" % (D.TAGS["shell"], slot["dungeon"]["short"], slot["k"])
    return "@e[type=minecraft:text_display,tag=%s,tag=%s]" % (D.TAGS["board"], st)


def board_body(doc, slot, rumour_line=None):
    D = _D()
    body = D.board_text(doc, slot["dungeon"], slot)
    if rumour_line:
        body += "\nRumour: " + rumour_line
    return D.snbt_str(D.text(body, "white"))


def start_lines(doc, slot):
    D = _D()
    dim = doc["engine"]["pocket"]["dimension"]
    t = D.OBJ["t"]
    rooms = prize_rooms(doc, slot)
    out = []
    for room in rooms:
        H = holder(slot, room)
        out += ["# the hidden prize of room %s: rolled here, at the threshold (the sigil is spent: no free re-roll)" % room["id"],
                "scoreboard players set %s dg.rs 0" % H,
                "scoreboard players set #pz %s 101" % t]
        for b in band_rows(doc):
            bn = b["band"]
            if species_at(doc, room, bn) is None or chance(doc, room, bn) <= 0:
                continue
            out.append("execute if score @s %s matches %d store result score #pz %s run random value 1..100" % (D.OBJ["band"], bn, t))
            out.append("execute if score @s %s matches %d if score #pz %s matches ..%d run scoreboard players set %s dg.rs 1"
                       % (D.OBJ["band"], bn, t, chance(doc, room, bn), H))
        # which of the band's pool it is (PRIZE-POOLS): rolled only when present; member 1 is every other value
        Hs = species_holder(slot, room)
        out.append("scoreboard players set %s dg.rs 1" % Hs)
        for b in band_rows(doc):
            n = pool_size(doc, room, b["band"])
            if n > 1 and chance(doc, room, b["band"]) > 0:
                out.append("execute if score %s dg.rs matches 1 if score @s %s matches %d store result score %s dg.rs run random value 1..%d"
                           % (H, D.OBJ["band"], b["band"], Hs, n))
    for room in reversed(rooms):
        H = holder(slot, room)
        line = rumour(doc, room)
        out.append("execute if score %s dg.rs matches 1 in %s as %s run data merge entity @s {text:%s}"
                   % (H, dim, board_sel(doc, slot), board_body(doc, slot, line)))
        out.append("execute if score %s dg.rs matches 1 run tellraw @s %s"
                   % (H, json.dumps({"text": "Rumour: " + line, "color": "light_purple", "italic": True})))
    return out


def arrive_lines(doc, slot):
    if not prize_rooms(doc, slot):
        return []
    dim = doc["engine"]["pocket"]["dimension"]
    return ["# the board without a rumour: one is added only at the threshold, when the run's prize is present",
            "execute in %s as %s run data merge entity @s {text:%s}" % (dim, board_sel(doc, slot), board_body(doc, slot))]


def patch_functions(doc, fns):
    """tools/dungeon.py build(): the roll at each slot's threshold and the board put back at its arrival."""
    D = _D()
    for slot in D.slots(doc):
        st = start_lines(doc, slot)
        if not st:
            continue
        g = slot["g"]
        fns["slot/s%d/start" % g] = list(fns["slot/s%d/start" % g]) + st
        fns["slot/s%d/arrive" % g] = list(fns["slot/s%d/arrive" % g]) + arrive_lines(doc, slot)


def _rel(d, room, slot, name):
    ns, path = R.room_fn(d, room, slot, name).split(":", 1)
    return "data/%s/function/%s.mcfunction" % (ns, path)


def key_sweep_files(doc):
    """{path: text}: every prize room's spawn and bind functions, as the pack carries them (prize_functions, the kind's
    own source). tools/key_ball.py boss_problems sweeps them: each spawn line's species against the bind it runs, so an
    Ultra Beast bound without the native tag (the x25) or a non-Ultra-Beast bound with it (x1) is named."""
    D = _D()
    files = {}
    for slot in D.slots(doc):
        for room in prize_rooms(doc, slot):
            for name, lines in prize_functions(doc, slot["dungeon"], slot, room)[0].items():
                files[_rel(slot["dungeon"], room, slot, name)] = "\n".join(lines) + "\n"
    return files


def build(doc):
    """{path: text}: the Beast Ball binds of every authored legendary prize (the pack's own text, from the same function the
    room kind uses), or the reference prize's when none is authored. data/key_ball.json's boss check reads this."""
    D = _D()
    files = {}
    for slot in D.slots(doc):
        for room in prize_rooms(doc, slot):
            fns = prize_functions(doc, slot["dungeon"], slot, room)[0]
            for name in ("prize/bind", "prize/bind_native"):
                if name in fns:
                    files[_rel(slot["dungeon"], room, slot, name)] = "\n".join(fns[name]) + "\n"
    if not files:
        ref = record()
        room = {"id": "reference", "kind": "habitat", "params": {"prize": {"legendary_by_band": {
            str(legendary_from(doc)): ref["species"]["id"].split(":", 1)[-1]}}}}
        rel = "data/%s/function/%s/prize/reference/bind.mcfunction" % (R.NS, R.FOLDER)
        files[rel] = "\n".join(bind_lines(doc, 1, room, True, (0, 0, 0, 90))) + "\n"
    return files


# ------------------------------------------------------------------------------------------------- the checks


def _rumour_ok(s):
    return isinstance(s, str) and 0 < len(s) <= RUMOUR_MAX and all(32 <= ord(c) < 127 for c in s) \
        and not any(c in s for c in "\"'\\")


def engine_problems(doc):
    bad = []
    c = cfg(doc)
    nb = len(band_rows(doc))
    ch = c.get("chance_by_band")
    if not (isinstance(ch, list) and len(ch) == nb and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 100 for v in ch)):
        bad.append("engine.prize.chance_by_band: %d integers 0..100, one a band" % nb)
    elif any(b < a for a, b in zip(ch, ch[1:])):
        bad.append("engine.prize.chance_by_band must rise with the band (the owner: rarer early)")
    if not _rumour_ok(c.get("rumour")):
        bad.append("engine.prize.rumour: 1..%d printable characters, no quotes or backslash" % RUMOUR_MAX)
    md = c.get("models_delivered", [])
    if not (isinstance(md, list) and all(isinstance(x, str) and SPECIES.match(x) for x in md)):
        bad.append("engine.prize.models_delivered: a list of model gate names (\"atm_subset\")")
    if c.get("level") != "lower_cap":
        bad.append("engine.prize.level must be \"lower_cap\" (the level cap's ball refusal; see tools/dungeon_prize.py)")
    return bad


def _species_map_problems(doc, who, label, v, legendary, is_pool):
    """A {band: species} (or, as a pool, {band: [species, ...]}) prize map: bands that exist and sit on the right side of
    the Beast Ball stage, jar species, legendary/mythical/Ultra Beast exactly when the map is the legendary one."""
    if v is None:
        return []
    bad = []
    lf = legendary_from(doc)
    nb = len(band_rows(doc))
    labels = jar_labels()
    if not isinstance(v, dict):
        return ["%s: %s is {band: %s}" % (who, label, "[species, ...]" if is_pool else "species")]
    for k, val in v.items():
        if not (str(k).isdigit() and 1 <= int(k) <= nb):
            bad.append("%s: %s names band %r" % (who, label, k))
            continue
        if legendary and int(k) < lf or not legendary and int(k) >= lf:
            bad.append("%s: %s band %s: the %s prize is %s band %d (engine.prize.legendary_from_band, the Beast Ball stage)"
                       % (who, label, k, "legendary" if legendary else "rare", "from" if legendary else "below", lf))
        if is_pool:
            if not isinstance(val, list) or not val:
                bad.append("%s: %s band %s: a pool is a non-empty list of species" % (who, label, k))
                continue
            if len(set(map(str, val))) != len(val):
                bad.append("%s: %s band %s: a pool repeats a species" % (who, label, k))
            items = val
        else:
            items = [val]
        for sp in items:
            if not isinstance(sp, str) or not SPECIES.match(sp):
                bad.append("%s: %s band %s: %r is not a lowercase species id" % (who, label, k, sp))
                continue
            if labels is not None:
                if sp not in labels:
                    bad.append("%s: %s band %s: %s is not a species in the Cobblemon 1.8.0 jar" % (who, label, k, sp))
                elif legendary and not (labels[sp] & LEGEND_LABELS):
                    bad.append("%s: %s band %s: %s is not a legendary, mythical, Ultra Beast or paradox" % (who, label, k, sp))
                elif legendary and RESTRICTED in labels[sp] and int(k) != len(band_rows(doc)):
                    bad.append("%s: %s band %s: %s is restricted (a box legendary): band %d only" % (who, label, k, sp, len(band_rows(doc))))
                elif not legendary and labels[sp] & LEGEND_LABELS:
                    bad.append("%s: %s band %s: %s is %s: before the Beast Ball stage the prize is a rare NON-legendary"
                               % (who, label, k, sp, "/".join(sorted(labels[sp] & LEGEND_LABELS))))
    return bad


def room_problems(doc, d, room):
    pz = prize_of(room)
    who = "%s room %s" % (d["id"], room.get("id"))
    if not isinstance(pz, dict):
        return ["%s: prize is an object" % who]
    bad = []
    if room.get("kind") != "habitat":
        bad.append("%s: a prize lives in a habitat (GREED weighs a catch by the room kind: elsewhere it would count as a %s catch)"
                   % (who, room.get("kind")))
    if room.get("gate", "open") != "open":
        bad.append("%s: a prize habitat's gate is open (an optional room: nothing waits on the prize)" % who)
    sources = [(key, legendary, pz.get(key), False, "prize.%s" % key)
               for key, legendary in (("rare_by_band", False), ("legendary_by_band", True))]
    sources += [(key, legendary, pz.get(key), True, "prize.%s" % key)
                for key, legendary in (("rare_pool_by_band", False), ("legendary_pool_by_band", True))]
    if "roster" in pz:
        name = pz["roster"]
        if not isinstance(name, str) or not SPECIES.match(name):
            bad.append("%s: prize.roster names a dungeon id of data/dungeon_prize_roster.json" % who)
        elif roster() is not None:
            e = roster_entry(name)
            if e is None:
                bad.append("%s: prize.roster %r: data/dungeon_prize_roster.json has no entry for it (accepted shapes: "
                           "tools/dungeon_prize.roster_entry)" % (who, name))
            else:
                if not (e.get("rare_pool_by_band") or e.get("legendary_pool_by_band")):
                    bad.append("%s: prize.roster %r: its entry names neither rare_pool_by_band nor legendary_pool_by_band"
                               % (who, name))
                for key, legendary in (("rare_pool_by_band", False), ("legendary_pool_by_band", True)):
                    sources.append((key, legendary, e.get(key), True, "data/dungeon_prize_roster.json %s.%s" % (name, key)))
    for _key, legendary, v, is_pool, label in sources:
        bad += _species_map_problems(doc, who, label, v, legendary, is_pool)
    if not any(pool_at(doc, room, b["band"]) for b in band_rows(doc)):
        bad.append("%s: a prize names a species for at least one band" % who)
    for b in band_rows(doc):
        if pool_size(doc, room, b["band"]) > POOL_MAX:
            bad.append("%s band %d: a prize pool of %d species; at most %d" % (who, b["band"], pool_size(doc, room, b["band"]), POOL_MAX))
    ch = pz.get("chance_by_band") or {}
    if not isinstance(ch, dict) or any(not (str(k).isdigit() and 1 <= int(k) <= nb) or not isinstance(v, int)
                                       or isinstance(v, bool) or not 0 <= v <= 100 for k, v in ch.items()):
        bad.append("%s: prize.chance_by_band is {band: percent 0..100}" % who)
    if "rumour" in pz and not _rumour_ok(pz["rumour"]):
        bad.append("%s: prize.rumour: 1..%d printable characters, no quotes or backslash" % (who, RUMOUR_MAX))
    extra = set(pz) - {"rare_by_band", "legendary_by_band", "rare_pool_by_band", "legendary_pool_by_band", "roster",
                       "chance_by_band", "rumour"}
    if extra:
        bad.append("%s: prize has unknown key(s) %s" % (who, ", ".join(sorted(extra))))
    return bad


def check_prizes(doc, d, slot):
    bad = []
    for r in R.all_records(R.resolve(doc, d, slot)):
        if prize_of(r) is not None:
            bad += room_problems(doc, d, r)
    return bad


def problems_record(doc):
    """data/dungeon_prize.json: the reference prize key_ball builds when no dungeon authors one."""
    bad = []
    try:
        rec = record()
    except (OSError, ValueError) as e:
        return ["data/dungeon_prize.json: %s" % e]
    sp = (rec.get("species") or {}).get("id", "")
    if not re.match(r"^cobblemon:[a-z0-9_]+$", sp):
        bad.append("data/dungeon_prize.json species.id %r is not cobblemon:<species>" % sp)
    labels = jar_labels()
    if labels is not None and sp.split(":")[-1] in labels and not (labels[sp.split(":")[-1]] & LEGEND_LABELS):
        bad.append("data/dungeon_prize.json species.id %s is not a legendary or Ultra Beast" % sp)
    return bad


_wrap_habitat()
R.EXTRA_CHECKS.append(check_prizes)
