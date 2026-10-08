# Legendary species in our Cobblemon 1.8.0 stack, and the boss tooling for a per-player Entei

**Answered for:** the offline server snapshot `C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05`
(`mods/`, `datapacks/`), plus the client resource packs in the local COBBLEVERSE Modrinth profile
(`%APPDATA%/ModrinthApp/profiles/COBBLEVERSE - Pokemon Adventure [Cobblemon]/resourcepacks/`), 2026-10-10 research
unit SPECIES. Companion to `docs/mechanics/NETHER_DUNGEON_SCOPE.md` section 7 (this is its research R1) and
`docs/research/notes/legendary-catalogue-reopened.md`.

## Method, and what was not read

- Python `zipfile` only: species JSON, `species_additions`, resolver/model/poser/texture entries, printable strings
  of class constant pools. No bytecode decompiled, nothing booted, nothing spawned. Scan scripts:
  `species_scan.py`, `species_report.py`, `resolver_report.py` (session scratchpad, not committed).
- **Server data** = every jar in `mods/` plus every zip in `datapacks/` (COBBLEVERSE-DP-v31 included). That the DP is
  enabled in the staging world is RELAYED (STATE "Latest install": "5 key packs enabled"), not re-read here.
  `datapacks/extra/` (Hoenn, Johto, Sinnoh, Terralith) was scanned separately: **it carries no species files at all**,
  so disabling it removed structures, never species.
- **Client models** = mod jars plus the 15 Pokemon RPs `modpack/config/resourcepackoverrides.json` `default_packs`
  enables. `ATMxMSD RP.zip` is listed only to show it is the sole source and is **disabled by our overlay**
  (STATE "Client models"). That players' clients hold the same RP files as this local profile is ASSUMED.
- "Renders" below means: a resolver variation with no required aspect points at a model, poser and texture that
  exist in an enabled source. It is a file check, **not seen in game**.

## 1. The species (VERIFIED, jar/zip entries)

**Cobblemon 1.8.0 itself implements almost none of them.** In `Cobblemon-fabric-1.8.0+1.21.1.jar` the species files
exist (`data/cobblemon/species/generationN/<name>.json`, with stats and learnsets) but carry no `implemented` key for
Entei, Raikou, Suicune, Heatran, Arceus, Dialga, Palkia, Kyogre, Groudon, Deoxys, Jirachi, Shaymin, Cresselia, Celebi,
Hoopa, Giratina and Darkrai, and the jar ships **no model** for any of them (Entei's only assets are its sounds and dex
entry). What implements and draws them in **our** stack is **Mega Showdown 1.0.2** (`mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar`,
`environment: "*"`, depends `cobblemon >=1.8.0`): `data/cobblemon/species_additions/<name>.json` sets
`"implemented": true`, and `assets/cobblemon/bedrock/pokemon/{resolvers,models,posers,animations}` plus
`textures/pokemon/` give the model. COBBLEVERSE-DP-v31 overrides the same `species_additions` path with its own copy
(also `implemented: true`, plus `behaviour`, scale and riding).

| Species | Types | HP/Atk/Def/SpA/SpD/Spe | Abilities (h = hidden) | Catch | Implemented by | Base model from | Renders? |
|---|---|---|---|---|---|---|---|
| **Entei** | fire | 115/115/85/90/75/100 | pressure, h:innerfocus | 3 | MSD addition; DP addition | MSD `0_entei_base.json` -> `entei.geo`, poser, `0244_entei/entei.png` | **yes** |
| **Raikou** | electric | 90/85/75/115/100/115 | pressure, h:innerfocus | 3 | MSD; DP | MSD | yes |
| **Suicune** | water | 100/75/115/90/115/85 | pressure, h:innerfocus | 3 | MSD; DP | MSD | yes |
| **Heatran** | fire/steel | 91/90/106/130/106/77 | flashfire, h:flamebody | 3 | MSD; DP | MSD (ZAMegas adds a mega) | yes |
| **Ho-Oh** (`hooh`) | fire/flying | 106/130/90/110/154/90 | pressure, h:regenerator | 3 | **Cobblemon itself** | Cobblemon `0_hooh_base.json` -> `ho_oh.geo` | yes |
| **Mewtwo** | psychic | 106/110/90/154/90/130 | pressure, h:unnerve | 3 | **Cobblemon itself** | Cobblemon `0150_mewtwo` | yes |
| **Arceus** | normal | 120 x6 | multitype | 3 | MSD; DP | MSD, with all 18 plate textures | yes |
| Cresselia | psychic | 120/70/110/75/120/85 | levitate | 3 | DP only | CavsCobbleMons RP | yes (client RP) |
| Shaymin | grass | 100 x6 | naturalcure | 45 | MSD; DP | MSD; MissingMons RP | yes |
| Dialga | steel/dragon | 100/120/120/150/100/90 | pressure, h:telepathy | 3 | MSD; DP | MSD; HydroReanimodel, Pokemans RPs | yes |
| Palkia | water/dragon | 90/120/100/150/120/100 | pressure, h:telepathy | 3 | MSD; DP | MSD; HydroReanimodel, Pokemans RPs | yes |
| Regieleki | electric | 80/100/50/100/50/200 | transistor | 3 | Cobblemon itself | Cobblemon | yes |
| Regidrago | dragon | 200/100/50/100/50/80 | dragonsmaw | 3 | Cobblemon itself | Cobblemon | yes |
| Deoxys | psychic | 50/150/50/150/50/150 | pressure | 3 | MSD; DP | MSD (all four formes) | yes |
| **Jirachi** | steel/psychic | 100 x6 | serenegrace | 3 | DP only | **only ATMxMSD (disabled)** | **no: the substitute doll** |
| Regigigas | normal | 110/160/110/80/110/100 | slowstart | 3 | Cobblemon itself | Cobblemon | yes |
| Kyogre | water | 100/100/90/150/140/90 | drizzle | 3 | MSD; DP | MSD (+ primal) | yes |
| Groudon | ground | 100/150/140/100/90/90 | drought | 3 | MSD; DP | MSD (+ primal) | yes |
| Rayquaza | dragon/flying | 105/150/90/150/90/95 | airlock | 3 | Cobblemon (MSD, DP override the file) | Cobblemon | yes |
| Regice / Regirock / Registeel | ice / rock / steel | Cobblemon standard | clearbody, h: icebody / sturdy / lightmetal | 3 | Cobblemon itself | Cobblemon | yes |
| Latias / Latios | dragon/psychic | standard | levitate | 3 | Cobblemon itself | Cobblemon | yes |
| Lugia | psychic/flying | 106/90/130/90/154/110 | pressure, h:multiscale | 3 | Cobblemon itself | Cobblemon | yes |
| Celebi | psychic/grass | 100 x6 | naturalcure | 45 | DP only | MissingMons RP | yes (client RP) |
| Hoopa | psychic/ghost | 80/110/60/150/130/70 | magician | 3 | MSD full species file; DP | MSD `hoopa_confined.geo` (+ unbound) | yes |
| Giratina | ghost/dragon | 150/100/120/100/120/90 | pressure, h:telepathy | 3 | MSD; DP | MSD; HydroReanimodel RP | yes |
| Darkrai | dark | 70/90/90/135/90/125 | baddreams | 3 | MSD; DP | MSD | yes |

**Every boss candidate in the Nether scope renders, and needs no region pack: Entei, Raikou, Suicune, Heatran, Ho-Oh,
Mewtwo.** The one doll among the disabled packs' legendaries is **Jirachi**. Entei, Raikou, Suicune, Heatran,
Arceus, Kyogre, Groudon and Deoxys depend on Mega Showdown for both implementation and model: removing MSD would
make them unimplemented and model-less (Cobblemon's own files have neither).

**The sweep beyond the list** (every species labelled legendary, mythical, ultra_beast or paradox; full output from
`species_report.py sweep`). Implemented and modelled through MSD or Cobblemon: the Kalos, Alola, Galar and Paldea
legendaries broadly (Xerneas, Yveltal, Zygarde, the Tapus, Cosmog line, Solgaleo, Lunala, Necrozma, Zacian,
Zamazenta, Eternatus, Calyrex and steeds, Kubfu/Urshifu, Koraidon, Miraidon, the loyal three, Ogerpon, Terapagos, the
Swords of Justice, Reshiram, Zekrom, Kyurem, the forces of nature, Enamorus, Meloetta, Genesect, Diancie, Volcanion,
Marshadow, Meltan, Melmetal, Victini, Keldeo, Zarude, the Ruinous four). **Dolls** (implemented by the DP, the only
model in disabled ATMxMSD, or no resolver at all): Jirachi, Manaphy, Phione, Pecharunt, every Ultra Beast but
Poipole/Naganadel/Kartana (Nihilego, Buzzwole, Pheromosa, Xurkitree, Celesteela, Guzzlord, Stakataka, Blacephalon),
and every Paradox but Walking Wake and Iron Leaves; Magearna and Zeraora have only a ZAMegas mega resolver.

## 2. Boss tooling in 1.8.0

**PokemonProperties keys** (VERIFIED as constant-pool strings of
`com/cobblemon/mod/common/api/pokemon/PokemonProperties*.class`; meaning per the repo's own use where cited):
`level`/`lvl`, `shiny`, `gender`, `nature`, `ability`, `friendship`, `pokeball`, `held_item`/`helditem`,
`moves`/`move`, `moveset_builder`, `<stat>_iv`, `<stat>_ev`, `ivs`/`evs`, `min_perfect_ivs`, `aspects`,
`alpha`/`is_alpha`, `scale_modifier`, `tera_type`, `dmax_level`, `gmax_factor`, `tradeable`, `originaltrainer`,
`nickname`, `status`. Custom flag properties registered in `com/cobblemon/mod/common/pokemon/properties/`:
**`uncatchable`** (`UncatchableProperty`, a `FlagProperty`; the string also appears in `Pokemon.class` and
`BattlePokemon$Companion`), `no_ai`, `freeze_frame`, `held_item_visible`, `hiddenability`, battle clone. Working
examples already in the repo: `data/placements.json:27772` (Necrozma: `level=80`, six `*_iv=30`,
`moves=nightslash,photongeyser,powergem,shadowclaw`) and `tools/gulch_mine.py:1495` (`$spawnpokemonat ... $(aspect)
uncatchable level=$(level)`). That `moves=` accepts a move outside the species' learnset is ASSUMED.

**There is no HP multiplier, shield, or multi-turn "boss" stat in the property set** (no such key among the
strings). `scale_modifier` is a size key; whether it touches stats is NOT READ (ASSUMED visual/hitbox). No raid-boss
mod is installed: no Cobblemon Raid Dens jar in the snapshot's `mods/`. So a "boss" in 1.8.0 is one wild Pokemon made
hard by level, IVs, EVs, nature, ability, held item and moves.

**"Bosses are native alphas" (STATE "Latest install") is Cobblemon 1.8.0's native Alpha** (VERIFIED, jar entries):
`alpha=true` in the properties; the jar's own 1,082 herd leaders use it. What the jar makes an alpha do, already read
in `docs/mechanics/ENCOUNTER_DESIGN.md:336-361` and re-confirmed here by entry and class name:
`callbacks/battle_fainted/pokemon_alpha_drops.molang` (tiered `loot_table/alpha/*` at level 31/51/66, plus type
rewards), `entity/pokemon/ai/sensors/AlphaLevelMatchingSensor` (re-levels the alpha to the nearest player's highest
party level +4/+8/+12/+16/+20, max 100, whenever a player is within 32 and it is not battling), `moveset_builders/alpha.json`
(offensive and TM moves in its slots), a "Wild Alpha" battle rule (`BattleRules.class`, `BattleBuilder.class`; what
it does in Showdown was NOT found by string search), the `start_alphaboost` action effect, alpha eyes and scale.
The owner kept the level matching (2026-10-05).

**For a legendary boss the alpha flag is a trap at cap 60.** Level matching lifts it above the party, and
`cobblers_levelcap`'s catch block makes anything over the cap break free (`docs/mechanics/LEAGUE_LEVEL_CAP.md:112`).
A party at 60 meets an alpha Entei at 76: uncatchable until the Champion falls. After Blue (cap 100) it only clamps
at 100. Use an explicit level instead, or `alpha=true` only on an `uncatchable` re-fight.

## 3. The Hoopa cradle: how "only the owner's ball holds" (repository, `tools/hoopa_cradle.py`, `data/hoopa_cradle.json`)

A 20-tick keeper function finds each player with the gate advancement and without the `caught` advancement standing
near the spot, gives them a number (`hp.id`), and if they have no live Hoopa spawns one through a macro
(`$spawnpokemonat $(x) $(y) $(z) $(species) $(props)`, EXP-046), then, as the new entity, tags it, writes the owner's
number to its `hp.own` score and sets `PersistenceRequired`. A lost one returns 1,200 ticks after it is first missed.
The ownership check is a MoLang callback in `data/cobblemon/callbacks/poke_ball_capture_calculated/`: if the struck
Pokemon has the cradle tag and the thrower is a player, it tags the Pokemon, runs `ball_check` as the thrower
(compare `hp.own` with the thrower's `hp.id`, plus the gate and not-caught advancements), and on refusal calls
`q.set_shakes(0)`, so the ball breaks free. A `pokemon_captured` callback grants the `caught` advancement for a catch
within `catch_radius`. Anyone may still battle it; only the catch is per player. **Built, never run**
(`runtime_checks` all open; the `q.pokemon.add_tag` it rests on is unproven, and its fallback is looser, never
stricter). A per-player Entei reuses this unchanged with species, spot, gate and caught advancement swapped, then a
second mode that spawns with `uncatchable` for repeat fights.

## 4. Entei as a boss (learnset VERIFIED from `data/cobblemon/species/generation2/entei.json`; the sets are suggestions)

Level-up: 1 leer, ember, firespin, stomp, **sacredfire**, **extremespeed**, smokescreen; 6 flamewheel; 12 bite;
18 calmmind; 24 roar; 30 firefang; 36 scaryface; 42 **crunch**; 48 extrasensory; 54 lavaplume; 60 swagger;
66 sunnyday; 72 fireblast; 78 eruption. TM/tutor include **flareblitz**, **stoneedge**, **stompingtantrum**,
ironhead, willowisp, flamethrower, overheat, shadowball, scorchingsands, bulldoze. Base experience 290, slow growth,
EV yield 1 HP / 2 Atk, egg group undiscovered. MSD and DP additions change scale, hitbox, riding and behaviour, not
moves (keys read).

| Phase | Suggested properties | Why |
|---|---|---|
| **Catch, cap 60** (after gym 8, before Blue) | `entei level=60 min_perfect_ivs=3 nature=adamant moves=sacredfire,extremespeed,crunch,stompingtantrum held_item=cobblemon:sitrus_berry` | 60 is the highest level the catch block lets a 60-cap player hold. No `alpha` (it would re-level to 76). Three of four moves are level-up; Stomping Tantrum is a TM move (ASSUMED `moves=` accepts it) |
| **Post-Champion, cap 100** | `entei level=100 min_perfect_ivs=6 nature=adamant ability=innerfocus attack_ev=252 speed_ev=252 moves=sacredfire,extremespeed,stoneedge,crunch held_item=cobblemon:life_orb` | Sacred Fire burns 50% of the time; Extreme Speed has priority; Stone Edge and Crunch cover Water/Rock/Ground and Psychic/Ghost. Item ids exist as `assets/cobblemon/models/item/*.json` (`life_orb`, `sitrus_berry`, `leftovers`, `assault_vest`, `choice_band`) |
| **Repeat fight, cap 100** | as above plus `uncatchable` (and `alpha=true` for the alpha drop tables, harmless at 100) | the gulch-mine Mega pattern |

**Difficulty is the open problem, not tooling.** One level-100 Entei against six level-100 Pokemon loses fast; the
property set has no HP multiplier. Whatever makes it a boss (double battles, an NPC escort, a forced weather) is
design work and an experiment, not a key.

## Not verified

- Every "renders" cell: file presence only; not seen in game, and players' RP files are assumed equal to this profile's.
- That COBBLEVERSE-DP-v31 is enabled in the staging world (relayed); Entei, Raikou, Suicune and Heatran do not
  depend on it (MSD implements them), Jirachi, Cresselia and Celebi do.
- What the "Wild Alpha" battle rule and `start_alphaboost` do in a battle.
- Whether `scale_modifier` changes stats; whether `moves=` enforces the learnset.
- The Hoopa cradle's callbacks (`add_tag` on a Pokemon from MoLang, `set_shakes(0)`): built, never run.
