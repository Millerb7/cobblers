# The Sundown Watch (Sunset Isle)

A place on Sunset Isle's western shoulder that is only worth the trip for about ninety seconds of every twenty
minutes. A stone dial and a Sun Gate on a paved terrace, benches facing the gate, a keeper's lamp house and a lamp mast.
By day it holds a keeper, a view and a few birds. When the clock reaches dusk, an activated Habitat Block in the dial's
plinth draws the Dreepy line out of the slope, the Dusk-form Lycanroc, and now and then a Drakloak that is five to eight
levels over the cap of the leg the place is pitched at.

- Data: `data/sunset_watch.json` (hand-authored). Generator: `tools/sunset_watch.py` -> `build/datapacks/cobblers_sunset_watch`
  (`plan` / `report` write nothing; `records --write` replaces this place's records in the shared files).
  Independent audit: `tools/sunset_watch_audit.py`. Tests: `tests/test_sunset_watch.py`.
- Re-apply: **R9SW** (block pass, before R9E: the dial's plinth and the mast's second log are blocks this pack writes and
  the two Habitat Blocks sit in them), **R18SW** (the keeper, after R17N). Pack `cobblers_sunset_watch`, world-local
  (`tools/reapply.py` SERVER_PACKS).
- Status: authored and audited offline, **not applied to any world, nothing seen in game.**

## The brief, and the premise check

The owner, 2026-10-09: *"SUNSET ISLAND: something special. It is empty, and it needs a reason to sail there."*

- **No file names "Sunset Island".** The island is `data/regions.json` `sunset_isle` ("Sunset Isle", 2.559 km², x816-3551
  z6664-8015; sub-regions `sunset_west` savanna tier 5 28-38, `sunset_east` flower meadow tier 8 43-53). "Sunset West" is
  the harbour TOWN on the mainland shore of the strait, not part of the island (`docs/world-building/SIDE_ISLANDS.md` F3).
  The island's dock is `data/ferries.json` `sunset_isle_landing`. One candidate; chosen.
- **"Empty" is half true.** The east has the Old Orchard and the Orchard Sleeper; the crest has the Dusk tower
  ((1156, 146, 7216), Champion-gated). Measured 2026-10-09 over every coordinate in every `data/*.json`: nothing authored
  lies within 150 blocks of the site, and the Dusk tower is 288.5 blocks off. The savanna west had a roster and no place.
- **There is no western cliff.** The brief's example imagined one. The west coast climbs about 0.4 blocks per block
  (y63 at the water, y100 at +100 blocks, y137 at +250) to a plateau at y133-142 along x1070-1160. The site is that
  plateau's western shoulder, a shelf whose 25 by 25 windows have a height range of 2 at (1072, 7492): the flattest on
  the island's west.

## The reason to sail: a time, not a creature

Every other place on the map is somewhere to go. This one is somewhere to be at a time. Nothing needs a badge, a key or a
fight; the gate is the clock. A group that sails over at noon has a keeper to talk to, twelve places to sit and an
hour to wait. A group that arrives as the sky changes gets the Dreepy line at levels that are catchable on the leg (30-38,
against the tier-5 cap of 40) and a one-in-sixteen chance of a Drakloak at 45-48.

Why it is unlike the others:

| Place | What it is | What the Watch is not |
|---|---|---|
| Ursaluna den | a boss in a cave | no cave, no boss, nothing sleeps |
| Old Orchard (same isle) | a ruin with a find in a cellar | the find here is incidental; the draw is the hour |
| Brass Petrel, Copperway Khan | wrecks and ruins to enter | the building is a hut and a terrace; the place is outdoors |
| Dusk tower (same isle) | a gated legendary for a Champion | no gate; the "dusk" here is the weather of the clock |
| Legendary shrines | an altar with an item | nothing to carry in |

Cobblemon's own data agrees with the theme, which is why it needs no new machinery: stock Dreepy is a coastal dusk
Pokemon (`spawn_pool_world/0885_dreepy.json`: ultra-rare, weight x5 at `timeRange: dusk`, levels 2-27, coast and ocean
biomes) and stock Lycanroc has a `dusk` form spawn with the same gate (`0745_lycanroc.json`).

## Siting (measured 2026-10-09, `tools/ground.py`, rounded)

| What | Where |
|---|---|
| Centre, cell | (1072, 7492), H2, sub-region `sunset_west` |
| Terrace | x1054-1085, z7481-7503 (32 by 23), paved at **y137** = the highest ground under it; ground y134-137 (range 3) |
| Dial centre / plinth (dusk Habitat Block) | (1068, 138, 7492) |
| Sun Gate | pillars x1055-1056, z7487-7488 and z7496-7497, 8 high; lintel y146; opening 7 wide on the dial's east-west axis |
| Benches | x1078, 1081, 1084; z7484-7489 and z7495-7500 (stone-brick stairs, backs east) |
| Way down | three-wide stair run from the lip at x1053, y137 down to y135, then six columns of dirt path |
| Lamp house | centre (1073, 7475), floor y137, ridge y146; door in the south wall at (1073, 138, 7478) |
| The find | barrel (1075, 138, 7473), trigger box (1074-1075, 138-139, 7473-7474) |
| Lamp mast | (1082, 7483), 13 logs, second log (1082, 139, 7483) = the day Habitat Block, crown lantern (1082, 151, 7483) |
| Keeper | stands at (1076, 138, 7487), facing west |
| Waymark at the isle's landing | sign (2576, 65, 6916) on dry beach (ground y63), 17 blocks south of the arrival spot (2575, 63, 6899), facing north |

Distances: landing to the terrace's centre 1,616 blocks straight (the line peaks at y140); coast to the terrace's west lip
233 blocks with 72 of climb. The mast's crown is visible from a boat at sea level 550 blocks west of the terrace with
3.9 blocks of clearance over the ground (the sight line is computed in `sunset_watch.py report` and again, independently,
in the audit's `see` check).

## What the pack writes (`cobblers_sunset_watch`, function `cobblers:sunset_watch/build`)

Every Y is derived from the heightmap: terrace P = max(ground under it) = 137 with stone-brick foundation to each
column's own ground, so the low west lip stands out of the slope as a retaining wall; the hut floor is max(ground under
its walls) + 1; every post, tree and stair is on its own column's ground. 2,823 cells and 78 clears in 1,924 commands.
Nothing reads a world (`WORLD_READS = set()`).

- **Terrace paving:** stone brick (a quarter mossy, a tenth cracked, by a fixed hash of the column).
- **The dial:** a 17-block stone dial (smooth-stone ring r 7.0-8.5; twelve hour marks of chiselled brick; polished
  andesite between), the chiselled-brick plinth at its centre one block proud of the floor.
- **The Sun Gate:** 2 by 2 pillars, a lintel, a slab cap, three lanterns on chains, on the lip.
- **Benches:** six groups of stone-brick stairs facing the gate across a two-wide aisle.
- **The lamp house:** 7 by 7, spruce on a stone-brick footing under an east-west gable, a south door, window holes,
  three casks, a lectern with no book, a crafting table, a rain cauldron, a lantern from the ridge, a door sign. No bed.
- **The lamp mast:** spruce pole, a fence cross-arm with a lantern at each end, a lantern at the crown.
- **Five wind-bent acacias**, persistent leaves; wind-flattened grass and fern through the margin (about one column in
  ten); a dirt-path approach from the east with lantern posts every ten.
- **The waymark:** two stripped-spruce stumps at the isle's landing, a standing sign on one and a lantern on the other.
- **Lanterns, never light blocks:** 26 of them; every column of the terrace is within 14 (Manhattan) of one, i.e. above
  block light 0 (the audit's `attached` check; ASSUMED that hostile mobs spawn at block light 0 in 1.21).

No flowers (every vanilla flower is a Combee condition in `data/spawn_blocks.json`), no bell (Chimecho), no sand, no chest,
no bed. The record declares no spawn condition and the audit refuses one.

## Life on it

The wilderness keeps `sunset_west`'s own table (savanna, 28-38); the Watch adds two activated Habitat Blocks (the orchard's
and the den's pattern; `cancel_range -1` leaves natural spawning alone):

| Pool (Habitat Block) | Block's cell | Range / cap | Entries | Time |
|---|---|---|---|---|
| `sunset_watch_dusk` (`sunset_watch_dial_ward`) | the plinth, mimic chiselled brick | 14 / 4 alive, 2 per activation | Dreepy 30-38 weight 24 (75%); Lycanroc **dusk form** 30-38 weight 6 (18.75%); **Drakloak 45-48** weight 2 (6.25%, 5-8 over the tier-5 cap of 40) | every entry `timeRange: dusk` |
| `sunset_watch_day` (`sunset_watch_mast_ward`) | the mast's second log, mimic spruce log | 12 / 3 alive, 1 per activation | Swellow 28-38 weight 12; Swablu 28-38 weight 6 | every entry `timeRange: day` |

- **Why two blocks.** An activated block counts what it has alive against its cap. Day birds in the dusk block would sit
  on the cap and shut the dusk pool out.
- **The nest.** The Drakloak is the creature the place is for: a place that suits it (the Dreepy line's dusk coast), strong
  enough that meeting it early is a mistake. It is rare, so a visit is mostly Dreepy; the path to the Watch and most of the
  place stay catchable (STATE "Wild Pokemon above the cap are welcome"). Dreepy is 30-38 (the evolution policy: it evolves
  at 50, so the whole band); Lycanroc is a final stage from Rockruff at 25; Swellow is final from Taillow (22); Swablu
  evolves at 35. The audit re-derives these from the 1.8.0 jar.
- **The dusk window** is `TimeRange` `dusk` in the 1.8.0 jar: ticks 11834-13701 of 24000 (read with `javap -c` on
  `com/cobblemon/mod/common/api/spawning/TimeRange.class`, 2026-10-09): 1,867 ticks, about **93 seconds of a 20-minute day**.
  The sky is orange for that stretch; `day` is 23460-12541.
- **Ambient (working Pokemon):** none. `data/ambient.json` is keyed to towns (`tools/ambient.py` Site, derived town
  plans), and a place with no town plan has no carrier. The foliage and the two pools are the life; this is stated, not
  hidden.

## How a player learns of it, and gets there

1. **The ferrymen.** The Sunset West pier's ferryman (`data/ferries.json` `sunset_south_pier`) now ends his greeting with
   "Folk who've been say the old Watch on the isle's west brow still lights its lamp at sundown, and that something comes up
   the slope to see it. West, with the sea on your right." The isle's boatman (`sunset_isle_landing`) says to go west along the
   shore, up the brow to the lamp, "and go at sundown, or you've walked for nothing". (These two records are the ferries'
   own; only the greeting text changed.)
2. **The waymark sign** on the beach 17 blocks ahead of the arrival spot: "SUNDOWN WATCH / west along the / shore, then up /
   to the lamp".
3. **The lamp** on a 13-block mast, visible from the sea and the slope.
4. **The keeper**, once there: Isaura Dray (`dlg_sunset_watch_keeper`, nine nodes, a per-player cursor). She says what the
   place is for, how to recognise the hour ("the colour of the inside of a shell ... about a minute and a half"), not to walk at
   what comes, and where the guild's store is.

**Getting there.** The Sunset strait ferry ($100 each way, `gates []`, reachable at 0 badges), then about 1,600 blocks west.
By Surf (Misty's training, S2) along the coast from the pier or the landing: about 2,170 blocks round the outline (an
estimate from the region polygon's vertices, not a sailed path), then 233 blocks and 72 of climb from the beach. The first
500 blocks west of the landing are `sunset_east`, tier 8 (43-53, cap 55); Cobblemon's wild Pokemon do not hunt a walker
(ASSUMED, not tested here), so that is a view of what the isle holds later and not a wall.
**Intended badge: four** (tier 5 is the leg Erika to Koga, cap 40); possible at zero.

A note for the owner: Dragapult is a Surf-capable ride species (`data/water_mounts.json`). The place hands out a Dreepy line
whose last stage carries a rider on water. That is a coincidence of the data, not a design.

## The find

`data/rewards.json` `sunset_watch_lamp_store`, a cache (ADR-002): the guild's store barrel in the lamp house's north-east
corner. **Eight Dusk Balls and a Spell Tag** (both verified in the 1.8.0 jar's item models). Dusk Balls are the right tool
for the thing the place is for. No evolution stone: stones are allocated (`docs/mechanics/EVOLUTION_STONES.md`) and this
is not a stone's place. Granted once per player on reaching the corner; the barrel is scenery. The cache is ungated and
not time-gated (a cache has no clock), so a daytime visit is not empty-handed.

## State model

| State | Where | Multiplayer |
|---|---|---|
| The keeper's talk | `quest.ambient_sunset_watch.keeper_cursor` (per player, `data/progression.json`) | each player advances and restores their own cursor; a late joiner starts at "greeting"; a death or disconnect mid-talk resumes at the next unread node |
| The cache | `data/rewards.json` (once per player, tools/rewards_pack.py) | each player has their own; two players share the barrel as scenery |
| The pools | the two Habitat Blocks | server-wide, not per player: whoever is within range when the dusk window opens sees the same spawns, and whoever catches a Dreepy takes it for everyone. Two players at dusk share the pool; four alive at most |
| The clock | the world's day time | server-wide; the dusk window recurs every 24,000 ticks. Sleeping through the night changes when it next comes, not whether |
| Nothing else | | the place sets no flag, no score, no scoreboard and no storage. A re-export erases it; R9SW and R18SW put it back |

Nothing is persisted by this place beyond the cursor and the cache grant, both of which are existing systems.

## Rung, per CLAUDE.md principle 6

1. **Cobblemon native** carries the whole behaviour: the Habitat Block's `timeRange` (verified in source,
   `docs/research/notes/habitat-blocks-underground.md` section 1) and the stock species files. Nothing earlier on the ladder
   can be skipped: there is no addon.
2. **Datapack/commands** carry the build (a `.mcfunction` of fills and setblocks, the repository's pattern for every
   authored place) and the keeper (the dialogue compiler).
3. Nothing from the scripting layer, a companion process or a Fabric mod. A sunset *effect* (the lamp lighting at dusk, a
   bell) would need a tick function reading `time query daytime`: that is a datapack rung, not built, because the pools
   already give the hour its meaning and the lanterns are lit all day like every other place's.

## Verified / not verified

Verified offline (this session): the generator runs against the canonical heightmap and passes `function_limits`; the
audit (`tools/sunset_watch_audit.py`) is clean and fails on 13 distinct generator mutations
(`tests/test_sunset_watch.py`, 22 tests); `python tools/validate_data.py` reports 0 errors; the compiled pools carry
`timeRange` on every entry; `TimeRange`'s ticks read from the jar.

**Not verified, needs a running server:** that the fills land; that the Habitat Blocks load and spawn; that an
**activated** block honours `timeRange` (verified in source for habitat details, never seen in game); that
`modifiers: "dusk"` on the Lycanroc entry resolves the Dusk form (the stock spawn writes it as `"lycanroc dusk"`; the
habitat pool's `modifiers` is a PokemonProperties string, as the jar's own habitat pools write it for regional forms);
that Dreepy and Drakloak find a `grounded` position on a paved terrace; that the dusk Pokemon do not simply drift off
(the nest-perching note: nothing in 1.8.0 keeps them near the block); that the cache grants; that the keeper renders and
talks; that the sun sets through the gate (ASSUMED from the vanilla sky's axis: the sun moves along the x axis, setting
at -x); that the stair run and the hut door are walkable; how it looks.

## Proof to run (small, before anyone builds more like it)

On a stopped-world copy, never the live world, after R9SW, R9E (restart) and R18SW:

1. `python tools/presence_audit.py --only extra` -> 15 of 15 probes (`world_probes.json` `sunset_watch`).
2. `/time set 6000`, stand at the terrace for 60 seconds; `/execute as @e[type=cobblemon:pokemon,distance=..16] run data get entity @s Pokemon.Species`
   -> only Swellow or Swablu (the day block) and nothing from the dusk pool.
3. `/time set 11800`, count the Pokemon within 16 of the plinth every ten seconds to 13,800; expect Dreepy/Lycanroc to
   appear after 11,834 and none new after 13,701. **Pass:** Dreepy only inside the window. **Fail:** a Dreepy at 6000 means
   the activated block ignores `timeRange`; fall back to a tick function that places and removes the Habitat Block at
   the window's edges, and write that up.
4. Read one spawned Lycanroc's `Pokemon.FormId`/aspects: `dusk`. If not, drop the modifier and take the stock form.
5. Stand on the benches at tick 12000 and look west: the sun in the gate or not.

## Collisions and flags

- **Dreepy is a pseudo-legendary line.** Stock Cobblemon already spawns it at coasts (ultra-rare, 2-27); here it is
  the anchor of a pool at 30-38, available from the leg Erika to Koga. It evolves at 50 and 60, so a trainer who catches
  one meets Drakloak/Dragapult on the late legs, not early. The owner may want it at 33-38 or rarer.
- **The cap trap.** The Drakloak at 45-48 is above the tier-5 cap (40) *and* above the next (45) at its top. Catching it
  early is blocked by the level-cap trap (`tools/levelcap_pack.py`, not run in game) if that trap works, which is
  exactly the point: the nest is seen on this leg and caught on the next.
- **Sunset West's ferry greetings** are two records in `data/ferries.json` that are the ferry system's; only the text of
  `greeting` changed. `python tools/ferries.py audit` was not run (it needs derived plans this worktree lacks).
- **`data/regions.json` still says `sunset_west.encounters.status "empty"`**, a stale line of the region's draft; not
  changed here.
