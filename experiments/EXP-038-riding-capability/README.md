# EXP-038: Can the installed pack identify Surf-capable and Dive-capable Pokemon?

**Spec question** (`docs/mechanics/DEATH_AND_WIPE.md`, open technical question 8): what identifies Surf-capable and
Dive-capable mounts in the installed pack, and can party contents be read for it? The spec says to stop and report if
the riding system cannot expose the capability. **It can.** The design does not need to stop.

Versions: Cobblemon 1.8.0 (`Cobblemon-fabric-1.8.0+1.21.1.jar`), COBBLEVERSE-DP v31,
`mega_showdown-fabric-1.0.2+1.8+1.21.1`, Minecraft 1.21.1 Fabric. All were read from the server's `mods/` and
`datapacks/`, a folder staging and the live server share.

## Findings (VERIFIED from the data and the bytecode)

1. **Riding is data, per species, by environment.** A species' `riding.behaviours` is keyed by `RidingStyle`
   (`LAND`, `LIQUID`, `AIR`). Each value names a behaviour from `data/cobblemon/ride_settings/`. There are three water
   keys:
   - `cobblemon:liquid/boat`: carries the rider on the surface.
   - `cobblemon:liquid/dolphin`: swims, surfacing and leaping.
   - `cobblemon:liquid/submarine`: travels underwater. It is the only underwater style.
2. **The installed set.**
   - 312 species are rideable once the jar, Cobbleverse's datapack and Mega Showdown are merged.
   - 55 have `LIQUID`.
   - **Surf (boat or dolphin), 45:** Arctovish, Armaldo, Basculegion, Carracosta, Clawitzer, Crawdaunt, Dewgong,
     Dracovish, Dragapult, Dragonite, Drednaw, Empoleon, Feraligatr, Garchomp, Golduck, Golisopod, Greninja, Gyarados,
     Jellicent, Kingdra, Koraidon, Kyogre, Lanturn, Lapras, Latias, Latios, Lugia, Lumineon, Mantine, Milotic,
     Miraidon, Poliwrath, Primarina, Rayquaza, Samurott, Sharpedo, Slowbro, Slowking, Suicune, Swampert, Swanna,
     Vaporeon, Walrein, Whiscash, Yveltal.
   - **Dive (submarine), 10:** Blastoise, Cloyster, Dhelmise, Dondozo, Kingler, Relicanth, Seaking, Toxapex, Wailmer,
     Wailord.
   - Most entries come from COBBLEVERSE-DP or Mega Showdown overriding the jar. That the usual datapack order decides
     which one wins is ASSUMED; the runtime check below confirms it.
3. **Runtime access.**
   - Server code reads `RidingProperties` per form.
   - **MoLang reaches the party but not the capability.**
     - `PlayerMoLangFunctions` has `party` and `riding_pokemon`.
     - `PartyMoLangFunctions` has `get_pokemon`.
     - `PokemonMoLangFunctions` has `species`, `form`, `form_name` and `has_learned`.
     - `PokemonEntityMoLangFunctions` has `riding_style` (the entity's current style) and `is_ridden`.
     - No MoLang function returns a party member's riding behaviours. So capability "in the party" is a match of
       `species` (and form) against lists generated from the data above.
   - **MoLang runs server-side.**
     - Cobblemon registers `/runmolang` and `/runmolangscript`.
     - It fires MoLang callbacks from `data/<ns>/callbacks/<event>/`, including `player_tick_pre`; Cobblemon's own
       `partner_mark.molang` runs there, throttled to every 10 s.
     - MoLang has `run_command`, `save_data`, `has_advancement` and `get_custom_stat`.
4. **What a datapack alone could do for the water ladder** (ASSUMED until the test):
   - a throttled `player_tick_pre` script matches the party's species against the generated lists, and checks the
     unlock (an advancement);
   - it runs vanilla commands: `attribute ... minecraft:generic.oxygen_bonus` for Surf's finite bonus,
     `effect ... water_breathing` for Dive's unlimited air, and `damage ... minecraft:drown` for the
     half-maximum-health pulse.

## Test (in game, a player online)

1. `/runmolang` as the player, with a party of Lapras, Wailmer and a non-rider: print
   `q.player.party.get_pokemon(i).species` and the form. This confirms the party read and the identifiers.
2. Ride Lapras (boat), Gyarados (dolphin) and Wailmer (submarine), and read `riding_style` / `get_riding_state` on the
   ridden entity. This confirms the merged data, and that submarine really stays under while dolphin does not.
3. A callback in our own namespace (`data/cobblers/callbacks/player_tick_pre/water_probe.molang`) fires, throttled,
   and writes a score or `save_data`. This confirms custom-namespace callbacks and their tick cost.

## Result

Static: **capability is identifiable** from the data, and readable at runtime by species through MoLang. The in-game
steps are not run yet.

## Decision it feeds

The water ladder does not need a companion module (ADR-005, proposed).
