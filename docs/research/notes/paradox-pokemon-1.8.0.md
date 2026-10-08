# Paradox Pokemon on this server: models, routes, balance (research, 2026-10-08)

**Research only. Nothing is built and no data changed.** I read these with Python zipfile and `javap`:
- the Cobblemon jar in the offline snapshot (`cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar`, "the jar");
- the snapshot's `mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar` ("MSD");
- the snapshot's `datapacks/COBBLEVERSE-DP-v31.zip` ("DP");
- every zip in `COBBLEVERSE/resourcepacks/`.

The fights were run with `tools/battle_sim.py`'s own `Mon`, `build_leader` and `duel`, from a scratch script that
wrote nothing. No world or server was touched. Nothing here has been seen in game.

## The short answer

**Flutter Mane and Iron Valiant have no usable model today, but they are not unmodelled.** They are in exactly the
same position as our 11 dolls:
- their only model is in `ATMxMSD RP.zip`;
- that pack sits in the instance's `resourcepacks/`, but our overlay disables it: it is in the base pack's
  `default_packs` (`base-pack/cobbleverse/config/resourcepackoverrides.json:33`) and missing from ours
  (`modpack/config/resourcepackoverrides.json:4-48`);
- the AllTheMons subset pack is built but not delivered, and it already carries both
  (`modpack/manifest/client-pack-atm-subset.json:14`, `:28`). Its ADR is ADR-006, Proposed.

So the work does not stop here, but every route below waits on the same delivery decision as the 11
(`docs/STATE.md:301-304`). **Seven of the 22 are usable today:**
- Walking Wake and Iron Leaves;
- Iron Hands, Iron Jugulis and Iron Boulder;
- Koraidon and Miraidon.

## 1. Models and species data (VERIFIED, the archives above)

A species counts as usable only if it has species data with `implemented`, plus a resolver and model in a pack the
client loads.

Notes on the table:
- In the jar, all 22 species files are in `data/cobblemon/species/generation9/` with labels `gen9, paradox`. The
  exceptions are Koraidon and Miraidon, labelled `gen9, legendary, restricted`.
- Every one has `evolutions: []` and no `preEvolution`.
- Abilities: Protosynthesis for the ancient ones, Quark Drive for the future ones, Orichalcum Pulse and Hadron
  Engine for the two legendaries.
- "DP" in the "implemented by" column means the DP's `data/cobblemon/species_additions/<name>.json` sets
  `implemented: true`.

| Species | BST | implemented by | model + resolver (installed, enabled) | usable | inherited wild spawn (DP `spawn_pool_world`) |
|---|---|---|---|---|---|
| Great Tusk | 570 | DP | ATMxMSD only (disabled) | **no** | rare 40-65, `is_arid`, sky |
| Scream Tail | 570 | DP | resolver ATMxMSD only; COBBLEVERSE RP ships the model but no resolver | **no** | rare 40-65, `is_floral`, rain |
| Brute Bonnet | 570 | DP | ATMxMSD only | **no** | rare 45-60, `is_jungle` |
| **Flutter Mane** | 570 | DP | ATMxMSD only | **no** | rare 45-60, `#cobblemon:is_spooky`, `deep_dark` |
| Slither Wing | 570 | DP | ATMxMSD only | **no** | ultra-rare 47-62 `is_jungle`; rare 66-76 crimson forest |
| Sandy Shocks | 570 | DP | ATMxMSD only | **no** | rare 60-70, `is_arid` |
| Roaring Moon | 590 | DP | ATMxMSD only | **no** | rare 55-70, `is_mountain`, night |
| **Walking Wake** | 590 | the jar | the jar (`resolvers/1009_walkingwake/`) | **yes** | ultra-rare 60-75, `is_mountain`, rain |
| Gouging Fire | 590 | DP | ATMxMSD only | **no** | ultra-rare 70-75, basalt deltas |
| Raging Bolt | 590 | DP | ATMxMSD only | **no** | ultra-rare 60-75, `is_arid` |
| Iron Treads | 570 | DP | ATMxMSD only | **no** | rare 50-70, arid/mountain |
| Iron Bundle | 570 | DP | ATMxMSD only | **no** | rare 50-70, freezing/glacial/tundra |
| **Iron Hands** | 570 | DP | `PlanetaCobblemon RP.zip` (`bedrock/species/0992_ironhands/`) | **yes** | rare 45-60, desert, night |
| **Iron Jugulis** | 570 | DP | PlanetaCobblemon RP | **yes** | rare 70-75, `is_mountain`, night |
| Iron Moth | 570 | DP | ATMxMSD only | **no** | rare 40-65, `is_hills`, day |
| Iron Thorns | 570 | DP | ATMxMSD only | **no** | rare 40-65, `is_mountain` |
| **Iron Valiant** | 590 | DP | ATMxMSD only | **no** | rare 55-70, `is_plains`, thundering |
| **Iron Leaves** | 590 | the jar | the jar (`resolvers/1010_ironleaves/`) | **yes** | ultra-rare 50-75, `is_forest`, night |
| **Iron Boulder** | 590 | DP | PlanetaCobblemon RP | **yes** | ultra-rare 45-60, dark forest, night |
| Iron Crown | 590 | DP | resolver ATMxMSD only; COBBLEVERSE RP model, no resolver | **no** | ultra-rare 50-75, `is_lush`, night |
| **Koraidon** | 670 | DP and MSD | MSD (`resolvers/1007_koraidon/`) | **yes** | ultra-rare 40, beach |
| **Miraidon** | 670 | DP and MSD | MSD | **yes** | ultra-rare 40, beach |

- **The 15 ATMxMSD-only species are all in the built subset pack**
  (`modpack/manifest/client-pack-atm-subset.json:6-50`). They are among its 43 species, which agrees with
  `docs/STATE.md:300-301`.
- **A correction to `docs/research/notes/legendary-species-1.8.0.md:78`.** It says every paradox but Walking Wake and
  Iron Leaves is a doll. Iron Hands, Iron Jugulis and Iron Boulder are not:
  - PlanetaCobblemon RP (enabled, `resourcepackoverrides.json:36`) ships their resolvers under the old
    `bedrock/species/` path;
  - Cobblemon 1.8.0 still loads that path. The string `bedrock/species` is in
    `client/render/models/blockbench/repository/VaryingModelRepository.class`, and `tools/client_model_fix.py:78`
    lists the folder;
  - the model scan did not flag the three (`docs/research/CLIENT_MODEL_FIXES.md`), and v4.0 is said to
    *mis-texture* Iron Hands (`:307`), which implies it renders now.
- **Uninstalled archives with models we do not ship.** Each "z DO NOT ENABLE z" archive repeats its pack's models,
  so the ones that matter are those whose base pack lacks the model:
  - `[LackingMons - Credits Only]` has Flutter Mane and Iron Valiant (the installed `LackingMons RP.zip` has neither);
  - `[MissingMons - Credits Only]` has Scream Tail, Flutter Mane and Iron Crown;
  - `[PlanetaCobblemon - Credits Only]` adds Roaring Moon, Iron Treads and Iron Crown beyond the installed pack's
    three.

  None is a second route: they are "credits only" and not enabled.
- **MSD also crafts Booster Energy** (`data/mega_showdown/recipe/booster_energy.json`: copper and iron ingots around
  an echo shard). That is the held item that turns Protosynthesis and Quark Drive on with no sun or terrain.
- **The DP also makes all 22 raid bosses** (`data/cobblemonraiddens/raid/boss/*.json`; Flutter Mane is
  `TIER_SIX`, Psyshock, Power Gem, Mystical Fire, Shadow Ball). Raid Dens is removed
  (`docs/research/COBBLEVERSE_COMPATIBILITY.md:53`), so these files do nothing.

**A finding outside the question: the paradoxes already spawn wild, as dolls.**
- The DP's spawn files are live wherever the bounded suppression does not reach: `retain_defaults` keeps
  "off-route wilderness" (`data/spawn_suppression.json:38`), and the live world has no suppression at all
  (`docs/STATE.md:361`).
- The Wedge is painted `minecraft:dark_forest` (`data/regions.json`, `regions[13]`), and that biome is in
  `#cobblemon:is_spooky`. So a Flutter Mane at 45-60 (rare) and an Iron Boulder (ultra-rare, night) can appear in
  the Wedge's unsuppressed parts. On clients without ATMxMSD, the Flutter Mane is a green doll.
- Our own encounter rules exclude paradoxes from our pools (`data/encounter_design.json:71`) and forbid dolls
  (`docs/mechanics/ENCOUNTER_DESIGN.md:207`). Neither rule reaches inherited files.
- In the DP's Flutter Mane file, `timeRange: night` sits outside its `condition`. Whether 1.8 honours it there was
  not read.

ASSUMED, not observed: that this happens in our world.

## 2. Can a Mismagius become a Flutter Mane? The mechanism (VERIFIED in bytecode, the jar)

**Yes. Nothing in an evolution ties its result to a related species.**
- The evolution's `result` is a `PokemonProperties`, a properties string
  (`api/pokemon/evolution/Evolution.class`: `getResult()`).
- `evolutionMethod` clones the Pokemon for the "before" copy, then calls `getResult().apply(pokemon)` on the
  evolving Pokemon itself (`Evolution.kt:200-204` by the class's LineNumberTable).
- `apply` sets the species through `Pokemon.setSpecies` (`Pokemon.kt:184`ff). That method:
  - writes the `species` field and clears the evolution controller;
  - then calls `updateAspects`, `updateForm`, `checkGender`, `updateHP` and `attemptAbilityUpdate`, and sends a
    `SpeciesUpdatePacket`;
  - **touches no level, IV, EV, nature, shiny, friendship or original-trainer field**.

**What carries over:**

| | Status |
|---|---|
| Level, IVs, EVs, nature, shininess, OT | **Kept**. VERIFIED: `setSpecies` writes none of them |
| Moves | Kept. The evolution adds its `learnableMoves`, and the benched/relearnable list is recomputed (`Evolution.kt:200-204`) |
| Ability | Re-mapped by `attemptAbilityUpdate`: Levitate becomes Protosynthesis. The slot mapping was NOT read |
| Gender | `checkGender` runs. Flutter Mane is genderless (`maleRatio` -1), so a male or female Mismagius should become genderless. ASSUMED from the method name |
| HP | Rescaled as a ratio (`updateHP(float)`) |

**How it would be written.** The data form already in the repo:
- `data/mythical_starters.json:288-303`: `"variant": "item_interact"`, `"result": "urshifu ..."`,
  `"requiredContext": "cobblemon:scroll_of_darkness"`, `requirements: [{variant: level, minLevel: 45}]`;
- emitted as `species_additions` by `tools/mythical_starters.py`.

For Mismagius it would be one `species_additions` file targeting `cobblemon:mismagius`, carrying one evolution with
`"result": "fluttermane"`. Two RELAYED points from `tools/mythical_starters.py:17-20`: our namespace never collides
with the DP's, and `evolutions` **append**.

**What can gate it** (VERIFIED: classes exist in `com/cobblemon/mod/common/pokemon/requirements/`):
- `requiredContext` is a vanilla `ItemPredicate` (`ItemInteractionEvolution.requiredContext: class_2073`), so in
  principle a key can be matched by its data components and not only by its id. How the adapter parses an object
  form was NOT read; the repo only uses the string form.
- Requirements include `AdvancementRequirement`, `AreaRequirement`, `StructureRequirement`, `BiomeRequirement`,
  `MoonPhaseRequirement`, `TimeRangeRequirement`, `LevelRequirement` and `PartyMemberRequirement`. So "level 60+,
  holding the champion's advancement, inside one place, at night" can all be stated as data. The JSON variant names
  are ASSUMED to be the class names lower-cased (the repo uses `level` and `time_range`).

**Unproven.** No one has run an evolution to an unrelated species in game. The same applies to the Pokedex and
summary UI showing a Flutter Mane with no `preEvolution` that came from a Mismagius. One staging experiment settles
both.

## 3. Four routes

Costs are in the repo's measured terms (CLAUDE.md "What a builder actually costs", relayed): a narrow follow-up is
about 2.6M, an end-to-end builder 3.4-4.6M, an independent audit about 3M. **Every route also needs the model
delivery first** (ADR-006 subset pack or ATM v4.0). That is the owner's decision plus a main-session install and an
in-game look; it is not costed here.

**A. Conversion from the counterpart (the owner's instinct).**

*How it works.* A Mismagius at level 60 or more, holding the gate advancement, has the key used on it at a
time-themed place. It becomes Flutter Mane (an `item_interact` evolution, section 2).

*Cost.* About 2.6M for the data, a small generator and the key's source, plus about 3M for the audit and tests:
**about 5.6M**. Add one staging experiment (main session) proving the cross-species step and what carries over.

*Effect on the game.*
- **It does not cheapen Mismagius if the key is one per player.** The player spends a Mismagius they chose, with
  its nature, IVs and shininess, so a good Mismagius becomes worth more. If the key is repeatable, every Mismagius
  is a Flutter Mane in waiting, and Mismagius stops being a final anyone keeps.
- Mismagius is easy to reach: it is wild in three sub-region rosters, the Wedge north at 33-43 among them
  (`data/spawns.json:44271`, `:39141`, `:54465`). So the key, not the Mismagius, is what holds the gate.
- **The fiction is ours.** The games show Flutter Mane resembling Misdreavus and Mismagius; they do not make it an
  ancestor (general knowledge, not in the jar).
- It is the only route that grows into a set. One evolution row per counterpart (ASSUMED pairings from the games'
  designs):
  - Donphan: Great Tusk and Iron Treads (a past key and a future key);
  - Volcarona: Slither Wing and Iron Moth;
  - Gardevoir or Gallade: Iron Valiant;
  - Salamence: Roaring Moon;
  - Tyranitar: Iron Thorns;
  - Hariyama: Iron Hands;
  - Hydreigon: Iron Jugulis;
  - Amoonguss: Brute Bonnet;
  - Jigglypuff's line: Scream Tail;
  - Magneton: Sandy Shocks;
  - Delibird: Iron Bundle.

  The six paradoxes whose counterparts are legendaries (Walking Wake, Gouging Fire, Raging Bolt, Iron Leaves,
  Iron Boulder, Iron Crown) should not convert: that would consume a boss prize.

**B. Dungeon or boss reward.**

*How it works.* Flutter Mane is a boss. It is caught once, then the room pays items: the Entei pattern
(`data/entei_boss.json`, "catch" keyed on the capture). Its homes by theme in `docs/mechanics/DUNGEONS.md:224-232`:
- dungeon 2, "The Street That Ends at Nothing", where time has slipped (psychic, fairy and ghost gems, `:270`);
- dungeon 3, "Under the Patriarch", in the dark-forest Wedge.

Either would hold it in band 5 or 6 (cap 60 or postgame, `:297-298`).

*Cost.*
- As a standalone room cloned from `tools/entei_boss.py`: a builder at 3.4-4.6M plus a 3M audit, **about 7M**.
- As a boss-pool entry once the dungeon engine exists: **about 2.6M**. But the engine is not built; The Night Shift
  comes first (`DUNGEONS.md:341`).

*Effect on the game.* It is earned by a fight, gives every player their own copy, and gives a dungeon a reason to
be cleared. It is the slowest route to reach players.

**C. A rare spawn at one place.**

*How it works.* A placement site (`data/spawns.json` `placement_sites`, as Poipole was done at the two towers:
`dusk_tower`, the last entry) or an encounter heart, at a fixed level, maybe at night.

*Cost.* About 2.6M plus an audit of about 3M, **about 5.6M**. That includes the decision on the inherited DP
paradox spawns, which should be switched off whatever route is chosen (section 1).

*Effect on the game.*
- It is found by exploring, but by luck: in co-op one player finds it and another never does.
- A spawn needs an exception to our own rule excluding paradoxes from pools (`encounter_design.json:71`).
- The level-cap catch block makes anything over a player's cap break free (`docs/mechanics/LEAGUE_LEVEL_CAP.md`).
  So the spawn level is effectively the gate, and in the Wedge's tier (33-43) it would arrive at gym 6. Section 4
  says that is early.

**D. Something else: fossil revival.**

*How it works.* An ancient paradox revived like a fossil. VERIFIED format: the jar ships 16
`data/cobblemon/fossils/*.json` files. The DP adds Mewtwo, Genesect and Type: Null this way:
`{"result": "mewtwo min_perfect_ivs=2 aspect=legendary", "fossils": ["lumymon:ancient_dna", "lumymon:cloning_catalyst"]}`.
So a fossils file can revive any species from any listed items.

Gaps:
- The machine's tag (`data/cobblemon/tags/item/fossils.json`) lists only Cobblemon's fossils, and the DP does not
  extend it. Whether the machine accepts a non-tagged item was NOT read; it can be added to the tag regardless.
- The fossil machine is crafting-only today (`docs/mechanics/ITEM_ROUTES.md:202`).

*Cost.* About 2.6M plus 3M, **about 5.6M**.

*Effect on the game.* It fits the ancient half well ("Area Zero is the past") and the future half poorly. It also
competes with Mewtwo's fossil route.

A trade with an NPC is not offered: our dialogue can take an item from the main hand, not a Pokemon
(`tools/compile_dialogue.py:196-197`, relayed via `data/entei_boss.json`).

## 4. Balance (MEASURED, battle_sim; 1v1 from full health, IVs 15, EVs 0, no items, no switching)

The table shows wins against each leader team at its cap (gyms 20-55 at relative cap 0), the Elite Four at 60 and
Blue at 62 (`LEAGUE_LEVEL_CAP.md` section 2). Flutter Mane's sets:
- "level-up" is `choose_moveset`: Shadow Ball, Dazzling Gleam, Power Gem and Mystical Fire;
- "TM" is Shadow Ball, Dazzling Gleam, Mystical Fire and Thunderbolt.

The comparators are the starters' **native** finals on their own level-up moves. They are not the starter record's
authored pools (those are in `docs/research/notes/larvesta-starter-1.8.0.md` section 5).

| | g1 | g2 | g3 | g4 | g5 | g6 | g7 | g8 | E4 (of 24) | Blue | from 45 (gyms, of 16) | League (of 30) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Flutter Mane, TM** | 3/3 | 3/3 | 4/4 | 4/4 | 5/5 | 4/5 | 4/5 | 3/6 | 17 | 4 | **11** | **21** |
| Flutter Mane, level-up | 3/3 | 2/3 | 2/4 | 4/4 | 5/5 | 4/5 | 4/5 | 3/6 | 16 | 4 | 11 | 20 |
| Mismagius, same TM set | 3/3 | 3/3 | 3/4 | 4/4 | 4/5 | 4/5 | 3/5 | 2/6 | 12 | 3 | 9 | 15 |
| Silvally (570) | | | | | | 5/5 | 4/5 | 5/6 | 18 | 4 | 14 | 22 |
| Lunala (680) | | | | | | 4/5 | 5/5 | 5/6 | 19 | 5 | 14 | 24 |
| Solgaleo (680) | | | | | | 5/5 | 0/5 | 3/6 | 21 | 5 | 8 | 26 |
| Urshifu (550) | | | | | | 4/5 | 2/5 | 6/6 | 17 | 3 | 12 | 20 |
| Volcarona (550; fixed special set) | | | | | | 5/5 | 1/5 | 3/6 | 11 | 3 | 9 | 14 |
| Naganadel (540) | | | | | | 0/5 | 4/5 | 2/6 | 10 | 2 | 6 | 12 |
| Melmetal (600) | | | | | | 4/5 | 0/5 | 1/6 | 8 | 4 | 5 | 12 |
| Iron Valiant (590, for reference) | 2/3 | 2/3 | 2/4 | 1/4 | 5/5 | 1/5 | 1/5 | 5/6 | 18 | 3 | 7 | 21 |

Base-stat totals were verified in the jar: Flutter Mane 570, Mismagius 495, Urshifu 550, Silvally 570, Solgaleo and
Lunala 680, Melmetal 600, Naganadel 540, Volcarona 550.

What the numbers say:
- **From 45 on, Flutter Mane is a starter final, not above one.** It wins 11 of 16 gym foes and 21 of 30 at the
  League: level with Urshifu, below Silvally and Lunala, above Volcarona, Naganadel and Melmetal. 570 is the band
  our finals already live in.
- **Its danger is arriving early.** It wins **19 of 19** foes at gyms 1-5. Any route that delivers it before gym 6
  hands a player a team by itself.
- Mismagius carrying the same moves does about two thirds as well at the League (15 against 21). The conversion is
  a real upgrade, not a sidegrade.

**What the simulator cannot see, and it all points upward:**
1. Set-up. `best_action` uses a boost move only when the attacker cannot damage the target
   (`tools/battle_sim.py:560-579`). Calm Mind (TM) therefore never fires.
2. Protosynthesis is not modelled (it is not in the ability list, `:24-28`). Flutter Mane learns **Sunny Day at
   level 1** (jar `fluttermane.json` `moves`), which turns its own ability on. Booster Energy is craftable (MSD
   recipe above). That the ability adds 50% to Speed or 30% to its highest other stat is general knowledge, ASSUMED
   to be what Showdown runs.
3. Average damage rolls and no crits favour a frail attacker (55/55/55 HP, Atk and Def).

REASONED, not measured: in real play Flutter Mane sits above this table's 21, as Volcarona does for Quiver Dance.

**A simulator defect, relayed and confirmed.** `choose_moveset` ignores the physical/special split
(`tools/battle_sim.py:315-336`, first found in the Larvesta note). It does not touch Flutter Mane's rows: every move
it picked is special. It does hand Naganadel Poison Jab and Fell Stinger, so Naganadel's row is low.

## Recommendation

**Route A, gated hard, after the model delivery.**
1. **First the models.** Flutter Mane cannot appear until ATMxMSD's files reach clients: the ADR-006 subset pack
   (built, `dfdd4f81...`) or ATM v4.0. That is the same decision as the 11 dolls, and it should be made once, for
   all of them.
2. **Gate at gym 8 or the Champion, never earlier.** At cap 60 it is an Elite Four tool on a par with the starter
   finals. At cap 100 it is a postgame trophy. Before 45 it is a sweeper.
3. **One key per player.** The rite then spends a Mismagius, which answers "does it cheapen catching one": no,
   because the Mismagius becomes the price. Give the key from an existing gate now (the gym-8 or Champion
   advancement, or Entei's first catch), and move it to a dungeon first clear (B) when dungeons exist.
4. **Build it as one generic tool ("paradox rites")**, so "a few others" are rows: Iron Valiant from Gardevoir,
   Roaring Moon from Salamence and so on, with no legendary counterpart consumed.
5. **Switch off the DP's inherited paradox spawns** whatever is chosen. They are above-cap dolls in the Wedge and
   elsewhere today.

Expected spend: about 5.6M plus one staging experiment, after the model delivery.

## Open questions for the owner

1. Model delivery: the AllTheMons subset (ADR-006) or ATM v4.0? Every route waits on it.
2. Which paradoxes? Flutter Mane alone, the 14 with non-legendary counterparts, or also the seven usable today
   (Walking Wake, Iron Leaves, Iron Hands, Iron Jugulis, Iron Boulder, Koraidon, Miraidon)?
3. One per player or one per key? And is the gate gym 8 (cap 60) or the Champion (cap 100)?
4. Should a shiny Mismagius make a shiny Flutter Mane? (It will: shininess is carried.)
5. Keep MSD's Booster Energy recipe (copper, iron, echo shard)? It switches every paradox's ability on at no cost.
6. Switch off the inherited wild paradox spawns now?
