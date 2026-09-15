#!/usr/bin/env python
"""Generate the progression datapack from data/progression.json.

One flag is one advancement. A flag is the badge ledger entry, and it is also
the unlock for its town's waystone, so both read the same data. The pack:

  advancement/flag/<id>.json           the flag. Set by an RCT defeat, by the
                                       first tick (run_start) or by command (trigger)
  function/flag/<id>/granted           reward: re-sync this player's waystones
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
SET_BY_KINDS = {"trainer_defeat", "run_start", "trigger"}


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


def plan(doc: dict, series: str | None = None) -> dict:
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
        flags.append(entry)
    return {"namespace": ns, "series": active, "flags": flags,
            "waystones": waystones, "unplaced": sorted(unplaced)}


# ------------------------------------------------------------------ writing


def _flag_advancement(ns: str, flag: dict) -> dict:
    if flag["kind"] == "trainer_defeat":
        criteria = {"defeated": {"trigger": "rctmod:defeat_count",
                                 "conditions": {"trainer_ids": flag["trainer_ids"]}}}
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
        out["data/%s/function/flag/%s/granted.mcfunction" % (ns, flag["id"])] = \
            "function %s:navigation/reconcile\n" % ns

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
        lines.append("execute if entity %s in %s run waystones forget @s %d %d %d"
                     % (_has(ns, ws["flag"], False), ws["dimension"], x, y, z))
    out["data/%s/function/navigation/reconcile.mcfunction" % ns] = "\n".join(lines) + "\n"

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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "progression.json")
    ap.add_argument("--series", help="override active_series (prestige)")
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "datapacks" / "cobblers_progression")
    args = ap.parse_args(argv)
    try:
        p = plan(load(args.data), args.series)
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
