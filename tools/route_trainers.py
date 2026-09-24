#!/usr/bin/env python
"""The Route 1-3 trainers as Radical Cobblemon Trainers data: build/datapacks/cobblers_trainers.

From data/trainers.json (generated from docs/story/TRAINER_RULES.json) and data/route_trainers.json (where each one
stands, tools/route_events.py):

  data/rctmod/trainers/<id>.json                    the team: name, ai, battleRules, bag, team from the record's rct
                                                    payload. rctapi 0.16's TrainerModel reads name, ai, bag, team and
                                                    battleTheme (read from the jar, 2026-09-24); battleFormat is left
                                                    out (singles is the default), battleRules is rctmod's own key
  data/rctmod/mobs/trainers/single/<id>.json        who it is to rctmod: type normal, no series, never spawns naturally
                                                    (spawnWeightFactor 0), beaten once per player (maxTrainerDefeats 1),
                                                    its skin (textureResource: one of rctmod's own trainer textures, which
                                                    every client has) and, for the first trainer, eye contact
                                                    (forceBattleOnSight: the lesson it teaches)
  data/rctmod/dialogs/trainers/single/<id>.json     the record's three lines: pre-battle (on_battle_start), the player
                                                    won (on_battle_lost, and trainer_lost for every talk after), the
                                                    player lost (on_battle_won, trainer_won). rctmod picks one line per
                                                    key; each key has one
  data/rctmod/loot_table/trainers/single/<id>.json  empty: route battles give no item in this pass (the handoff)
  data/cobblers/advancement/trainer/<id>.json       the per-player defeat field quest.<id>.defeated, set only by the
                                                    player-win callback: rctmod's defeat_count trigger, which it fires
                                                    for the players on the winning side of a finished battle and never
                                                    on a loss or a forfeit (EXP-027). The North Bank Angler's also sets
                                                    quest.evt_viltri_north_bank.trainer_defeated.

Placement is not a function: tools/reapply.py (R17) forceloads each seat and runs
`rctmod trainer summon_persistent <id> <x> <y> <z>` over RCON once, unless a trainer already stands there.

  python tools/route_trainers.py [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "datapacks" / "cobblers_trainers"
NS = "cobblers"
EXTRA_FIELDS = {"route_02_shore_trainer_01": ["quest.evt_viltri_north_bank.trainer_defeated"]}
AFTER_WIN = {"route_02_shore_trainer_01": "The angler nods at the tackle box on the bank."}


def key(field):
    return "cobblers__" + field.replace(".", "__")


def load():
    t = json.loads((ROOT / "data" / "trainers.json").read_text(encoding="utf-8"))
    seats = json.loads((ROOT / "data" / "route_trainers.json").read_text(encoding="utf-8"))["trainers"]
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    fields = {f["id"] for f in prog["quest_fields"]}
    return {r["id"]: r for r in t["trainers"]}, seats, fields


def files():
    recs, seats, fields = load()
    out = {"pack.mcmeta": {"pack": {"pack_format": 48, "description": "Cobblers Route 1-3 trainers (tools/route_trainers.py)"}}}
    for s in seats:
        r = recs.get(s["id"])
        if r is None:
            raise SystemExit("data/route_trainers.json seats %s, which data/trainers.json does not have" % s["id"])
        tid, rct = r["id"], r["rct"]
        out["data/rctmod/trainers/%s.json" % tid] = {k: rct[k] for k in ("name", "ai", "battleRules", "bag", "team") if k in rct}
        mob = {"type": "normal", "series": [], "requiredDefeats": [], "optional": True, "maxTrainerWins": -1,
               "maxTrainerDefeats": 1, "battleCooldownTicks": 240, "spawnWeightFactor": 0,
               "biomeTagBlacklist": [], "biomeTagWhitelist": [], "textureResource": s["skin"]}
        if s.get("eye_contact"):
            mob.update({"forceBattleOnSight": True, "forceBattleMaxDistance": 8.0, "forceBattleLookTicks": 30,
                        "forceBattleMaxLevelDiff": 10})
        out["data/rctmod/mobs/trainers/single/%s.json" % tid] = mob
        d = r["dialogue_text"]
        line = lambda text: [{"text": text}]
        out["data/rctmod/dialogs/trainers/single/%s.json" % tid] = {
            "on_battle_start": line(d["pre"]), "on_battle_lost": line(d["player_win"]), "trainer_lost": line(d["player_win"]),
            "on_battle_won": line(d["player_loss"]), "trainer_won": line(d["player_loss"])}
        out["data/rctmod/loot_table/trainers/single/%s.json" % tid] = {"pools": []}
        setf = ["quest.%s.defeated" % tid] + EXTRA_FIELDS.get(tid, [])
        missing = [f for f in setf if f not in fields]
        if missing:
            raise SystemExit("%s would set undeclared fields %s (data/progression.json)" % (tid, missing))
        mol = "t.d = q.player.data(); %s q.player.save_data();" % " ".join("t.d.%s = 1;" % key(f) for f in setf)
        fn = ["# %s: this player won (rctmod defeat_count, winning side only)" % tid, 'runmolang "%s" @s' % mol]
        if tid in AFTER_WIN:
            fn.append('tellraw @s {"text":%s,"color":"gray","italic":true}' % json.dumps(AFTER_WIN[tid]))
        out["data/%s/function/trainers/won/%s.mcfunction" % (NS, tid)] = fn
        out["data/%s/advancement/trainer/%s.json" % (NS, tid)] = {
            "criteria": {"won": {"trigger": "rctmod:defeat_count", "conditions": {"trainer_ids": [tid], "count": 1}}},
            "rewards": {"function": "%s:trainers/won/%s" % (NS, tid)}}
    return out


def placements():
    """[(trainer id, (x, y, z), yaw)] for tools/reapply.py."""
    _recs, seats, _f = load()
    return [(s["id"], tuple(s["seat"]), s["yaw"]) for s in seats]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(OUT))
    a = p.parse_args(argv)
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    fs = files()
    for rel, content in fs.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(content) + "\n" if isinstance(content, list) else json.dumps(content, indent=2, ensure_ascii=False) + "\n"
        f.write_text(text, encoding="utf-8", newline="\n")
    print("wrote %d files for %d trainers to %s" % (len(fs), len(placements()), out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
