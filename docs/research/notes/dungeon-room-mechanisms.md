# Dungeon room mechanisms: fishing, eggs, fossils, gamble, bait, bank vault (Cobblemon 1.8.0, MC 1.21.1)

Question (the owner's "Next phase", `docs/mechanics/DUNGEON_PASS2.md:108-121`): what do Cobblemon 1.8.0 and this pack
actually support for the six new room types? Answered for **Cobblemon 1.8.0+1.21.1, Cobbreeding 2.3.0, MC 1.21.1**.
Researched 2026-10-10 by `cobblemon-researcher`.

**Method and limit.** No shell this session: the jars in `C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/`
were **not opened**. Sources are Cobblemon's tagged GitLab source at `1.8.0` (raw files), Cobbreeding's GitLab `master`
(NOT the 2.3.0 tag: tags there stop at 1.3.0, so master is ASSUMED to equal 2.3.0), the Minecraft wiki, the NeoForge 1.21.1
patch of vanilla `ItemStack`, and earlier jar reads already recorded in this repository (cited by path). Nothing here was run
in a game. Labels: **V** = VERIFIED (source, docs, local data), **A** = ASSUMED.

## Verdicts

| # | Room | Verdict |
|---|---|---|
| 1 | Fishing | **Works with a Habitat Block or a boxed spawn entry.** The Habitat Block route is the better fit, with one dungeon caveat (a command-placed block needs a chunk reload). A starter can be in the pool. Nothing is run in game. |
| 2 | Eggs | **Works.** `/givepokemonegg` (alias of `/cobbreeding egg give`) takes a species by properties. An egg cannot be hand-built with `/give` (its payload is encrypted). It hatches only in a player's inventory. Cobblemon 1.8.0 has no native eggs. |
| 3 | Fossils | **Works, but NOT by brushing as the dungeons stand.** Brushing is impossible in adventure mode unless the brush carries `can_place_on` for the block. Smallest: either a `can_place_on` brush (one experiment), or skip brushing and grant the fossil by command when a `can_break` block is mined. |
| 4 | Gamble | **Works.** Item entity in a box, `random value`, `loot give`/`give`, `kill`. Pure vanilla. |
| 5 | Bait | **Works with a custom table; Cobblemon's own bait does not do what the room wants.** Cobblemon bait raises type and egg-group weights for rod and Poke Snack spawns only. Left-item detection and a per-player score are vanilla. |
| 6 | Bank vault code | **Works.** Signs written by `data merge block`, a button keypad that reuses the existing `sequence` puzzle, a vault chest. Buttons are allowed in adventure mode. |

## Premises that were wrong or loose

- "Resurrection machine": there is no such block. Fossils are restored by `cobblemon:fossil_analyzer` + `cobblemon:restoration_tank`
  + `cobblemon:monitor` (V: `tags/item/fossil_machine_parts.json`, read from the jar and recorded in `docs/world-building/FOSSIL_DIG.md:19-22`).
- "Brush works because it interacts with the block": it does not in adventure mode (section 3).
- "Bait lures by species": no Cobblemon bait does (section 5).
- "An egg can be given with an item id and component": the item id is derived from the species' types and the species
  lives in an encrypted component, so the command is the only route (section 2).

## 1. Fishing

**Rods, bait, cast.**
- V: bait is attached by clicking a berry/bait item onto a Poke Rod in the inventory; the cast reads it back with
  `PokerodItem.getBaitStackOnRod` (`FishingSpawnablePosition`, 1.8.0 source, `api/spawning/position/FishingSpawnablePosition.kt`).
  The changelog notes bait-stacking and take-bait-out exploit fixes in 1.8.0 (CHANGELOG 1.8.0 lines on "Poke Baits").
- A: a Poke Ball on the rod is cosmetic (Cobblemon.gg guide, https://cobblemon.gg/guides/fishing, version not stated). Open: `STATE` still lists "what a rod's ball changes" as unresearched.
- V (jar read, 1.8.0): a Poke Rod's loot is junk 66 / `cobblemon:fishing/pokerod_treasure` 17 / vanilla treasure 17, both treasure entries
  conditioned on `cobblemon:poke_bobber` `in_open_water: true` (`docs/world-building/ICE_LODGE.md:101-107`).

**Where fishing spawns come from.**
- V: `FishingSpawningCondition` (1.8.0, `api/spawning/condition/FishingSpawningCondition.kt`) adds `rod` (an item), `rodType`,
  `bait` (a ResourceLocation, so a spawn entry can require one bait item), `minLureLevel`/`maxLureLevel` (max only checked
  when min is set) and `neededNearbyBlocks`, a list of blocks of which at least one must be within a 10-block cube of the
  bobber (`nearbyBlocks = AABB.ofSize(pos, 10, 10, 10)`). It extends `SpawningCondition`, which carries `minX/maxX/minY/maxY/minZ/maxZ`,
  `biomes`, `dimensions`, `structures`, `canSeeSky`, `minSkyLight/maxSkyLight`, `markers`, `isPokeSnack`, `timeRange`
  (`api/spawning/condition/SpawningCondition.kt`).
- V: the fishing position is the bobber's `BlockPos` (`FishingSpawnablePosition(cause, world, pos, influences)` sets `position = pos`,
  `canSeeSky = world.canSeeSkyFromBelowWater(pos)`).
- V: stock Cobblemon fishing lives in `spawn_pool_world` with `"spawnablePositionType": "fishing"`. Example, `0129_magikarp.json` at 1.8.0: 43 fishing
  entries, none uses `rod` or `bait`; the only lure key is `minLureLevel: 1` on the variant forms; `canSeeSky` and sky-light ranges split the
  entries by cover.
- V: server buckets for fishing (`server/config/mods/cobblemon/spawning/best-spawner-config.json:16-21`): common 83.25, uncommon 11.25, rare 4.125, ultra-rare 1.375. Poke Snack
  and activated-habitat buckets are identical.
- V: `data/spawns.json` carries **0** entries with `"spawnable_position": "fishing"`; `tools/position_types.py` deliberately ignores `fishing` when
  deriving positions; `tools/compile_spawns.py:150-159` writes whatever `spawnable_position` an entry names, and `spawnable_position_authored`
  `{position, why}` (read at `tools/position_types.py:107-109`) keeps an authored position through a re-derivation. So a fishing entry is a **data**
  change, not a generator change; whether `validate_data`/`build_encounters` accepts the value was not read (A).

**Can a datapack give one room better pools?** Three ways, in the order recommended:
1. **Habitat Block with a pool of `fishing` details (V, source).** `NaturalHabitatSpawning.affectsFishing` is true if any detail in the pool has
   position type `fishing` and `affectsOverworld` is true if any detail is not `fishing`; `HabitatBlockEntity.getInfluentialRange` returns 0 for the
   fishing spawner when `affectsFishing` is false, else `rangeOfInfluence` (1.8.0, `block/habitat/HabitatBlockEntity.kt`). So a **pure-fishing pool**
   influences only casts within its sphere and leaves every other spawn in the room alone. `ReplaceSpawns` true replaces the cast's normal table;
   false adds to it. Range is a 3D sphere (`docs/research/notes/habitat-blocks-underground.md` section 3). The pool is a `habitat_pools/*.json` file
   (`species`, `spawnablePositionType`, `bucket`, `weight`, `levelRange`, optional `modifiers`, `phases`, `timeRange`, `minLight`, `maxLight`) and
   `tools/compile_spawns.py:439-462` already emits that shape from `mechanism: "habitat_block"` entries, passing `spawnable_position` through.
   **Fishing influence has never been tested**: `data/spawn_suppression.json:17` says "vertical reach and fishing untested" (EXP-021).
   **Dungeon caveat (V, EXP-021 result at `data/spawn_suppression.json:17`)**: a command-placed Habitat Block activates only after one chunk reload,
   and overlapping `ReplaceSpawns` ranges spawn nothing. A room rebuilt each run needs the block to survive reset, or its chunk reloaded.
2. **A boxed `spawn_pool_world` fishing entry.** Use `minX/maxX/minY/maxY/minZ/maxZ` plus `dimensions: ["cobblers:pocket"]` (V field names; the
   dimension check is V in `docs/research/notes/spawn-dimension-condition-1.8.0.md:9-16`). No POI dependency, so it survives room resets. That the
   fishing context honours the box is A (the field exists and `position` is the bobber; `fits` was not read at 1.8.0). Planned as proof P7 in `docs/mechanics/WATER_BUILD_PLAN.md:628`.
3. **`neededNearbyBlocks` or `bait`/`rod` keyed entries.** A "lure block" in the room, or an entry that needs a given bait, works without coordinates (V fields). A shared
   global entry would apply wherever that block or bait appears, so it fits a special bait better than a room.

**Bait effects (V, 1.8.0 `SpawnBait.kt`, `SpawnBaitInfluence.kt`).** Effect JSON is `{type, subcategory?, chance, value}` (all but `subcategory` required). Types
that exist: nature, IV, shiny reroll, mark chance, drops reroll, gender chance, level raise, hidden-ability chance, alpha chance, friendship, size, plus the
weight effects `cobblemon:typing` (multiplies a matching-type species' weight by `value`), `cobblemon:egg_group` (same, by egg group) and `cobblemon:ev`
(species whose EV yield for the stat is 0 or less get weight 0). Examples read: `payapa_berry` = typing `psychic` value 10; `cheri_berry` = egg groups
`fairy`, `grass` value 10 each; `poke_bait` = no effects. Constants `POKEMON_CHANCE` and `RARITY_BUCKET` exist but `SpawnBaitInfluence` does not act on them
(A: whether some other code does was not found). Bait therefore reshapes weights **inside the pool that already exists**; it cannot add a species.

**Can a starter be in a fishing pool?** A: yes mechanically, since `HabitatSpawn.species` and `PokemonSpawnDetail` take any species. Whether a land starter
placed at a bobber behaves (swims, drowns, is catchable) is untested. Water starters (Squirtle, Totodile, Mudkip, Piplup, Oshawott) are the safe pick. The level-cap
catch block (`docs/research/notes/level-cap-catch-block.md`) applies to a fished Pokemon like any wild one.

**Bucket warning (A).** The fishing buckets above are applied before weights, so a room that puts its cool species in `rare` (4.125%) gets them 4.125% of the time
whatever their weight. For "better chances", use a `ReplaceSpawns` pool with the wanted species in `common`. How the spawner behaves when a rolled bucket is empty
was not read (A: it retries or skips).

**Smallest mechanism:** a pure-fishing `habitat_pools` file for the room, species in `common`, one Habitat Block with `ReplaceSpawns` and a range just over the
room's water, placed so it survives the slot reset (or re-placed with a chunk reload). Fall back to option 2 if the block cannot survive.

## 2. Eggs

- V (Modrinth, https://modrinth.com/mod/cobbreeding): `/givepokemonegg` "gives a Pokemon Egg item to a player", arguments as Cobblemon's `/pokegiveother`; forms by
  `form=` (example `/givepokemonegg Ludichat vulpix form=alola`). Eggs in a player's inventory hatch as time passes; the timer pauses outside an inventory;
  `eggHatchMultiplier` 1.0 gives about 10 minutes for an egg cycle of 20. Config also has `eggEncryptionEnabled` (default true). Source: https://gitlab.com/ludichat/Cobbreeding.
- V (Cobbreeding `master`, `commands/main/eggCommands/EggGiveCommand.kt`): `give <player> <properties>`, permission `command.cobbreeding.egg.give` at
  `CHEAT_COMMANDS_AND_COMMAND_BLOCKS`, builds the stack with `EggUtilities.getEggFromPokemonProperties(props)`, null species gives an error, `player.addItem(stack)`. The
  `<player>` argument is parsed but the recipient is `context.player()` (the executing player). A (inference): run it as
  `execute as <player> run givepokemonegg <player> <species> ...` from a function; a console or an unattributed command may fail.
- V (`EggUtilities.kt`, `components/CobbreedingComponents.kt`, master): the item id is built from the species' types (`cobbreeding:<type>_pokemon_egg` or
  `<type1>_<type2>_pokemon_egg`, `manaphy_egg`, fallback `pokemon_egg`); components `cobbreeding:name` (species name, always set), `cobbreeding:timer`, `cobbreeding:second`,
  `cobbreeding:egg_info` (the properties, **AES-encrypted** with a per-install key), `cobbreeding:pokemon_properties` (plaintext only when encryption is off) and
  `cobbreeding:version`. Local evidence of the item ids and version component: `base-pack/cobbleverse/config/roughlyenoughitems/config.json5:202` (`cobbreeding:version`
  `2.0.3`, `cobbreeding:fire_pokemon_egg`). **So an egg cannot be written with `/give`**; only the command makes one. The same command's `random` species form exists (A: it needs the literal `random`).
- V (`PokemonEgg.kt`, master): the timer counts down in `inventoryTick` for a **player** only (about 20 per second, extra with Magma Armor/Flame Body/Steam Engine in the party); at zero it hatches
  into the **party** with friendship 120 (the source has no PC fallback, so a full party is a question, A for 2.3.0), updates the Pokedex and removes the egg. No lore component is used: the tooltip shows the species
  name (from `cobbreeding:name`) and the time left, so **the egg's species is not hidden** even with encryption on.
- A: `level=` and other properties pass through `props.asString(" ")` into the hatched Pokemon; this was not seen. `/hatch` forces a hatch (timer 0) for the executor's main-hand egg.
- V: Cobblemon 1.8.0's changelog has no egg or breeding entry (CHANGELOG 1.8.0, search for egg and breeding found only "Eggant berries"). A, absence only: no native eggs.
- Caveat: `docs/research/CASINO.md:323` says a Ditto grant "enables Cobbreeding"; what gates the mod's behaviour was not looked up. Vendor eggs by command do not depend on pasture breeding (A).

**Smallest mechanism:** the vendor's dialogue calls a function that runs `execute as @s run givepokemonegg @s <species>` (the repo's dialogue pipeline already has `give_item`/function steps,
`docs/world-building/ICE_LODGE.md:150`). The "description" is the vendor's dialogue line, or `item modify ... set_lore` on the held egg (A: a standard component, not tested on this item).
The hatch timer runs in the inventory, so the dungeon clock and the egg clock overlap. Not tested: the command from a function; the hatched level; party-full behaviour.

## 3. Fossils

- V (jar read 2026-10-05, `docs/world-building/FOSSIL_DIG.md:12-28`): the 15 fossil items are in `tags/item/fossils.json`; I re-read it from GitLab 1.8.0: `cobblemon:helix_fossil`, `dome_fossil`, `old_amber_fossil`,
  `root_fossil`, `claw_fossil`, `skull_fossil`, `armor_fossil`, `cover_fossil`, `plume_fossil`, `jaw_fossil`, `sail_fossil`, `fossilized_bird`, `fossilized_fish`, `fossilized_drake`, `fossilized_dino`.
  Fossils are **archaeology loot**: `data/cobblemon/loot_table/fossils/{common,uncommon,rare}/*.json` are `"type": "minecraft:archaeology"`; `rare/<name>.json` is one pool, one roll, the one fossil;
  `common/` holds no fossil. The Analyzer, Tank and Monitor recipes are in FOSSIL_DIG.md:19-22 (the Analyzer needs amethyst, the Tank a Revive). Fossil-to-species data is a `data/cobblemon/fossils/<name>.json` folder
  (the Cobbleverse datapack overrides one: `docs/mechanics/ITEM_ROUTES.md:136`).
- V (`docs/research/OBTAINABILITY_VANILLA_COBBLEMON.md:86-90`): 14 of 15 fossils have no source but natural trainer loot, and the world's own fossil sites are worldgen. This repo already built a dig that
  uses `suspicious_gravel{LootTable:"cobblemon:fossils/rare/<name>"}` (Scorchbone Dig, `docs/world-building/FOSSIL_DIG.md`, `data/fossil_dig.json`); its authors list "that `setblock ... suspicious_gravel{LootTable}` keeps its table and brushes out the fossil" as not verified (FOSSIL_DIG.md:166).
- V (Minecraft wiki, Suspicious Sand): the block entity has an `item` field ("The item in the block. May not exist."). A (vanilla knowledge, not on the fetched page): `LootTable` and `LootTableSeed` are also saved.
  So the fossil can be set directly, `suspicious_gravel{item:{id:"cobblemon:helix_fossil",count:1}}`, with no loot table (A: the 1.21.1 `item` form is `{id, count}`; the 1.21.1 `count` key is confirmed by `base-pack/.../config.json5:202`).
  A datapack can also add its own archaeology table, `data/<ns>/loot_table/...` with `"type": "minecraft:archaeology"` (A).

**Brushing in adventure mode: it does not work as things stand (V).**
- V (Minecraft wiki "Adventure", wikitext, https://minecraft.wiki/w/Adventure): "Using a brush on suspicious blocks" is in the **Impossible in Adventure mode** column (with the axe-strip, shovel and hoe uses).
  The same table lists button/lever/pressure plate use as possible, and inserting items into a jukebox, chiseled bookshelf, lectern, flower pot, decorated pot (and the newer shelf) as possible.
  The table is the current Java page, not 1.21.1 specifically.
- V (NeoForge 1.21.1 patch of vanilla `ItemStack`, https://raw.githubusercontent.com/neoforged/NeoForge/1.21.1/patches/net/minecraft/world/item/ItemStack.java.patch): in `useOn`'s helper,
  `if (player != null && !player.getAbilities().mayBuild && !this.canPlaceOnBlockInAdventureMode(new BlockInWorld(...)))` the call returns `InteractionResult.PASS`. This gate is on **every** item's use-on-block, so
  `BrushItem.useOn` never starts the brush for an adventure player unless the held stack passes `canPlaceOnBlockInAdventureMode`.
- A: that method reads the stack's `minecraft:can_place_on` component. Then `give @s minecraft:brush[minecraft:can_place_on={predicates:[{blocks:["minecraft:suspicious_gravel"]}]}]` should enable brushing
  that block; the shape is the same as the proven-to-parse `can_break` (EXP-074 R2 RCON part passed; the in-game owner half is still open). `can_place_on` on a torch is already listed UNPROVEN
  (`docs/mechanics/DUNGEON_ROOMS.md:461`). Once brushing starts, the brush tick has no adventure check (A, from memory of vanilla), and the loot drops from the block entity (A).
- The dig the dungeons would copy was written for survival play; `data/fossil_dig.json` gives no `can_place_on`.

**Smallest mechanism, two options.**
1. **A brush with `can_place_on`** for the dig block, then count the dig by the block turning into gravel (the same "block changed" event the old seam counted). One experiment decides it.
2. **No brush.** The fossil is a block the rift pick may break (`can_break`, the existing resources-room mechanism, `tools/dungeon.py:554-559`); `tools/dungeon_greed.py` already counts any
   `minecraft.mined:<block>` objective at a table value (`dungeon_greed.py:17-23`) and so "a fossil counts as a resource (greed)" for free. The fossil itself is given by the same function that reads the
   count (`give @s cobblemon:<fossil>` or `loot give @s loot cobblemon:fossils/rare/<name>`; `/loot ... loot` on an archaeology table is A, since the wiki page does not cover table types).
   This depends on `can_break` and the mined stat working in adventure mode, which EXP-073/EXP-074 still list as an open owner half.
The Fossil Analyzer/Tank are separate crafted blocks and are not part of a dungeon room.

## 4. Gamble (wishing well)

All of this is vanilla 1.21.1; no mod is needed. Detection and roll:
- V (wiki, https://minecraft.wiki/w/Item_(entity)): an item entity has `Item`, `Age`, `PickupDelay`, `Owner` and `Thrower` (the UUID of the dropper). Item stacks in 1.21.1 are `{id, count, components}` (V: the `count` key, local `config.json5:202`).
- V: `execute if|unless items block|entity ...` exists from 1.20.5 (wiki, `/execute`); `execute if data` from 1.14; `/random value <min>..<max>` from 1.20.2 and its range size must be 2 to 2147483646, so `1..1` is an error
  (wiki, `/random`); `execute store result score ... run random value 1..100` is the documented form and the pack already writes it in 8 generators (e.g. `tools/gulch_mine.py:1624`,
  `tools/dungeon_prize.py:306`). In-game proof of `random value` in the dungeons is not recorded (`docs/mechanics/DUNGEON_ROOMS.md:44-46` lists it unproven).
- V: `loot give <players> loot <table>` and `loot spawn <pos> loot <table>` (wiki, `/loot`).
- A: adventure mode can drop and pick up items (the wiki's table has no row against it). A dropped item has a `PickupDelay` (V field, wiki; the value, about 40 ticks for a thrown item, is A), so a tick function sees it before the player can take it back.
- A (a standard pattern): per tick, `execute as @e[type=item,x=X,y=Y,z=Z,dx=2,dy=2,dz=2,nbt={Item:{id:"minecraft:emerald"}}] run function <ns>:gamble/take`; `take` reads `data get entity @s Item.count`, `kill @s`, rolls
  `random value 1..100`, and `loot give` or `give` the reward to the run's member. Attribution is trivial because dungeon slots are solo (`members_max` 1, `tools/dungeon_prize.py:15`, `tools/dungeon_greed.py:32`);
  with co-op, copy `Thrower` into storage and compare it with each player's `UUID` (A).
- Economy: whatever is gambled must be weighed in `tools/dungeon_greed.py`'s table, or a gamble is an arbitrage loop (`CLAUDE.md`, economy audits).

**Smallest mechanism:** one tick-run function in the room (guarded by "a member is in the room", like the relic pickup, `docs/mechanics/DUNGEON_ROOMS.md:495`) plus a loot table. Not run in game.

## 5. Bait carried between runs

**Cobblemon's own bait (V, 1.8.0 source).** Bait effects reshape the weights of species already in a pool, by type or egg group, or change a spawned Pokemon's stats; they apply to **rod casts** and **Poke Snacks**
(`PokeSnackSpawnerFactory`, 1.8.0 changelog; `docs/research/DROPS_AUDIT.md:134-142`: a snack spawns about 9 Pokemon over roughly 20 minutes and is consumable). No bait selects a species. Leaving a berry in a room
therefore cannot make Cobblemon spawn "the Pokemon that berry lures"; the room needs its own table.

**Detecting a left item (all vanilla).**
- A container slot: a barrel or chest the player opens (the engine already treats vault chests as usable in adventure; `docs/mechanics/DUNGEON_ROOMS.md:44` lists it unproven) and
  `execute if items block X Y Z container.* <item_predicate>`; or a decorated pot (any item, one stack; `item` field, V wiki Decorated Pot) via `execute if data block X Y Z item{id:"..."}`, and `data remove block X Y Z item`
  to take it. The wiki table lists inserting into a decorated pot or lectern as possible in adventure mode (V, current Java page).
- An item entity in a box, as in section 4.
- **Not an item frame**: placing item frames is impossible in adventure mode (V, same table), and the dungeon notes already avoid them (`DUNGEON_ROOMS.md:521`).

**Storing it per player across runs (V, local).** The engine already keeps cross-run per-player state in scoreboards and advancements (`dg.rl_<short>` counts, the relic advancement; `docs/mechanics/DUNGEON_ROOMS.md:499-507`;
"no function resets or removes a count"). A: store `scoreboard players set @s dg.bait <code>` from a table (item id to code), or a storage key per player UUID with macros.

**Making it appear in the next dungeon (V, local).** `spawnpokemonat $(x) $(y) $(z) $(species) level=$(level) uncatchable no_ai` as a function macro was proven on staging (EXP-046; `tools/ambient.py:15,460-463`), and
`tools/dungeon_prize.py` already spawns a band prize at a room anchor at entry. The bait room reuses that with a species chosen from the stored code. The species table (item to species/type, level from the entrant's band cap) is the room's data.

**Smallest mechanism:** a slot (decorated pot or barrel), a tick function that reads it, a `dg.bait` score, a table, and the next run's room-enter spawn through the existing prize macro. Not run in game.

## 6. Bank vault code

- V (repo, 6 generators write it): 1.21.1 sign block entity form `{front_text:{messages:['<json>','<json>','<json>','<json>']}}` with optional `is_waxed:1b`
  (`tools/deep_city.py:503`, `tools/dungeon_crossroads.py:28,142` which says "the 1.21.1 block-entity form `front_text.messages` as JSON strings, read from the format, not run here"). Text can be rewritten at run
  time with `data merge block X Y Z {front_text:{messages:[...]}}` (V: the wiki's sign page gives a `data merge block ... {front_text:{color,messages}}` example). A macro (`$data merge block $(x) ...`) fills in the digits from a score. The JSON-string `messages` form applies to 1.20.5 to 1.21.4 (A, my recollection).
- V (wiki, Adventure table): editing sign text is impossible in adventure mode, so players cannot tamper with a sign; buttons, levers and pressure plates are usable. A: waxing is not needed.
- V (repo, built and simulated, **not run in game**): `tools/dungeon_puzzles.py:20-35` already has a `sequence` variant (N wooden buttons, press them in the order shown, a progress lamp per right press, a wrong press resets everything, `penalty_s` charged), and it
  chooses its target at room entry with `random value 0..K-1` among up to 8 precomputed variants. A digit keypad is that variant with 10 digit buttons and the order shown on signs in other rooms.
- Cross-room signs: the code is picked once at slot start, and each sign is written when its room is entered (functions in this engine carry a `# chunks-loaded-by:` comment: a `data merge block` on an unloaded chunk does nothing). A (inference).
- The vault is a chest with a loot table, "the vault's proven-in-code form" (`data/dungeon_resources.json:60`, `tools/dungeon_puzzles.py build_vault`); the engine counts the opened chest as greed (`dungeon_greed.py:24-25`).
- Why it could fail in adventure mode: an unwaxed sign is not editable but `is_waxed` is not required; a button needs no `can_place_on`. Nothing in the table blocks the keypad. The open risk is the existing unproven puzzle (lever/button/plate in adventure, `DUNGEON_ROOMS.md:44`).

**Smallest mechanism:** reuse the `sequence` puzzle for the keypad, roll the code with `random value`, and write the digits to the signs on room entry; the vault is the existing vault chest.

## Unknown / experiment candidates (not entered in `docs/research/EXPERIMENT_BACKLOG.md`: this brief limited writes to `docs/research/notes/`)

1. **Fishing through a Habitat Block**: a pure-fishing pool with `ReplaceSpawns` true, one block, cast 100 times with a Poke Rod; must show only pool species. Then place the block by `setblock` and check it needs a chunk reload. Then a boxed `spawn_pool_world` fishing entry with `dimensions: ["cobblers:pocket"]`. Then `canSeeSky` false (an enclosed room): do pool entries without `canSeeSky` still fire?
2. **A land starter at a bobber**: a Bulbasaur in a fishing pool; does it appear, swim, accept a ball?
3. **Empty bucket**: a pool with only `common` entries; do 5% of casts roll an empty bucket and spawn nothing?
4. **Brush in adventure mode** (the decisive one for section 3): `give @s minecraft:brush[minecraft:can_place_on={predicates:[{blocks:["minecraft:suspicious_gravel"]}]}]`, then brush `suspicious_gravel{item:{id:"cobblemon:helix_fossil",count:1}}`. Must show: the brush starts, the block becomes gravel, the fossil drops and can be picked up. Control: the same without the component must do nothing.
5. **`setblock ... suspicious_gravel{LootTable:...}` and `{item:...}`** both keep their contents (FOSSIL_DIG.md:166 already asks).
6. **The egg command from a function**: `execute as <player> run givepokemonegg <player> bulbasaur`; the item id and components; hatched level with `level=5`; hatching with a full party; `item modify ... set_lore` keeps the egg working; the same on Cobbreeding 2.3.0 (this note read `master`).
7. **Wishing well**: an item thrown into a 2x2x2 box by an adventure player is seen, killed, and rolls; the `Thrower` UUID's int-array form.
8. **Decorated pot / barrel in adventure mode** in `cobblers:pocket`: can an adventure player insert and withdraw?
9. **Keypad**: the buttons of the `sequence` puzzle in adventure; the signs rewritten on room entry; the old unproven items in `DUNGEON_ROOMS.md:44-46`.
10. **Bait-effect check**: a Payapa Berry on a rod in a pool containing Psychic and non-Psychic species shifts the catch ratio by about 10x (the weight multiplier).

## Not reached

- The jar's own `fits` bytecode for the fishing context at 1.8.0 (box honoured, bucket retry).
- Cobbreeding 2.3.0 source (only `master` was readable) and its server config values in this pack.
- Whether the Cobbleverse datapack (`COBBLEVERSE-DP-v31`) edits fishing spawns, rods or bait effects; it is an unreadable zip here.
- `docs/research/CAPABILITY_MATRIX.md` and `EXPERIMENT_BACKLOG.md` were not updated (outside the brief's write scope); the caller can fold the table above into them.
