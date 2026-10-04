#!/usr/bin/env python
"""Every placed trainer as Radical Cobblemon Trainers data: build/datapacks/cobblers_trainers.

From data/trainers.json (generated from docs/story/TRAINER_RULES.json) and four seat sources:

  data/route_trainers.json      Routes 1-3, where each one stands (tools/route_events.py)
  data/late_route_trainers.json Routes 4-8's twenty-eight, seated by tools/late_route_trainers.py on the
                                same shoulder rule. Their records in data/trainers.json carry dialogue ids
                                that resolve nowhere, so their three lines are authored beside their seat,
                                the way Victory Road's are (lines_of below)
  data/mansion_guardians.json   the Gastly mansion's five Channeler guardians, record and seat together
  data/arena_trainers.json      Heaven's Arena's seven tier champions. UNSEATED since 2026-10-03 (the owner: "leave
                                current spire, but remove the trainer battles, have the middle just be hubs"):
                                each record says `seated: false` and keeps its old stand under `superseded_seat`;
                                the record is read for its team only, which tools/arena_runtime.py turns into the
                                rank-up exam it spawns per player. Nothing below is emitted for them now.
                                Until then: record and seat together, on the stands
                                tools/deep_city.py's arena_plan() reserves in derived/deep_city/plan.json
                                ("arena".tiers[n].stand, y16 to y118). PLAIN STANDALONE FIGHTS, by the owner's
                                decision of 2026-10-01: no series, no requiredDefeats, no tier gating at all,
                                because a player's level cap is derived from their next required trainer in
                                their series and the seriesless-gate path (EXP-A1) is unproven. They are the
                                first REPEATABLE seats: `repeatable: true` gives maxTrainerDefeats -1 and NO
                                Cooldown line in the cycle, which is the whole of "endless fights, real money"
                                (CobbleDollars pays every win by itself). See the file's own repeatability
                                block for the argument and what it is not verified to do
  data/vr_trainers.json         Victory Road's ten, on the stands tools/vr_caves.py carved along its walked
                                route. All ten records are in data/trainers.json; the tenth is the League
                                Examiner, chosen by the owner on 2026-10-01 over the Gate Warden this file
                                used to author beside the seat (kept there, decided against, emitted nowhere)
  data/hq_trainers.json         the Compact HQ tower's seven (2026-10-04), record and seat together like the
                                mansion guardians, on the floors tools/hq_tower.py builds inside the tower's shell
  data/gym_trainers.json        the eight gym leaders. No seat either: our own gym build sets
                                rctmod:trainer_spawner{TrainerIds:["kanto_brock"]} and the badge is awarded
                                for beating that id, so the id cannot be re-pointed and our roster reaches a
                                player only by overriding it. Emits the team and nothing else -- their
                                dialogue is Codex's to write. gym_08_giovanni's hold was cleared by the
                                owner on 2026-10-01 -- data/trainers.json gives him status 'authored',
                                blocked_by None and six Pokemon topping out at 55, his contract level -- so
                                all EIGHT leaders' teams now reach a player, where seven did before
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
                                                    battleTheme (read from the jar, 2026-09-24); battleRules is rctmod's own key.
                                                    An OVERRIDE (below) also writes battleFormat, because it replaces
                                                    upstream's whole file and would otherwise drop it
  data/rctmod/mobs/trainers/single/<id>.json        who it is to rctmod: type normal, no series, never spawns naturally
                                                    (spawnWeightFactor 0), beaten once per player (maxTrainerDefeats 1;
                                                    -1, documented as infinity, for a seat marked `repeatable`),
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
                                                      through -- EXCEPT for a seat marked `repeatable`, which gets
                                                      no Cooldown line at all (the seven arena champions: the
                                                      hold-off is the only thing that would refuse a rematch, so
                                                      dropping it IS the endless ladder). Those seats keep the home
                                                      line and the tag line. rctmod itself never refuses a rematch with a trainer
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
                 "league": "Take the room. I will be here.",
                 # the arena's tiers are repeatable, so this is never OUR hold-off talking: it is rctmod's own
                 # battleCooldownTicks (240, twelve seconds) in the moment after a fight either way
                 "arena": "Breathe. The stand is still here when you are ready."}
EXTRA_FIELDS = {"route_02_shore_trainer_01": ["quest.evt_viltri_north_bank.trainer_defeated"]}
AFTER_WIN = {"route_02_shore_trainer_01": "The angler nods at the tackle box on the bank."}


def key(field):
    return "cobblers__" + field.replace(".", "__")


def doc(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ who authors what
# data/trainers.json is the ROSTER -- who a trainer is and what it fights with. A seat file is the
# STAND -- where it stands and how it behaves standing there. The two are halves of one trainer, not
# rival authors, so the guard below is FIELD-level, not id-level.
#
# It was id-level until 2026-10-01, and that was right while it was true: Victory Road's tenth had no
# generated record at all, so data/vr_trainers.json carried a whole one beside its seat, and a record
# appearing in data/trainers.json for the same id could only mean two authors. #96 then generated all
# ten, git merged it CLEANLY because the two authors sit in DIFFERENT FILES, and the id-level guard
# fired on the only reading it had -- "re-authors" -- which stopped the whole pytest suite at
# collection. vr_trainers.json had not re-authored anything; it still owns the ten stands, and its yaw,
# faces, eye_contact, sight_distance, skin and per-stand rationale exist nowhere else.
#
# A seat file owns these, and the roster must not carry one of them:
STAND_FIELDS = frozenset({
    "seat", "yaw", "faces", "eye_contact", "sight_distance", "skin", "stand_index", "route_index",
    "route_progress", "climb_gained_blocks", "gap_from_previous_blocks", "unavoidable", "listed",
    "listed_off_walked_line", "moved_blocks", "walked_distance", "authored_distance", "shoulder",
    "why", "superseded_roster", "sets", "gates", "checkpoint", "room", "after_win",
    # the arena's stands: which tier floor it stands on, whether it may be refought endlessly (the Cooldown
    # line and maxTrainerDefeats), and which on_cooldown line it speaks. All three are how it behaves STANDING
    # THERE, so if data/trainers.json ever generates records for these seven, a copy of one of these in the
    # roster is two authors for one value and must fault rather than quietly win.
    "tier", "repeatable", "cooldown",
    # 2026-10-03: the arena's seven were unseated; whether a record stands anywhere, and the stand it used to have,
    # are stand facts too
    "seated", "superseded_seat",
})
# Fields a seat file may RESTATE for whoever reads the seat list, and never the value this tool uses:
# the roster's copy is read, the seat file's must match it exactly, and a drift apart is a fault.
ROSTER_ECHO = frozenset({"lesson", "trainer_order", "route", "name"})
# The one field with a declared precedence rather than one owner (see lines_of): the roster's wins when
# it has one, and the seat file's is the fallback for a record that has none. Kept, not emptied, after the
# 2026-10-01 deletion of Victory Road's ten dead sets: Routes 4-8's twenty-eight records carry
# dialogue_text {} -- the key is present and empty -- so those twenty-eight seats STILL hold the only
# lines those trainers have, and the fallback in lines_of() is what puts them in front of a player. The
# guard is what stops a seat-side set going dead unnoticed, which is how the ten came to be dead.
ROSTER_PRECEDENCE = frozenset({"dialogue_text"})


# [(trainer id, field)] where the roster has a value of its own AND the seat file's differs, so the seat
# file's is dead: filled by load(), warned about by main() only when non-empty.
#
# It used to be every divergence, empty roster value included, and that made the count it printed every
# run wrong: "38 superseded sets" counted Victory Road's ten, whose records really do carry text, TOGETHER
# WITH Routes 4-8's twenty-eight, whose records carry {} and whose seat-side lines lines_of() has always
# preferred and emitted. Twenty-eight live sets were reported as dead. An empty roster value is the
# fallback working as designed, not a supersession, so it is no longer counted -- and with the ten deleted
# the list is empty and a clean run says nothing (the owner, 2026-10-01: no count every run).
SUPERSEDED: list = []


def ownership(recs, entries, src):
    """Every field a seat file and the roster both author. Faults raise; the superseded are returned.

    Three ways a field can sit in both files and only one of them is legal silently. A STAND field in
    the roster, or any field outside these three sets in both, is two authors for one value: one of the
    two is dead and nothing says which. An echo that no longer matches is a drift. A precedence field
    is the designed case."""
    faults, superseded = [], []
    for e in entries:
        r = recs.get(e["id"])
        if r is None:
            continue              # the seat file carries the whole record (every mansion guardian)
        for f in sorted(set(e) & set(r) - {"id"}):
            if f in ROSTER_PRECEDENCE:
                # only a roster value that actually WINS supersedes: lines_of() falls back on a falsy one
                if r[f] and e[f] != r[f]:
                    superseded.append((e["id"], f))
            elif f in ROSTER_ECHO:
                if e[f] != r[f]:
                    faults.append((e["id"], f, "%s restates the roster's %s and no longer matches it"
                                               % (src, f)))
            elif f in STAND_FIELDS:
                faults.append((e["id"], f, "data/trainers.json carries %s, which the stand owns (%s)"
                                           % (f, src)))
            else:
                faults.append((e["id"], f, "%s and data/trainers.json both author %s" % (src, f)))
    if faults:
        joined = "\n".join("  %s %s: %s" % f for f in faults)
        raise SystemExit("two authors for one trainer field (%d):\n%s\n\nThe roster owns who a "
                         "trainer is; a seat file owns where it stands and how it behaves standing "
                         "there. Move the field to its owner -- do not delete the hand-authored side "
                         "(CLAUDE.md)." % (len(faults), joined))
    return superseded


def load():
    t = doc("trainers.json")
    seats = doc("route_trainers.json")["trainers"] + doc("late_route_trainers.json")["trainers"]
    dupe = sorted(i for i in {s["id"] for s in seats} if sum(1 for s in seats if s["id"] == i) > 1)
    if dupe:
        raise SystemExit("two seat files claim the same trainer: %s" % dupe)
    guards = doc("mansion_guardians.json")["trainers"]
    vr = doc("vr_trainers.json")["trainers"]
    arena = doc("arena_trainers.json")["trainers"]
    # the Compact HQ tower's seven (2026-10-04, data/hq_trainers.json): record and seat together, like the guardians
    hq = doc("hq_trainers.json")["trainers"]
    prog = doc("progression.json")
    fields = {f["id"] for f in prog["quest_fields"]}
    recs = {r["id"]: r for r in t["trainers"]}
    del SUPERSEDED[:]
    for name, entries in (("data/route_trainers.json", doc("route_trainers.json")["trainers"]),
                          ("data/late_route_trainers.json", doc("late_route_trainers.json")["trainers"]),
                          ("data/mansion_guardians.json", guards),
                          ("data/vr_trainers.json", vr),
                          ("data/arena_trainers.json", arena),
                          ("data/hq_trainers.json", hq)):
        SUPERSEDED.extend(ownership(recs, entries, name))
    # a seat file whose trainer has no generated record carries the record itself: the five mansion
    # guardians, the arena's seven, and before #96 Victory Road's tenth. ownership() has already proved it
    # clashes with nothing, so this adds rather than overwrites
    for e in guards + vr + arena + hq:
        if "rct" in e and e["id"] not in recs:
            recs[e["id"]] = e
    # The arena's seven are RECORDS, not seats, since 2026-10-03 (the owner: "leave current spire, but remove the
    # trainer battles, have the middle just be hubs"). Each carries `seated: false` and its old stand under
    # `superseded_seat`; its team is the rank-up exam tools/arena_runtime.py spawns per challenger. So they stay in
    # `recs` above and are never seated, gated or cycled here. A record with `seat` would be seated again, and one
    # with `seated: false` AND a `seat` is a contradiction that fails rather than guesses.
    both = [e["id"] for e in arena if e.get("seated") is False and "seat" in e]
    if both:
        raise SystemExit("data/arena_trainers.json: %s say seated false and still carry a seat" % both)
    arena_seated = [e for e in arena if "seat" in e and e.get("seated", True)]
    return recs, seats + guards + vr + arena_seated + hq, fields


def overrides():
    """[(our record, the upstream rctmod id it overrides, the entry, the file it came from)].

    The trainers who stand in somebody else's template and whose spawner names an upstream id we cannot
    re-point: the Elite Four and the Champion (data/league_trainers.json) and the eight gym leaders
    (data/gym_trainers.json). One mechanism, two files, for the same reason -- the id is load-bearing.
    Re-pointing a gym's spawner would break its badge: data/gym_buildings/gym1.json records that a
    persistent kanto_brock anywhere awards the badge (verified on staging 2026-09-24), and
    data/progression.json binds gym1_cleared and the first-win rewards to the same id.

    An entry marked "held" is skipped with its reason, and the reason is printed rather than trusted.
    Nothing is held as of 2026-10-01: gym_08_giovanni's hold quoted an empty team and status 'held' that
    no longer exist -- the format question is settled (singles), #96 generated the roster, and he carries
    six Pokemon at 52-55 with blocked_by None and an ace at exactly his contract level -- so the owner
    cleared it and all thirteen overrides emit. The mechanism stays: a leader can be held again, and a
    held leader must be loud rather than missing.
    """
    recs, _seats, _f = load()
    out, held = [], []
    for name in ("league_trainers.json", "gym_trainers.json"):
        for e in doc(name)["trainers"]:
            r = recs.get(e["id"])
            if r is None:
                raise SystemExit("data/%s names %s, which data/trainers.json does not have" % (name, e["id"]))
            if e.get("held"):
                held.append((e["id"], e.get("held_because", "held")))
                continue
            if not r.get("team"):
                raise SystemExit("data/%s would override %s with %s, whose team in data/trainers.json is empty"
                                 % (name, e["upstream_trainer_id"], e["id"]))
            # the contract is checked, never applied: a leader whose roster disagrees with
            # generation_contract.gym_ace_levels is a finding for docs/story/TRAINER_RULES.json, and this
            # refuses to emit rather than quietly adjusting a level
            if e.get("contract_ace_level") is not None:
                top = max(m["level"] for m in r["team"])
                if top != e["contract_ace_level"]:
                    raise SystemExit("%s tops out at level %d, but generation_contract.gym_ace_levels says %d "
                                     "for gym %s. Fix it in docs/story/TRAINER_RULES.json, not here."
                                     % (e["id"], top, e["contract_ace_level"], e.get("order")))
            out.append((r, e["upstream_trainer_id"], e, name))
    return out, held


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
        # maxTrainerDefeats: -1 is documented as infinity. It does nothing for a trainer we place
        # (couldBattleAgainst returns true for a persistent trainer before it checks who beat it), so this
        # states the intent in the data and is the DOCUMENTED path should a tier ever move to a spawner block.
        # `series` and `requiredDefeats` stay empty for every seat, the arena's seven included: the owner's
        # 2026-10-01 decision is plain standalone fights, because the level cap is derived from the next
        # required trainer in the player's series and EXP-A1 (whether requiredDefeats gates a seriesless
        # trainer) is unproven. Authoring a gate here would risk hijacking every level cap in the game.
        mob = {"type": "normal", "series": [], "requiredDefeats": [], "optional": True, "maxTrainerWins": -1,
               "maxTrainerDefeats": -1 if s.get("repeatable") else 1,
               "battleCooldownTicks": 240, "spawnWeightFactor": 0,
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
            "on_cooldown": line(COOLDOWN_LINE[s.get("cooldown") or ("guardian" if "sets" in r else "route")])}
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
    cycle += leader_cycle_lines()
    if undeclared:
        raise SystemExit("data/progression.json quest_fields does not declare %d field(s):\n%s"
                         % (len(undeclared), "\n".join("  %s sets %s" % (t, f) for t, f in undeclared)))
    # the League's five and the eight gym leaders: the team at the upstream id the spawner is locked to, and
    # the lines only where the entry carries them (the League's are authored beside their entry; the leaders'
    # are Codex's to write, so upstream's lines stand). No mob file (the spawner owns how each is spawned), no
    # loot table (upstream_neutralised empties them and first_win_rewards pays instead), no advancement (every
    # gymN_cleared and champion_cleared flag already fires from the upstream id through progression_pack), no
    # cycle and no placement: none of these is summoned at a seat.
    over, _held = overrides()
    for rec, upstream, entry, _src in over:
        rct = rec["rct"]
        over_file = {k: rct[k] for k in ("name", "ai", "battleRules", "bag", "team") if k in rct}
        # battleFormat, from the record and not inherited: THIS FILE REPLACES UPSTREAM'S WHOLE FILE, so a key we
        # do not write is a key the game loses. All twelve read GEN_9_SINGLES in COBBLEVERSE-RCT-DP-v20 (checked
        # 2026-09-30) and all twelve were silently dropping it. See battle_format_why in the two data files.
        over_file["battleFormat"] = entry.get("battle_format", "GEN_9_SINGLES")
        out["data/rctmod/trainers/%s.json" % upstream] = over_file
        if not entry.get("dialogue_text"):
            continue
        d = lines_of(rec, entry)
        ln = lambda text: [{"text": text}]
        out["data/rctmod/dialogs/trainers/single/%s.json" % upstream] = {
            "on_battle_start": ln(d["pre"]), "on_battle_lost": ln(d["player_win"]), "trainer_lost": ln(d["player_win"]),
            "on_battle_won": ln(d["player_loss"]), "trainer_won": ln(d["player_loss"]),
            "on_cooldown": ln(COOLDOWN_LINE[entry.get("cooldown", "league")])}
    out["data/%s/function/trainers/cycle.mcfunction" % NS] = cycle
    out["data/%s/function/trainers/tick.mcfunction" % NS] = [
        "scoreboard players add #clock cobblers_trainers 1",
        "execute if score #clock cobblers_trainers matches %d.. run function %s:trainers/cycle" % (PERIOD, NS)]
    out["data/%s/function/trainers/load.mcfunction" % NS] = ["scoreboard objectives add cobblers_trainers dummy"]
    out["data/minecraft/tags/function/tick.json"] = {"values": ["%s:trainers/tick" % NS]}
    out["data/minecraft/tags/function/load.json"] = {"values": ["%s:trainers/load" % NS]}
    return out


def leader_cycle_lines():
    """The eight gym leaders' hold-off, keyed on their badge flag instead of a quest field.

    WHY THEY WERE MISSING. The cycle is built from placements(), and a gym leader is not placed by us:
    its gym's own `rctmod:trainer_spawner` spawns it. So the cooldown covered the 28 trainers we seat -
    13 route, 5 mansion, 10 Victory Road - and NONE of the eight leaders, and CLAUDE.md's standing
    limitation ("rctmod never refuses a rematch with a placed trainer") applied to all of them with
    nothing against it. The owner demonstrated it on 2026-09-30: beat Brock, then started him again by
    sending a Pokemon at him.

    WHAT A REMATCH COSTS, measured rather than feared: nothing in items. The per-win rctmod loot table
    we write for each leader is {"pools": []}, deliberately emptied (data/progression.json
    upstream_neutralised), and the badge and the TMs come from a cobblers:first_win table that fires
    once. What it does give is battle XP, and data/level_cap.json caps CATCHING, not battling - so a
    leader who can be refought at will is a level-cap bypass, and stops being a gate.

    The test is the badge advancement, not a quest field: gymN_cleared already exists, is already bound
    to the leader's upstream id, and is what the rest of progression reads. That also means neither a
    molang callback nor a tag is needed here - the player selector tests the advancement directly.

    The same INTERIM caveat as the seated trainers (see cycle_lines): Cooldown is entity NBT on a
    shared trainer, so it cannot be held per player. A player holding the badge is protected; an
    unbeaten partner beside them may have to start the fight by interacting.
    """
    seats = []
    for f in sorted((ROOT / "data" / "gym_buildings").glob("gym*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        lead = doc.get("leader") or {}
        seats.append((doc["id"], lead.get("id"), lead.get("spawner"), lead.get("flag")))
    # Misty's gym 2 is the one surviving CARVED interior, so it has no data/gym_buildings record and was
    # the one leader this loop still missed. Her spawner is the gym template's own, recorded in
    # data/gym_interiors.json as `expect_spawner_at` - a measurement of where the donor puts it, which is
    # exactly what this needs.
    for g in json.loads((ROOT / "data" / "gym_interiors.json").read_text(encoding="utf-8"))["gyms"]:
        if not g.get("built"):
            continue
        lead = g.get("leader") or {}
        if lead.get("id") and lead.get("expect_spawner_at"):
            seats.append((g["id"], lead["id"], lead["expect_spawner_at"], lead.get("flag")))
    out = []
    for gid, tid, seat, flag in sorted(seats):
        if not tid or not seat:
            continue
        flag = flag or "gym%s_cleared" % gid.replace("gym", "")
        doc = {"id": gid}
        x, y, z = seat
        me = '@e[type=rctmod:trainer,x=%d.5,y=%d,z=%d.5,distance=..24,nbt={TrainerId:"%s"}]' % (x, y, z, tid)
        out += ["# %s (%s), the leader: no rematch once the badge is held" % (tid, doc["id"]),
                "execute as %s at @s if entity @a[distance=..9.0,advancements={%s:flag/%s=true}] "
                "run data merge entity @s {Cooldown:40}" % (me, NS, flag)]

    # THE SAME GAP, FIVE MORE TRAINERS. Found by the 2026-09-30 sweep the owner asked for, straight after
    # the leaders: the Elite Four and the Champion are overrides at the `kanto_league` template's OWN
    # spawners, so like the leaders they are not in placements() and had no hold-off either. The Champion
    # matters most - champion_cleared gates the endgame, and a refightable Blue is a level-cap bypass at
    # the top of the ladder where the cap is loosest.
    #
    # Two things differ from a gym. There is no per-trainer seat: the spawners are inside the template and
    # their coordinates are not ours to know, so each selector is scoped to the League lot
    # (placements.json anchors.league_building) rather than to a cell. And the beaten test is UPSTREAM's own
    # defeat advancement, which exists in COBBLEVERSE-DP-v31 (data/cobbleverse/advancement/trainer/kanto/
    # defeat_elite_lorelei.json and its four siblings, read from the installed zip) - we do not need to
    # mint a flag for something Cobbleverse already grants.
    lot = None
    for a in (((json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
                .get("settlements") or {}).get("league") or {}).get("plan", {}).get("anchors") or []):
        if a.get("id") == "league_building" and a.get("rect"):
            lot = (a["rect"], a.get("level"))
    if lot:
        (x0, z0, x1, z1), level = lot
        cx, cz = (x0 + x1) // 2, (z0 + z1) // 2
        reach = max(x1 - x0, z1 - z0) // 2 + 12
        for e in json.loads((ROOT / "data" / "league_trainers.json").read_text(encoding="utf-8"))["trainers"]:
            tid = e.get("upstream_trainer_id")
            adv = e.get("beaten_advancement") or "cobbleverse:trainer/kanto/defeat_%s" % (
                "champion_blue" if "champion" in (e.get("id") or "") else
                "elite_" + (e.get("id") or "").split("_")[-1])
            if not tid:
                continue
            me = ('@e[type=rctmod:trainer,x=%d.5,y=%d,z=%d.5,distance=..%d,nbt={TrainerId:"%s"}]'
                  % (cx, level or 88, cz, reach, tid))
            out += ["# %s, the League: no rematch once upstream's defeat advancement is held" % tid,
                    "execute as %s at @s if entity @a[distance=..9.0,advancements={%s=true}] "
                    "run data merge entity @s {Cooldown:40}" % (me, adv)]
    return out


def cycle_lines(tid, seat, field):
    """One trainer's part of the cycle: its seat, its players' tags from their field, its cooldown.

    A seat marked `repeatable` gets the first two and NOT the cooldown: our Cooldown merge is the only
    thing in the game that refuses a rematch with a trainer we placed, so a seat that wants endless
    rematches wants exactly this line gone (data/arena_trainers.json repeatability). The home line stays
    because knockback still moves a champion pinned at movement speed 0, and the tag line stays because
    the per-player defeat field is still the record of having taken that tier -- a future prize or lift
    condition reads it, and it is set on the first win only."""
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
            ] + ([] if seat.get("repeatable") else [
            "execute as %s at @s if entity @a[distance=..%s,tag=%s] run data merge entity @s {Cooldown:40}"
            % (me, near, tag)]) + gate_lines(tid, seat, tag)


def gate_lines(tid, seat, tag):
    """Heaven's Arena's climb (data/arena_trainers.json gate_why): a player in the stair shaft above this tier who
    has not beaten its champion is told so and set back on this tier's floor beside the stair's exit. Creative and
    spectator players pass. Down is never stopped: the shaft is above the floor the player is put on."""
    g = seat.get("gate")
    if not g:
        return []
    x, y, z, dx, dy, dz = g["box"]
    lx, ly, lz, yaw = g["landing"]
    who = "@a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d,tag=!%s,gamemode=!creative,gamemode=!spectator]" % (
        x, y, z, dx, dy, dz, tag)
    say = {"text": "Beat %s on this floor to climb to %s." % (seat.get("display_name", tid), g["to"]), "color": "gold"}
    return ["title %s actionbar %s" % (who, json.dumps(say)),
            "tp %s %s %s %s %s 0" % (who, lx, ly, lz, yaw)]


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
    over, held = overrides()
    print("wrote %d files for %d seated trainers and %d upstream-id overrides to %s"
          % (len(fs), len(placements()), len(over), out))
    for tid, why in held:
        print("  held, nothing emitted: %s -- %s" % (tid, why.split(". ")[0] + "."))
    # A clean run says nothing here. SUPERSEDED is empty while no seat file holds a dialogue_text the
    # roster also has text for: Victory Road's ten were deleted on 2026-10-01 and Routes 4-8's
    # twenty-eight are the only lines their trainers have, not superseded ones. It is kept rather than
    # removed because what it catches is a value that is dead and silent -- how the ten came to be dead
    # across a clean merge nobody could see. If this ever prints, the named seat file's text reaches no
    # player and one of the two sides should go.
    byf = {}
    for tid, f in SUPERSEDED:
        byf.setdefault(f, []).append(tid)
    for f, ids in sorted(byf.items()):
        print("  WARNING: %d seat-file %s set(s) are DEAD -- the roster has its own and that is what is "
              "emitted: %s%s" % (len(ids), f, ", ".join(sorted(ids)[:4]), " ..." if len(ids) > 4 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
