# EXP-036: A wild Mega Pokémon

## Objective
The owner wants a mega stone mine in the southern Rift whose wild Pokémon are all Megas, uncatchable and enraged
(`docs/world-building/SOUTHERN_RIFT.md`). `docs/research/notes/wild-mega-pokemon.md` found from source that a spawn
can carry Cobblemon 1.8's `mega_evolution` aspect. The open question: does a battle against a spawned Mega start
cleanly, fight as the Mega and stay Mega?

## Setup
- Staging world `cobblers-dryrun10`, Blaine's town ash square, 2026-09-25. Cobblemon 1.8.0+1.21.1, the Cobbleverse
  1.7.42 stack with Mega Showdown and fightorflight as pinned in `modpack/manifest/`.
- Command, over RCON when the owner stood at (6074, 108, 4995):
  `spawnpokemonat 6080 108 4995 charizard mega_evolution=mega_x uncatchable level=25`.
- The owner's party: level 25.

## Results
| Check | Result | Evidence |
| --- | --- | --- |
| The entity is a Mega | **yes** | `Pokemon.FormId` `megax`; feature `mega_evolution: "mega_x"`; ability `toughclaws` (Mega Charizard X's) |
| Uncatchable flag carried | **yes** (data) | `PokemonData` `["uncatchable", ...]` |
| A battle starts | **yes** | the owner: "battle started" |
| It stays Mega in battle | **yes** | the owner: "mega stayed" |
| A thrown ball refused | not reported yet | |
| Mega after the battle; behaviour after | not reported yet | |
| Enraged (fightorflight `always_aggro_aspects`) | not tested: the config line is not set | |
| From a spawn pool or Habitat Block rather than a command | not tested | |

## Decision
A wild Mega is achievable with Cobblemon's own `mega_evolution` aspect: the mega stone mine's "true wild Mega" mode is
viable. Still to prove before building it: uncatchable in play, enraged by config, and spawning from our pools.
