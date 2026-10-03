# The ten named residents

Codex authored ten memorable non-legendary residents in sparse parts of the map (`data/resident_encounters.json`,
merged from PR #107; its `rules` block is the spec). This build turns all ten into one pack with one tool.

| | |
|---|---|
| Data | `data/resident_encounters.json` (Codex's records, plus a `build` block on the file and on each record) |
| Generator | `tools/resident_encounters.py` -> `build/datapacks/cobblers_residents` (`--report` writes nothing) |
| Independent audit | `tools/resident_encounters_audit.py` (never imports the generator's geometry) |
| Tests | `tests/test_resident_encounters.py` (mutate the generator, never the record) |
| Re-application | step **R18R**, after R17N and R18U; the pack is world-local (`tools/reapply.py` `WORLD_LOCAL`) |
| Contract | `data/system_contracts.json` C17: a resident that wins becomes the claim's guardian, and the keeper never touches a guardian |
| Status | **built, not placed.** Generated and audited offline on 2026-10-02. Nothing here has run on any world |

## 1. Where they are

Every x/z is Codex's, measured and kept: none needed moving (section 2). Feet are one above the rounded canonical
heightmap ground (`tools/ground.py`); River Grip's are one above the sea's surface block. `bbox` is every block the
dressing writes plus the anchor's standing space, inclusive `[x0, z0, x1, z1]`; R18R force-loads exactly that box.

| id | name | species | level | anchor (x, feet y, z) | ground y | trigger / leash | appears after | catch | bbox |
|---|---|---|---|---|---|---|---|---|---|
| old_jaw | Old Jaw | drednaw | 25 | (613, 81, 4306) | 80 | 24 / 28 | (always) | level cap until gym 1 | [550, 4301, 618, 4311] |
| wiremother | Wiremother | galvantula | 33 | (1138, 127, 3610) | 126 | 20 / 28 | gym3_cleared | catchable after gate | [1116, 3602, 1160, 3619] |
| ridgejaw | Ridgejaw | tyrantrum | 39 | (3544, 161, 1600) | 160 | 22 / 30 | gym4_cleared | catchable after gate | [3541, 1593, 3554, 1606] |
| red_rail | Red Rail | scolipede | 44 | (5541, 96, 1703) | 95 | 18 / 26 | gym5_cleared | catchable after gate | [5500, 1662, 5552, 1712] |
| whiteback | Whiteback | mamoswine | 50 | (7022, 80, 312) | 79 | 24 / 34 | (always) | never | [7015, 271, 7036, 353] |
| river_grip | River Grip | grapploct | 52 | (6970, 63, 3970) | 53 (bed), water y62 | 20 / 30 | gym7_cleared | catchable after gate | [6956, 3944, 6973, 3974] |
| **dustback** | Dustback | copperajah | 56 | **(6216, 142, 6112)** | 141 | 24 / 36 | gym8_cleared | catchable after gate | [6179, 6059, 6253, 6153] |
| **hornwall** | Hornwall | bouffalant | 56 | **(4200, 138, 5920)** | 137 | 24 / 34 | gym8_cleared | never | [4194, 5914, 4206, 5926] |
| **orchard_sleeper** | Orchard Sleeper | slaking | 60 | **(2816, 67, 7080)** | 66 | 18 / 26 | gym8_cleared | catchable after gate | [2786, 7067, 2817, 7101] |
| **split_bark** | Split-Bark | kleavor | 63 | **(7360, 139, 7376)** | 138 | 20 / 28 | champion_cleared | catchable after gate (see 4.3) | [7356, 7367, 7371, 7387] |

The four in bold are the south ones the owner cares about most: Dustback in the south-east dunes, Hornwall on the
Rift Foot shelf, the Orchard Sleeper on Sunset Isle, Split-Bark in Long Isle South's jungle.

## 2. The relayed coordinates, measured

Codex's x/z and y values were relayed; each was measured on 2026-10-02 with `tools/ground.py` and checked by the
audit's `site` check against every footprint in the data. All ten pass, so no `supersedes_location` was needed.

| id | measured ground (Codex said) | sub-region | nearest walked route point | nearest other site |
|---|---|---|---|---|
| old_jaw | y80 (80.4) | west_shore | 839 | none within 200 (Viltri estuary landmark anchor at the spot) |
| wiremother | y126 (126) | viltris_path_valley | 491 | Viltri Ravine landmark 39 west |
| ridgejaw | y160 (160.2) | the_crags | 245 | crag sapling 24 west |
| red_rail | y95 (95) | marshy_marsh | 1,139 | marsh outflow river 24 east (surface y91 there) |
| whiteback | y79 (79.1) | north_pine_isle | 2,950 | elder tree 24 west |
| river_grip | bed y53 (53), sea y62 | (sea) | 332 | the Tilpey outflow's mouth, at the spot |
| dustback | y141 (141.1) | south_east_dunes | 1,053 | desert sapling 24 west |
| hornwall | y137 (136.7) | rift_foot | **59** | storm sapling 24 west |
| orchard_sleeper | y66 (65.8) | sunset_east | 1,015 | palm sapling 24 east |
| split_bark | y138 (138.3) | long_isle_south | 2,679 | jungle elder 24 west (root flare 13) |

Every land anchor is dry within 2 blocks (the painted lakes and sea of `tools/water_mask.py`, and the river corridors
of `data/rivers.json`), outside every town footprint and placement by leash + 16, outside every Rift zone box, and
off the route line by trigger + 16. Hornwall is the closest: 59 from Route 8's line, so a player on the route is 35
outside its trigger. Split-Bark's earlier Jungle West anchor (4464, 7312), which Codex had already moved, was
re-measured too: ground y53 there and y53-54 on every column within 16, under sea level y62.

## 3. What is built at each site

All dressing is block work seated on each column's own rounded ground. Surface work replaces the ground's top block
only (the height never changes), plants are cleared with `fill ... air replace #minecraft:replaceable`, nothing is
written under the ground, and no land piece is written on a wet column. Everything stays at least 12 from every elder
trunk, themed sapling and Habitat Block, and 8 from every route line. Wild sites: dark by design (one lantern on River
Grip's observation post).

| id | dressing (data `build.dressing`) |
|---|---|
| old_jaw | the bowl (radius 5, mud/coarse dirt/gravel/clay), two drag marks running 50 west, and a spruce wreck 62 west on their line |
| wiremother | the failed survey crossing: two standing and two snapped poles, a fallen pole, sagging cobwebs, a flag, a chain, an instrument case (barrel), a survey flag. Blocks stand before gym 3; the resident appears after it |
| ridgejaw | scraped stone (radius 3) and a scrape line east of the spot; four bone-block chips |
| red_rail | a 69-block iron-red trail (red terracotta, granite, terracotta, coarse dirt) through the reeds, with shell fragments |
| whiteback | the old trail (80 blocks of coarse dirt, gravel, packed ice), five snow banks, two broken markers, a bare spruce windbreak |
| river_grip | a drowned mooring (all under the surface), two snapped chains and spruce debris on the bed; a dry plank deck and lantern post on the north bank, 25 out, beyond the trigger |
| **dustback** | a 100-block migration scar, 15 broad, across the dunes (sandstone, smooth sandstone, coarse dirt, gravel); one crushed marker |
| **hornwall** | the bare standing circle (radius 6). The bypass is the open slope toward Route 8: nothing built |
| **orchard_sleeper** | seven storm-bent oaks in two rows leaning north-east, two overgrown rows, a windfall and a collapsed shed, all west of x2814. The anchor is INSIDE the template box of the giant palm `sapling_palm_sunset_east` (box x2814-2862 z7055-7105, RELAYED by the orchard builder, not measured here: no palm block within 4 of the anchor below y115), so the Slaking sleeps under the palm's crown. The record declares that box `keep_out`; the audit refuses any block set in it, and only the standing space's plant clear (y67-68) reaches in |
| **split_bark** | two split logs (bark half and heart half side by side), a third split log, two scored stumps |

## 4. How the residents behave

### 4.1 The keeper, the trigger and the leash

One pack, `cobblers_residents`, namespace `cobblers:residents/*`. `residents/keeper` runs every 40 ticks (a scheduled
loop, the Ursaluna den's) and calls each resident's `keep` only while its anchor's chunk is loaded.

- **Present** is a resident carrying its tag `cobblers.res.<id>`, or a guardian the blackout rebuilt (no resident tag)
  found by `tag=cobblers.guardian` and its species within leash + 8 of the anchor. Never a bare distance (the Ursaluna
  den's THE SUMMON GUARD: R14C failed twice on one).
- **Dormant** (`cobblers.res_dormant`): NoAI, held on its spot facing its yaw (toward the nearest walked route point).
- **Trigger** (a state check on the loop, never an advancement): the first non-spectator player within `trigger` of
  the anchor wakes it: NoAI off, a message and a sound to players within 48. Cobblemon 1.8.0 has no command that
  starts a wild battle, so the trigger is the wake, not a forced battle; what it does awake is its own AI and Fight or
  Flight's global config, which this pack never touches (`rules.aggression`).
- **Leash**: awake or asleep, a resident more than `leash` from its anchor is teleported back to it.
- **Settle**: awake, when no player is within leash + 16, it goes back to its spot and sleeps again.
- **Duplicates** (a spawn that raced a slow entity load): the furthest one is killed, and never one tagged
  `cobblers.guardian`.

### 4.2 Respawn and presence gates

The respawn clock is the gulch Megas' (`tools/gulch_mine.py` `megas/keep_*`): the game time a resident was first seen
gone on two keeper passes in a row, written only by the keeper. It comes back `rules.respawn_ticks_after_faint_death_or_catch`
(36,000 ticks, 30 minutes) later, through the macro `residents/spawn_at` (EXP-046: `spawnpokemonat` written plainly in a
function spawns nothing), only when a player is within 96 of the anchor and **no** player is within 48.

A gated resident (`build.appears_after`) also needs that nearby player to hold the gate's advancement
(`cobblers:flag/<gate>`). It is a world entity, so the first qualified player brings it in **for the server**, as the
woken Celebi stays for everyone. Old Jaw (met before gym 1 by design; its gate is the catch gate) and Whiteback (no
gate) have no presence gate and are summoned by R18R.

### 4.3 Catching

- **Whiteback and Hornwall** spawn `uncatchable` (EXP-023: stored in `Pokemon.PokemonData`, refused by the ball,
  survives a restart). Permanent.
- **Everyone else** is gated per thrower by the existing level-cap refusal (`data/level_cap.json`): a catch strictly
  above the thrower's RCT cap is refused. The audit recomputes, from `data/trainers.json` and
  `modpack/config/rctmod-server.toml` alone, that each level is above every cap a player can hold before its gate and
  within the bound after it:

| id | level | cap bound before gate | cap bound after gate |
|---|---|---|---|
| old_jaw | 25 | 20 (initial cap, Brock's ace) | 25 |
| wiremother | 33 | 30 | 35 |
| ridgejaw | 39 | 35 | 40 |
| red_rail | 44 | 40 | 45 |
| river_grip | 52 | 50 | 55 |
| dustback | 56 | 55 | 60 (the Elite Four) |
| orchard_sleeper | 60 | 55 | 60 |
| split_bark | 63 | **62** (Champion Blue) | not known (post-champion cap, NOT VERIFIED) |

These are upper bounds: a player still owing a route trainer has a lower cap and is refused until they beat it.

**Split-Bark is level 63** (the owner, 2026-10-02): at Codex's 62 it equalled the Champion's strongest, so a player
between the Elite Four and the Champion could catch it. At 63 the cap refusal closes that window, and the audit errs on
any level inside it.

### 4.4 The blackout (decision, with reasons)

A resident that beats or kills a player is an ordinary wild victor (`data/blackout.json` claims): it makes the item
claim and becomes that claim's guardian, and beating, catching or killing it returns the items. It is **not** exempt
like the gulch Megas (`claims.exempt_tag` `cobblers.gm`), because Codex's `old_jaw_blackout_check` plans exactly this
("returned by defeating or catching the same guardian") and `rules.keeper` says recovery belongs to that exact
Pokemon. From the moment a resident carries `cobblers.guardian` this pack never touches it: no hold, leash, wake,
settle, teleport, merge or kill. The blackout's own leash (24, to the claim's site) and maintenance own it. It still
counts as present, so no second resident spawns beside it; when it is beaten, caught or killed the claim settles and
the respawn clock starts. Contract C17 records this.

### 4.5 Drops and rewards

Nothing in the pack gives, loots or summons an item, and no resident has a reward record: capture is the reward where
catchable (`rules.capture_is_reward_where_catchable`). Cobblemon's own species drop table is untouched, and whether it
fires on a battle knock-out is **not verified** (probe below).

### 4.6 More than one player

| Case | What happens |
|---|---|
| Two players arrive together | One resident. The first within its trigger wakes it for both. |
| A gated resident, an ungated player alone | It is not there until someone holding the gate has come within 96. |
| A gated resident already present, an ungated player arrives | It is there, awake for them too; catching is still refused by their own cap. |
| Caught or knocked out | Gone for the server for 30 minutes, then back only with nobody within 48. |
| It beats a player | It becomes the claim's guardian; the keeper only counts it until it is beaten, caught or killed. |
| Restart | The clock and the entities survive (scoreboard, PersistenceRequired). Nothing respawns early. |
| Re-export | The world is new: R18R dresses all ten and summons Old Jaw and Whiteback; the other eight wait for their gates. |
| Re-application without a re-export | Dressing re-runs in place; a summon is skipped while the resident (or its guardian) exists, but one caught minutes ago is put back early (the den's bear behaves the same). |

## 5. The re-application, R18R

For each resident, in record order: `forceload add <bbox>`, wait, `function cobblers:residents/<id>/dress`; for Old Jaw
and Whiteback only, the RCON summon

```
execute unless entity @e[type=cobblemon:pokemon,tag=cobblers.res.<id>] positioned <x+.5> <feet> <z+.5>
  unless entity @e[type=cobblemon:pokemon,tag=cobblers.guardian,distance=..<leash+8>,nbt={Pokemon:{Species:"cobblemon:<species>"}}]
  unless entity @e[type=cobblemon:pokemon,distance=..4,nbt={Pokemon:{Species:"cobblemon:<species>"}}]
  run spawnpokemonat <x+.5> <feet> <z+.5> <species> level=<L> [uncatchable]
```

then `function cobblers:residents/<id>/bind_new`; then `forceload remove <bbox>`. 46 steps, 2 summons. The pack's load
tag starts the keeper; it must be world-local, because the keeper spawns Pokemon on its own.

## 6. World probes

For the session that holds the server, after `R18R` on a staging world. Each block probe expects **1**
(`execute if block` reports a test passed). Run from the server console; the chunk must be loaded
(`forceload add <bbox>` first, or stand there).

### Blocks (dressing landed)

```
execute if block 550 67 4306 minecraft:spruce_stairs[facing=east]          # old_jaw: the wreck's bow
execute if block 558 70 4302 minecraft:mud                                  # old_jaw: drag mark north
execute if block 1116 128 3602 minecraft:stripped_spruce_log                # wiremother: standing pole
execute if block 1127 128 3607 minecraft:stripped_spruce_log[axis=x]        # wiremother: fallen pole
execute if block 3550 163 1603 minecraft:bone_block[axis=x]                 # ridgejaw: bone chip
execute if block 5523 99 1681 minecraft:red_terracotta                      # red_rail: shell fragment
execute if block 5526 97 1687 minecraft:coarse_dirt                         # red_rail: the trail
execute if block 7030 79 302 minecraft:snow_block                           # whiteback: snow bank
execute if block 7027 78 288 minecraft:cobblestone                          # whiteback: broken marker
execute if block 7036 80 304 minecraft:spruce_fence                         # whiteback: windbreak
execute if block 6964 54 3967 minecraft:mossy_stone_bricks                  # river_grip: drowned mooring
execute if block 6956 54 3968 minecraft:chain[waterlogged=true]             # river_grip: snapped chain
execute if block 6961 65 3944 minecraft:spruce_planks                       # river_grip: observation deck
execute if block 6970 62 3970 minecraft:water                               # river_grip: water over the spot
execute if block 6228 143 6124 minecraft:cut_sandstone                      # dustback: the crushed marker
execute if block 6216 141 6106 minecraft:sandstone                          # dustback: the migration scar
execute if block 4200 137 5920 minecraft:coarse_dirt                        # hornwall: the standing circle
execute if block 2790 67 7071 minecraft:oak_log                             # orchard_sleeper: a bent tree
execute if block 2794 71 7098 minecraft:oak_planks                          # orchard_sleeper: the shed
execute if block 7364 138 7367 minecraft:jungle_log[axis=z]                 # split_bark: split log, bark half
execute if block 7365 138 7367 minecraft:stripped_jungle_log[axis=z]        # split_bark: split log, heart half
```

Standing space (expects 1 each; a 0 means a WorldPainter tree or rock stands where the resident spawns, which the
heightmap cannot show):

```
execute if block 613 81 4306 minecraft:air
execute if block 1138 127 3610 minecraft:air
execute if block 3544 161 1600 minecraft:air
execute if block 5541 96 1703 minecraft:air
execute if block 7022 80 312 minecraft:air
execute if block 6970 63 3970 minecraft:air
execute if block 6216 142 6112 minecraft:air
execute if block 4200 138 5920 minecraft:air
execute if block 2816 67 7080 minecraft:air
execute if block 7360 139 7376 minecraft:air
```

### Entities (one per resident)

The selector for each is `@e[type=cobblemon:pokemon,tag=cobblers.res.<id>,nbt={Pokemon:{Species:"cobblemon:<species>"}}]`.
Count with `execute if entity <selector>`, which reports how many matched.

| id | expected count after R18R | expected after a gated player comes within 96 |
|---|---|---|
| old_jaw (drednaw) | **1** | 1 |
| whiteback (mamoswine) | **1** | 1 |
| wiremother (galvantula), ridgejaw (tyrantrum), red_rail (scolipede), river_grip (grapploct), dustback (copperajah), hornwall (bouffalant), orchard_sleeper (slaking), split_bark (kleavor) | **0** | 1, for a player holding its gate (gym3, gym4, gym5, gym7, gym8, gym8, gym8, champion_cleared) |

For each present resident, read with `data get entity <selector with limit=1> <path>`:

| what | path | expected |
|---|---|---|
| UUID | `UUID` | any; record it, and it must be the same after a restart |
| species | `Pokemon.Species` | `cobblemon:<species>` |
| level | `Pokemon.Level` | the table's level |
| persistence | `PersistenceRequired` | `1b` |
| dormant | `NoAI` | `1b` before anyone comes within the trigger, `0b` after; `1b` again once everyone has left leash + 16 |
| catch rule | `Pokemon.PokemonData` | contains `uncatchable` for whiteback and hornwall only |
| River Grip float | `NoGravity` | `1b` while dormant |
| tags | `Tags` | `cobblers.res`, `cobblers.res.<id>`, `cobblers.res_dormant` while dormant; never `cobblers.gm` |

And the keeper's state: `scoreboard players get #<id>.gone cobblers.res` is `-2147483648` while the resident is
present; `scoreboard players get #resp cobblers.res` is `36000`.

### In game (needs a player)

1. Walk toward Old Jaw from the east: nothing at 30; at 24 the message "Old Jaw lifts its head from the dry bowl." and
   it starts to move. Walk 50 away: within 2 s it is back on its spot, still.
2. Throw a ball at Old Jaw on a fresh account (cap 20): refused by the level cap. Throw at Hornwall at any cap: "it
   cannot be caught".
3. Lose a battle to Old Jaw: the blackout message names it as holding your items, and its `Tags` gain
   `cobblers.guardian`; it is no longer pulled to its spot by this pack. Beat it: items back; 30 minutes later, with
   nobody within 48, a fresh Old Jaw is back.
4. Knock out a resident: note what drops, if anything (Cobblemon's species drops: not verified).

## 7. Not verified, and findings for others

- Nothing has run in Minecraft. Every behaviour above is from the generated text and the audit.
- `data merge` of `NoAI:0b` / `1b` on a live Cobblemon entity waking and settling it is unproven (EXP-023 proved NoAI
  set at spawn holds; the den's EXP-049 asks the neighbouring question about `Unbattleable`).
- That a woken resident with Fight or Flight's global config attacks, flees or idles is the mod's behaviour, unobserved.
- A WorldPainter tree or rock at an anchor would put the resident inside it: the standing-space probes find that.
- **Split-Bark's catch gate leaks** between the Elite Four and the Champion (4.3).
- **Integration: two orchards on Sunset Isle.** Another builder in this wave is building an orchard round the same
  anchor (its keeper NPC at (2786, 67, 7058), nothing within 4 of the anchor). This build's orchard dressing occupies
  bbox [2786, 7067, 2817, 7101]. Whether the two overlap, and which orchard stands, is the integrator's check: one of
  them should probably drop its trees.
- **Finding, not this unit's to fix:** `cobblers_ursaluna_cave` is in `tools/reapply.py` `SERVER_PACKS` but not in
  `WORLD_LOCAL`, although its own comment says "so world-local": its keeper loop is installed in the global datapacks
  folder, which every world the server runs loads, the live one included. It looks harmless there (it acts only on its
  own tagged bear), but it is the opposite of what the comment says. `cobblers_residents` IS in `WORLD_LOCAL`.
