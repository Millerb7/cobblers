# EXP-054: Do the Mega field's Megas attack a player in the open Rift, by day and by night?

## Objective

The owner wants the south-west Rift basin to be "an aggressive and hostile resource farm"
(`docs/world-building/MEGA_FIELD.md`). The Megas are spawned by the gulch keeper
(`tools/gulch_mine.py` `megas/spawn_at`, `mega_evolution=mega uncatchable level=L`). Aggression comes
from Fight or Flight 0.11.0 (the jar `modpack/manifest/overlay.json` pins, SHA-1 `d3031a63...`), whose
`always_aggro_aspects` the server runs as `["alpha", "mega", "mega_x", "mega_y", "mega_z"]`
(`server/config/mods/fightorflight.json5:98-104`). Two things are not known:

1. **The light gate (proof M-3, `SOUTHERN_RIFT_MEGA.md:681-683`).** `light_dependent_unprovoked_attack`
   is `true` (`fightorflight.json5:7`). FoF's own comment (`fightorflight.json5:6`): "If the aggressive
   pokemon will only attack unprovoked in the dark area.(similar to the spider in Minecraft". The research note reads the
   source as applying this gate even to an `always_aggro` Pokemon and assumes the cut-off at a light
   of about 12 (`docs/research/notes/wild-mega-pokemon.md:133-136`). The installed jar's
   `PokemonWildProactiveSensor` and `PokemonNearestAttackableTargetGoal` both read the key and both
   call intermediary `method_5718` (read 2026-10-03 with Python `zipfile`). The field is outdoors under
   open sky, so **by this reading its Megas attack unprovoked only at night**.
2. **Whether the aspect is `mega`.** `always_aggro_aspects` matches `pokemon.getAspects()`. EXP-036
   showed `mega_evolution=mega_x` gives the form `megax`; which ASPECT string a keeper-spawned
   `mega_evolution=mega` carries has not been read.

"Yes" to both by day would make the field hostile with no further change. "Only at night" leaves the
owner a choice (section Decision).

## Success criteria

- A1: at noon (`/time set 6000`), a survival player walking to 12 blocks of a keeper-spawned field Mega
  (level >= 25) is or is not targeted within 30 s (FoF's sensor: the Mega walks at the player and
  hits). Record which.
- A2: the same at midnight (`/time set 18000`).
- A3: the Mega's aspects, read with `/data get entity <mega> Pokemon` (the `Aspects`/form field), include
  or do not include `mega`.
- A4: when the Mega hits the player's sent-out Pokemon, a battle starts
  (`force_wild_battle_on_pokemon_hurt: true`, `fightorflight.json5:231`); when it hits the player, no
  battle starts (`force_wild_battle_on_player_hurt: false`, `:235`).
- A5 (only if A1 fails and the owner asks for it): with `light_dependent_unprovoked_attack: false` in a
  staging-only copy of the config and a restart, A1 again; plus one vanilla-spawned `always_aggro`
  species (e.g. a Gyarados, `fightorflight.json5` `always_aggro`) by day, to see what the global change
  does outside the field.
- A6: one timed win: a party at the cap against a field Mega at its tier's level, wall-clock minutes and
  how many of the party fainted. This is the number `farm_tiers` is ASSUMED on.

## Dependencies

Cobblemon 1.8.0+1.21.1, Mega Showdown 1.0.2, Fight or Flight 0.11.0; the gulch pack built with the
field's farms (`python tools/gulch_mine.py build`, step R9S); staging only.

## Implementation

Nothing new: the field's dens are ordinary `data/gulch_mine.json` `farms[].dens` and the keeper spawns
them when a player is inside a field farm's approach box with nobody within 24 of the den.

## Test instructions

1. Session start per `CLAUDE.md` (process and port check, the coordination lock, `install_check.py`).
   STAGING world only.
2. Install and run R9S as the re-application does; stand in the approach box of `field_west_low`
   (`data/gulch_mine.json`) more than 24 from its first den, wait for the keeper (every 100 ticks).
3. A3: `/data get entity @e[type=cobblemon:pokemon,tag=cobblers.gm.farm,limit=1,sort=nearest] Pokemon`.
4. A1 then A2: survival mode, no Pokemon out, walk toward the den; note the time to the first hit.
5. A4: send out a Pokemon, let the Mega hit it; then recall it and let the Mega hit the player.
6. A6: fight it with a capped party; time it.
7. A5 only on the owner's word.

## Results

Not run.

## Limitations

The 20-level exemption the owner asked for (`SOUTHERN_RIFT_MEGA.md:671`, M-3b) is not a FoF key and is
not tested here. Two players at once, and a player disconnecting mid-fight, are not covered.

## Decision

Pending. If A1 fails and A2 passes, the owner chooses: (a) the field is hostile at night only (today's
config, no change); (b) `light_dependent_unprovoked_attack: false` in `modpack/config/` and
`server/config/` (one documented key, global: every aggressive wild Pokemon on the map attacks by day);
(c) something narrower, which needs its own experiment first.

## Follow-up

Re-set `farm_tiers` (level, drop rate, respawn) from A6.
