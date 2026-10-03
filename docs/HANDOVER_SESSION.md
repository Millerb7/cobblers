# Handover: the 2026-10-03 follow-ups (session a292b1c5)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file. `docs/REVIEW_2026-10-02.md` (items 1-52) lists every
call made and every defect recorded and not chased; read it before reversing anything.

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
