# Handover: the 2026-10-03 follow-ups (session a292b1c5)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file. `docs/REVIEW_2026-10-02.md` (items 1-52) lists every
call made and every defect recorded and not chased; read it before reversing anything.

## 0. THE NIGHT OF 2026-10-04 (the owner asleep: "Build until done, do not stop for approval, record defects and keep going")

Branch `build/2026-10-04-placement` (stacked on #117's `build/2026-10-03-towns`). Plan, in the owner's numbering:
1. Wrong-country spawns: sweep every COMPILED roster (cobblers_spawns) for species that do not belong (Crabominable on
   warm southern ground); fix by condition where a condition does it, by removal where not. Builder + independent audit.
2. Mega area fills the southern Rift: expand the farms over the gulch and both southern arms; crowding legible
   (overlapping ranges, scarred ground, broken rock at territory edges, kills). Builder + audit.
3. Placement fault: DONE as diagnosis (Brock's spawners one block high in all 7 halls, fixed 281c0c9; the other three
   are correct in data; no stray NPCs near current seats). Left: route_03_trainer_05 inside a signpost; the rotated-donor
   keep-clear fault (town_dressing.building_footprints / markets.donor_footprints). Apply Brock's fix.
4. Queue: tent stalls (agent running) then stall keepers -> cobbledollars:cobble_merchant with per-stall
   CobbleMerchantShop (DEFAULT TAKEN: badge-gated counters stay dialogue clerks, the merchant screen cannot gate per
   player); ambient Pokemon (cap ~30 spread, sleepers by cobblemon:pokemon_sleeps species, wake at 16 blocks; Buneary
   round the snow house); water life next tranche; the southern map; "the three extra starters" (UNRESOLVED: config and
   data offer five; ask what the screen shows); rift_crisis_resolved (its setter is invoked by the binder since
   2026-10-03 -- check it fires at the finale stage).
5. Walk the whole game, Oak's lab to the Champion, as a player: two research agents (lab..gym 4; gym 5..Champion).
6. Finish the finale: the HQ interior (a factory-like tower for battles and exploration), the cradle chamber with Elara
   and Brann and the release, the HQ door gated on the finale's quest stage. Codex's finale:
   `git show codex/trainer-modes:docs/story/NPCS_AND_RIFT_FINALE.md` (local, unpushed).
7. Giovanni: set the fight up so it waits for the owner; say where to stand.
8. Obtainability sweep: every item a recipe/evolution/mechanic needs with no route in a pre-generated world; two
   research agents; build only what is cheap and obviously right.
Morning report: IN THE WORLD with coordinates, the review list, what is blocked on the owner.

## 1. The branch

- **`build/2026-10-03-followups`**, stacked on #114 (merged into main 2026-10-03 08:21). One draft PR against main;
  re-read its head before quoting it (`git fetch --prune; gh pr view build/2026-10-03-followups --json headRefOid`).
- #109-#113 are MERGED (nothing to close). Delete when convenient: every `worktree-agent-*` branch.

## 2. Where it stopped

- **Applied and verified in staging-2026-10-01** at 12:43 (`--only R9Z,R9DC,R9RU,R9NR,R9E,R9F,R17,R18RU,R18NR`,
  0 problems), restarted: `presence_audit` 257 of 266 (the nine absent are the known stale/open probes, STATE
  "Latest applies"), `npc_seats.py verify` 20/20, `install_check` 0. Snapshot before it:
  `C:/Users/wnd/Documents/cobblers-staging/snapshot-2026-10-03-before-batch2`.
- **Server UP** (started `nohup ... & disown` from the server dir with `--universe C:/Users/wnd/Documents/cobblers-staging
  --world staging-2026-10-01`; `level-name` is the LIVE world). `max-tick-time=60000` (set -1 with the server stopped
  before a `reapply.py run`). The lock is released at the end of this session.
- Next, in order:
  1. Z2's gate, once the owner says where (review 44).
  2. Fly-checks below; then the review list's open items.
  3. `python tools/reapply.py stale --server-dir C:/Users/wnd/Documents/github/cobblers-server` after the next full
     apply: every step reads `unknown` until it runs with a hash.

## 3. What waits on the owner

- **Z2's gate "to the gatehouse, 1,316 blocks"**: not reproduced. G2 stands in its own trailhead gatehouse (3548, 112,
  5322); Gym 8's building (3572, 6416) is 1,094 straight / 1,164 walked. Is the intended move into Gym 8's gatehouse?
- **In game, with coordinates:** Heaven's Arena (3609, 3249): win tier 1 at (3609, 17, 3257), then walk the stair up
  from the east exit (3612, 16, 3243); without the win the shaft should set you back at (3613.5, 16, 3243.5)
  (review 51 is the tag-timing risk). Gatehouses: G2 (3548, 112, 5322), G5 (3573, 85, 2680) from the south, the wilds
  slip (4200, 95, 4300) west mouth. Zapdos on Fungal Isle, altar (895, 69, 5583); the coast site (577, 2628) should
  be bare ground. Northern residents: stubborn_tree (1588, 3280), wandering_stone (5264, 2680), hide_and_seek (6700, 3710).
- Shrew Station was sited to study the coast Zapdos; it is now 2,777 blocks away. Move it too?
- The standing list: the shared server config (review 20, 25), z5's binder grant (22), EXP-049/054/048 in-game
  checks, the Sinnoh pack, Mega field levels and night aggression, the diamond pack price, unsited markets.

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

- `reapply.py prepare` needs `--server-dir` and the lock env (`COBBLERS_SERVER_LOCK`, `COBBLERS_LOCK_OWNER`); with them
  it ran 140 jobs clean in 1,046 s.
- A gatehouse rebuild leaves the OLD shell standing wherever the new one does not write: the one-off used here is
  scratch (regenerate the old functions at 1cbce5c, voxelise, air what the new shell does not overwrite at/above the
  guard's feet). Same shape for any shell that moves.
- Run records now carry `hash` and `world_dir`; before 2026-10-03 they held only function counts, which is why a
  changed function under an unchanged step was invisible.
- Pre-existing failures, not from this work: `tests/test_rift_mines.py` x2 (review 45), contracts C12/C14 on the Mega
  field's multi-Mega den (50), `test_mines_independent` vl_water_a (52).
- The Zapdos cleanup (`tools/zapdos_tower.py build`) and any staging cleanup pack are built on demand into
  `build/staging/`, copied into the world's datapacks for one run, and deleted again.

## 5. Cost

`python tools/session_cost.py`: main session ~300k context at the end (over the hand-over line; it ran on to finish
the integration and apply); agents together ~57M weighted before today's five (gatehouses, arena audit, northern
audit, northern re-site, Zapdos, qa).
