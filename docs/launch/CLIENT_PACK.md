# The client pack: what friends install

Written 2026-10-14. **A client that does not match the server's mods is the most likely launch-night failure.**

## The files (built tonight, in `build/client/`, never committed)

| File | What | sha1 |
|---|---|---|
| `cobblers-client-0.1.0.mrpack` (747,998 bytes; with Lootr, without Custom Splash Screen, rebuilt 2026-10-15) | the modpack: Minecraft 1.21.1, Fabric Loader 0.19.5, every mod below (downloaded from Modrinth by the launcher) | `adb0bce6603cbec951a3edb0f80accb7f884af6f` |
| `cobblers-client-AllTheMons-subset.zip` (1,468,971 bytes, built 2026-10-13) | a resource pack: Cobblemon model fixes plus the AllTheMons x Mega Showdown models for the species that otherwise show as a placeholder doll | `dfdd4f8118a66ff854d23a1e5c2f7651ff042e97` |

Rebuild with `python tools/client_pack.py build` and `python tools/client_model_fix.py build --server-pack`. Check a
friend's install with `python tools/client_pack.py verify <their instance folder>`.

**The pack is the Cobblemon 1.8.2 set, the same set the server runs** (swapped 2026-10-14; 101 server jars).

**The AllTheMons subset's licence question is open** (`docs/decisions/ADR-006-server-delivered-client-pack.md`); you
chose to give it to players directly. Without it the game works; about 43 species render as a placeholder doll.

## Install steps for friends

1. Install the **Modrinth App** (modrinth.com/app). (Prism Launcher also imports `.mrpack` files.)
2. In the app: **Add an instance → From file**, and choose `cobblers-client-0.1.0.mrpack`. It downloads the mods.
   Give the instance at least **6 GB** of memory (instance settings → Java and memory).
3. **The COBBLEVERSE files the pack may not include** (their licence forbids redistribution, so each player takes
   them from COBBLEVERSE itself): download **COBBLEVERSE 1.7.42** from modrinth.com/modpack/cobbleverse (the
   `.mrpack` file), open it like a zip, and copy from its `overrides/` folder into your instance folder:
   - `overrides/mods/cobblemon-battle-positions-1.1.3.jar` → `mods/`
   - every file below from `overrides/resourcepacks/` → `resourcepacks/`:
     COBBLEVERSE RCTmod RP, COBBLEVERSE RP, COBBLEVERSE Soundtrack, CavsCobbleMons RP, CobbleMotion RP,
     E19 Cobblemon Minimap Icons, GlitchDex RP, HydroReanimodel RP, LackingMons RP, MissingMons RP, MundialMons RP,
     MysticMons RP, OJsAnimations RP, PlanetaCobblemon RP, Pokemans RP, TDmon RP (and, optionally, ATMxMSD RP).
   - from its `overrides/config/fancymenu/`: the `assets/` and `slideshows/` folders → your instance's
     `config/fancymenu/` (the title screen's images; without them the menu is black with magenta squares).
4. Copy `cobblers-client-AllTheMons-subset.zip` into `resourcepacks/`. It also carries our NPC looks (Brock, data/npc_looks.json; without it he is a substitute doll) and the dungeon rip's oval (without it a rip is a plain purple shard).
5. Launch once, open **Options → Resource Packs**, and make sure the packs are enabled (the subset zip at the top).
6. **Multiplayer → Add Server**, the address from the owner (see `docs/launch/HOSTING.md`). Your Minecraft username
   must be on the whitelist: send it to the owner first.

If the server says your mods do not match: you are on an old pack. Delete the instance and import the current
`.mrpack` again.

## The mod list (client and both sides), from `python tools/pack_manifest.py plan --side client`

134 files (Lootr added, Custom Splash Screen removed 2026-10-15: it crashed the loading screen with MidnightLib 1.9.3). Status `replace` is one of our updates over COBBLEVERSE 1.7.42; `base` is COBBLEVERSE's own.

| File | Side | Status |
|---|---|---|
| `AdvancementPlaques-1.21.1-fabric-1.6.8.jar advancementplaques` | client | base |
| `BadOptimizations-2.4.1-1.21.1.jar badoptimizations` | client | base |
| `BetterF1-Fabric-1.1+1.21.7.jar betterf1` | client | base |
| `BetterF3-11.0.3-Fabric-1.21.1.jar betterf3` | client | base |
| `BetterThirdPerson-Fabric-1.21-1.9.0.jar betterthirdperson` | client | base |
| `Carved Wood-fabric-1.21.1-1.9.8-B.jar carved_wood` | both | replace |
| `CobbleDollars-fabric-2.0.0+Beta-6.1+1.21.1.jar cobbledollars` | both | replace |
| `CobbleFurnies-fabric-1.2.jar cobblefurnies` | both | base |
| `Cobblemon-fabric-1.8.2+1.21.1.jar cobblemon` | both | replace |
| `CobbleverseBadges-1.3.jar cobbleversebadges` | both | base |
| `Cobbreeding-fabric-2.4.1.jar cobbreeding` | both | replace |
| `Controlling-fabric-1.21.1-19.0.5.jar controlling` | client | base |
| `Debugify-1.21.1+1.1.jar debugify` | both | replace |
| `EuphoriaPatcher-1.9.3-r5.8.1-fabric.jar euphoria_patcher` | client | base |
| `ForgeConfigAPIPort-v21.1.6-1.21.1-Fabric.jar forgeconfigapiport` | both | base |
| `Iceberg-1.21.1-fabric-1.3.2.jar iceberg` | both | base |
| `ImmediatelyFast-Fabric-1.6.14+1.21.1.jar immediatelyfast` | client | replace |
| `IronChests-2.0.4.jar ironchest` | both | base |
| `LegendaryMonuments-Cobbleverse.jar legendarymonuments` | both | base |
| `Luckys-Cozyhome-Refurnished-1.1.20.jar cozyhome` | both | base |
| `LumyMon-0.6.6.jar lumymon` | both | base |
| `LumyREI-1.1.3.jar lumyrei` | client | base |
| `MobsBeGone-0.0.9.jar mobsbegone` | both | replace |
| `MoreCobblemonTweaks-fabric-1.3.5.jar more_cobblemon_tweaks` | both | replace |
| `MouseTweaks-fabric-mc1.21-2.26.jar mousetweaks` | client | base |
| `NoChatRestrictions-Fabric-MC1.21.11-v1.0.3.jar nochatrestrictions` | both | replace |
| `Only Bottle Caps-1.5.0-fabric.jar obc` | both | replace |
| `Ping-Wheel-1.12.2-fabric-1.21.1.jar pingwheel` | both | base |
| `Platform-fabric-1.21.1-1.3.3.jar platform` | both | base |
| `ResourcePackOverrides-v21.1.0-1.21.1-Fabric.jar resourcepackoverrides` | client | base |
| `RoughlyEnoughItems-16.0.799-fabric.jar roughlyenoughitems` | both | base |
| `SafePastures(Fabric)-1.1.2+1.21.1.jar safepastures` | both | replace |
| `ScalableLux-0.1.0.1+fabric.d0d58ab-all.jar scalablelux` | both | base |
| `Searchables-fabric-1.21.1-1.0.2.jar searchables` | client | base |
| `StackDeobfuscatorFabric-1.4.3+08e71cc.jar stackdeobfuscator` | both | base |
| `VanillaBackport-fabric-1.21.1-1.1.7.10.jar vanillabackport` | both | base |
| `accessories-fabric-1.1.0-beta.53+1.21.1.jar accessories` | both | base |
| `accessories_compat_layer-fabric-0.1.12+1.21.1.jar accessories_compat_layer` | both | base |
| `advancementdisable-fabric-1.0.1+1.21.jar advancementdisable` | both | base |
| `architectury-13.0.11-fabric.jar architectury` | both | replace |
| `athena-fabric-1.21.1-4.0.6.jar athena` | both | base |
| `balm-fabric-1.21.1-21.0.66.jar balm` | both | replace |
| `beautify-3.0.0+1.21.1.jar beautify` | both | replace |
| `betterbeds-fabric-1.4.0.jar betterbeds` | client | base |
| `biomereplacer-2.1-hippo-fabric.jar biome_replacer` | both | base |
| `brb-1.10.0-rc5+1.21.jar brb` | client | base |
| `catchindicator-fabric-3.0.jar catchindicator` | client | replace |
| `catchrate-display-fabric-2.12.3.jar catchrate-display` | client | replace |
| `cloth-config-15.0.140-fabric.jar cloth-config` | both | base |
| `cobblecuisine-2.0.1-1.7.rc1.jar cobblecuisine` | both | base |
| `cobblemon-additions-4.3.0.jar cobblemon-additions` | both | replace |
| `cobblemon-battle-extras-fabric-1.13.45.jar cobblemon-battle-extras` | both | base |
| `cobblemon-battle-positions-1.1.3.jar cobblemonbattlepositions` | both | base |
| `cobblenav-fabric-2.4.1.jar cobblenav` | both | replace |
| `comforts-fabric-9.0.5+1.21.1.jar comforts` | both | base |
| `configurable-3.5.2+1.21.1-fabric.jar configurable` | both | base |
| `continuity-3.0.0+1.21.jar continuity` | client | base |
| `defaultoptions-fabric-1.21.1-21.1.8.jar defaultoptions` | both | replace |
| `entity_model_features-3.3.11-1.21-fabric.jar entity_model_features` | client | replace |
| `entity_texture_features-7.2.5-1.21-fabric.jar entity_texture_features` | client | replace |
| `entityculling-fabric-1.11.3-mc1.21.1.jar entityculling` | both | replace |
| `fabric-api-0.116.17+1.21.1.jar fabric-api` | both | replace |
| `fabric-language-kotlin-1.14.2+kotlin.2.4.21.jar fabric-language-kotlin` | both | replace |
| `fancymenu_fabric_3.9.14_MC_1.21.1.jar fancymenu` | both | replace |
| `ferritecore-7.0.3-fabric.jar ferritecore` | both | base |
| `fightorflight-fabric-0.11.0.jar fightorflight` | both | replace |
| `forgivingvoid-fabric-1.21.1-21.1.7.jar forgivingvoid` | both | base |
| `fusion-1.3.16-fabric-mc1.21.jar fusion` | both | replace |
| `fzzy_config-0.7.7+1.21.jar fzzy_config` | both | replace |
| `geckolib-fabric-1.21.1-4.9.3.jar geckolib` | both | replace |
| `globalpacks-fabric-1.21.1-21.0.6.jar globalpacks` | both | base |
| `handcrafted-fabric-1.21.1-4.0.3.jar handcrafted` | both | base |
| `highlight-fabric-1.21-3.0.0.jar highlight` | both | base |
| `huge-structure-blocks-fabric-1.1.6.jar hugestructureblocks` | both | base |
| `infinite-music-0.4.6.jar infinite-music` | client | base |
| `interactic-0.2.3+1.21.jar interactic` | both | base |
| `iris-fabric-1.8.14-beta.1+mc1.21.1.jar iris` | client | base |
| `konkrete_fabric_1.9.9_MC_1.21.jar konkrete` | both | base |
| `krypton-0.2.8.jar krypton` | both | base |
| `lenientdeath-1.2.5+1.21.1.jar lenientdeath` | both | base |
| `libjf-3.17.5.jar libjf` | both | base |
| `lithium-fabric-0.15.4+mc1.21.1.jar lithium` | both | base |
| `mega_showdown-fabric-1.3.0+1.8.2+1.21.1-hotfix.jar mega_showdown` | both | replace |
| `melody_fabric_1.0.10_MC_1.21.jar melody` | both | base |
| `midnightlib-fabric-1.9.3+1.21.1.jar midnightlib` | both | replace |
| `moar-concrete-1.3.1.jar moarconcrete` | both | base |
| `modernfix-fabric-5.25.1+mc1.21.1.jar modernfix` | both | base |
| `modmenu-11.0.5.jar modmenu` | client | replace |
| `moreculling-fabric-1.21.1-1.0.10.jar moreculling` | client | replace |
| `musicnotification-fabric-3.0.0+mc1.21.1.jar musicnotification` | client | base |
| `neruina-3.3.3+1.21.1-fabric.jar neruina` | both | base |
| `nethermap-4.0.0-1.21.1.jar nethermap` | both | base |
| `netherportalfix-fabric-1.21.1-21.1.3.jar netherportalfix` | both | base |
| `notenoughanimations-fabric-1.12.6-mc1.21.1.jar notenoughanimations` | both | replace |
| `notenoughcrashes-fabric-4.4.9+1.21.1.jar notenoughcrashes` | both | base |
| `owo-lib-0.12.15.4+1.21.jar owo` | both | base |
| `packetfixer-3.3.1-1.20.5-1.21.X-merged.jar packetfixer` | both | base |
| `paginatedadvancements-2.5.1.jar paginatedadvancements` | client | base |
| `particle_core-0.3.3+1.21.jar particle_core` | client | base |
| `particlerain-4.0.2+1.21.1-fabric.jar particlerain` | client | replace |
| `particular-1.21.1-Fabric-1.5.7.jar particular` | both | replace |
| `pastureLoot-1.0.5+1.21.1.jar pasture-loot` | both | base |
| `playerxp-fabric-1.1.1+1.21.1.jar playerxp` | both | replace |
| `pokeblocks-1.5.0-1.21.1.jar pokeblocks` | both | replace |
| `rctapi-fabric-1.21.1-0.16.2-beta.jar rctapi` | both | replace |
| `rctmod-fabric-1.21.1-0.19.2-beta.jar rctmod` | both | replace |
| `rechiseled-1.2.6-fabric-mc1.21.jar rechiseled` | both | replace |
| `reeses-sodium-options-fabric-2.2.4+mc1.21.1.jar reeses-sodium-options` | client | replace |
| `repurposed_structures-7.5.22+1.21.1-fabric.jar repurposed_structures` | both | replace |
| `resourcefullib-fabric-1.21-3.0.12.jar resourcefullib` | both | base |
| `respackopts-4.14.0+1.21.1.4.jar respackopts` | both | base |
| `sodium-fabric-0.8.13+mc1.21.1.jar sodium` | client | replace |
| `sophisticatedbackpacks-1.21.1-3.23.4.3.106.jar sophisticatedbackpacks` | both | base |
| `sophisticatedcore-1.21.1-1.2.9.21.168.jar sophisticatedcore` | both | base |
| `sophisticatedstorage-1.21.1-1.3.7.9.139.jar sophisticatedstorage` | both | base |
| `sound-physics-remastered-fabric-1.21.1-1.5.1.jar sound_physics_remastered` | both | base |
| `soundsbegone-fabric-1.6.0+mc1.21.jar soundsbegone` | client | replace |
| `supermartijn642configlib-1.1.8-fabric-mc1.21.jar supermartijn642configlib` | both | base |
| `supermartijn642corelib-1.1.25-fabric-mc1.21.jar supermartijn642corelib` | both | replace |
| `timcore-fabric-1.8.2-1.34.0.jar tim_core` | both | replace |
| `tmcraft-1.4.19+1.8.2.jar tmcraft` | both | replace |
| `toms_storage_fabric-1.21-2.4.2.jar toms_storage` | both | replace |
| `tooltipfix-1.1.1-1.20.jar tooltipfix` | client | base |
| `trinkets-3.10.0.jar trinkets` | both | base |
| `villagerconfig-fabric-4.5.4+1.21.1.jar villagerconfig` | both | base |
| `waystones-fabric-1.21.1-21.1.46.jar waystones` | both | replace |
| `xaerominimap-fabric-1.21.1-26.6.0.jar xaerominimap` | both | replace |
| `xaeroworldmap-fabric-1.21.1-1.47.0.jar xaeroworldmap` | both | replace |
| `yet_another_config_lib_v3-3.8.2+1.21.1-fabric.jar yet_another_config_lib_v3` | both | base |
| `zamega-fabric-1.8.2+1.8.2.jar zamega` | both | replace |
| `zfastnoise-1.0.13+1.21.jar zfastnoise` | both | base |
| `zoomify-2.15.2+1.21.1.jar zoomify` | client | base |
| `DistantHorizons-3.3.3-1.21.1-fabric-neoforge.jar distanthorizons` | both | add |
| `lootr-fabric-1.21.1-1.11.38.127.jar lootr` | both | add |
