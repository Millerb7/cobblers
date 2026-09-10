# Cobbleverse → Cobblemon 1.8 compatibility

## Decision snapshot

**EXP-000 is not complete, and the repository is not ready for EXP-001.** The isolated dedicated server reached Minecraft's `Done` state on 2026-09-09 after two runtime-caused exclusions. Client connection and all gameplay smoke tests remain unverified.

The current target is Minecraft 1.21.1, Fabric Loader 0.19.5, Java 21, and Cobblemon 1.8.0. The effective dedicated-server set has 101 jars: 89 unchanged base jars and 12 replacements. Better Pokédex Scanner and Raid Dens are removed, PlayerXP is excluded from the server only, and the disabled legacy Particular jar is omitted; Particular Reforged remains.

## Evidence standard

- **Verified fact:** read from local `fabric.mod.json`, a recorded cryptographic hash, the Modrinth version API, Fabric Meta, or an executed command captured in EXP-000.
- **Supported upstream:** a 1.8-targeted release exists. This proves metadata intent, not successful behavior in this pack.
- **Needs boot test:** metadata permits the target, but the loader has not resolved the assembled set.
- **Needs functional test:** loading would still not prove that the addon behaves correctly.
- **Unknown:** no 1.8 release statement or runtime result was found. Unknown components are preserved for testing unless they are proven blockers.

## Verified baseline and assembled target

| Item | Reference | Target | Evidence |
| --- | --- | --- | --- |
| Cobbleverse | 1.7.42 | upstream reference remains unchanged | local manifest and hash inventory |
| Minecraft | 1.21.1 | 1.21.1 | Cobblemon metadata and Fabric installer |
| Fabric Loader | ≥0.18.4 required | 0.19.5 stable | Fabric Meta queried 2026-09-08 |
| Fabric installer | — | 1.1.2 stable | Fabric Meta queried 2026-09-08 |
| Java | 21 | Temurin 21.0.9 | executed `java -version` |
| Cobblemon | 1.7.3+1.21.1 | 1.8.0+1.21.1 | local metadata and Modrinth version `YgmyyFcs` |
| Server jars | 104 baseline jars | 101 effective jars | `pack_manifest.py verify` and boot capture `20260909-001735` |
| Client jars | base client set | 135 effective jars | `pack_manifest.py plan`; full post-removal client assembly still pending |
| Config files | 223 base files | 224 assembled files | isolated runtime inventory |
| Datapacks | 10 zip files | 10 assembled zip files | isolated runtime inventory |

The immutable base verification found 104 matching server-side jars, zero missing, and zero hash mismatches. The 34 extras were exactly the 33 enabled client-only jars plus the disabled legacy Particular jar. The final target verification found all 101 planned server jars with zero missing, mismatched, extra, or unverified files. That exact set reached `Done (6.377s)` with mod-set hash `D1483348BC2D`.

## Required compatibility overlay

| Component | Base | Target | Action | Why |
| --- | --- | --- | --- | --- |
| cobblemon | 1.7.3+1.21.1 | 1.8.0 | UPDATE | Target Cobblemon version for the campaign (1.8.0 Fabric, published 2026-09-06). Requires Fabric API (P7dR8mSH). |
| tmcraft | 1.4.18+1.7.3 | 1.4.19+1.8.0 | UPDATE | fabric.mod.json hard-pins cobblemon 1.7.3+1.21.1; 1.4.19+1.8.0 build exists (2026-09-06). |
| capture_xp | 1.7.3-fabric-1.3.0 | 1.8.0-fabric-1.3.0 | UPDATE | fabric.mod.json hard-pins cobblemon 1.7.3+1.21.1; 1.8.0 build exists (2026-09-08). Also requires Tim Core (lVP9aUaY). |
| tim_core | 1.7.3-fabric-1.32.0 | 1.8.0-fabric-1.32.0 | UPDATE | fabric.mod.json hard-pins cobblemon 1.7.3+1.21.1; 1.8.0 build exists (2026-09-08). Library for Capture XP. |
| rctmod | 0.18.1-beta | 0.19.0-beta | UPDATE | Radical Cobblemon Trainers 0.19.0-beta (2026-09-07) raises the minimum Cobblemon to 1.8. Loads on 1.8 only with this update. |
| rctapi | 0.15.2-beta | 0.16.0-beta | UPDATE | Paired RCT API release published 2026-09-06 alongside rctmod 0.19.0-beta; assumed required by rctmod 0.19.0 (verify at boot: rctmod's fabric.mod.json rctapi constraint). |
| mega_showdown | 1.8.4+1.7.3+1.21.1 | 1.0.2+1.8+1.21.1-release | UPDATE | Mega Showdown 1.0.2 for Cobblemon 1.8 (2026-09-08). Note the version scheme reset (1.8.4 -> 1.0.2); its required dependencies are present in the base pack. |
| cobbreeding | 2.2.2 | 2.3.0 | UPDATE | Release 2.3.0 explicitly updates Cobbreeding for Cobblemon 1.8. |
| obc | 1.3.0 | 1.5.0-fabric | UPDATE | Release 1.5.0-fabric explicitly targets Cobblemon 1.8 and is not backward-compatible. |
| playerxp | 1.0.9+1.21.1 | 1.1.1+1.21.1 | CLIENT OPTIONAL; SERVER EXCLUDE | No newer 1.21.1 release exists. Version 1.1.1 and current upstream source register client-only `ItemTooltipCallback` from the common `ModInitializer`, crashing a dedicated server during entrypoint initialization. Preserve in the client provisionally; connection safety and usefulness remain unverified. |
| cobblenav | 2.3.3 | 2.4.1 | UPDATE | CobbleNav 2.4.x explicitly updates for Cobblemon 1.8. |
| zamega | 1.7.3 | 1.7.7+1.8 | UPDATE | The base jar requires Mega Showdown's 1.7-era version range; release 1.7.7+1.8 targets the reset Mega Showdown 1.0.x line. |
| fightorflight | 0.10.9 | 0.11.0 | UPDATE | Maintained Reborn release reports normal operation on Cobblemon 1.8; preserve provisionally and verify aggression, fleeing, battle start, and XP behavior. |
| better_pokedex_scanner | better-pokedex-scanner-1.0.0.jar | — | REMOVE | Depends on cobblemon >=1.7.3 <1.8.0 and has no 1.8 build (single release 1.0.0, 2026-04-15). Client-side QoL; safe to drop. |
| particular | particular-1.1.2+1.21.jar.disabled | — | REMOVE | Already .disabled in the base pack; duplicate mod id with Particular Reforged 1.5.5 (particular-1.21.1-Fabric-1.5.5.jar). Drop the file entirely. |
| cobblemonraiddens | 0.11.3+1.21.1 | — | REMOVE | Runtime datapack reload fails with `NoSuchMethodError: GraalShowdownService.getContext()`. Published 0.11.7 and current upstream source retain the same removed API call. This also removes den blocks and structures before campaign world construction. |

All replacement downloads are pinned by URL, Modrinth version ID, SHA-1, and SHA-512 in `modpack/manifest/overlay.json`. The six replacements added by current research are Cobbreeding, Only Bottle Caps, PlayerXP, CobbleNav, ZAMegas, and Fight or Flight Reborn. ZAMegas is mandatory: the base jar requires the old Mega Showdown version line, while Mega Showdown resets to 1.0.x for Cobblemon 1.8.

## Preserved systems requiring functional tests

The retained functional scope contains 26 Cobblemon-integrating addons and libraries after removing Raid Dens. PlayerXP is client-optional and needs a client connection test before it can be kept safely. Server boot cannot validate PlayerXP, Catch Indicator, Catch Rate Display, or LumyREI. High-risk server checks include RCT trainer lifecycle and multiplayer behavior, Mega Showdown plus ZAMegas, CobbleNav, Cobbreeding, CobbleDollars, Capture XP, TMCraft, and world-critical CobbleFurnies/LumyMon/Legendary Monuments/Cobblemon Additions.

No standalone quest system was found. Cobbleverse progression behavior comes from RCT series and level-cap configuration, datapack advancements/functions, and badge items. Global Packs force-loads `config/cobbleverse`, `datapacks/`, and optional `datapacks/extra/`; these are part of the compatibility surface.

## Complete mod matrix

This matrix covers all 138 jar records, including the disabled legacy Particular jar. `GAMEPLAY-CRITICAL / LIBRARY` means the jar is infrastructure required by another gameplay or world component.

| Component | Type | Current Version | Minecraft Version | Loader | Cobblemon Dependency | 1.8 Status | Action | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Advancement Plaques | OPTIONAL/CLIENT-QOL | 1.6.8 | 1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only advancement toast visuals. Needs Iceberg. CC BY-NC-ND. |
| BadOptimizations | OPTIONAL/CLIENT-QOL | 2.4.1 | >=1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only perf. |
| BetterF1 | OPTIONAL/CLIENT-QOL | 1.1 | ~1.21 | Fabric | — | NEEDS BOOT TEST | CLIENT ONLY | ODD: jar named +1.21.7 but depends minecraft ~1.21 (any 1.21.x). Built against a newer MC; client mixin may not apply cleanly on 1.21.1. No source/contact in metadata. |
| BetterF3 | OPTIONAL/CLIENT-QOL | 11.0.3 | >=1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only debug HUD. |
| Better Third Person | OPTIONAL/CLIENT-QOL | 1.9.0 | ~1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only camera. ARR. |
| Carved Wood | WORLD-CRITICAL | 1.9.7-B | >=1.21 <1.22 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | 325 blockstates of decorative wood blocks; if used in the handcrafted map it must stay. Bundles cardinal-components. Contact points at fabric-example-mod template (no real source URL). |
| CobbleDollars | GAMEPLAY-CRITICAL | 2.0.0+Beta-5.1+1.21.1 | >=1.21.1 | Fabric | >=1.6.0+1.21.1 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Currency + merchant NPCs (villager template pools). cobblemon >=1.6.0+1.21.1 (no upper bound). 55 classes reference Cobblemon API. ARR. |
| CobbleFurnies | WORLD-CRITICAL | 1.2 | ~1.21.1 | Fabric | >=1.7.1 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | 372 blockstates of Pokemon-themed furniture (labs, Pokecenters). Hard-required by LegendaryMonuments. cobblemon >=1.7.1, athena >=4.0.2, architectury >=13.0.8. 8 classes touch Cobblemon API. |
| Cobblemon | GAMEPLAY-CRITICAL | 1.7.3+1.21.1 | 1.21.1 | Fabric | — | NEEDS BOOT TEST | UPDATE → 1.8.0 | Core mod 1.7.3+1.21.1. Target per task premise is 1.8.x. Bundles fabric-language-kotlin nested. Requires fabricloader >=0.17.2, fabric-api >=0.116.6+1.21.1, Java 21. |
| COBBLEVERSE Badges | GAMEPLAY-CRITICAL | 1.3 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Gym badges/trophies items (Kanto-Sinnoh) - progression items. No cobblemon dependency declared, 0 API refs (pure items). Pack-specific Lumyverse mod, CC BY-NC-ND 4.0 (no-derivatives; distribution outside the pack is license-sensitive). Once given to players they persist in inventories. |
| Cobbreeding | GAMEPLAY-CRITICAL | 2.2.2 | 1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | UPDATE → 2.3.0 | Breeding via pasture. cobblemon >=1.7.0 (no upper bound). Overrides cobblemon pasture blockstate. architectury 13.x, cloth-config >=15. 40 API refs - high coupling. |
| Controlling | OPTIONAL/CLIENT-QOL | 19.0.5 | 1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only keybind search. Needs Searchables. |
| Debugify | OPTIONAL/CLIENT-QOL | 1.21.1+1.0 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Vanilla bug fixes; env=* (has server-side fixes). |
| Euphoria Patcher | OPTIONAL/CLIENT-QOL | 1.9.3-r5.8.1-fabric | >=1.14.0 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; patches Complementary shaders (shaderpacks/ComplementaryUnbound_r5.8.1). |
| Forge Config API Port | GAMEPLAY-CRITICAL / LIBRARY | 21.1.6 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: sophisticatedcore (>=21.1.3), rctmod (>=21.1.1), particular (Reforged). |
| Iceberg | GAMEPLAY-CRITICAL / LIBRARY | 1.3.2 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: advancementplaques. CC BY-NC-ND. |
| ImmediatelyFast | OPTIONAL/CLIENT-QOL | 1.6.11+1.21.1 | >=1.21 <=1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only render perf. minecraft >=1.21 <=1.21.1. |
| Iron Chests | GAMEPLAY-CRITICAL | 2.0.4 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Storage blocks players keep items in (10 blockstates). Bundles libgui. |
| Legendary Monuments | WORLD-CRITICAL | Cobbleverse | ~1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Worldgen structures + 48 blockstates (shrines, Giratina island, etc.) for legendary encounters. version='Cobbleverse' = pack-custom build; no public source (template contact). Hard-depends cobblefurnies * and cobblemon >=1.7.0. 6 API refs. |
| Cozy Home | WORLD-CRITICAL | 1.1.20 | ~1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | 278 blockstates furniture. Template contact (no real source). |
| LumyMon | WORLD-CRITICAL | 0.6.6 | ~1.21.1 | Fabric | >=1.7.1 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Pack-specific Lumyverse mod: worldgen + structures + 64 blockstates + custom mechanics (17 API refs). cobblemon >=1.7.1 (no upper). Bundles fabric-permissions-api. CC BY-NC-ND 4.0 - license-sensitive to carry forward. Also GAMEPLAY-relevant. |
| LumyREI | OPTIONAL/CLIENT-QOL | 1.1.3 | ~1.21.1 | Fabric | >=1.7.1 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Client-only REI recipe integration (cooking pot/brewing/stark forge). cobblemon >=1.7.1. GPL-3.0. |
| MobsBeGone | GAMEPLAY-CRITICAL | 0.0.7 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Server-side entity spawn blacklist; config/mobsbegone-blacklist.json lists most vanilla mobs (allay..giant..) - defines the campaign's mob roster. Keep mod + config together. ARR/Custom, modpack permission on file. |
| MoreCobblemonTweaks | OPTIONAL/CLIENT-QOL | 1.3.3 | ~1.21 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Cobblemon client QoL (PC multiselect, egg lore). cobblemon >=1.7.0, architectury >=13.0.8. 30 API refs (UI-level coupling - likely to break on UI changes). GPL-3.0. |
| Mouse Tweaks | OPTIONAL/CLIENT-QOL | 2.26 | ~1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only. |
| No Chat Restrictions | OPTIONAL/CLIENT-QOL | Fabric-MC1.21.11-v1.0.0 | >=1.21 <=1.21.11 | Fabric | — | NEEDS BOOT TEST | PRESERVE FOR BOOT | ODD: built for MC 1.21.11 (depends >=1.21 <=1.21.11 so it will load on 1.21.1). Mixins were compiled against 1.21.11 - verify they apply. Purpose: removes chat signing restrictions. |
| Only Bottle Caps | GAMEPLAY-CRITICAL | 1.3.0 | 1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | UPDATE → 1.5.0-fabric | Bottle cap items (IV training). cobblemon >=1.7.0. No fabricloader dep declared. Bundles supermartijn642configlib. |
| Ping Wheel | OPTIONAL/CLIENT-QOL | 1.12.2 | >=1.21 <=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Location pings; needs server side too (env=*). |
| Platform | GAMEPLAY-CRITICAL / LIBRARY | 1.3.3 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: vanillabackport (>=1.3.3). Contains worldgen helper classes. |
| Resource Pack Overrides | OPTIONAL/CLIENT-QOL | 21.1.0 | 1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; forces pack resource packs active (config/resourcepackoverrides.json). |
| Roughly Enough Items | OPTIONAL/CLIENT-QOL | 16.0.799 | ~1.21- | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Recipe viewer. env=* (server side for recipe sync). Bundles error_notifier. |
| Safe Pastures | GAMEPLAY-CRITICAL | 1.1.1+1.21.1 | 1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Pasture protection. cobblemon >=1.7.0. 1 API ref (low coupling). |
| ScalableLux | OPTIONAL/CLIENT-QOL | 0.1.0.1+fabric.d0d58ab | >=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Light engine rewrite (provides starlight). Server+client perf. |
| Searchables | GAMEPLAY-CRITICAL / LIBRARY | 1.0.2 | 1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Needed by: controlling. Client-only. |
| StackDeobfuscator | DEVELOPMENT-ONLY | 1.4.3+08e71cc | >=1.14-alpha.18.49.a | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Deobfuscates stack traces in logs; useful while debugging the 1.8 migration, not needed by players. |
| VanillaBackport | WORLD-CRITICAL | 1.1.7.10 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Backports newer vanilla content: 72 blockstates + worldgen/biomes/structures (terrablender entrypoint). Anything built with these blocks persists. Needs Platform. ARR. Bundles mixinsquared. |
| Accessories | GAMEPLAY-CRITICAL / LIBRARY | 1.1.0-beta.53+1.21.1 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: mega_showdown (>=beta.52), zamega, accessories_compat_layer. Needs owo. Beta build. |
| Accessories Compatibility Layer | GAMEPLAY-CRITICAL / LIBRARY | 0.1.12 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Bridges Trinkets/Curios APIs onto Accessories (provides tclayer/cclayer). Needed only if any mod uses Trinkets API; nothing in this pack hard-depends on trinkets. |
| AdvancementDisable | OPTIONAL/CLIENT-QOL | 1.0.0 | 1.21.x | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Disables mod advancements. Check config/advancementdisable.toml. |
| Architectury | GAMEPLAY-CRITICAL / LIBRARY | 13.0.8 | ~1.21- | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: cobblefurnies, cobbreeding, more_cobblemon_tweaks, fightorflight, mega_showdown, rctapi, zamega, brb. Version 13.0.8 is exactly the minimum several mods require. |
| Athena | GAMEPLAY-CRITICAL / LIBRARY | 4.0.6 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: cobblefurnies (>=4.0.2). Client entrypoint only. |
| Balm | GAMEPLAY-CRITICAL / LIBRARY | 21.0.63 | >=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: waystones, defaultoptions, forgivingvoid, netherportalfix. Bundles kuma_api. |
| Beautify | WORLD-CRITICAL | 2.0.0+1.21.1 | ~1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | 57 decorative blockstates (blinds, trellis, frames). Needs cloth-config. |
| Better Pokédex Scanner | OPTIONAL/CLIENT-QOL | 1.0.0 | 1.21.1 | Fabric | >=1.7.3 <1.8.0 | INCOMPATIBLE | REMOVE | HARD BLOCKER: depends cobblemon ">=1.7.3 <1.8.0" - loader will refuse to start with Cobblemon 1.8.x until a new build exists. Also needs fabric-language-kotlin >=1.13.6. Small QoL (aspect detection in scanner) - candidate for REMOVE if no 1.8 build. |
| Better Beds | OPTIONAL/CLIENT-QOL | 1.4.0 | >=1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only bed renderer. |
| Biome Replacer | WORLD-CRITICAL | 2.1-hippo | >=1.19.4 <1.21.2 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Replaces biomes at generation (config/biome_replacer.properties). Changing/removing it changes terrain of newly generated chunks - must be frozen for the map. minecraft >=1.19.4 <1.21.2. |
| Better Recipe Book | OPTIONAL/CLIENT-QOL | 1.10.0-rc5+1.21 | >=1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only recipe book tweaks. Needs architectury >=11. |
| Concurrent Chunk Management Engine | OPTIONAL/CLIENT-QOL | 0.4.0-alpha.0.23+1.21.1 | ["=1.21.1", "=1.21"] | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Chunk perf (alpha). 28 nested jars. Requires fabricloader >=0.18.3. Touches worldgen threading - verify chunk output identical before generating the map. |
| Cobblemon Capture XP | GAMEPLAY-CRITICAL | 1.7.3-fabric-1.3.0 | 1.21.1 | Fabric | 1.7.3+1.21.1 | NEEDS FUNCTIONAL TEST | UPDATE → 1.8.0-fabric-1.3.0 | HARD BLOCKER: depends cobblemon "1.7.3+1.21.1" (exact pin; Fabric treats a bare version as equality) and tim_core >=1.7.3-fabric-1.31.0. Will not load with 1.8.x without a new build. |
| Catch Indicator | OPTIONAL/CLIENT-QOL | 1.7.0 | 1.21.1 | Fabric | — | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Client-only Pokedex status indicator. Does NOT declare a cobblemon dependency but 13 classes reference com.cobblemon API (incl. Alphas/SizeVariation compat) - silent runtime breakage risk. ARR + permission. |
| Cobblemon Catch Rate Display | OPTIONAL/CLIENT-QOL | 2.8.22 | >=1.21 <1.22 | Fabric | >=1.6.0 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Client-only catch-rate HUD. cobblemon >=1.6.0, breaks <1.6.0. 19 API refs. |
| Cloth Config v15 | GAMEPLAY-CRITICAL / LIBRARY | 15.0.140 | >=1.21- | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: cobbreeding, fightorflight, beautify, moreculling, musicnotification, nethermap, paginatedadvancements, soundsbegone, toms_storage, brb, betterf3 (several also bundle it nested). |
| CobbleCuisine | GAMEPLAY-CRITICAL | 2.0.1 | 1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Food/snack items + bean crop block. cobblemon >=1.7.0. 22 API refs. Jar name says '1.7.rc1' (built for Cobblemon 1.7). |
| Cobblemon Additions | WORLD-CRITICAL | 4.1.6 | ~1.21.1 | Fabric | — | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Pokemon-themed villages/structures (datapack-turned-mod), spawn pools. No cobblemon dependency declared but ships assets/cobblemon + spawn_pool data and 2 API refs. Worldgen: villages will be in the map. CC0. |
| Cobblemon Battle Extras | OPTIONAL/CLIENT-QOL | 1.13.45 | ~1.21.1 | Fabric | >=1.6 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Battle UI/QoL + controller support. cobblemon >=1.6. 74 API refs (battle UI coupling - high break risk). Breaks cobblemon-ui-tweaks/cobblestats/move_inspector. ARR, permission on file. |
| Cobblemon Battle Positions | GAMEPLAY-CRITICAL | 1.1.2 | ~1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Arena marker blocks (5 blockstates) placed in world for NPC/PVP battle positions - blocks persist in map. cobblemon >=1.7.0, rctapi >=0.14.0. Jar says 1.1.3, metadata version 1.1.2. |
| Cobblemon Raid Dens | WORLD-CRITICAL / GAMEPLAY-CRITICAL | 0.11.3+1.21.1 | 1.21.1 | Fabric | >=1.7.0 | INCOMPATIBLE | REMOVE | Fatal on Cobblemon 1.8 during datapack reload: `NoSuchMethodError` for removed `GraalShowdownService.getContext()`. Latest published 0.11.7 and current source retain the call. Removing before map construction avoids orphaned den blocks and structures. |
| Cobblenav | GAMEPLAY-CRITICAL | 2.3.3 | 1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | UPDATE → 2.4.1 | PokeNav item (spawn info/trainer contacts). cobblemon >=1.7.0. 191 API refs (very high coupling). MPL-2.0. |
| Comforts | WORLD-CRITICAL | 9.0.5+1.21.1 | ~1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Sleeping bags/hammocks - placeable blocks (34 blockstates). Bundles spectrelib + cardinal-components. |
| Configurable | GAMEPLAY-CRITICAL / LIBRARY | 3.5.2 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: neruina (~3.5.2). |
| Continuity | OPTIONAL/CLIENT-QOL | 3.0.0+1.21 | >=1.21 <=1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only connected textures. |
| Custom Splash Screen | OPTIONAL/CLIENT-QOL | 2.2.0 | — | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; no minecraft dep declared. Needs midnightlib. |
| Default Options | OPTIONAL/CLIENT-QOL | 21.1.7 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Ships default keybinds/options (config/defaultoptions). Needs balm. ARR. |
| Entity Model Features | OPTIONAL/CLIENT-QOL | 3.2.4 | * | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only CEM support; minecraft '*'. Needs ETF >=7.1. Used by Fresh Animations resource pack. |
| Entity Texture Features | OPTIONAL/CLIENT-QOL | 7.1 | * | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; minecraft '*'. |
| EntityCulling | OPTIONAL/CLIENT-QOL | 1.10.5 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Client perf (env=* but client entrypoint only). tr7zw protective license. |
| Fabric API | GAMEPLAY-CRITICAL / LIBRARY | 0.116.14+1.21.1 | >=1.21- <1.21.2- | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Fabric API 0.116.14+1.21.1 (49 modules). Cobblemon 1.7.3 requires >=0.116.6. |
| Fabric Language Kotlin | GAMEPLAY-CRITICAL / LIBRARY | 1.13.13+kotlin.2.4.10 | — | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Kotlin 2.4.10. Needed by: cobblemon (also nests its own copy), catchrate-display, better_pokedex_scanner (>=1.13.6+kotlin.2.2.20), fzzy_config, particle_core, zoomify (>=1.13.8), cobblemon-additions. |
| FancyMenu | OPTIONAL/CLIENT-QOL | 3.9.8 | >=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Custom menus (config/fancymenu). env=* but cosmetic. Needs konkrete, melody. DSMSL license. |
| FerriteCore | OPTIONAL/CLIENT-QOL | 7.0.3 | >=1.21.1 <1.22 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Memory perf, server+client. |
| Cobblemon Fight or Flight Fabric | GAMEPLAY-CRITICAL | 0.10.9 | 1.21.1 | Fabric | >=1.7.2 | NEEDS FUNCTIONAL TEST | UPDATE → 0.11.0 | Wild Pokemon attack/flee behaviour. cobblemon >=1.7.2, architectury, cloth-config. 83 API refs (high coupling). |
| Forgiving Void | OPTIONAL/CLIENT-QOL | 21.1.7 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Void fall teleport rule. Needs balm. ARR. |
| Fusion | GAMEPLAY-CRITICAL / LIBRARY | 1.2.12 | >=1.21 <1.22 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: rechiseled (>=1.2.12). Connected-texture lib. ARR. |
| Fzzy Config | GAMEPLAY-CRITICAL / LIBRARY | 0.7.6+1.21 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: particle_core (>=0.7.5). Requires fabric-language-kotlin. |
| GeckoLib 4 | GAMEPLAY-CRITICAL / LIBRARY | 4.9.2 | >=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: cobblemonraiddens (>=4.7.0), pokeblocks (>=4.7.3). fabricloader >=0.17. |
| Global Data- & Resourcepacks | GAMEPLAY-CRITICAL | 21.0.6 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | PACK INFRASTRUCTURE: config/global_packs.toml force-loads datapacks/ (required), datapacks/extra/ (optional: Hoenn/Johto/Sinnoh region DPs + Terralith-DP) and config/cobbleverse as a required resourcepack. Without it the COBBLEVERSE-DP-v31 / Loot / RCT datapacks are not applied. ARR. Metadata description is the template placeholder. |
| Handcrafted | WORLD-CRITICAL | 4.0.3 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | 268 blockstates furniture. Needs resourcefullib >=3.0.0. Terrarium license. |
| Highlight | OPTIONAL/CLIENT-QOL | 3.0.0 | >=1.20.5 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Block selection outline shapes. Bundles resourcefullib. |
| Huge Structure Blocks | DEVELOPMENT-ONLY | 1.1.6 | >=1.21 <=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Bigger structure blocks - map-building tool. Keep while building the map; if huge structure blocks are left in the world, removing the mod would delete them (verify before removal). |
| Infinite Music | OPTIONAL/CLIENT-QOL | 0.4.6 | — | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; no minecraft dep declared. |
| Interactic | OPTIONAL/CLIENT-QOL | 0.2.3+1.21 | >=1.20.3 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Item throw/pickup animations (env=*). Needs owo. Bundles owo-sentinel. |
| Iris | OPTIONAL/CLIENT-QOL | 1.8.14-beta.1+mc1.21.1 | ["1.21.1"] | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only shaders; requires sodium 0.8.x. Beta build. |
| Konkrete | GAMEPLAY-CRITICAL / LIBRARY | 1.9.9 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: fancymenu (>=1.9.4). |
| Krypton | OPTIONAL/CLIENT-QOL | 0.2.8 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Network perf, server+client. |
| Lenient Death | OPTIONAL/CLIENT-QOL | 1.2.5+1.21.1 | >=1.20.5 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Server-side death-item rules (config/lenientdeath.json5) - a gameplay rule, not Cobblemon-coupled. Bundles jackfredlib + fabric-permissions-api. |
| LibJF | GAMEPLAY-CRITICAL / LIBRARY | 3.17.5 | * | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: respackopts (libjf-base/config-core-v2/data-manipulation). 12 nested modules. |
| Lithium | OPTIONAL/CLIENT-QOL | 0.15.4+mc1.21.1 | ["1.21", "1.21.1"] | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Server+client perf. |
| Cobblemon:Mega Showdown | GAMEPLAY-CRITICAL | 1.8.4+1.7.3+1.21.1 | ~1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | UPDATE → 1.0.2+1.8+1.21.1-release | Mega Evolution/Z-moves/Tera/Dynamax + 34 blockstates (keystone ore, meteorite - world-persistent) + worldgen + 28 species files. cobblemon >=1.7.0, accessories >=beta.52, architectury. 163 API refs. NOTE: '1.8.4' is MSD's own version, NOT Cobblemon 1.8. Jar name pins '+1.7.3'. Custom MSD license. |
| Melody | GAMEPLAY-CRITICAL / LIBRARY | 1.0.10 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: fancymenu (>=1.0.6). Audio lib. |
| MidnightLib | GAMEPLAY-CRITICAL / LIBRARY | 1.7.5 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: repurposed_structures (>=1.5.7), customsplashscreen (also nested there). |
| Moar Concrete | WORLD-CRITICAL | 1.3.1 | ~1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | 178 concrete-variant blockstates. Template contact. |
| ModernFix | OPTIONAL/CLIENT-QOL | 5.25.1+mc1.21.1 | >=1.16.2 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Perf, server+client. |
| Mod Menu | OPTIONAL/CLIENT-QOL | 11.0.4 | >=1.21-beta.2 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only. |
| More Culling | OPTIONAL/CLIENT-QOL | 1.0.8 | >=1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; sodium >=0.6.7 required by breaks rule. Needs cloth-config. |
| MusicNotification | OPTIONAL/CLIENT-QOL | 3.0.0 | 1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; no fabricloader dep declared. |
| Neruina | OPTIONAL/CLIENT-QOL | 3.3.3 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Ticking-entity crash guard (server+client). Needs configurable ~3.5.2. Bundles github-api (auto-report). |
| Better Nether Map | OPTIONAL/CLIENT-QOL | 4.0.0-1.21.1 | >=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Maps in nether. Needs cloth-config2. |
| NetherPortalFix | OPTIONAL/CLIENT-QOL | 21.1.3 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Server-side portal linking. Needs balm. ARR. |
| NotEnoughAnimations | OPTIONAL/CLIENT-QOL | 1.12.4 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Client animations (env=*, client entrypoint). tr7zw protective license. |
| Not Enough Crashes | OPTIONAL/CLIENT-QOL | 4.4.9+1.21.1 | >=1.17 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Crash handling. Sodium breaks <4.4.8 (ok at 4.4.9). |
| oωo | GAMEPLAY-CRITICAL / LIBRARY | 0.12.15.4+1.21 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: accessories (>=0.12.15.1), accessories_compat_layer (>=0.12.15.4), interactic (>=0.11.3), particular 1.1.2 (disabled). |
| Packet Fixer | OPTIONAL/CLIENT-QOL | 3.3.1 | >=1.20.5 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Raises packet/NBT size limits - useful for large Cobblemon PC/NBT payloads on servers. minecraft >=1.20.5, fabricloader '*'. |
| Paginated Advancements | OPTIONAL/CLIENT-QOL | 2.5.1 | >=1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only advancement screen. Needs cloth-config. |
| Particle Core | OPTIONAL/CLIENT-QOL | 0.3.3+1.21 | >=1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only particle perf. Needs fzzy_config, kotlin. |
| Particle Rain | OPTIONAL/CLIENT-QOL | 4.0.0-beta.10 | 1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only weather particles (beta). |
| Particular | OPTIONAL/CLIENT-QOL | 1.1.2+1.21 | ~1.21 | Fabric | — | REMOVE | REMOVE | Disabled in the reference pack. DISABLED duplicate: original 'Particular' 1.1.2 (client-only, needs owo-lib ^0.12.10). Same mod id 'particular' as the enabled Particular Reforged 1.5.5 - enabling both would be a duplicate-mod load failure. Delete or keep disabled. |
| Particular Reforged | OPTIONAL/CLIENT-QOL | 1.5.5 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Particular Reforged (multiloader fork) - ambience particles. Needs forgeconfigapiport. env=* (server presence needed?) - verify; recommends iris. |
| PastureLoot | GAMEPLAY-CRITICAL | 1.0.5+1.21.1 | 1.21.1 | Fabric | >=1.7.1+1.21.1 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Pasture loot drops (config/PastureLoot.json). cobblemon >=1.7.1+1.21.1. 1 API ref. Empty description; ARR. |
| PlayerXP | OPTIONAL/CLIENT-QOL | 1.1.1+1.21.1 | 1.21.1 | Fabric | >=1.6.0 | INCOMPATIBLE ON SERVER / NEEDS CLIENT TEST | CLIENT OPTIONAL; SERVER EXCLUDE | The common entrypoint loads Fabric's client-only `ItemTooltipCallback` and crashes a dedicated server. No newer release or source fix exists as of 2026-09-09. Client retention is provisional. |
| Pokeblocks | WORLD-CRITICAL | 1.4.0-1.21.1 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | 314 blockstates (Pokemon figurines, baskets, etc.) - decorative blocks in the map. No cobblemon dependency; needs geckolib >=4.7.3. CC-BY-NC-4.0. |
| Radical Cobblemon Trainers API | GAMEPLAY-CRITICAL / LIBRARY | 0.15.2-beta | ~1.21.1 | Fabric | >=1.7 | NEEDS FUNCTIONAL TEST | UPDATE → 0.16.0-beta | Radical Cobblemon Trainers API - trainer/battle API. Needed by: rctmod (>=0.15.0-beta), cobblemonbattlepositions (>=0.14.0); suggested by raiddens. cobblemon >=1.7 (no upper). 56 API refs. Gameplay-critical library. |
| Radical Cobblemon Trainers | GAMEPLAY-CRITICAL | 0.18.1-beta | 1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | UPDATE → 0.19.0-beta | 1500+ trainers spawning (Radical Red/Unbound/BDSP) + 3 blockstates. cobblemon >=1.7.0, rctapi, forgeconfigapiport >=21.1.1. Pack ships COBBLEVERSE-RCT-DP-v20 datapack + RCTmod RP for it. Bundles jgrapht. |
| Rechiseled | WORLD-CRITICAL | 1.2.4 | >=1.21 <1.21.2 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | 3628 blockstates of decorative block variants - by far the largest block set; any use in the map makes it mandatory. Needs supermartijn642corelib >=1.1.20 <1.2.0, configlib, fusion. ARR + modpack permission. |
| Reese's Sodium Options | OPTIONAL/CLIENT-QOL | 2.2.3+mc1.21.1 | 1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; sodium >=0.8.12 (exactly the shipped version). |
| Repurposed Structures | WORLD-CRITICAL | 7.5.21+1.21.1-fabric | >=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Worldgen: extra structure variants. Removing changes future chunk generation. Needs midnightlib >=1.5.7. |
| Resourceful Lib | GAMEPLAY-CRITICAL / LIBRARY | 3.0.12 | >=1.20.5 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: handcrafted (>=3.0.0), highlight (also nested there). |
| Resource Pack Options | OPTIONAL/CLIENT-QOL | 4.14.0+1.21.1.4 | * | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Resource pack option menus (.rpo files in resourcepacks/). Needs libjf. Conflicts with quilt_loader/connectormod. |
| Sodium | OPTIONAL/CLIENT-QOL | 0.8.12+mc1.21.1 | ["1.21", "1.21.1"] | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only renderer. Provides 'indium'. Large breaks list (iris <1.8.13, moreculling <1.0.8, notenoughcrashes <4.4.8, iceberg <1.2.7 - all satisfied). |
| Sophisticated Backpacks | GAMEPLAY-CRITICAL | 1.21.1-3.23.4.3.106 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Backpacks holding player items. Needs sophisticatedcore >=1.2.9.15 <1.22. GPL-3 unofficial Fabric port. |
| Sophisticated Core | GAMEPLAY-CRITICAL / LIBRARY | 1.21.1-1.2.9.21.168 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: sophisticatedbackpacks, sophisticatedstorage. Needs forgeconfigapiport >=21.1.3, team_reborn_energy (nested). Breaks jei <19.21. 12 nested porting_lib jars. |
| Sophisticated Storage | GAMEPLAY-CRITICAL | 1.21.1-1.3.7.9.139 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Storage blocks with player items (49 blockstates). Needs sophisticatedcore. |
| Sound Physics Remastered | OPTIONAL/CLIENT-QOL | 1.21.1-1.5.1 | ["1.21", "1.21.1"] | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Audio (env=*, client effect). Breaks voicechat <2.3.0. |
| SoundsBeGone | OPTIONAL/CLIENT-QOL | 1.5.2 | >=1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only sound muting. Bundles posthog analytics lib (privacy note). |
| SuperMartijn642's Config Lib | GAMEPLAY-CRITICAL / LIBRARY | 1.1.8 | >=1.21 <1.22 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: rechiseled (>=1.1.6), obc (>=1.1.8; also nested there). ARR. |
| SuperMartijn642's Core Lib | GAMEPLAY-CRITICAL / LIBRARY | 1.1.21 | >=1.21 <1.21.2 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: rechiseled (>=1.1.20 <1.2.0). minecraft >=1.21 <1.21.2. ARR. |
| Tim Core | GAMEPLAY-CRITICAL / LIBRARY | 1.7.3-fabric-1.32.0 | 1.21.1 | Fabric | 1.7.3+1.21.1 | NEEDS FUNCTIONAL TEST | UPDATE → 1.8.0-fabric-1.32.0 | HARD BLOCKER: depends cobblemon "1.7.3+1.21.1" (exact pin). Needed by: capture_xp. 106 API refs. Both Tim mods must be rebuilt for 1.8 or removed together. |
| TM Craft | GAMEPLAY-CRITICAL | 1.4.18+1.7.3 | 1.21.1 | Fabric | 1.7.3+1.21.1 | NEEDS FUNCTIONAL TEST | UPDATE → 1.4.19+1.8.0 | HARD BLOCKER: depends cobblemon "1.7.3+1.21.1" (exact pin). TMs with crafting recipes + move tutor / breeder table blocks (world-persistent). 31 API refs. GPL-3.0. |
| Tom's Simple Storage Mod | GAMEPLAY-CRITICAL | 2.3.0 | >=1.21 <1.21.2 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Storage network blocks holding items (16 blockstates). minecraft >=1.21 <1.21.2. Bundles cardinal-components + cloth-config. |
| ToolTip Fix | OPTIONAL/CLIENT-QOL | 1.1.1-1.20 | — | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; jar says 1.20 but declares no minecraft dep (loads anywhere). Tiny mixin - low risk. |
| Trinkets | GAMEPLAY-CRITICAL / LIBRARY | 3.10.0 | >1.18 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Nothing in the pack hard-depends on trinkets (only recommended by accessories_compat_layer). Candidate for removal unless a resource/data pack or server plugin uses Trinkets slots. minecraft '>1.18' (very loose). |
| VillagerConfig | OPTIONAL/CLIENT-QOL | 4.5.4 | — | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Villager trade customization (config/VillagerConfig/villagerconfig.json5). If the pack defines custom trades there, becomes gameplay-relevant. No minecraft dep declared. Bundles fiber. |
| Waystones | WORLD-CRITICAL | 21.1.37 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Waystone blocks (45 blockstates) + worldgen placement; player-activated waystones are world state. Needs balm. fabricloader >=0.17.3. ARR. |
| Xaero's Minimap | OPTIONAL/CLIENT-QOL | 26.4.2 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Minimap (env=*, has server entrypoint; safe on server). Bundles xaerolib. Breaks xaeroworldmap <1.44.0 (ok). |
| Xaero's World Map | OPTIONAL/CLIENT-QOL | 1.44.2 | >1.20.6 <1.21.2 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | World map. minecraft >1.20.6 <1.21.2. Breaks xaerominimap <26.4.0 (ok). |
| YetAnotherConfigLib | GAMEPLAY-CRITICAL / LIBRARY | 3.8.2+1.21.1-fabric | ~1.21 <1.21.2 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: zoomify (>=3.6.6); recommended by debugify. fabricloader >=0.17.0. |
| zamega | GAMEPLAY-CRITICAL | 1.7.3 | ~1.21.1 | Fabric | >=1.7 | NEEDS FUNCTIONAL TEST | UPDATE → 1.7.7+1.8 | Legends Z-A megas: pure data (species_additions, spawn pools, cobblemon assets) - 0 API refs, but hard-depends mega_showdown >=1.6.2+1.7+1.21.1, cobblemon >=1.7, accessories, architectury. Follows MSD's fate. Jar version '1.7.3' = Cobblemon target. |
| Fast Noise | OPTIONAL/CLIENT-QOL | 1.0.13+1.21 | ~1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Worldgen noise optimization - if it changes noise output the map's future chunks differ; verify determinism vs vanilla before generating. Requires fabricloader >=0.18.4 (highest floor in pack). Breaks moonrise/noisium. |
| Zoomify | OPTIONAL/CLIENT-QOL | 2.15.2+1.21.1 | ~1.21 <1.21.2 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only zoom. Needs YACL, kotlin >=1.13.8. fabricloader >=0.18.0. |

## Non-mod pack components

| Component | Type | Current Version | Minecraft Version | Loader | Cobblemon Dependency | 1.8 Status | Action | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| datapacks/COBBLEVERSE - No Ender Dragon.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/COBBLEVERSE - No Hunger.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/COBBLEVERSE-DP-v31.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/COBBLEVERSE-Loot-DP-v11.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/COBBLEVERSE-RCT-DP-v20.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/PokeCenterPCs-DP.zip | WORLD-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/extra/COBBLEVERSE-Hoenn-DP.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/extra/COBBLEVERSE-Johto-DP.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/extra/COBBLEVERSE-Sinnoh-DP.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/extra/Terralith-DP.zip | WORLD-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| resourcepacks/ATMxMSD RP.zip | OPTIONAL / CLIENT-QOL | 3.6.1 in base 1.7.42 | 1.21.1 | Fabric | Cobblemon model resolvers; Mega Showdown assets | INCOMPATIBLE | PRESERVE INSTALLED; DISABLE BY DEFAULT | First 1.8 client launch failed its resource reload because the pack resolves Mega Mewtwo X as `cobblemon:mewtwo_mega_x.geo`; Mega Showdown 1.0.2 for Cobblemon 1.8 provides `cobblemon:mewtwo_x.geo`. The fallback reload reached the title/welcome screen but left the custom splash visible. Retest a newer or patched pack separately. |
| resourcepacks/COBBLEVERSE RCTmod RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/COBBLEVERSE RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/COBBLEVERSE Soundtrack.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Canon PC Wallpapers.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/CavsCobbleMons RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Classic Grass.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/CobbleMotion RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Cobblemon Interface Modded.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Cobblemon Interface.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Comforts Modernized.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/E19 Cobblemon Minimap Icons.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/EeveelutionsReimagined RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Emissive Cobblemon Ores.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Fresh Animations.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Fresh Icons.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Fresh Moves.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/FullyHisuianStarters RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/GlitchDex RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/HydroReanimodel RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/JigglyRadio.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/LackingMons RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Low Fire.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/MissingMons RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/MundialMons RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/MysticMons RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/OJsAnimations RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Original Pokemon Battle Music.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/PlanetaCobblemon RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/PokeDiscs.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/PokeRods3D.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Pokemans RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/TDmon RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [ATM x MSD - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [CavsCobbleMons - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [CobbleMotion - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [E19 Minimap Icons - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [GlitchDex - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [Hydro Reanimodel - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [LackingMons - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [MissingMons - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [MundialMons - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [MysticMons - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [PlanetaCobblemon - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [Pokemans - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [TDmon - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [Terralith - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| shaderpacks/ComplementaryUnbound_r5.8.1.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | LIKELY WORKING | CLIENT ONLY | shaderpack |

## Boot and smoke-test status

The isolated runtime contains the pinned Fabric launcher, all 101 target server jars, base configuration, overlay configuration, and all 10 datapacks. The effective client plan contains 135 jars, 47 resource packs, 10 datapacks, and one shader pack; its post-removal assembly and GUI launch remain pending.

The first real complete-overlay launch failed in PlayerXP's common entrypoint. The next launch failed in Raid Dens during datapack reload. After applying the scoped exclusions above, capture `20260909-001735` reached `Done (6.377s)` and stopped cleanly. The retained upstream datapacks still emit nonfatal errors for orphaned Raid Dens loot tables; these were recorded without expanding the boot-fix scope. A client connection and the multiplayer smoke checklist are next. Server startup is verified for this exact mod set, while individual gameplay components remain unverified until their functional checks pass.

## Sources

- Local evidence: `base-pack/inventory/mod_inventory.json`, `base-pack/inventory/pack_hashes.csv`, `modpack/manifest/base-cobbleverse-1.7.42.json`, and `modpack/manifest/overlay.json`.
- [Fabric Meta loader API](https://meta.fabricmc.net/v2/versions/loader/1.21.1) and [installer API](https://meta.fabricmc.net/v2/versions/installer).
- Modrinth version records are linked by stable version ID in `overlay.json`; examples include [Cobblemon 1.8.0](https://api.modrinth.com/v2/version/YgmyyFcs), [RCT 0.19.0-beta](https://api.modrinth.com/v2/version/jdUENp3C), and [Mega Showdown 1.0.2](https://api.modrinth.com/v2/version/TACsHsKC).
- PlayerXP evidence: [Modrinth 1.21.1 releases](https://api.modrinth.com/v2/project/cobblemon-playerxp/version?loaders=%5B%22fabric%22%5D&game_versions=%5B%221.21.1%22%5D) and [current common entrypoint source](https://github.com/chudders1231/PlayerXP/blob/1.21.1/fabric/src/main/java/chadlymasterson/playerxp/PlayerXp.java).
- Raid Dens evidence: [Modrinth releases](https://api.modrinth.com/v2/project/cobblemonraiddens/version?loaders=%5B%22fabric%22%5D&game_versions=%5B%221.21.1%22%5D) and [current reload-listener source](https://github.com/necro50n3/cobblemon-raiddens/blob/master/fabric/src/main/java/com/necro/raid/dens/fabric/events/reloader/StatusEffectsReloadListener.java).
