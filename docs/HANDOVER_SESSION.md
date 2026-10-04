# Handover: the 2026-10-04 overnight build (session a292b1c5)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file. **The owner's morning report is
`docs/MORNING_REPORT_2026-10-04.md`**: what is in the world with coordinates, the review list, what is blocked on them,
and where to stand for Giovanni. `docs/REVIEW_2026-10-02.md` (items 1-72) lists every call made and every defect
recorded and not chased; read it before reversing anything.

## 1. The branch

- **`build/2026-10-04-placement`**, stacked on #117 (`build/2026-10-03-towns`), itself on #116 and #115 (all OPEN at
  the time of writing; re-read heads before quoting: `git fetch --prune; gh pr view <N> --json headRefOid`). One draft
  PR for this branch against `build/2026-10-03-towns`; its branch is frozen once reported.
- Delete when convenient: every `worktree-agent-*` branch (all merged here).

## 2. Where it stopped

- **Done and verified:** the full prepare (157 jobs, 0 problems), install, `--only R9S,R9SX,R9HQ,R9SF,R9MD,R9MB,R9FS,
  R9E,R13,R16C` then `--only R16G,R15,R17,R17M,R18HQ,R18FS`, restart, the world checks (STATE "Latest applies").
- **R16C's verify was fixed AFTER the run (bda1fbb)**, so `build/prepare_stamp.json` predates it: the next install or
  run will ask for a fresh prepare. Expected, not a fault.
- **Server UP** (staging, started detached from the server dir; `level-name` is the LIVE world), `max-tick-time=60000`.
  The coordination lock is released at the end of this session.
- `cobblers_test` (the Giovanni setup) sits in the staging world's datapacks by hand; delete it once the owner has
  fought him.
- Next, in order: the owner's answers to the morning report's section 4; then 3a below.

## 3. What waits on the owner

The morning report's section 4 (twelve items, the Nether question first) and the Giovanni fight (section 1).

## 3a. The next session's job (the owner, 2026-10-03, approved: about 25-30M, a fresh session)

Two items, after the tour. Same rule as the overnight: record defects, do not chase them.

1. **Town squares and traders.** "Does it have a middle" is the MAIN question: the owner expects several towns to have
   none (the character pass dressed them; the squares were never built). Survey every town first (read-only agent):
   middle or not, stalls, traders, and somewhere to spend money. Then builders give each town a market square or civic
   centre, extend trader stock per town the way the backpack ladder was built (reading as the place), and every town
   gets somewhere a player spends money. Independent audit per unit; one batched apply.
2. **More ambient Pokemon per town.** Cap approved in principle: 2 carriers, 1-2 followers, ~10 idle per town --
   ADJUSTED TO THE FRAME-RATE TEST (the tick is not the constraint: docs/mechanics/TOWN_TICK_BUDGET.md 3.5, the old
   2+4 cap is 0.12% of a tick). Most should be idle (sleeping on a roof, sitting by a door, following a kid), not
   working. **Check the sleeping and sitting poses in game before building around them**: "lying still on a roof" is
   a worse feature the owner would rather know about now. Results of the frame-rate and pose tests run during the
   tour are recorded below if they ran.

3. **Heaven's Arena, redirected (the owner, on the tour, 2026-10-03, looking at the map):** "Heaven's Arena wasn't
   supposed to be the hub of the city like this, it was meant to go in the slot next to it: the empty space in the
   north of the Deep particularly. Heaven's Arena should be a battle zone where a player can go in and always find a
   cool battle or gauntlet to match up against. Early levels will be single battles, then transition into more back to
   back. It should be a small tower that becomes a large dome sort of place with several fighting venues inside the
   main place; each player will have their own progress and their opponent will be spawned in front of them. We might
   need to make a list of fights a player can get."
   So, in order: (a) MEASURE the empty north of the Deep (what it is, its extent and floor y, what must stay clear:
   the mouth plaza and the Victory Road tunnel are the known keep-clears, HEAVENS_ARENA.md site C); (b) RESEARCH the
   mechanism -- an opponent spawned per player in front of them with per-player progress: rctmod cannot hold a
   per-player opponent (docs/research/notes/rct-arena-capabilities.md); candidates are Cobblemon 1.8 NPCs with party
   pools spawned per player, or the scene runtime's per-player trainers (EXP-034) -- a small proof before building
   (principle 20); (c) DESIGN the fight list (trainer-balance-designer): single battles early, back-to-back gauntlets
   later, banded to the level caps; the seven authored tier champions (data/arena_trainers.json) are its first
   material; (d) the site design: a small tower opening into a dome with several venues. The schema-2 halls stand at
   the city's hub (3609, 3249) in staging now; what the hub goes back to (the Core spire, build_spire_ring without
   `arena`, is the precedent) is part of (d).

   **Decided on the tour (the owner, 2026-10-03):** the dome goes on **site A, centre (3584, 3171), radius 40**
   (docs/world-building/ARENA_SITE_NORTH.md; "it makes more sense"; it lengthens the walk to Victory Road by 34). The
   halls at the hub (3609, 3249) **stay standing but lose their trainer battles**: "leave current spire, but remove the
   trainer battles, have the middle just be hubs or something" (a non-battle hub). The mechanism is PROVEN for one
   player (docs/research/notes/arena-per-player-opponents.md section 8): Cobblemon NPC class with a pool party,
   `spawnnpcat` at absolute coords, `start_battle` from runmolang, a battle_victory callback tagging won/lost. The
   fight ladder is data/arena_fights.json (nine ranks; the owner's open questions are its open_questions).

**Pose test, in game 2026-10-03 (Eevee at (807, 177, 248) on Frostpeak, the owner watching):** NO control we have
gives a sleeping or sitting pose. `spawnpokemonat ... status=sleep uncatchable no_ai`: the server holds
`Pokemon.Status {StatusName: cobblemon:sleep, StatusTimer: 292}` but the timer never runs and nothing shows. The same
with AI on and `generic.movement_speed` 0: the timer runs down in SECONDS (292 -> 213 in ~80 s) and still no pose;
with AI on it also has gravity (it fell into a trench). `freeze_frame=0.5` is accepted with no visible effect;
`/freezepokemon` is not registered on this server. The one route left is Cobblemon's own resting behaviour (species
`behaviour.resting`: Eevee `drowsyChance 0.0333`, `willSleepOnBed true`), which needs AI on and is probably night-only:
untested unless the next lines say so.
**Then, natural sleep WORKS** (same session, in game): Cobblemon 1.8's own `cobblemon:pokemon_sleeps` behaviour (the
jar's data/cobblemon/behaviours/pokemon/pokemon_sleeps.json: find_resting_place, then sleep, wake_up) puts a Pokemon in
the real sleep pose. It is in a species' default behaviour list only when its `behaviour.resting.canSleep` is true
(482 species; NOT Eevee). Needs AI ON. A wild-spawned Pidgey (night sleeper, light 0-4) slept at night, the owner
watching; a Snorlax slept in DAYLIGHT (time 6993), read from the server. **The server can measure it without anyone
watching: entity NBT `PoseType` reads "SLEEP" / "STAND" / "WALK"** (writing PoseType by `data merge` does not hold:
it is recalculated). Light/time gate per species: 270 sleep only at night in light 0-4, 99 any time in light 0-4,
56 by day in light 0-4 (dark interiors); **19 can sleep in daylight outdoors**: snorlax (fastest, drowsy 0.0167),
slowpoke, slakoth, slaking, purrloin (day), murkrow, litwick, lampent, pumpkaboo, gourgeist, bronzong, vanillite,
honchkrow, lunatone, galvantula, chandelure, venipede, whirlipede, scolipede. They sleep and WAKE on their own
(rouseChance), so a sleeper is a dozer, not a statue. Behaviour lists are writable: `data merge {BehavioursAreCustom:1b,
Behaviours:[...]}` took effect live (dropping cobblemon:wanders stopped an Eevee wandering). Untested: the
`cobblemon:stationary` behaviour (home_walk_task, variables home_x/y/z) to hold a sleeper on a roof, and
`cobblemon:pokemon_follows_owner` for "following a kid". Test debris in staging: two snow blocks at (808-809, 175,
247) now air (a test bed), and tagged test Pokemon `cobblers_fps` near (807, 177, 248) unless cleared.

**Frame-rate test, in game 2026-10-03** (the owner's client, Brock's plaza (1756, 139, 3620), idle test Pokemon
spawned `uncatchable no_ai` in rings 5/8/11 blocks round the player, 18 mixed species, the town's own ~7 within 48):
0 -> 120-130 FPS; 10 -> 90-100; 20 -> 100-110; 30 -> 85-100. The drop is in the first ten; 10 to 30 is inside the
noise. The approved cap (2 carriers, 1-2 followers, ~10 idle, ~14 a town) is far under anything the client notices:
"how busy a town looks" is the limit, not the draw. Sleepers and followers need AI on (server-side cost only).
Then 50 in rings -> 65-70 FPS (the first real bend: everything close and in view at once), and **50 spread through
the town the way a town would hold them** (groups of 1-3 at plaza corners, the Center and Mart doors, along the four
streets, in yards; scratchpad town_spread.py) -> **100-110 standing in the plaza, 100-130 running round**, about the
same as 10-20 in rings. Spread, not count, is what costs. **Cap to use: up to ~30 ambient Pokemon a town, spread in
small groups** (2-3 carriers, 1-2 followers, the rest idle), comfortably inside what was measured; the limit is how
the town looks. Test Pokemon cleared afterwards.

## 4. Do not rediscover

- `reapply.py prepare` needs `--server-dir`, the lock env (`COBBLERS_SERVER_LOCK`, `COBBLERS_LOCK_OWNER`),
  `COBBLERS_SERVER_ROOT`, `COBBLERS_JAR_DIR` and `COBBLERS_COBBLEMON_JAR`; a full run is 157 jobs in about 21 minutes.
  ANY commit touching data/ or tools/ makes every finished job stale, so `--from` after a fix is refused: run the
  cheap audits by hand first, then one full prepare.
- Worktree agents never have built packs another tool replays; an audit that is clean in a worktree can refuse in the
  full checkout (tonight: deep_walk_audit's REPLAY lacked R9HQ; hq_tower_audit could not model R9RU's
  replace-by-tag). Run new audits in the full checkout before trusting them.
- A mob saves `NoAI` only while it is true: "Found no elements matching NoAI" means AI ON.
- `presence_audit` prints only misses; tonight's probe of new systems was a scratch sampler over the built packs'
  block writes (setblock and plain fill; `fill ... replace` lines need their own check).
- The 12 stalls whose keeper is a `cobblemon:npc`, not a merchant, are the badge-gated counters, by design.
- A gatehouse rebuild leaves the OLD shell standing wherever the new one does not write (regenerate the old functions,
  air what the new shell does not overwrite).
- Pre-existing failures, not from this work: `tests/test_rift_mines.py` x2 (review 45), `test_mines_independent`
  vl_water_a (52). Contracts C12/C14 (review 50) now pass with the per-den field.

## 5. Cost

`python tools/session_cost.py`: 1,183 turns, 61.5M weighted for the main session, context about 200k at the hand-over.
Agents are listed by the same command.
