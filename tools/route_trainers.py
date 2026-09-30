#!/usr/bin/env python
"""Every placed trainer as Radical Cobblemon Trainers data: build/datapacks/cobblers_trainers.

From data/trainers.json (generated from docs/story/TRAINER_RULES.json) and four seat sources:

  data/route_trainers.json      Routes 1-3, where each one stands (tools/route_events.py)
  data/mansion_guardians.json   the Gastly mansion's five Channeler guardians, record and seat together
  data/vr_trainers.json         Victory Road's ten, on the stands tools/vr_caves.py carved along its walked
                                route; the tenth (the Gate Warden) carries its own record beside its seat,
                                because data/trainers.json is generated and holds only nine
  data/league_trainers.json     the Elite Four and the Champion. These have no seat: Cobbleverse's
                                kanto_league template already carries five rctmod:trainer_spawner blocks
                                locked to kanto_league_lorelei/_bruno/_agatha/_lance and kanto_champion_blue
                                (data/structures.json, docs/world-building/STRUCTURE_INVENTORY.md), so our
                                five authored teams reach a player by overriding those upstream ids' team and
                                dialogue at the upstream path (.claude/rules/datapacks.md), the way
                                data/progression.json upstream_neutralised already overrides their loot
                                tables. Nothing else of theirs is overridden: the mob file stays upstream's
                                so its spawner keeps working, and they are absent from placements() because
                                there is no seat for reapply to summon at.

A seated trainer gets:

  data/rctmod/trainers/<id>.json                    the team: name, ai, battleRules, bag, team from the record's rct
                                                    payload. rctapi 0.16's TrainerModel reads name, ai, bag, team and
                                                    battleTheme (read from the jar, 2026-09-24); battleFormat is left
                                                    out (singles is the default), battleRules is rctmod's own key
  data/rctmod/mobs/trainers/single/<id>.json        who it is to rctmod: type normal, no series, never spawns naturally
                                                    (spawnWeightFactor 0), beaten once per player (maxTrainerDefeats 1),
                                                    its skin (textureResource: one of rctmod's own trainer textures, which
                                                    every client has) and, for the first trainer, eye contact
                                                    (forceBattleOnSight: the lesson it teaches; every mansion
                                                    guardian too, so each room is a fight before it is a puzzle,
                                                    at its own sight_distance: the sight check passes through walls)
  data/rctmod/dialogs/trainers/single/<id>.json     the record's three lines: pre-battle (on_battle_start), the player
                                                    won (on_battle_lost, and trainer_lost for every talk after), the
                                                    player lost (on_battle_won, trainer_won). rctmod picks one line per
                                                    key; each key has one
  data/rctmod/loot_table/trainers/single/<id>.json  empty: route battles give no item in this pass (the handoff)
  data/cobblers/advancement/trainer/<id>.json       the per-player defeat field quest.<id>.defeated, set only by the
                                                    player-win callback: rctmod's defeat_count trigger, which it fires
                                                    for the players on the winning side of a finished battle and never
                                                    on a loss or a forfeit (EXP-027). The North Bank Angler's also sets
                                                    quest.evt_viltri_north_bank.trainer_defeated. A guardian sets
                                                    only the fields its record lists (`sets`: its room's guard field,
                                                    which gates the room's puzzle)

  data/cobblers/function/trainers/cycle.mcfunction  every 10 ticks, for each placed trainer (#minecraft:tick):
                                                    - back to its seat when a battle's knockback moved it (pinned at
                                                      movement speed 0, which knockback ignores);
                                                    - each player near it gets tag cobblers_beat_<id> exactly when
                                                      their own defeat field is set (the field stays the truth);
                                                    - while only players who have beaten it are near, a short
                                                      Cooldown, which rctmod's canBattleAgainst refuses to battle
                                                      through. rctmod itself never refuses a rematch with a trainer
                                                      placed by summon_persistent: couldBattleAgainst returns true
                                                      for a persistent trainer before checking who beat it, and for
                                                      the others that memory (TrainerMob.winsAndDefeats) is never
                                                      saved (rctmod 0.19.0-beta bytecode; the owner re-battled a
                                                      persistent Brock at once, and Hope across a restart,
                                                      2026-09-24). maxTrainerDefeats does nothing for ours.

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
PERIOD = 10
COOLDOWN_LINE = {"guardian": "Leave me be a moment.", "route": "Let me catch my breath.",
                 "league": "Take the room. I will be here."}
EXTRA_FIELDS = {"route_02_shore_trainer_01": ["quest.evt_viltri_north_bank.trainer_defeated"]}
AFTER_WIN = {"route_02_shore_trainer_01": "The angler nods at the tackle box on the bank."}


def key(field):
    return "cobblers__" + field.replace(".", "__")


def doc(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def load():
    t = doc("trainers.json")
    seats = doc("route_trainers.json")["trainers"]
    guards = doc("mansion_guardians.json")["trainers"]
    vr = doc("vr_trainers.json")["trainers"]
    prog = doc("progression.json")
    fields = {f["id"] for f in prog["quest_fields"]}
    recs = {r["id"]: r for r in t["trainers"]}
    clash = sorted(g["id"] for g in guards if g["id"] in recs)
    if clash:
        raise SystemExit("data/mansion_guardians.json reuses trainer ids from data/trainers.json: %s" % clash)
    recs.update({g["id"]: g for g in guards})
    # Victory Road: nine of the ten are seats only and keep the record data/trainers.json generated for them;
    # the tenth carries its own record beside its seat, as a mansion guardian does
    for e in vr:
        if "rct" not in e:
            continue
        if e["id"] in recs:
            raise SystemExit("data/vr_trainers.json re-authors %s, which data/trainers.json already has" % e["id"])
        recs[e["id"]] = e
    return recs, seats + guards + vr, fields


def league():
    """[(our record, the upstream rctmod id it overrides, the seat entry)] for the Elite Four and the Champion."""
    recs, _seats, _f = load()
    out = []
    for e in doc("league_trainers.json")["trainers"]:
        r = recs.get(e["id"])
        if r is None:
            raise SystemExit("data/league_trainers.json names %s, which data/trainers.json does not have" % e["id"])
        out.append((r, e["upstream_trainer_id"], e))
    return out


def lines_of(rec, seat):
    """The three dialogue lines: the record's own text, or the seat file's when the record has only ids.

    data/trainers.json carries dialogue_text for Routes 1-3 only; for Victory Road and the League it carries
    dialogue ids (dlg_*) that resolve nowhere yet (data/dialogue.json has none of them, 2026-09-30, and the
    generation_contract calls them 'campaign metadata; RCT sidecars require a future compiler'). The seat file
    is where their text is authored until that compiler exists."""
    d = rec.get("dialogue_text") or (seat or {}).get("dialogue_text")
    if not d:
        raise SystemExit("%s has no dialogue_text in data/trainers.json or in its seat file" % rec["id"])
    return d


def files():
    recs, seats, fields = load()
    out = {"pack.mcmeta": {"pack": {"pack_format": 48,
                                    "description": "Cobblers placed trainers: Routes 1-3, the mansion guardians, "
                                                   "Victory Road's ten and the League's five "
                                                   "(tools/route_trainers.py)"}}}
    cycle = ["scoreboard players set #clock cobblers_trainers 0",
             "# each placed trainer: home, its players' beaten tags (from their own fields), and no rematch for them"]
    # every undeclared field, not just the first: one run should name the whole list to add to data/progression.json
    undeclared = []
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
            mob.update({"forceBattleOnSight": True, "forceBattleMaxDistance": float(s.get("sight_distance", 8.0)),
                        "forceBattleLookTicks": 30,
                        "forceBattleMaxLevelDiff": 10})
        out["data/rctmod/mobs/trainers/single/%s.json" % tid] = mob
        d = lines_of(r, s)
        line = lambda text: [{"text": text}]
        out["data/rctmod/dialogs/trainers/single/%s.json" % tid] = {
            "on_battle_start": line(d["pre"]), "on_battle_lost": line(d["player_win"]), "trainer_lost": line(d["player_win"]),
            "on_battle_won": line(d["player_loss"]), "trainer_won": line(d["player_loss"]),
            # what it says while on cooldown: after a battle either way, and to a player who has beaten it (cycle)
            "on_cooldown": line(COOLDOWN_LINE["guardian" if "sets" in r else "route"])}
        out["data/rctmod/loot_table/trainers/single/%s.json" % tid] = {"pools": []}
        setf = r["sets"] if "sets" in r else ["quest.%s.defeated" % tid] + EXTRA_FIELDS.get(tid, [])
        undeclared += [(tid, f) for f in setf if f not in fields]
        mol = "t.d = q.player.data(); %s q.player.save_data();" % " ".join("t.d.%s = 1;" % key(f) for f in setf)
        fn = ["# %s: this player won (rctmod defeat_count, winning side only)" % tid, 'runmolang "%s" @s' % mol,
              "tag @s add cobblers_beat_%s" % tid]
        after = r.get("after_win") or AFTER_WIN.get(tid)
        if after:
            fn.append('tellraw @s {"text":%s,"color":"gray","italic":true}' % json.dumps(after))
        out["data/%s/function/trainers/won/%s.mcfunction" % (NS, tid)] = fn
        out["data/%s/advancement/trainer/%s.json" % (NS, tid)] = {
            "criteria": {"won": {"trigger": "rctmod:defeat_count", "conditions": {"trainer_ids": [tid], "count": 1}}},
            "rewards": {"function": "%s:trainers/won/%s" % (NS, tid)}}
        cycle += cycle_lines(tid, s, setf[0])
    if undeclared:
        raise SystemExit("data/progression.json quest_fields does not declare %d field(s):\n%s"
                         % (len(undeclared), "\n".join("  %s sets %s" % (t, f) for t, f in undeclared)))
    # the League's five: the team and the lines only, at the upstream id the template's spawner is locked to.
    # No mob file (upstream's spawner owns how each is spawned), no loot table, no advancement (champion_cleared
    # already fires from kanto_champion_blue through tools/progression_pack.py), no cycle and no placement:
    # these five are not summoned at a seat, they stand where Cobbleverse's template puts them.
    for rec, upstream, entry in league():
        rct = rec["rct"]
        out["data/rctmod/trainers/%s.json" % upstream] = {k: rct[k] for k in
                                                          ("name", "ai", "battleRules", "bag", "team") if k in rct}
        d = lines_of(rec, entry)
        ln = lambda text: [{"text": text}]
        out["data/rctmod/dialogs/trainers/single/%s.json" % upstream] = {
            "on_battle_start": ln(d["pre"]), "on_battle_lost": ln(d["player_win"]), "trainer_lost": ln(d["player_win"]),
            "on_battle_won": ln(d["player_loss"]), "trainer_won": ln(d["player_loss"]),
            "on_cooldown": ln(COOLDOWN_LINE["league"])}
    out["data/%s/function/trainers/cycle.mcfunction" % NS] = cycle
    out["data/%s/function/trainers/tick.mcfunction" % NS] = [
        "scoreboard players add #clock cobblers_trainers 1",
        "execute if score #clock cobblers_trainers matches %d.. run function %s:trainers/cycle" % (PERIOD, NS)]
    out["data/%s/function/trainers/load.mcfunction" % NS] = ["scoreboard objectives add cobblers_trainers dummy"]
    out["data/minecraft/tags/function/tick.json"] = {"values": ["%s:trainers/tick" % NS]}
    out["data/minecraft/tags/function/load.json"] = {"values": ["%s:trainers/load" % NS]}
    return out


def cycle_lines(tid, seat, field):
    """One trainer's part of the cycle: its seat, its players' tags from their field, its cooldown."""
    x, y, z = seat["seat"]
    near = max(float(seat.get("sight_distance", 8.0)), 6.0) + 1
    tag = "cobblers_beat_%s" % tid
    me = '@e[type=rctmod:trainer,x=%d.5,y=%d,z=%d.5,distance=..24,nbt={TrainerId:"%s"}]' % (x, y, z, tid)
    home = '@e[type=rctmod:trainer,x=%d.5,y=%d,z=%d.5,distance=..24,nbt={TrainerId:"%s",InBattle:0b}]' % (x, y, z, tid)
    mol = ("t.d = q.player.data(); (t.d.%s == 1) ? { q.run_command('tag ' + q.player.uuid + ' add %s'); } : "
           "{ q.run_command('tag ' + q.player.uuid + ' remove %s'); };" % (key(field), tag, tag))
    return ["# %s" % tid,
            "execute as %s positioned %d.5 %d %d.5 unless entity @s[distance=..0.75] run tp @s %d.5 %d %d.5" % (home, x, y, z, x, y, z),
            'execute positioned %d.5 %d %d.5 as @a[distance=..%s] run runmolang "%s" @s' % (x, y, z, near, mol),
            # INTERIM (the owner, 2026-09-29). The hold-off fires whenever ANY player near has beaten this trainer.
            # It used to require that EVERY player near had beaten it (`unless entity @a[...,tag=!<tag>]`), so a pair
            # at mixed progress got no cooldown at all and the one who had already won was dragged back into a forced
            # rematch while their partner fought. `Cooldown` is entity NBT on a shared trainer, so it cannot be held
            # per player: one of the two has to give. The owner's call is that being dragged into a fight you already
            # won is worse than having to right-click one you have not, so the beaten player is protected and the
            # unbeaten partner may have to start the fight by interacting while their friend stands there.
            # The real fix is per-player trainers through the scene runtime (docs/STATE.md), gated on EXP-034.
            "execute as %s at @s if entity @a[distance=..%s,tag=%s] run data merge entity @s {Cooldown:40}"
            % (me, near, tag)]


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
    print("wrote %d files for %d seated trainers and %d League overrides to %s"
          % (len(fs), len(placements()), len(league()), out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
