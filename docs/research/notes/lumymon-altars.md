# What a pasted LumyMon altar can and cannot do (offline reading, 2026-10-02)

> **CORRECTION, 2026-10-02, measured by the main session against the server's files under the lock.** This note's claim that the feathers and the crown are inside the templates' barrels is **wrong**. The templates were read: Articuno's barrel holds wind charges, ice gems, glass panes, breeze rods and diamond boots; Zapdos's holds redstone, electric gems, a trident and copper bulbs; the cemetery stocks no barrel. Across all 102 mod jars and every server datapack, **no recipe or loot table produces `glacier_feather`, `thunder_feather` or `calyrex_crown`** (they appear only as advancement icons and TM-recipe ingredients). Obtainable: the `origin_fossil` (LumyMon recipe) and the shaderoot carrot (the cemetery's own crop). So a working altar is usable in play only for Mew and for the cemetery's Spectrier trigger, unless the campaign supplies the item.

Prepared for EXP-048. Nothing here was booted, placed or clicked. **VERIFIED** means read in a jar, zip or
config file named on the line. **INFERRED** means a conclusion from names, strings or vanilla behaviour that
the files do not state outright. LumyMon is closed source (`CC BY-NC-ND 4.0`, `fabric.mod.json`); it was read
with Python `zipfile` only: metadata, resources, and the UTF-8 entries of class constant pools (class, method
and field names and string literals). No bytecode was disassembled or decompiled and no code is reproduced.
Numeric values held in bytecode (radii, delays, default booleans) were therefore NOT read and are marked
unknown.

## Sources

| Source | What was read |
|---|---|
| `cobblers-server/mods/LumyMon-0.6.6.jar` | `fabric.mod.json`, `lumymon.mixins.json`, `assets/lumymon/lang/en_us.json`, `assets/lumymon/blockstates/*.json`, `data/lumymon/**`, class names, constant-pool strings of `block/custom/{SummonAltar,ArticunoAltar,ZapdosAltar,MewShrine,CalyrexStatue,SummonTrigger,SummonAnchor}`, `block/entity/ModBlockEntities`, `item/ModItems`, `block/ModBlocks`, `util/{ModPermissions,SummonScheduler}`, `config/LumyMonConfig` |
| `cobblers-server/datapacks/COBBLEVERSE-DP-v31.zip` | every `.json`/`.mcfunction` naming the altars, items or `defeat_champion_blue`; the four templates `data/cobbleverse/structure/{crown_cemetery,legendary/articuno,legendary/zapdos,mythical/mew}.nbt` (palette names, container item ids, command-block `Command` strings) |
| `cobblers-server/datapacks/COBBLEVERSE-{RCT-DP-v20,Loot-DP-v11}.zip`, `PokeCenterPCs-DP.zip`, `COBBLEVERSE - No *.zip` | same string scan |
| `cobblers-server/mods/*.jar` (102) | `fabric.mod.json` id/version/env of each, and class names matching fake-player patterns |
| `cobblers-server/server.properties` | the lines `enable-command-block`, `function-permission-level`, `op-permission-level`, `level-name` only |
| `cobblers-server/config/lumymon.json` | whole file (11 keys) |

The reference snapshot in the main checkout (`base-pack/cobbleverse/`) holds no `mods/` and no datapack
zips, so the server's copies were the only ones available. They are the ones that matter: they are what runs.

## 1. The LumyMon jar (0.6.6)

`fabric.mod.json`: id `lumymon`, version `0.6.6`, env `*`, depends `cobblemon >=1.7.1`, `minecraft ~1.21.1`,
`fabricloader >=0.17.2`, `fabric-api *`; nests `fabric-permissions-api-0.3.1.jar`. VERIFIED.

### Blocks and activation items

Every altar here is a subclass of one base, `block/custom/SummonAltar`, which declares the methods
`getActivationItem`, `getRequiredAnchorBlock`, `isAnchorRequired`, `getPokemonName`, `generatePokemonCommand`,
`getCheckRadius`, `getAnchorRadiusXZ/HeightUp/HeightDown`, `getSpawnDelayTicks`, `spawnRewardItem`,
`applyEffects`, `findAnchor`, `isPokemonNearby`, `checkCooldown` and `onUseWithItem`. VERIFIED (constant pool).

| Block id | Class | Activation item (field it returns) | Spawn strings in the class | Block entity |
|---|---|---|---|---|
| `lumymon:articuno_altar` | `ArticunoAltar extends SummonAltar` | `lumymon:glacier_feather` (`ModItems.GLACIER_FEATHER`) | `articuno level=50..60 ... aspect=legendary`, two `articuno shiny level=50/60` | none |
| `lumymon:zapdos_altar` | `ZapdosAltar extends SummonAltar` | `lumymon:thunder_feather` (`THUNDER_FEATHER`) | `zapdos level=50..60 ... aspect=legendary`, two shiny | none |
| `lumymon:mew_shrine` | `MewShrine extends SummonAltar` | `lumymon:origin_fossil` (`ORIGIN_FOSSIL`) | `mew level=75/80 ... aspect=mythical`, `mew shiny level=75/90` | none |
| `lumymon:calyrex_statue` | `CalyrexStatue extends SummonAltar` | `lumymon:calyrex_crown` (`CALYREX_CROWN`; also references `CALYREX_CROWN_SHINY`) | `calyrex level=70 ...`, `calyrex shiny level=70 ...` | none |
| `lumymon:summon_trigger` | `SummonTrigger` (NOT an altar subclass) | none held: reacts to an item **entity** — `ICEROOT_CARROT` -> `spawnGlastrier`, `SHADEROOT_CARROT` -> `spawnSpectrier` | `spectrier level=50..59 ...`, `spectrier level=70 ...`, shiny 70; same for glastrier | none |
| `lumymon:summon_anchor` | `SummonAnchor` | — | none; tooltip "Pokemon from Altars appear here" | none |

All VERIFIED: ids from `ModBlocks`/`ModItems` registration strings and `blockstates/*.json`; activation fields
from each class's constant pool; lang tooltips confirm the pairing in plain words (`tooltip.lumymon.glacier_feather`
"Required to summon Articuno at its Altar", `thunder_feather` likewise for Zapdos, `origin_fossil` "revive Mew
within the Mew Shrine", `calyrex_crown` "Placed upon its statue summons the King of Bountiful Harvests",
`shaderoot_carrot` "Awakens the Spectral Steed in the Crown Cemetery").

**No altar is a block entity.** `ModBlockEntities` registers exactly eleven block-entity types (apricorn box,
map trader x7 tables, stark forge, arceus pedestal, space-time altar, palkia/dialga/origin statues, regigigas
statue, elevator) and none of the six blocks above. VERIFIED. Blockstates: `articuno_altar`, `zapdos_altar`,
`mew_shrine`, `summon_trigger`, `summon_anchor` have one variant `""`; `calyrex_statue` has
`facing x has_crown`. VERIFIED.

**Consequence: there is nothing per-block for worldgen to write that a paste could miss.** The open worry in
`data/adopted_legendary_sites.json` ("whether an altar needs state written at WORLDGEN time") is answered as far
as the block goes: no NBT, no block entity, only a palette entry `/place template` copies like any other block.
VERIFIED for the block. INFERRED for the world: the only `PersistentState`-looking classes are
`util/ArceusGlobalState` and `util/NightmareState`, neither summon-related; `SummonScheduler` is an in-memory
`ConcurrentLinkedQueue` drained on `ServerTickEvents.END_SERVER_TICK`, and the cooldown is an in-memory
`ConcurrentHashMap` keyed by player UUID with `currentTimeMillis`. Nothing in the strings names a structure
start, a `location_check` or a biome, so **nothing found ties an altar to having been generated by worldgen.**

### What a right-click requires (from strings and lang; order of checks NOT read)

1. **The activation item in hand.** Message `message.lumymon.altar_requirement` = "This altar requires a %s to
   activate". VERIFIED string. Whether the item is consumed: UNKNOWN.
2. **Permission `lumymon.altar.use`** via `me/lucko/fabric/api/permissions/v0/Permissions.check(player, node,
   boolean default)` (`ModPermissions`); refusal text "You do not have permission to use this altar" (the
   statue: "...to use the Calyrex Statue."). VERIFIED. No permissions provider (LuckPerms or similar) is in the
   server's mods, so the call returns its **default**, which is a bytecode constant not read. INFERRED that the
   default is `true` (Cobbleverse is played by non-ops), unverified.
3. **A `lumymon:summon_anchor` near the altar**, unless the altar's `isAnchorRequired` says otherwise. Refusal
   text "Summon Anchor not found near the Altar". VERIFIED string. **Articuno, Zapdos and Mew do not override
   `isAnchorRequired`** (absent from their pools; VERIFIED), so they take the base's default, which was not read.
   **None of the three templates contains a summon anchor** (palette scan: articuno.nbt's only `lumymon:` block
   is `articuno_altar`, zapdos.nbt's `zapdos_altar`, mew.nbt's `mew_shrine`; VERIFIED). INFERRED: the base default
   is "not required", or Cobbleverse's own towers would never work; Articuno's override of the anchor radii
   argues the anchor is used when present. **This is the single most likely way a paste fails, and the probe
   names it in chat.**
4. **No wild one already nearby.** `isPokemonNearby` searches for a `com/cobblemon/.../PokemonEntity` of the
   same species name that `isPlayerOwned` is false for, within `getCheckRadius`; message
   `message.lumymon.pokemon_already_nearby`. VERIFIED strings; radius UNKNOWN.
5. **Calyrex statue only:** "This statue requires the Crown of the King to be restored." and a `has_crown`
   blockstate. VERIFIED. INFERRED: the crown is placed onto the statue (`has_crown=true`) as part of activation.

**No time, weather, dimension, biome, advancement or flag condition appears in any altar class's strings.**
VERIFIED as absence of strings; a condition expressed only through obfuscated Minecraft calls
(`class_xxxx`/`method_xxxx`) cannot be ruled out without reading bytecode, which was not done.

### What firing does

The base formats `pokespawnat %.1f %.1f %.1f %s` (US locale) with the species string and executes it through
the `MinecraftServer` command dispatcher, scheduled via `SummonScheduler` after `getSpawnDelayTicks`; failures
log `Summoning failed: {}` to the `LumyMon` logger. The trigger formats `pokespawnat %d %d %d %s` and logs
`Error executing pokespawn command: {}`. VERIFIED strings. On success the player is sent a
`message.lumymon.<species>_summoned` line (e.g. "Articuno has descended: a chilling breeze heralds the coming
of winter!"), and the classes reference a status effect, a sound and particles. VERIFIED strings; which effect
is not readable (obfuscated field). `pokespawnat` is a Cobblemon command (the Necrozma towers' command blocks
use it, per `data/adopted_legendary_sites.json`). INFERRED that it runs with server-level permission, so the
player's op level does not matter.

**Levels, VERIFIED from the class strings** — this corrects the uncited "70-90" relayed in
`data/adopted_legendary_sites.json` `what_is_actually_known`:

| Species | Levels in the jar |
|---|---|
| Articuno, Zapdos | 50, 55, 60 (shiny 50 or 60) |
| Mew | 75, 80 (shiny 75 or 90) |
| Calyrex | 70 |
| Spectrier, Glastrier (trigger) | 50-59, 70 |

Every one is above the 65 champion cap that file cites, so the "uncatchable if it works" concern stands, but
Articuno and Zapdos at 50-60 are closer to it than the record says.

### SummonTrigger is driven by a dropped item, not a click

`SummonTrigger` holds the strings `entity`, `itemEntity`, `item`, `findNearestSummonAnchor`,
`ICEROOT_CARROT`, `SHADEROOT_CARROT`, `spawnGlastrier`, `spawnSpectrier`, and prints "Summon Anchor not found
near the Altar" to `System.out` when it has no anchor. VERIFIED strings. INFERRED: a carrot item entity
touching the trigger summons the steed at the nearest anchor. It also formats
`summon minecraft:item %d %d %d {Item:{id:"lumymon:calyrex_crown_shiny",Count:1b}}` — INFERRED a reward drop on
one branch. **If the item-entity reading is right, this one needs no player at all** (see section 4).

## 2. The Cobbleverse datapacks

Nothing in any datapack's functions, predicates or loot tables names an altar block, `summon_trigger` or
`summon_anchor`. VERIFIED (string scan of all six zips). What does exist:

- **The activation items ship inside the templates.** `legendary/articuno.nbt` has `lumymon:glacier_feather` in a
  `sophisticatedstorage` barrel's `Items`; `legendary/zapdos.nbt` has `lumymon:thunder_feather` likewise;
  `crown_cemetery.nbt` has `lumymon:calyrex_crown` in a barrel and `lumymon:shaderoot_carrot_crop` at `age=7`
  (harvestable; the jar ships `loot_table/blocks/shaderoot_carrot_crop.json`); `mythical/mew.nbt` has
  `lumymon:ancient_dna` in a container. VERIFIED (item ids in container context). **So a pasted Articuno or
  Zapdos site is self-contained: altar and feather arrive together.** Mew is not: `origin_fossil` must be
  crafted (jar `recipe/origin_fossil.json`: `lumymon:ancient_dna` + 5 x `#cobblemon:fossils` +
  `cobblemon:ancient_origin_ball`). VERIFIED.
- **`defeat_champion_blue`** (`data/cobbleverse/advancement/trainer/kanto/defeat_champion_blue.json`): granted by
  `rctmod:defeat_count` on `trainer_ids: ["kanto_champion_blue"]`, reward function
  `cobbleverse:blue_champion_defeated`. It is the parent of `item/craft_origin_fossil`. VERIFIED.
- **Mew's command blocks.** `mythical/mew.nbt` carries 7 command-block occurrences and 2 stone pressure plates.
  The commands read: `fill ~-6 ~ ~-6 ~6 ~6 ~6 air replace minecraft:stone_pressure_plate`; a `tellraw` "You have
  proven yourself worthy..."; `execute if entity @p[advancements={cobbleverse:trainer/kanto/defeat_champion_blue=true},distance=..5]
  run fill ~-3 ~ ~-3 ~6 ~6 ~6 air replace minecraft:chiseled_stone_bricks`; and the `=false` branch telling the
  player to defeat Blue. VERIFIED. So the command blocks gate **access** (they clear a chiseled-stone-brick
  wall), not the shrine: `MewShrine` itself names no advancement. INFERRED from the two together.
- Advancements `catch_articuno`, `catch_zapdos`, `catch_mew` (and shiny) use the feathers/fossil as icons and
  `cobblemon:aspects_collected` on `aspects: ["legendary"]`/`["mythical"]` — the same aspects the altar spawn
  strings set. They observe a summon; they do not enable one. VERIFIED.
- RCT DP: `kanto_giovanni` loot drops `lumymon:ancient_dna` on first defeat. VERIFIED. TMCraft recipes consume
  `glacier_feather`, `thunder_feather`, `calyrex_crown`, `ancient_dna`. VERIFIED.

**What a placed altar needs from the world:** the block, the item, (possibly) an anchor, and a server that
runs `pokespawnat`. Not a structure start, an advancement, a function or a tag. INFERRED from the absence above.

## 3. Command blocks, data markers and `/place template`

- None of the four templates contains a `structure_block` (data marker) or `jigsaw`. VERIFIED (string counts 0).
  Only Mew carries command blocks.
- `/place template` writes each block's stored block-entity NBT, including a command block's `Command`.
  INFERRED from vanilla behaviour; it is consistent with STRUCTURE_INVENTORY's record that the Necrozma towers'
  command blocks run.
- **`enable-command-block=false`** in `cobblers-server/server.properties` (line 10), with
  `function-permission-level=2`, `op-permission-level=4`. VERIFIED. That file is the live server's
  (`level-name=cobblers-10240`); staging may differ, and EXP-048 already asks for `true`. With `false`, Mew's
  door never opens whatever the advancement, but that does not touch the shrine block. Some of Mew's command
  blocks store `auto` (4 occurrences); INFERRED that an `auto:1b` impulse block could fire once on placement
  when command blocks are enabled.

## 4. A fake player

**There is none.** No Carpet, no fake-player or bot mod among the 102 jars in `cobblers-server/mods/`, and none
in `disabled-mods/`. VERIFIED (mod ids and file names). Two jars contain fake-player classes — Architectury
(`dev/architectury/hooks/level/entity/fabric/FakePlayers.class`, a detection hook) and WorldEdit
(`WorldEditFakePlayer`, internal) — and neither exposes a command. No permissions provider is present either.

So an altar right-click still needs a human. The exception, INFERRED: `summon_trigger` reacts to an item
entity, and a console can make one with vanilla `summon minecraft:item`, so the Crown Cemetery's Spectrier
branch may be drivable over RCON.

## Not verified (needs the running game)

Whether the base altar requires an anchor by default; whether the activation item is consumed; the
permission default; the radii and delay; the trigger's collision behaviour; whether `pokespawnat` succeeds on
Cobblemon 1.8.0 with these property strings; any condition expressed only in obfuscated calls.
