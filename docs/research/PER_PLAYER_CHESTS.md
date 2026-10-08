# Per-player ("instanced") chests

**Question.** The owner's play-test note 15: "Add an instanced-chest mod and make every chest per-player"
(`docs/PLAYTEST_2026-10-05.md:33`), after a friend took the feathers from a shared container (note 14,
`docs/PLAYTEST_2026-10-05.md:32`). Which mod, for Minecraft 1.21.1 Fabric with Cobblemon 1.8.0, and does it
cover the three ways this project places containers?

**Answered for:** Minecraft 1.21.1, Fabric, Cobblemon 1.8.0+1.21.1 (runtime per `docs/STATE.md`). Researched
2026-10-04. Nothing here was run in a game; every behaviour below is from documentation or source, not from a test.

**Sources and how far to trust them.** Modrinth pages and API, the Lootr GitHub wiki and the Lootr source on
branch `mdg-1.21.1` (the branch the repository page shows; the released jar may lag or lead it). All web
content was read through a fetch tool that summarises pages; quoted code lines and hashes came back through that
summariser. **Hashes below are relayed, not measured**: download the jar and compute its sha512 before pinning.

---

## 1. Local evidence

- **VERIFIED: Lootr is not in the base pack or our overlay.** No match for `lootr` in `base-pack/inventory/`
  (`mod_inventory.md`, `pack_hashes.csv`, `mod_inventory.json`) or `modpack/manifest/overlay.json` (grep,
  2026-10-04). No other per-player-loot mod is in either.
- **VERIFIED: Lootr's one non-Fabric-API dependency is already shipped.** `base-pack/inventory/pack_hashes.csv:53`
  `mods/cloth-config-15.0.140-fabric.jar`; Fabric API at `:68`.
- **VERIFIED: how rewards work today (ADR-002, Proposed).** A find that matters is a per-player grant keyed to a
  vanilla advancement, with the reward function run as the earning player; the container is scenery
  (`docs/decisions/ADR-002-reward-delivery-mechanism.md:63-81`). `data/rewards.json:4` records the owner chose it
  for the Victory Road and Route 1/3 finds and that "the container is scenery: an empty barrel". ADR-002 already
  rejected "one container instanced per player" as N physical chests (`ADR-002:132-133`); it never considered an
  instancing **mod**, and it names the open question "a native ... per-player container" as a revisit trigger
  (`ADR-002:196-198`). **So rewards in `data/rewards.json` are already per-player and need no mod.**
- **VERIFIED: what our generators put in containers today** (grep of `tools/`, excluding audits):
  - Donor and town templates have their loot tables **stripped**: `tools/place_donor.py:178-181`,
    `tools/place_town.py:96, 389`, `tools/deep_city.py:2336` emit `data remove block <x y z> LootTable`.
  - **One generator places a loot-table chest:** `tools/portals.py:575-576` writes
    `minecraft:chest[facing=north]{LootTable:"cobblers:portals/<id>"}`, and `tools/portals.py:311-313` makes that
    table deterministic (one pool per item, `rolls: 1`, `set_count`). **Today that chest is shared: first opener
    takes it.**
  - **One generator places literal `Items`:** `tools/sea_town.py:851-852`, a barrel of oak boats.
- **VERIFIED, and a disagreement in our own docs: the feather containers.** `docs/research/notes/lumymon-altars.md:135-139`
  says `legendary/articuno.nbt` and `legendary/zapdos.nbt` carry the feather in a **`sophisticatedstorage` barrel's
  `Items`** (explicit items, not a loot table). `docs/STATE.md:209` says "the templates' barrels do not hold them",
  and `docs/research/notes/legendary-catalogue-reopened.md:49-51` says the Nether Moltres template's barrels hold
  blaze powder, fire gems and glass. The play test says the friend got a free Moltres from "feather chests"
  (`docs/PLAYTEST_2026-10-05.md:32`). **STATE and the altar note cannot both be right**; whichever is, the
  feather container was not a loot-table chest, which matters for section 3.
- **VERIFIED: Sophisticated Storage is in the base pack** (`base-pack/inventory/pack_hashes.csv:121`,
  `sophisticatedstorage-1.21.1-1.3.7.9.139.jar`). Cobblemon gilded chests are carried by at least one adopted
  template (`data/adopted_legendary_sites.json:126`, `cobblemon:gilded_chest` in `cobbleverse:mythical/mew`).
- **VERIFIED: per-player state carried across a re-export is a fixed list** (`tools/carry_players.py:65-87`):
  playerdata, advancements, stats, cobblemonplayerdata, pokedex, pokemon, cobbledollars, rctmod, molang,
  `data/rctmod.trainers.*`, `data/scoreboard.dat`, the recovery ledger. **No container-instancing state is in it.**

## 2. Candidates

### Lootr (recommended candidate)

VERIFIED:
- Modrinth project id **`EltpO5cN`**, slug `lootr`, licence **MIT** (https://modrinth.com/mod/lootr; repository
  footer https://github.com/LootrMinecraft/Lootr). CurseForge project **361276** is the Forge/NeoForge page
  (https://www.curseforge.com/minecraft/mc-mods/lootr); the Fabric build was taken from Modrinth.
- Newest Fabric 1.21.1 build: **`1.21.1-1.11.38.127`**, Modrinth version id `nar56EsW`, published 2026-09-25,
  release channel, file `lootr-fabric-1.21.1-1.11.38.127.jar`, 1,111,591 bytes, URL
  `https://cdn.modrinth.com/data/EltpO5cN/versions/nar56EsW/lootr-fabric-1.21.1-1.11.38.127.jar`
  (https://api.modrinth.com/v2/project/lootr/version?loaders=["fabric"]&game_versions=["1.21.1"]). Relayed hashes:
  sha1 `6671786d4c36a33dcefff85d757022c2a8ed535f`, sha512
  `6a0d50423c76740b3da18853af743d697127cd38a83b98b363305aae0cf74a18fe9b61a68ffe25498232344fe2d1b325fd960396ae49135f59458ea1ec6efab1`
  (**relayed through the summariser; re-measure**). The `1.21.1-` line has 26 Fabric builds since 2025-12-18 (24 release, 2 alpha); older `1.21-1.10.x` builds
  are also tagged for 1.21.1.
- Required dependencies: `P7dR8mSH` (Fabric API) and `9s6osm5g` (Cloth Config, slug `cloth-config`, LGPL-3.0;
  https://api.modrinth.com/v2/project/9s6osm5g). Both already in the base pack (section 1).
- **Client and server both**: "Lootr is required on both the client and the server"; no server-only build
  (https://modrinth.com/mod/lootr; https://github.com/LootrMinecraft/Lootr/wiki/FAQs). It adds blocks
  (`lootr:lootr_chest`, `lootr:lootr_inventory`, ...), so every player installs it.
- **Removing it removes containers**: "Removing Lootr will unfortunately also remove all containers from your
  world" (FAQs). It is world-critical once used.

### SlashLoot (server-only alternative)

VERIFIED (https://modrinth.com/mod/slashloot; https://api.modrinth.com/v2/project/slashloot;
https://github.com/mindfulent/SlashLootr README):
- Modrinth id `mRZVkEL7`, licence **CC-BY-4.0**, `client_side: unsupported`, `server_side: required`.
- Newest Fabric 1.21.1: `0.5.2+mc1.21.1-fabric`, version id `zj3pQgmH`, published 2026-10-03, file
  `slashloot-0.5.2+mc1.21.1-fabric.jar`, 63,722 bytes; requires Fabric API only. Relayed sha512
  `ba649deaa24d6452485a3a777daf08766e33cc13c592b3075a5cbd5cef2431e1618abc1d1f92709f4f7f76f01264c3cc969af1004da97fc76bfe7ad869b0d86f`
  (**re-measure**).
- **Young**: first published 2026-05-24, six Fabric 1.21.1 versions since 2026-05-31, 898 downloads at fetch time.
- Mechanism: "when a player right-clicks a container that still has a `LootTable` tag, look up (or roll fresh) a
  per-player `SimpleContainer`"; "Containers you place yourself are never touched". Covers chests, trapped chests,
  barrels, shulker boxes, chest/hopper minecarts, chest boats, double chests, and **Cobblemon gilded chests**;
  excludes Gimmighoul chests, decorated pots, suspicious sand/gravel. Hoppers do not pull from instanced
  containers; comparators read 0.
- Commands (permission 2+): `/slashloot forget here | at <x y z> | player <p> | all`, `prune`, `stats`, `reload`.
  Config `config/slashloot.json`: `enabled`, `dimensionBlocklist`, `lootTableBlocklist`,
  `handleUnknownContainers` (off by default), `delegateContainerAnimation`, `playOpenCloseSounds`,
  `cleanupOnBreak`, `pruneIntervalTicks`, `debugLogging`.
- State: `world/<dimension>/data/slashloot.dat`.

### Others looked at

- **Instanced Containers** (Modrinth `PNxd8alC`, https://modrinth.com/mod/instanced-containers): Fabric 1.21.1,
  server-side, **All Rights Reserved**, and "when 1 player is interacting with a chest, no other player can open
  that chest". VERIFIED from its page; not recommended on licence and on that limit.
- **Lootrmon** (https://www.curseforge.com/minecraft/mc-mods/lootrmon): MIT, Fabric and NeoForge 1.21.1, a Lootr
  add-on that turns Cobblemon gilded chests into instanced ones; client and server. Supported Cobblemon version
  not stated on the page; last file 2026-02-20, which predates Cobblemon 1.8. ASSUMED unverified for 1.8.
- "Prosperity" and "LootIn" (named by search results and the Lootr FAQ) were not found as Fabric 1.21.1
  per-player-loot mods on Modrinth; not pursued.

## 3. The crux: which containers become per-player

### Lootr

VERIFIED:
- **Automatic conversion needs a loot table.** The conversion check reads
  `ResourceKey<LootTable> lootTable = adapter.getLootTable(entity); if (lootTable == null)` and rejects the
  container; it also rejects blacklisted tables, blocked dimensions, and requires the 5x5 chunks around it to be
  loaded (`common/.../block/entity/BlockEntityTicker.java`, `isValidEntityFull`, branch `mdg-1.21.1`). It does
  **not** look at `Items` or at whether the chest was opened (same method). A chest that has already been opened
  has, in vanilla, already lost its `LootTable`, which is why Modrinth says "loot containers which were already
  opened will not be converted" (https://modrinth.com/mod/lootr).
- **What the auto path covers:** blocks tagged as barrels, chests, trapped chests and shulker boxes whose block
  entity descends from `RandomizableContainerBlockEntity` (wiki "How Lootr Works"); the barrel tag includes
  `#c:barrels` (`common/src/generated/resources/data/lootr/tags/block/convert/barrels.json`).
- **When it runs:** a mixin on `LevelChunk.updateBlockEntityTicker` (HEAD) calls `BlockEntityTicker.addEntity`
  for every block entity (`common/.../mixin/ticker/MixinLevelChunk.java`). The wiki's "only during world
  generation" description carries the note "As of 1.21.1 `100` and later, this is no longer accurate"
  (https://github.com/LootrMinecraft/Lootr/wiki/How-Lootr-Works). `checkStructureValidity` does **not** require
  the container to be inside a structure; it only applies structure black/whitelists when they are set.
- **Explicit `Items` (no loot table) are left alone unless an operator converts them.** `/lootr custom-chest
  <target>` (permission 2) accepts only blocks in `lootr:convert/custom_eligible` = `minecraft:barrel`,
  `minecraft:chest` (`.../tags/block/convert/custom_eligible.json`), requires a non-empty inventory and **no** loot
  table, and replaces it with a `lootr:lootr_inventory` in which "each player receives a personalized copy of the
  items originally placed inside" (`CommandLootr.java`; wiki "Custom Containers and Maps"). `/lootr custom-map
  <level>` converts every non-empty, no-loot-table eligible container in a dimension, force-loading all generated
  chunks (wiki; `CommandLootr.java` registers it and starts `CustomConvertJob`).
- **Placing one by command:** `/lootr <block-type> [<loot table>]` spawns a Lootr container with an optional
  loot table (wiki "Lootr Command"; `CommandLootr.java` registers per-block subcommands with a
  `ResourceKeyArgument` of `Registries.LOOT_TABLE`).
- **Other commands** (wiki "Lootr Command", 1.21.1 build 100+): `clear <player>`, `cclear <entities>`,
  `open_as`, `open_as_uuid`, `id`, `openers`, `force_chunk`, `force_radius <r>`, `force_all`; `refresh` and
  `decay` deprecated.
- **Config (Fabric, source HEAD, names as read by the summariser from
  `fabric/.../fabric/config/ConfigManager.java`; confirm against the generated config file):**
  `dimension_whitelist`, `dimension_blacklist`, `loot_table_blacklist`, `loot_modid_blacklist`,
  `loot_table_forced_whitelist`, `disable_break` / `enable_break` (default false/false), `blast_resistant`,
  `blast_immune`, `should_drop_player_loot`, `break_to_drop_loot`, `world_border` (false),
  `bypass_spawn_protection` (true), refresh (`refresh_value` 24000, `refresh_all`, `refresh_loot_tables`,
  `refresh_dimensions`, ...), decay (`decay_value` 6000, `decay_all`, ...), `team_loot` (false),
  `vanilla_textures` (false). Refresh and decay are "optional features that are not enabled by default"; refresh
  clears every player's inventory so loot generates again; decay destroys the container
  (wiki "What are Refresh and Decay"). There is **no block-id blacklist in config**; a block-entity tag
  `CONVERT_BLACKLIST` exists (`BlockEntityTicker.isValidEntity`).
- **On break:** "By default, Lootr prevents players from breaking containers unless they are sneaking", with a
  warning (FAQs; Modrinth).
- **Structure saving:** saving a structure with a structure block makes Lootr containers drop their id and opener
  data so they save as vanilla containers with their loot table (`common/.../mixin/structure_saving/MixinStructureTemplate.java`).
- **State lives in the overworld's data storage under `data/lootr/<c>/<cc>/...`**, keyed per container
  (`common/.../data/DataStorage.java`).

ASSUMED (inferred, not run):
- That `setblock ... minecraft:chest{LootTable:"..."}` and a `/place template` whose chest still carries a
  `LootTable` both get converted. Reason: vanilla calls `updateBlockEntityTicker` whenever a block entity is set
  in a loaded chunk and when a chunk's block entities are registered on load; the NBT is merged after the block
  entity is created, and Lootr validates later (tick delay 20), by which time the table is set. Vanilla call sites
  were not read for 1.21.1.
- That a barrel converted by `custom-chest` becomes chest-shaped (`lootr_inventory`) rather than staying a barrel.
- That breaking with the defaults drops nothing (`should_drop_player_loot`, `break_to_drop_loot` default false).
- That a re-placed container (our re-apply or re-export runs `setblock` again) gets a new container id, so every
  player can loot it again; and that `data/lootr/` is lost in a re-export because `carry_players.py` does not
  carry it.

### SlashLoot

VERIFIED: **only containers that still carry a `LootTable` at the moment a player opens them**; explicit `Items`
are vanilla and shared (README, quoted above). It has no "convert filled chest" command. Because the check is lazy
(on open), placement method does not matter.

### Answer for our three placement paths

| Path | Today | Lootr | SlashLoot |
|---|---|---|---|
| (a) `/place template` with a **`LootTable`** chest | stripped by `clear_loot` in donor/town/deep-city tools | per-player (auto), if the table is left in | per-player, if the table is left in |
| (a) template with **explicit `Items`** (the feather barrels) | shared | **not automatic**; `custom-chest` only for vanilla `chest`/`barrel`, so a `sophisticatedstorage` barrel cannot be converted (VERIFIED tag contents; ASSUMED that the SS barrel is not otherwise eligible) | **never** |
| (b) generator `setblock` with `LootTable` (`portals.py`) | shared | per-player (ASSUMED auto; or place with `/lootr chest <table>`) | per-player |
| (b) generator `setblock` with `Items` (`sea_town.py` boats) | shared | per-player only after `/lootr custom-chest <pos>` | never |
| (b) ADR-002 reward caches | empty scenery; reward per player by advancement | not needed | not needed |
| (c) players' own chests | shared | untouched (no loot table) | untouched |

**So "every chest per-player" is not literally what either mod does, and should not be**: both leave
players' own chests shared, as the owner needs. What becomes per-player is every container that still holds a
loot table; for Lootr, also any vanilla chest/barrel an operator converts.

## 4. WorldPainter world, container types

- VERIFIED: Lootr's conversion is no longer worldgen-only on 1.21.1 build 100+ (wiki note; `MixinLevelChunk`), and
  Modrinth says containers convert "when added to pre-existing worlds". Our containers are all placed by commands
  after export, not by worldgen, so worldgen is irrelevant to us either way.
- VERIFIED: Lootr covers chests, trapped chests, barrels, shulker boxes, minecarts; SlashLoot covers those plus
  chest boats, double chests and gilded chests (sources above). Lootr needs Lootrmon for gilded chests.
- ASSUMED: A Lootr `custom-map` run on our 8192-block world would force-load every generated chunk of the
  dimension; that is a long, heavy job and would also convert any non-empty vanilla chest/barrel, including
  players' own. Not to be used on the live world.

## 5. Conflicts

- **Cobblemon:** no reported Lootr-Cobblemon conflict found; the known gap is gilded chests, which Lootrmon exists
  to fill (CurseForge Lootrmon page). SlashLoot handles gilded chests itself. ASSUMED no conflict with Cobblemon 1.8.
- **Distant Horizons (server-side, `modpack/manifest/overlay.json:548-561`):** no report found either way
  (web search 2026-10-04). Unknown.
- **Base-pack storage mods:** Tom's Simple Storage (`pack_hashes.csv:128`), Iron Chests (`:19`), Sophisticated
  Storage (`:121`). No report found. Unknown whether a storage network can read a Lootr container.
- Lootr on NeoForge 1.21.1 had a mixin clash with "Unsuspicious Block" (CurseForge file page, search result);
  not in our pack.

## 6. Recommendation

1. **The incident does not need a mod.** The feather container was explicit items in a template barrel, which no
   candidate instances automatically; the owner's note 14 already removes it. Do that through the existing
   template path (`data remove block ... Items` or replace the block), and resolve the STATE vs altar-note
   disagreement first.
2. **Rewards that matter already have a per-player answer**: ADR-002 advancements. Keep them; no mod improves them.
3. **If the owner still wants per-player chests as a texture** (lootable rooms, portal chests, flavour stashes),
   **Lootr 1.21.1-1.11.38.127** is the candidate: MIT, actively maintained on 1.21.1 Fabric, its only extra
   dependency already installed, and the only one that can also instance a chest of explicit items
   (`custom-chest`). Cost: a client install for every player, and it becomes world-critical. **SlashLoot** is the
   server-only fallback (no client change, handles gilded chests) but is five months old with under a thousand
   downloads, and does nothing for explicit items.
4. **The authoring rule that makes either work:** every container whose contents should be per-player carries a
   loot table (deterministic, like `portals.py:311-313`, so each player gets the same items). That moves
   `sea_town.py`-style literal `Items` to tables, and makes `clear_loot` a per-site choice rather than the default.

**What an ADR must decide:**
- Mod or no mod; Lootr vs SlashLoot (client install and world-critical status vs maturity and coverage).
- Which containers are per-player by design: portal chests, flavour stashes, donor-template loot (re-enabling
  Cobbleverse loot tables per player changes the economy), gilded chests.
- **Re-apply and re-export behaviour**: re-placing an instanced container likely resets it for everyone, and its
  opener state is not in `carry_players.py`. Either re-apply must skip existing instanced containers, or the state
  file (`data/lootr/` or `<dim>/data/slashloot.dat`) must become a carried category, or resets are accepted.
- Break protection (`disable_break`), refresh/decay (both off by default; leave off), the `world_border` check.
- How audits prove a container is instanced (Lootr changes the block id; SlashLoot does not).

## 7. Unknown: experiment candidates

Not added to `docs/research/EXPERIMENT_BACKLOG.md` (this brief allowed only this file); listed here for the ADR.

1. On staging with Lootr: `setblock` a vanilla chest with a `LootTable`, wait 2 s; does it become
   `lootr:lootr_chest`? Two players open it: same deterministic contents, independent inventories?
2. `/place template` of a template with a `LootTable` chest: converted? With explicit `Items`: left alone?
3. `/lootr custom-chest` on a filled barrel: does it stay a barrel? Can a function run it (permission level 2)?
4. Re-run the same `setblock` over a looted Lootr chest: does every player get it again?
5. Break with defaults: sneaking required? Items dropped?
6. SlashLoot same tests 1, 2, 4 (no client mod), plus a gilded chest.
7. Server-side Distant Horizons generating LODs over chunks with Lootr chests: errors or premature conversion?
8. Which mod actually placed the friend's feathers (template barrel `Items` vs something else), so note 14's fix
   targets the right block.
