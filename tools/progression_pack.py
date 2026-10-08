#!/usr/bin/env python
"""Generate the progression datapack from data/progression.json.

One flag is one advancement. A flag is the badge ledger entry, and it is also
the unlock for its town's waystone, so both read the same data. The pack:

  advancement/flag/<id>.json           the flag. Set by an RCT defeat, by the
                                       first tick (run_start), by command (trigger) or by a
                                       story beat (quest_transition, below)
  function/flag/<id>/grant             quest_transition flags only: `advancement grant @s only` the
                                       flag. The one way to set it. A dialogue transition in
                                       data/quests.json names it as a `function` effect, which
                                       tools/compile_dialogue.py runs as and at THAT player (the
                                       relic HQ guard's hq_admit is the same construct). No /trigger
                                       is exposed for it, so no player can set it by typing.
  function/flag/<id>/granted           reward: re-sync this player's waystones, offer that player a
                                       Xaero's waypoint to the next gym (gym_markers, one gym ahead), and
                                       give the leader's rewards once (loot_table/first_win/<trainer>), and
                                       call carry when the flag declares one
  function/flag/<id>/carry             carries_stage flags only (the gym badges): `runmolang` on THIS player's
                                       q.player.data() moves the reveal's stage up to the badge's stage, never
                                       down (the owner, 2026-10-05: playable end to end). NOT yet run in game
  rctmod leader loot tables            emptied: upstream drops them on every win, rematches included
  cobbleverse loot tables, functions   upstream_neutralised: Cobbleverse's gym maps emptied (they point at
                                       naturally generated gyms), its missing leader reward functions defined empty
  function/navigation/reconcile        for each placed waystone: activate if the
                                       flag is set, forget if not (runs as a player)
  advancement/navigation/used_waystone re-syncs one tick after a waystone is
                                       used, so right-clicking cannot unlock early
  function/tick, function/load         join re-sync and trigger objectives

Waystones without a position are skipped and listed, because town locations
are placed after the next terrain rendition.

  python tools/progression_pack.py                      # -> build/datapacks/cobblers_progression
  python tools/progression_pack.py --series johto       # prestige: another region's leaders
  python tools/progression_pack.py --out some/dir
  python tools/progression_pack.py --report <stopped world copy>   # each player's flags

Command syntax used here was loaded on this server's Waystones 21.1.37 and
rctmod 0.19.0-beta (EXP-020). Its runtime effect still needs a player.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK_FORMAT = 48  # Minecraft 1.21.1
ID_RE = re.compile(r"^[a-z0-9_]+$")
SET_BY_KINDS = {"trainer_defeat", "run_start", "trigger", "quest_transition"}


class ProgressionError(ValueError):
    pass


# ------------------------------------------------------------------ reading


def load(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf8"))
    if doc.get("schema") != "cobblers.progression/1":
        raise ProgressionError("%s: schema must be cobblers.progression/1" % path)
    return doc


def _obj(value, what) -> dict:
    if not isinstance(value, dict):
        raise ProgressionError("%s must be an object" % what)
    return value


def plan(doc: dict, series: str | None = None, placements: dict | None = None) -> dict:
    """Validate the parts the pack needs and return a normalised plan. Fails closed."""
    _obj(doc, "progression document")
    ns = doc.get("namespace") or "cobblers"
    if not isinstance(ns, str) or not ID_RE.match(ns):
        raise ProgressionError("namespace %r is not a valid id" % ns)
    active = series or doc.get("active_series")
    known = {s.get("id") for s in doc.get("series") or [] if isinstance(s, dict)}
    if not active:
        raise ProgressionError("no active_series set and none given")
    if active not in known:
        raise ProgressionError("series %r is not declared in series[]" % active)

    flags, seen, waystones, unplaced, objectives = [], set(), {}, [], {}
    for fl in doc.get("flags") or []:
        fl = _obj(fl, "every flag")
        fid = fl.get("id")
        if not isinstance(fid, str) or not ID_RE.match(fid):
            raise ProgressionError("flag id %r is not a valid id" % fid)
        if fid in seen:
            raise ProgressionError("flag %r is declared twice" % fid)
        seen.add(fid)
        set_by = fl.get("set_by")
        if not isinstance(set_by, dict) or set_by.get("kind") not in SET_BY_KINDS:
            raise ProgressionError("flag %r: set_by.kind must be one of %s"
                                   % (fid, sorted(SET_BY_KINDS)))
        entry = {"id": fid, "kind": set_by["kind"]}
        if set_by["kind"] == "trainer_defeat":
            ids = _obj(set_by.get("trainer_ids") or {}, "flag %r trainer_ids" % fid).get(active)
            if (not isinstance(ids, list) or not ids
                    or not all(isinstance(i, str) and ID_RE.match(i) for i in ids)):
                raise ProgressionError("flag %r has no trainer_ids for series %r (a non-empty list of ids)"
                                       % (fid, active))
            entry["trainer_ids"] = list(ids)
        if set_by["kind"] == "trigger":
            obj = set_by.get("objective")
            if not isinstance(obj, str) or len(obj) > 32 or not re.match(r"^[a-z0-9_.]+$", obj):
                raise ProgressionError("flag %r: trigger objective %r is not valid" % (fid, obj))
            if obj in objectives:
                raise ProgressionError("trigger objective %r is used by %s and %s"
                                       % (obj, objectives[obj], fid))
            objectives[obj] = fid
            entry["objective"] = obj
        if set_by["kind"] == "quest_transition":
            # the flag is granted by its own grant function, which one transition of one quest names as an effect;
            # the cross-file check (that transition exists and calls exactly this function) is
            # tests/test_rift_crisis_resolved.py, because this tool reads progression.json only
            for key in ("quest", "transition"):
                v = set_by.get(key)
                if not isinstance(v, str) or not ID_RE.match(v):
                    raise ProgressionError("flag %r: quest_transition needs a %s id, got %r" % (fid, key, v))
            entry["quest"], entry["transition"] = set_by["quest"], set_by["transition"]
        ws = fl.get("waystone")
        if ws is not None:
            ws = _obj(ws, "flag %r waystone" % fid)
            town = ws.get("town")
            if not isinstance(town, str) or not ID_RE.match(town):
                raise ProgressionError("flag %r: waystone has no town (a town id)" % fid)
            if town in waystones:
                raise ProgressionError("town %r has a waystone on two flags (%s, %s)"
                                       % (town, waystones[town]["flag"], fid))
            pos = ws.get("position")
            if pos is None:
                unplaced.append(town)
            elif not (isinstance(pos, list) and len(pos) == 3
                      and all(type(v) is int for v in pos)):
                raise ProgressionError("flag %r: waystone position must be [x, y, z] integers" % fid)
            dim = ws.get("dimension") or "minecraft:overworld"
            if not isinstance(dim, str) or not re.match(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$", dim):
                raise ProgressionError("flag %r: dimension %r is not a resource id" % (fid, dim))
            waystones[town] = {"flag": fid, "position": pos, "dimension": dim}
        if fl.get("offers_marker") is not None:
            entry["offers_marker"] = fl["offers_marker"]
        if fl.get("carries_stage") is not None:
            entry["carries_stage"] = _carry(fid, fl["carries_stage"], doc)
        flags.append(entry)
    markers = _markers(doc.get("gym_markers"), placements)
    for f in flags:
        if "offers_marker" in f and f["offers_marker"] not in markers:
            raise ProgressionError("flag %r offers the marker %r, which gym_markers does not define"
                                   % (f["id"], f["offers_marker"]))
    neutral = doc.get("upstream_neutralised") or {}
    rid = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$")
    empty_loot = list(neutral.get("empty_loot_tables") or [])
    empty_fn = list(neutral.get("empty_functions") or [])
    for r in empty_loot + empty_fn:
        if not isinstance(r, str) or not rid.match(r):
            raise ProgressionError("upstream_neutralised: %r is not a resource id" % (r,))
    first_win = {}
    fw = neutral.get("first_win_rewards")
    if fw and fw.get("series") == active:
        by_flag = {f["id"]: f for f in flags}
        for tid, r in (fw.get("trainers") or {}).items():
            f = by_flag.get(r.get("flag"))
            if f is None or tid not in (f.get("trainer_ids") or []):
                raise ProgressionError("first_win_rewards: %s is not a trainer of flag %r in series %r"
                                       % (tid, r.get("flag"), active))
            items = list(r.get("items") or []) + list(r.get("one_of") or [])
            if not items or not all(isinstance(i, str) and rid.match(i) for i in items):
                raise ProgressionError("first_win_rewards: %s needs item ids" % tid)
            if "rctmod:trainers/single/%s" % tid not in empty_loot:
                # without it the leader's own table still drops on every win, and the reward is given twice
                raise ProgressionError("first_win_rewards: %s's rctmod loot table is not emptied" % tid)
            first_win[tid] = {"flag": r["flag"], "items": list(r.get("items") or []), "one_of": list(r.get("one_of") or [])}
    return {"namespace": ns, "series": active, "flags": flags,
            "waystones": waystones, "unplaced": sorted(unplaced), "markers": markers,
            "empty_loot_tables": empty_loot, "empty_functions": empty_fn, "first_win": first_win,
            "waystone_gate": bool(_obj(doc.get("waystone_gate") or {"enforced": True}, "waystone_gate").get("enforced", True))}


def _carry(fid: str, spec, doc: dict) -> dict:
    """A flag's carries_stage ({"field": <enum quest field>, "to": <value>}): validated against the field's declared
    allowed_values in this same document, which are in story order. Returns {field, key, to, earlier}, where
    `earlier` is every value before `to`: the carry moves a stage up to `to` from one of those, and never down."""
    spec = _obj(spec, "flag %r carries_stage" % fid)
    field, to = spec.get("field"), spec.get("to")
    fdef = next((f for f in doc.get("quest_fields") or [] if isinstance(f, dict) and f.get("id") == field), None)
    if fdef is None:
        raise ProgressionError("flag %r carries_stage: %r is not a quest_fields id" % (fid, field))
    vals = fdef.get("allowed_values")
    if fdef.get("type") != "enum" or fdef.get("scope") != "player" or not isinstance(vals, list):
        raise ProgressionError("flag %r carries_stage: %r must be a player enum with listed allowed_values" % (fid, field))
    if to not in vals:
        raise ProgressionError("flag %r carries_stage: %r is not a value of %s" % (fid, to, field))
    for v in vals:
        if not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9_]+", v):
            raise ProgressionError("flag %r carries_stage: value %r of %s needs quoting this tool does not do"
                                   % (fid, v, field))
    tag = spec.get("requires_tag")
    if tag is not None and (not isinstance(tag, str) or not re.fullmatch(r"[a-z0-9_.]+", tag)):
        raise ProgressionError("flag %r carries_stage: requires_tag %r is not [a-z0-9_.]+" % (fid, tag))
    return {"field": field, "key": "cobblers__" + field.replace(".", "__"), "to": to,
            "earlier": vals[:vals.index(to)], "requires_tag": tag}


def carry_molang(c: dict) -> str:
    """The Molang that moves THIS player's stage up to c["to"]: the store tools/compile_dialogue.py's conversations
    read and write (q.player.data(), key cobblers__<field with . as __>). An unset key reads 0, which is the field's
    initial value, so 0 counts as earlier. A stage at or past `to` is left alone. With requires_tag, a player without
    that tag (the starter gate's, tools/compile_dialogue.py STARTER_TAG) is left alone too."""
    k = "t.d.%s" % c["key"]
    cond = " || ".join(["%s == 0" % k] + ["%s == '%s'" % (k, v) for v in c["earlier"]])
    if c.get("requires_tag"):
        cond = "q.player.has_tag('%s') && (%s)" % (c["requires_tag"], cond)
    return "t.d = q.player.data(); (%s) ? { %s = '%s'; q.player.save_data(); };" % (cond, k, c["to"])


MARKER_NAME = re.compile(r"^[A-Za-z0-9 ]{1,32}$")      # Xaero's share: 1-32 characters, and no ':', '-' or '_'
MARKER_INITIALS = re.compile(r"^[A-Za-z0-9]{1,3}$")    # 1-3 characters


MARKER_HINT_MAX = 240      # one chat line's worth; the hint is the sentence that says where to go and why


def _npc_seat(npc_id):
    """(x, y, z) of a seated dialogue NPC (data/npc_seats.json, the seat reapply R17N summons it at), or None."""
    doc = json.loads((ROOT / "data" / "npc_seats.json").read_text(encoding="utf-8"))
    for s in doc.get("seats") or []:
        if s.get("id") == npc_id and isinstance(s.get("at"), list) and len(s["at"]) == 3:
            return tuple(int(v) for v in s["at"])
    return None


def _markers(spec, placements) -> dict:
    """{town: {name, initials, color, x, y, z[, hint]}}: each gym marker at the middle of its building's placed
    footprint (tools/place_donor.py box, from the placement's position, size and rotation in data/placements.json),
    or, for a marker naming `npc_seat`, at that NPC's seat in data/npc_seats.json (the Rift surveyor, whom the Earth
    Badge points at: docs/world-building/POST_GYM8_DIRECTION.md). Either way the point is read from the file that
    places the thing, never written down twice, so the marker follows it when it moves. An optional `hint` is one
    sentence printed with the offer, saying where to go and why."""
    if not spec:
        return {}
    if placements is None:
        raise ProgressionError("gym_markers need data/placements.json to find the buildings")
    sys.path.insert(0, str(ROOT / "tools"))
    import place_donor
    rows = placements.get("placements")
    rows = rows if isinstance(rows, list) else list((rows or {}).values())
    by_id = {r.get("id"): r for r in rows}
    color = spec.get("color", 0)
    if type(color) is not int or not 0 <= color <= 15:
        raise ProgressionError("gym_markers.color must be a Xaero colour index 0-15")
    out = {}
    for town, m in (spec.get("markers") or {}).items():
        m = _obj(m, "gym marker %r" % town)
        if not MARKER_NAME.match(str(m.get("name", ""))) or not MARKER_INITIALS.match(str(m.get("initials", ""))):
            raise ProgressionError("gym marker %r: name must be 1-32 letters, digits or spaces and initials 1-3 "
                                   "letters or digits (Xaero's share format)" % town)
        hint = m.get("hint")
        if hint is not None and (not isinstance(hint, str) or not hint.strip() or len(hint) > MARKER_HINT_MAX):
            raise ProgressionError("gym marker %r: hint must be a non-empty string of at most %d characters"
                                   % (town, MARKER_HINT_MAX))
        if ("placement" in m) == ("npc_seat" in m):
            raise ProgressionError("gym marker %r: name exactly one of placement or npc_seat" % town)
        if "npc_seat" in m:
            seat = _npc_seat(m["npc_seat"])
            if seat is None:
                raise ProgressionError("gym marker %r: npc_seat %r has no seat in data/npc_seats.json"
                                       % (town, m["npc_seat"]))
            out[town] = {"name": m["name"], "initials": m["initials"], "color": color,
                         "x": seat[0], "y": seat[1], "z": seat[2]}
        else:
            rec = by_id.get(m.get("placement"))
            if not rec or not rec.get("position") or not rec.get("size"):
                raise ProgressionError("gym marker %r: placement %r not found, or has no position and size"
                                       % (town, m.get("placement")))
            lo, hi = place_donor.box(rec)
            out[town] = {"name": m["name"], "initials": m["initials"], "color": color,
                         "x": (lo[0] + hi[0]) // 2, "y": rec["position"]["y"], "z": (lo[2] + hi[2]) // 2}
        if hint is not None:
            out[town]["hint"] = hint.strip()
    return out


def xaero_share(m: dict) -> str:
    """A Xaero's Minimap waypoint share, as xaerominimap 26.4.2 writes it (WaypointSharingHandler)."""
    return "xaero-waypoint:%s:%s:%d:%d:%d:%d:false:0:Internal-overworld-waypoints" % (
        m["name"], m["initials"], m["x"], m["y"], m["z"], m["color"])


# ------------------------------------------------------------------ writing


def _flag_advancement(ns: str, flag: dict) -> dict:
    if flag["kind"] == "trainer_defeat":
        # rctmod fires defeat_count only for the players on the winning side of a finished battle
        # (TrainerBattle.distributeRewards, from Cobblemon's BATTLE_VICTORY), and matches when this player's own
        # defeats of the trainer reach count. count 1 says so rather than leaning on the codec's default
        criteria = {"defeated": {"trigger": "rctmod:defeat_count",
                                 "conditions": {"trainer_ids": flag["trainer_ids"], "count": 1}}}
    elif flag["kind"] == "run_start":
        criteria = {"started": {"trigger": "minecraft:tick"}}
    else:
        criteria = {"set": {"trigger": "minecraft:impossible"}}
    return {"criteria": criteria,
            "rewards": {"function": "%s:flag/%s/granted" % (ns, flag["id"])}}


def _has(ns: str, fid: str, value: bool) -> str:
    return "@s[advancements={%s:flag/%s=%s}]" % (ns, fid, "true" if value else "false")


def files(p: dict) -> dict:
    """Return {relative path: text} for the whole pack."""
    ns = p["namespace"]
    out = {}
    out["pack.mcmeta"] = json.dumps({"pack": {
        "pack_format": PACK_FORMAT,
        "description": "Cobblers progression flags and waystone unlocks (generated, series %s)"
                       % p["series"]}}, indent=2) + "\n"

    for flag in p["flags"]:
        out["data/%s/advancement/flag/%s.json" % (ns, flag["id"])] = \
            json.dumps(_flag_advancement(ns, flag), indent=2) + "\n"
        granted = ["function %s:navigation/reconcile" % ns]
        if flag.get("offers_marker"):
            # one gym ahead (NAVIGATION.md section 6): the reward runs as the player who earned the flag, so only
            # they see the offer; Xaero's shows it as a shared waypoint with an [Add] button
            m = p["markers"][flag["offers_marker"]]
            granted.append("tellraw @s " + json.dumps(
                ["", {"text": "Next: %s. " % m["name"], "color": "gold"}]
                + ([{"text": m["hint"] + " ", "color": "white"}] if m.get("hint") else [])
                + [{"text": "Add it to your map: ", "color": "gray"},
                   {"text": xaero_share(m), "color": "dark_gray"}]))
        for tid, fw in sorted(p.get("first_win", {}).items()):
            if fw["flag"] != flag["id"]:
                continue
            # the leader's rewards, once, to the winner: this reward runs only when the flag is first granted
            # (upstream_neutralised.first_win_rewards; the leader's own rctmod loot table is emptied)
            granted.append("loot give @s loot %s:first_win/%s" % (ns, tid))
            pools = [{"rolls": 1, "entries": [{"type": "minecraft:item", "name": i}]} for i in fw["items"]]
            if fw["one_of"]:
                pools.append({"rolls": 1, "entries": [{"type": "minecraft:item", "name": i} for i in fw["one_of"]]})
            out["data/%s/loot_table/first_win/%s.json" % (ns, tid)] = json.dumps({"pools": pools}, indent=2) + "\n"
        if flag.get("carries_stage"):
            # the badge carries the reveal forward (data/progression.json flags[].carries_stage): runs once, as the
            # winner, because a held advancement never re-runs its reward. Its own function, so the reward reads as
            # one line per effect; runmolang + q.player.save_data() is the store tools/hq_tower.py's won functions write
            c = flag["carries_stage"]
            out["data/%s/function/flag/%s/carry.mcfunction" % (ns, flag["id"])] = "\n".join([
                "# Generated by tools/progression_pack.py. Runs as the player who earned %s: moves their %s up to %s,"
                % (flag["id"], c["field"], c["to"]),
                "# never down (data/progression.json flags[].carries_stage).",
                'runmolang "%s" @s' % carry_molang(c),
            ]) + "\n"
            granted.append("function %s:flag/%s/carry" % (ns, flag["id"]))
        out["data/%s/function/flag/%s/granted.mcfunction" % (ns, flag["id"])] = "\n".join(granted) + "\n"
        if flag["kind"] == "quest_transition":
            # run as the player by the transition's `function` effect (tools/compile_dialogue.py). Granting a held
            # advancement again is a no-op and does not re-run its reward, so a repeated call is harmless
            out["data/%s/function/flag/%s/grant.mcfunction" % (ns, flag["id"])] = "\n".join([
                "# Generated by tools/progression_pack.py. Runs as one player: data/quests.json %s transition %s."
                % (flag["quest"], flag["transition"]),
                "advancement grant @s only %s:flag/%s" % (ns, flag["id"]),
            ]) + "\n"

    for rid in p.get("empty_loot_tables", []):
        rns, path = rid.split(":", 1)
        out["data/%s/loot_table/%s.json" % (rns, path)] = json.dumps({"pools": []}, indent=2) + "\n"
    for rid in p.get("empty_functions", []):
        rns, path = rid.split(":", 1)
        out["data/%s/function/%s.mcfunction" % (rns, path)] = \
            "# Named as an advancement reward by Cobbleverse and defined by no installed pack: kept empty on purpose\n" \
            "# (data/progression.json upstream_neutralised).\n"

    lines = ["# Generated by tools/progression_pack.py. Runs as one player.",
             "# Placed waystones follow their flag; unplaced towns are listed and skipped."]
    for town in sorted(p["waystones"]):
        ws = p["waystones"][town]
        if ws["position"] is None:
            lines.append("# %s (%s): waystone not placed" % (town, ws["flag"]))
            continue
        x, y, z = ws["position"]
        lines.append("execute if entity %s in %s run waystones activate @s %d %d %d"
                     % (_has(ns, ws["flag"], True), ws["dimension"], x, y, z))
        if p.get("waystone_gate", True):
            lines.append("execute if entity %s in %s run waystones forget @s %d %d %d"
                         % (_has(ns, ws["flag"], False), ws["dimension"], x, y, z))
    out["data/%s/function/navigation/reconcile.mcfunction" % ns] = "\n".join(lines) + "\n"

    # waystone_gate.enforced false (the owner, play test 2026-10-05, review 89): a badge still activates its town's
    # waystone, but nothing is forgotten and a right-click activates as the Waystones mod does, so no re-sync on use
    if p.get("waystone_gate", True):
        out["data/%s/advancement/navigation/used_waystone.json" % ns] = json.dumps({
            "criteria": {"used": {"trigger": "minecraft:any_block_use", "conditions": {
                "location": [{"condition": "minecraft:location_check",
                              "predicate": {"block": {"blocks": "#waystones:waystones"}}}]}}},
            "rewards": {"function": "%s:navigation/on_use" % ns}}, indent=2) + "\n"
        out["data/%s/function/navigation/on_use.mcfunction" % ns] = "\n".join([
            "advancement revoke @s only %s:navigation/used_waystone" % ns,
            "tag @s add %s.resync" % ns,
            "schedule function %s:navigation/deferred 1t replace" % ns,
        ]) + "\n"
        out["data/%s/function/navigation/deferred.mcfunction" % ns] = "\n".join([
            "execute as @a[tag=%s.resync] at @s run function %s:navigation/reconcile" % (ns, ns),
            "tag @a remove %s.resync" % ns,
        ]) + "\n"

    triggers = [f for f in p["flags"] if f["kind"] == "trigger"]
    load = ["scoreboard objectives add %s.left minecraft.custom:minecraft.leave_game" % ns]
    tick = ["execute as @a[scores={%s.left=1..}] at @s run function %s:navigation/reconcile" % (ns, ns),
            "scoreboard players reset @a[scores={%s.left=1..}] %s.left" % (ns, ns)]
    for f in triggers:
        obj = f["objective"]
        load.append("scoreboard objectives add %s trigger" % obj)
        tick.append("scoreboard players enable %s %s" % (_all_without(ns, f["id"]), obj))
        tick.append("execute as @a[scores={%s=1..}] run advancement grant @s only %s:flag/%s"
                    % (obj, ns, f["id"]))
        tick.append("scoreboard players reset @a[scores={%s=1..}] %s" % (obj, obj))
    out["data/%s/function/load.mcfunction" % ns] = "\n".join(load) + "\n"
    out["data/%s/function/tick.mcfunction" % ns] = "\n".join(tick) + "\n"
    out["data/minecraft/tags/function/load.json"] = json.dumps(
        {"values": ["%s:load" % ns]}, indent=2) + "\n"
    out["data/minecraft/tags/function/tick.json"] = json.dumps(
        {"values": ["%s:tick" % ns]}, indent=2) + "\n"
    return out


def _all_without(ns: str, fid: str) -> str:
    return "@a[advancements={%s:flag/%s=false}]" % (ns, fid)


def write(p: dict, out_dir: Path) -> list:
    if out_dir.exists():
        if any(out_dir.iterdir()) and not (out_dir / "pack.mcmeta").is_file():
            raise ProgressionError("%s exists and is not a datapack; refusing to replace it" % out_dir)
        shutil.rmtree(out_dir)
    written = []
    for rel, text in files(p).items():
        target = out_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf8", newline="\n")
        written.append(rel)
    return sorted(written)


def report(p: dict, world: Path) -> int:
    """Which flags each player of a STOPPED world copy holds, read from its advancements files. Fails closed: a
    plan with no flags, or a world with no player advancements, has nothing to show and fails."""
    sys.path.insert(0, str(ROOT / "tools"))
    import runtime_guard
    world = runtime_guard.check(world, "read player advancements from")
    ns = p["namespace"]
    expected = [f["id"] for f in p["flags"]]
    found = sorted((world / "advancements").glob("*.json")) if (world / "advancements").is_dir() else []
    if not expected or not found:
        print("FAIL: %d flags planned, %d player advancement files in %s" % (len(expected), len(found), world))
        return 1
    for path in found:
        adv = json.loads(path.read_text(encoding="utf8"))
        held = [fid for fid in expected if adv.get("%s:flag/%s" % (ns, fid), {}).get("done")]
        # the first 8 characters of the file name only: enough to tell players apart, not an identity
        print("player %s: %d of %d flags%s" % (path.stem[:8], len(held), len(expected),
                                              (": " + ", ".join(held)) if held else ""))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", type=Path, metavar="WORLD",
                    help="print each player's flags from a stopped world copy instead of writing the pack")
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "progression.json")
    ap.add_argument("--series", help="override active_series (prestige)")
    ap.add_argument("--placements", type=Path, default=ROOT / "data" / "placements.json",
                    help="where the gym markers find their buildings")
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "datapacks" / "cobblers_progression")
    args = ap.parse_args(argv)
    try:
        p = plan(load(args.data), args.series, json.loads(args.placements.read_text(encoding="utf8")))
        if args.report:
            return report(p, args.report)
        written = write(p, args.out)
    except (ProgressionError, OSError, json.JSONDecodeError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    print("series %s: %d flags, %d waystones (%d unplaced), %d files -> %s"
          % (p["series"], len(p["flags"]), len(p["waystones"]), len(p["unplaced"]),
             len(written), args.out))
    if p["unplaced"]:
        print("unplaced: %s" % ", ".join(p["unplaced"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
