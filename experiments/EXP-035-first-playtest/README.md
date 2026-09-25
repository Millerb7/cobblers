# EXP-035: The first playtest, Pallet to the third gym town

## Objective
The owner played the early game on a fresh staging export with everything re-applied, to find what breaks, what is
missing and what feels wrong before the live re-export. This is the record: every note the owner made, what caused it,
what was done, and what is still open.

## Setup
- **World:** `cobblers-runtime-proof/dryrun10/cobblers-dryrun10`, a fresh staging export from main `55e7505`, re-applied
  end to end by `tools/reapply.py` (EXP-026 run 4). The live world was not touched.
- **Versions:** Minecraft 1.21.1, Fabric, Cobblemon 1.8.0+1.21.1, rctmod 0.19.0-beta, rctapi 0.16.0-beta (0.16.1-beta
  from 2026-09-25), Waystones 21.1.37, the Cobbleverse 1.7.42 stack.
- **Rules in force:** `relativeLevelCap` 0 (`modpack/config/rctmod-server.toml`), leader rewards on first win only.
- **Player:** the owner, alone, survival.
- **Not yet in the world when the playtest ran:** our route spawns and the suppression of the inherited ones, so every
  wild encounter was Cobbleverse's default pools. Installed on 2026-09-25 (below).

## What the owner found

| # | Note (the owner's words, shortened) | Cause | Done | Status |
|---|---|---|---|---|
| 1 | Cubes in the mansion | The scene props' interaction boxes. They are visible only in creative | Nothing to change | closed |
| 2 | Hope can be battled again after beating her | rctmod skips the "already beaten" check for persistent trainers, and keeps defeats only in the loaded entity | Tag and cooldown cycle per placed trainer (PR #49) | fixed, re-tested |
| 3 | Brock can be re-fought for his TM and items | His rctmod loot table drops on every win | Leader rewards are given once, by the badge flag (PR #49) | fixed, re-tested |
| 4 | Celebi is not on the tree | It had never been built: EXP-023 tested the mechanism and stopped there | Built (below). R14C re-applies it | **owner to check** |
| 5 | No birds on the Route 1 sapling | Nothing gave the crown a pool | A Habitat Block of Route 1's birds in the crown (below) | **owner to check** |
| 6 | Gastly stuck at the foot of the library stairs after beating the trainer at the top | Working as built: after Jody, the bedroom-hall candles must be lit before Gastly climbs. The hint did not say so | Pip's library line and Jody's after-battle line both now point at the candles and the Litwick order | **owner to check** |
| 7 | Make the mine after the forest about 100 blocks long with a few branches | Owner request | The old mine's workings (below) | **owner to check** |
| 8 | Brock's battle froze when Cranidos fainted to recoil as it knocked out Wooloo | rctapi bug #132, a softlock on a double faint. Fixed in rctapi 0.16.1-beta | rctapi 0.16.1-beta pinned in `modpack/manifest/overlay.json` and installed on staging | installed. **Fix not reproduced yet** |
| 9 | Caught a Phantump and got Brock's badge | The frozen battle was cleared with `/stopbattle`, which left rctmod's battle state behind. The next battle to end, a wild catch, was credited as the Brock win | None beyond #8. Staging still holds the false badge and `gym1_cleared` | open: any stuck battle can mis-credit. Revoke the staging badge if you want a clean retest |
| 10 | Nothing to buy in Brock's town, like Poké Balls | The town's traders sell only regional goods, and the Mart building had no clerk. A template placed by command never fills its shopkeeper jigsaw | A Mart clerk in all 13 placed Marts, selling Poké Balls, Potions and Antidotes from the start | **owner to check** |
| 11 | No waypoint for the next gym | The eight gym waystone blocks stood in their towns, but `data/progression.json` had no positions for them, so the badge flags never activated them. Xaero shows only activated waystones. The chat offer of the next gym's marker did appear | Positions filled from the town plans. Each gym's waystone now activates on the badge, and a touch before that is undone | **owner to check** |
| 12 | Caught an Ursaluna at 44 before Misty | Cobbleverse's default spawns: ours were not installed | Route spawns and suppression installed | **owner to check** |
| 13 | **The level-cap trap** (owner's addition) | The level cap stops experience but not catching. rctmod refuses every trainer battle while a party member is over the cap, and says nothing about why. A player who catches something strong is silently locked out of the next gym | Nothing yet | **open: needs a fix** (options below) |
| 14 | Whiting out did not send me to the Poké Center | No blackout mechanic exists in the campaign or in the stack as configured | Nothing yet | open: research what Cobblemon 1.8 and the stack offer |
| 15 | Could not beat Misty; want custom gym teams | The leaders are Cobbleverse's own teams. The owner's custom rosters (Codex) are not installed | The rosters were checked against the cap-0 curve (reported 2026-09-25). Trainer work is paused while the owner collects ideas | open, paused |
| 16 | **Reached the third gym town within an hour** (owner) | Route lengths and the level curve, not yet measured against play time | Nothing yet | **open: flagged for the route-length and level-curve work. The owner thinks it may be the game's biggest structural problem** |
| 17 | Few Wooper, Quagsire or Clodsire at the river | Cobbleverse's default spawns again | Our waterway and route pools installed | **owner to check** |

## Done on staging, 2026-09-25

- **Route spawns and suppression** (`tools/reapply.py`):
  - `prepare` compiles our pools (`tools/compile_spawns.py`).
  - `install` generates the suppression against this server and world (`tools/suppress_inherited_spawns.py --subregions --boxes merged --grid 16`).
  - Both packs go into the world's own datapacks folder, never the global one. They load last, above Cobbleverse (`datapack list enabled`: 85 `cobblers_spawns`, 86 `cobblers_suppress` of 87). The boot logged 0 load problems.
  - The first install failed: the League's spawn-free box was off the 8-block grid (x1 3776, z1 2504). It is now snapped outward to 3783 and 2511, as its note intended.
  - Found and removed on the way: a stale `cobblers_spawns` in the **global** folder. The live world shares that folder, so its next boot will not see that pack. What the live world had enabled is unknown, because it was not read. The live re-export installs both packs into the live world's own folder.
- **Mart clerks** (`data/traders.json`, `tools/traders.py`):
  - 13 clerks with the new `mart` stock, one per placed Mart: hometown, gym1-8, mining town, Northlight, Sunset West and Tea Town.
  - Each stands one block above its template's shopkeeper jigsaw, behind the counter, facing the door, and is named "Poké Mart". It is read from BCA's general shopkeeper and keeps exactly Poké Ball 200, Potion 200 and Antidote 100.
  - The League and the Displaced City have no Mart building.
  - `traders.py verify --rcon`: 24 traders checked, 0 problems, including the check that a Mart sells exactly those three items.
- **Gym waystones** (`data/progression.json`): the eight positions come from the town plans (x, z) and their placement reports (y). All eight blocks, lower and upper, were confirmed standing over RCON.
- **The old mine's workings** (`tools/route1_old_mine.py`):
  - A 70-block main drift west-north-west from the chamber on the old track bed, to a stope with a second find.
  - A north branch of about 33 blocks to a copper face, and a south branch of about 32 blocks that ends in a fall of ground.
  - The main line is now about 110 blocks with the adit, incline and chamber.
  - The tool refuses to write it if any roof comes within 2 blocks of the heightmap's ground.
  - The existing mine tests replay every column the build writes, and pass: walked from the notch, every roofed walked cell lit, no air reaching open sky.
  - Built on staging and checked over RCON: both barrels, drift, branches and stope air, and solid ground at y128 over six roof points.
- **The stope's find** (`data/rewards.json r1_old_mine_stope`): an Everstone, two Great Balls and a Super Potion. The item ids were checked against the Cobblemon jar.
- **Celebi** (`data/sapling_celebi.json`, `tools/sapling_celebi.py`, R14C):
  - EXP-023's Pokémon entity on the branch at (1383.5, 144, 4630.5), with every proved flag. Checked over RCON: `PoseType` SLEEP, `Unbattleable` 1b, `PokemonData` uncatchable.
  - EXP-023 showed a player can kill it, so the branch is walled in barrier blocks, with the Celebi's own column left open.
  - A keeper removes a second copy and returns it to its branch if moved.
  - Found on the way:
    - Cobblemon's `spawnpokemonat` does nothing when a function runs it; the same line from the console works.
    - Vanilla `summon cobblemon:pokemon` is refused ("Unable to summon entity"), even with a full Pokémon compound.
    - So the summon runs over RCON as a new `cmd` action in the re-apply driver.
- **Sapling birds** (`data/spawns.json` habitat `route_1_sapling_crown`, `data/habitat_blocks.json route1_sapling_crown`):
  - Pidgey (24) and Hoothoot (9) at 5-8, the meadow's levels.
  - One block inside the trunk at (1380, 147, 4628), range 14.
  - Placed, its data confirmed, and its chunk reloaded by a restart.
  - A habitat pool carries no time condition, so Hoothoot is there by day too.
- **Gastly hints** (`data/dialogue.json p_library`, `data/mansion_guardians.json` Jody `after_win`): both now name the candles and the Litwick order.

## The level-cap trap: options (for the owner)

| Option | How | Cost |
|---|---|---|
| Warn on catch | A check after each catch (an advancement on `cobblemon:pokemon_caught`, or a periodic party scan) compares party levels with the player's RCT cap and says in chat: "X is over your level cap; the next gym will not battle you while it is in your party" | Needs the cap readable from a command (RCT exposes it to Molang or a scoreboard? **not verified**) |
| Explain at the refusal | When a leader refuses, say why. rctmod's own refusal text may already exist as a dialog key; if it is silent, our trainer data can carry the line | Only helps once the player is already stuck |
| Block over-cap catches | Make Pokémon above the cap uncatchable, or refuse the ball | Changes nuzlocke rules, and needs a hook RCT may not have (**not verified**) |
| Cap the spawns | Route pools never spawn above the next cap (our pools already follow the level curve; the trap came from Cobbleverse's defaults) | Does not cover raids, fishing or events |

Our installed route pools remove the most likely way into the trap. The trap itself stays until one of these is built.

## The owner still has to check
Rows 4-7, 10-12 and 17 above. The rctapi fix (row 8) needs a double knockout reproduced. The flag-driven gym waystone
(EXP-020 part F) needs a won badge, a touch before it and a reconnect.

## Limitations
- One player, one sitting. No two-player case.
- The spawn change is checked by load order and the absence of load errors, not yet by what spawns on the routes.
- Staging holds a false Brock badge from row 9.
