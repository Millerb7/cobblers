# Challenge mode teams: a different fight, not a bigger one

**Status: authored, not generated, not run.** The thirteen boss Challenge teams are written in
`docs/story/TRAINER_RULES.json` (`bosses[].modes.challenge`), the human-editable rule set that
`docs/story/generate_trainers.py` turns into `data/trainers.json`. `data/trainers.json` is **stale until the main
session runs the generator** (section 7). No battle was simulated and nothing was played.

The instruction (the owner, 2026-10-13, decided): *"Every challenge fight should be a good bit different from Normal."*

## 1. What Challenge was before (measured from `docs/story/TRAINER_RULES.json` at 77bf707d)

| Fight | Normal size | Old Challenge size | Normal species kept in Challenge | Ace |
|---|---:|---:|---|---|
| Brock | 3 | 6 | 3 of 3 | Onix, same moves, Weakness Policy instead of Berry Juice |
| Misty | 3 | 6 | 2 of 3 (Horsea's rain role taken by Drizzle Pelipper) | Starmie, Psybeam -> Thunderbolt |
| Lt. Surge | 4 | 6 | 4 of 4 | Raichu, identical |
| Erika | 4 | 6 | 4 of 4 | Vileplume, identical |
| Koga | 5 | 6 | 5 of 5 | Venomoth, + Quiver Dance and Focus Sash |
| Sabrina | 5 | 6 | 5 of 5 | Alakazam, + Nasty Plot and Focus Sash |
| Blaine | 5 | 6 | 5 of 5 | Charizard, same moves, Life Orb |
| Giovanni | 6 | 6 | 6 of 6 | Rhyperior, same moves, Rindo Berry |
| Lorelei, Bruno, Agatha, Lance, Blue | 6 | 6 | **6 of 6, identical** | identical |

- Gyms 1-4: the shared members were raised one or two levels inside the same cap; gyms 5-8: every member at the cap.
- The League's five Challenge teams were the Normal team under the `_challenge` identity. For Lorelei both blocks
  were read whole; for Bruno, Agatha, Lance and Blue the species, level offsets, held items, AI profile and strategy
  text were compared (grep of the file) and match, movesets were not compared line by line.
- Every old Challenge gym team's `open_line` was its Normal answer: Koga's six were exactly Normal's
  `availability_contract.answers`. **The premise held: Challenge was Normal plus members, items and levels, and the
  Normal answer still won every fight.**
- Route trainers (Routes 1-8, 41 records): rule-level only. One extra member for the `gym_prep`/`strategist` roles,
  a held item on the last member, the `route_challenge` AI. Same species and moves otherwise.
- Victory Road (10) and gym juniors (26): explicit Challenge teams (the generator requires a junior's Challenge to add
  exactly one member). Not compared member by member in this unit.

The old gym teams are kept in place under `modes.superseded_challenge` with a note. Nothing reads that key:
`build_boss_mode` reads `modes.<mode>` only, and no tool or test iterates `modes` in the rules file (grep of
`tools/` and `tests/`).

## 2. The principle

1. **Same cap, same level budget, different question.** Every member keeps the level offset of its slot in the old
   Challenge team, slot by slot, so the ace is at `ace_level` (generator, `tools/challenge_mode.py` and
   `tests/test_trainer_modes.py` all hold that) and each team's level sum is unchanged, in the same order. The income
   model's battle payout depends only on that sum (`tools/income_model.py` `kotlin_b`), so `data/markets.json`
   `income_basis` and the voucher (`tools/challenge_voucher.py`) are not moved by this change.
2. **Different from Normal is measured three ways**: at most one Normal species per gym (zero for Erika, Koga and
   Giovanni), a different lead, and a different engine (weather, terrain, hazards, screens, Trick Room or none),
   chosen so that **Normal's answer is punished** by at least two members.
3. **A different answer, available by then.** Each team names an `open_line` of six species a player can hold at
   that point, checked against the tables in section 5. At least two independent lines per fight.
4. Theme kept: every member is the leader's type or a dual type containing it, except Brock's Hippopotas (Ground,
   the gym's "Fault Line") and Erika's Ludicolo (Grass/Water).

## 3. The thirteen fights

Levels are `ace_level + level_offset` as authored. "Punishes" is what the member does to Normal's answer.

### Gym 1 Brock (cap 20): Sandstone Bastion
Hippopotas 19 (Sand Stream, Smooth Rock) / Lileep 19 (Storm Drain) / Carkol 19 (Flame Body) / Dwebble 19 (Sturdy,
Shell Smash, White Herb) / Nosepass 20 (Sturdy, Thunder Wave) / **Onix 20** (Sturdy, Rock Polish, Weakness Policy).
- Normal's answer, special Water and Grass, is punished three ways: eight turns of sand add half to every Rock
  member's Special Defense; Storm Drain absorbs Water; Carkol takes Grass neutrally and burns contact.
- Answer: physical, multi-hit and status. Machop and Pawmo (Low Kick, Arm Thrust), Diggersby (Ground, four times
  over on Carkol), Azumarill (physical Water), Krabby (Metal Claw is Steel), Mareep (Thunder Wave).
- Shared with Normal: Onix only (different set and role).

### Gym 2 Misty (cap 25): Undertow
Slowpoke 23 (Regenerator, Yawn) / Tentacool 24 (Liquid Ooze, Toxic Spikes) / Goldeen 24 (Lightning Rod, Drill Run)
/ Shellder 24 (Skill Link Icicle Spear) / Azumarill 25 (Huge Power, Aqua Jet) / **Starmie 25** (Scald, Thunder Wave,
Recover).
- Normal is a rain speed race. Challenge has no weather: it is attrition. Electric is absorbed by Goldeen, which
  Drill Runs Electric types. Draining Grass is hurt by Liquid Ooze. Grass is shredded by Shellder. Scald burns
  physical answers.
- Answer: split Electric (Luxio, Kilowattrel), non-draining Grass (Bayleef's Razor Leaf), Dark for the two Psychic
  types (Nuzleaf), Ground for Tentacool (Diggersby), Pawmo.
- Shared with Normal: Starmie only.

### Gym 3 Lt. Surge (cap 30): Live Wire
Kilowattrel 28 (Volt Absorb, Volt Switch) / Lanturn 28 (Volt Absorb, Scald) / Emolga 29 (Motor Drive, Acrobatics,
no item on purpose) / Vikavolt 29 (Levitate, Energy Ball) / Raichu 30 (Lightning Rod, Grass Knot, Surf, Focus Sash) /
**Pawmot 30** (Iron Fist, Mach Punch, Ice Punch).
- Normal's answer is Ground. Three members are immune to it. The three grounded ones punish a Ground switch-in with
  Scald, Grass Knot, Surf and Ice Punch.
- Answer: Rock for the fliers and Ground only for the grounded. Rhyhorn (Ground/Rock: Electric-immune, with the badge-1
  Rock Slide TM), Lycanroc, Thick Fat Hariyama (halves Ice Punch), Quagsire (Water Absorb walls Lanturn), Dugtrio
  (Arena Trap holds the grounded three), Pachirisu (Volt Absorb).
- Shared with Normal: Raichu (not the ace, different set).

### Gym 4 Erika (cap 35): Rain Garden
Whimsicott 33 (Prankster Rain Dance and Tailwind, Damp Rock, Encore) / Ferroseed 34 (Iron Barbs, Gyro Ball) /
Breloom 34 (Technician, Mach Punch, Focus Sash) / Cradily 34 (Rock Slide) / Lurantis 35 (Contrary Superpower) /
**Ludicolo 35** (Swift Swim, Life Orb, Hydro Pump, Ice Beam).
- Normal is sun, and Fire is its answer. Challenge sets rain, which halves Fire. Ludicolo takes Fire and Ice
  neutrally and hits Fire with Hydro Pump. Gyro Ball and Mach Punch punish Ice. Rock Slide punishes Flying and Fire.
- Answer: Poison (Tentacruel; Skuntank hits Whimsicott four times over), Flying that survives Ice Beam (Staraptor,
  Noctowl), Bug (Scyther), and Dark types, which Prankster cannot touch (Houndoom, Skuntank).
- Shared with Normal: none.

### Gym 5 Koga (cap 40): Ambush
Ariados (Toxic Spikes, Focus Sash) / Skuntank (Sucker Punch, Black Glasses) / Tentacruel (Liquid Ooze, Scald,
Rapid Spin) / Roserade (Giga Drain, Shadow Ball) / Toxicroak (Dry Skin, Sucker Punch, Swords Dance) / **Glimmora**
(Toxic Debris, Focus Sash, Energy Ball, Earth Power). All at 40.
- Normal's answers are Ground and Psychic. Skuntank is immune to Psychic and Sucker Punches it. Roserade, Tentacruel
  and Glimmora hit Ground with Grass and Water. Toxicroak drinks Water.
- Answer: Steel, which is immune to the poison: Bronzong (Levitate, so Earth Power misses too), Excadrill, Empoleon.
  Then Xatu, Medicham and Delphox for the Psychic line.
- Shared with Normal: none.

### Gym 6 Sabrina (cap 45): Mind Field
Indeedee (Psychic Surge, Terrain Extender, Expanding Force) / Gallade (Sharpness, Close Combat) / Gardevoir (Trace,
Moonblast) / Reuniclus (Magic Guard, Focus Blast) / Espeon (Magic Bounce) / **Alakazam** (Magic Guard, Focus Sash,
Nasty Plot, Focus Blast, Dazzling Gleam). All at 45.
- Normal is Trick Room, answered with Dark and priority. Challenge lays Psychic Terrain for eight turns, so priority
  fails against the grounded team. Gallade and Gardevoir resist Dark and punish it; Focus Blast and Dazzling Gleam
  hit the Dark types; Magic Bounce reflects status.
- Answer: Ghost (Banette), Poison for the two Fairy and Fighting halves (Scolipede, Skuntank), Bug (Pinsir), and
  Dark (Houndoom, Absol) once the terrain runs out.
- Shared with Normal: Alakazam (different set).

### Gym 7 Blaine (cap 50): Wildfire
Talonflame (Gale Wings, Tailwind, Will-O-Wisp, Heavy-Duty Boots) / Chandelure (Energy Ball) / Scovillain (Grass/Fire)
/ Infernape (Grass Knot, Mach Punch, Focus Sash) / Charizard (Dragon Dance, Earthquake, Lum Berry) / **Volcarona**
(Quiver Dance, Giga Drain). All at 50.
- Normal is sun, with Water as the answer. Challenge has no sun. Tailwind outspeeds the Water answer; Energy Ball,
  Scovillain, Grass Knot and Giga Drain hit it; Will-O-Wisp burns the physical one.
- Answer: Rock, which the team cannot cover. Stealth Rock (badge-6 TM) takes half of Volcarona's and Charizard's
  health; Rhydon, Lycanroc, Coalossal. Gyarados (Grass only neutral, Intimidate), Flygon and Crawdaunt help.
- Shared with Normal: Charizard (not the ace, different set).

### Gym 8 Giovanni (cap 55): Grand Strategy
Claydol (Levitate, Stealth Rock, Ice Beam, Mental Herb) / Gastrodon (Storm Drain) / Gliscor (Poison Heal, Toxic
Orb) / Donphan (Ice Shard, Gunk Shot) / Excadrill (Mold Breaker) / **Garchomp** (Rough Skin, Focus Sash, Swords
Dance). All at 55.
- Normal is sand, with Water and Grass as the answer. Challenge has no sand. Storm Drain eats Water; Gliscor and
  Garchomp take Grass neutrally; Ice Beam and Ice Shard hit Grass; Mold Breaker Earthquake goes through Levitate.
- Answer: Ice (Abomasnow, Avalugg; Ice Beam is a badge-6 TM), Fairy (Tinkaton, Gardevoir), Gyarados (Intimidate,
  Ground-immune), and Swampert for Excadrill. The player's own Stealth Rock breaks Garchomp's sash.
- Shared with Normal: none.

### Lorelei (ace 60): Snow Fortress
Abomasnow 57 (Snow Warning, Aurora Veil, Light Clay) / Cloyster 58 (Shell Smash, Rock Blast) / Crabominable 58
(Iron Fist, Assault Vest) / Frosmoth 59 (Ice Scales, Quiver Dance) / Cetitan 59 (Slush Rush, Belly Drum) /
**Lapras 60** (Weakness Policy, Heal Bell).
- Normal's answers are Fire, Fighting, Rock and Steel. Veil halves every hit for eight turns. Rock Blast hits Fire,
  Drain Punch and Earthquake hit Steel, and Ice Scales halves special Fire.
- Answer: stop or break the Veil (Taunt, a fast KO on Abomasnow, Brick Break, Infiltrator Chandelure), Thick Fat
  Hariyama, Excadrill, priority for Cetitan, Coalossal, Empoleon, Toxicroak.
- Shared with Normal: Lapras.

### Bruno (ace 60): Iron Discipline
Scrafty 57 / Hitmonchan 58 (Punching Glove) / Medicham 58 (Pure Power, Bullet Punch, Poison Jab) / Quaquaval 59
(Aqua Step) / Conkeldurr 59 (Stone Edge, Knock Off) / **Annihilape 60** (Defiant, Rage Fist, Bulk Up).
- Normal's answers are Flying, Psychic, Fairy, burn and physical walls. Every member covers one of them, and Defiant
  turns Intimidate into a boost.
- Answer: Tinkaton (resists Bullet Punch, immune to Poison Jab), Gardevoir, Talonflame, Banette (immune to Fighting),
  Bronzong, Staraptor.
- Shared with Normal: none.

### Agatha (ace 60): The Slow Haunting
Cofagrigus 57 (Trick Room, Mental Herb) / Sableye 58 (Prankster) / Mimikyu 58 / Trevenant 59 (second Trick Room) /
Jellicent 59 / **Golurk 60** (No Guard Dynamic Punch, Assault Vest).
- Normal's answers are Dark, Ghost and priority. Under Trick Room the slow hitters move first. Dynamic Punch and Play
  Rough punish Dark.
- Answer: run out or reverse the five turns. Then slow Steel and Dark (Kingambit, Bronzong, Rhydon), Tinkaton for
  Mimikyu, Houndoom and Chandelure.
- Shared with Normal: none (Gengar is gone).

### Lance (ace 60): Dragon's Armour
Duraludon 57 (Stealth Rock, Thunder Wave, Focus Sash) / Tyrantrum 58 (Rock Head, Head Smash, Dragon Dance) / Kingdra
58 (Sniper, Scope Lens) / Hydreigon 59 (Choice Scarf, Flash Cannon) / Goodra 59 (Gooey, Assault Vest, Sludge Bomb) /
**Dragonite 60** (Multiscale, Heavy-Duty Boots, Roost).
- Normal's answers are Ice and Fairy. Two members take both only neutrally, three carry Steel or Poison for Fairy,
  and Boots plus Roost keep Multiscale whole.
- Answer: Fighting and Ground for the Steel and Rock dragons (Excadrill, Machamp), then Fairy and Ice (Tinkaton,
  Gardevoir, Abomasnow), Flygon. For Dragonite: phazing, Haze, Encore or Taunt.
- Shared with Normal: Dragonite.

### Champion Blue (ace 62): The counter-team
Aerodactyl 58 / Machamp 59 (No Guard) / Scizor 60 (Technician) / Magnezone 60 (Air Balloon, Sturdy) / Gengar 61
(Choice Specs) / **Tyranitar 62** (Sand Stream, Dragon Dance, Lum Berry).
- Normal's lesson (a balanced six, speed and hazard control) still applies, but every slot changes.
- Answer: Lucario, Excadrill, Chandelure (Fire for Scizor), Gyarados, Gardevoir, Kingambit.
- Shared with Normal: none.

## 4. Winnability: how it was checked, and what was not

- **Species**: `data/encounter_design.json` tables. Tier N means "on the way to gym N", per
  `docs/mechanics/ENCOUNTER_DESIGN.md` section 1. An evolved form counts if its evolution level is at or under the cap.
  Every gym `open_line` species, or its pre-evolution, is in a table of tier at or under that gym:

| Species | Where it comes from |
|---|---|
| Machop, Krabby | west_shore, tier 1 |
| Pawmi | route1_maze_forest |
| Marill | river_of_shrews_vale |
| Bunnelby, Seedot | viltri_plateau and river vale, tier 1 |
| Mareep | pallet_meadows |
| Shinx | river vale, tier 1 |
| Wattrel | west_shore, evolves at 25 |
| Chikorita | lake_viltri_hollow, tier 2 |
| Rhyhorn, Rockruff, Makuhita | mt_clay, tier 3 |
| Wooper | lake_viltri_hollow, tier 2 |
| Diglett, Pachirisu | foothill_woods, tier 3 |
| Tentacool | west_shore, evolves at 30 |
| Stunky, Houndour, Starly | north_east_downs, tier 4 |
| Hoothoot | maze forest, tier 1 |
| Scyther | foothill_woods, tier 3 |
| Bronzor, Natu, Meditite | mt_vessu, tier 3 |
| Drilbur, Fennekin | glacier_foot_fields, tier 5 |
| Piplup | lower_trough, tier 5 |
| Shuppet | fungal_south, tier 3, an island |
| Venipede | maze forest |
| Pinsir | tilpey_east_shore, tier 6 |
| Absol | tier 3 and 4, rare |
| Rolycoly | the_crags, tier 4 |
| Trapinch | east_coast_dunes, tier 7 |
| Magikarp | tier 2 |
| Corphish | tier 2 |
| Snover, Bergmite | tier 4 |
| Tinkatink | long_isle_north, tier 7, and plateau_south, tier 8 |
| Ralts | tier 1, rare |
| Mudkip | marshy_marsh, tier 5 |

  The League answers are all at or under tier 9.
- **`docs/story/AVAILABILITY.md` is stale** (measured 2026-09-23; the encounter rebuild is 2026-10-05). Its Gym-2
  list has no Ralts or Wooper, for example. It was not used as evidence. Finding:
  `python tools/availability.py --write`.
- **TMs**: the badge bands in `docs/mechanics/TM_POWER_GATE.md` section 3 and the shelf in section 4 (RELAYED, not
  re-measured). Gym N is fought with badge N-1 TMs. No answer relies on TM Mega Drain. The TMs named:
  - Rock Slide, badge 1 (Surge's Rhyhorn line)
  - Brick Break, badge 5 (Lorelei)
  - Stealth Rock and Ice Beam, badge 6 (Blaine, Giovanni)
- **Not checked**:
  - Movesets against learnsets. Trainer teams are not learnset-validated as far as the existing teams show (they
    already carry TM and egg moves); ASSUMED.
  - Damage numbers. No battle was simulated: `tools/battle_sim.py` exists, and a run over the new teams is the
    natural next check.
  - That the rctmod AI uses setup, hazards and Trick Room well (ASSUMED: rctmod's own AI profiles).

## 5. Cross-system consequences (run these; the author has no shell)

1. **The generator.** Run `python docs/story/generate_trainers.py --check-active` (it should report stale), then
   `--write-active`, then `--check-active` again.
2. **Tests.** Run `python -m pytest tests/test_trainer_modes.py tests/test_challenge_mode.py tests/test_gym_trainers.py
   tests/test_system_contracts.py -q --tb=line`.
3. **Gym arena clearance.** `tools/gym_arenas_audit.py` sizes every leader's clearance over every species in the
   record, Challenge included (its docstring, lines 25-30). `data/gym_arena_sizes.json` (`tools/pokemon_sizes.py
   --write`) lists the design species. New species that may exceed a gym's current largest model are listed below.
   If one fails, swap it for the named fallback rather than enlarge the arena.

   | Gym | Species to check | Fallback |
   |---|---|---|
   | Surge | Kilowattrel, Lanturn | Electrode with Volt Switch; Magneton |
   | Koga | Tentacruel, Glimmora | Toxapex; Skuntank's set on Muk |
   | Sabrina | Gallade, Gardevoir | Medicham; Hatterene |
   | Blaine | Volcarona, Talonflame | Magmortar as the ace; Houndoom |
   | Giovanni | Gliscor, Garchomp | Krookodile; Flygon |
4. **Income and voucher.** Unchanged by construction (section 2.1). `python tools/challenge_voucher.py --check`
   should still pass. If `income_model` reports a one-dollar drift, it is float ordering, and the order was kept
   slot for slot.
5. **Guides.** Regenerate the Challenge guide (`tools/challenge_guide.py`) and the battle guide
   (`tools/player_guide_battles.py`), which read `strategy` and `open_line`.

## 6. Generator changes needed

- **Bosses: none.** Every field used (`species`, `level_offset`, `moveset`, `ability`, `heldItem`, `nature`, `ace`,
  `ai_profile`, `strategy`, `ace_math_change`, `open_line`, `line_obviousness`) is one the generator already reads or
  copies. Emolga carries no `heldItem` (Acrobatics); `make_rct` copies the member as is.
- **Route trainers (next unit): `challenge_team_species`.** Today `build_route_mode` can add one member from a pool,
  set one held item and override movesets, but cannot change species. The proposal:
  - an optional placement field, a list of `species_kits` keys;
  - when present it replaces `selected` for the Challenge team only, before `build_route_mode` runs;
  - levels are computed exactly as Normal's;
  - the length must equal Normal's, or Normal's + 1 (`tests/test_trainer_modes.py`
    `test_route_challenge_preserves_density_and_adds_at_most_one_member`);
  - fail on an unknown kit.

  Without it, a route Challenge can differ only by moves and items, or by hand-writing both teams in `teams`.
- **Gym juniors and Victory Road: none.** Both already take explicit teams.

## 7. Not done in this unit

77 Challenge fights still play as Normal plus a member and an item:

- the 41 route trainers on Routes 1-8;
- Victory Road's 10;
- the 26 gym juniors.

Worse, the route Challenge rehearsals teach Normal's answers, which the new leaders punish. Route 3's Challenge intent
reads "without hidden Ground counters" in front of a Surge whose Challenge team is built against Ground.

A follow-up unit should re-aim each route's Challenge at its new leader, with `challenge_team_species` once built:

| Route | Leader ahead | What its Challenge should teach |
|---|---|---|
| 1 | Brock | sand and Sturdy: multi-hit and physical |
| 2 | Misty | Lightning Rod and Liquid Ooze: non-draining Grass and Ground |
| 3 | Surge | fliers and Levitate: Rock |
| 4 | Erika | rain and Prankster: Poison, Dark |
| 5 | Koga | Toxic Spikes: Steel |
| 6 | Sabrina | Psychic Terrain: Ghost and Poison |
| 7 | Blaine | Tailwind and Grass coverage: Rock and Stealth Rock |
| 8 | Giovanni | Storm Drain and Mold Breaker: Ice and Fairy |

Victory Road's examiners should preview the Challenge League: Veil, Trick Room, Steel-dragons.

## 8. Assumptions and their status

- **Items: VERIFIED as registered `cobblemon:` items** in `docs/research/ITEMS_ABILITY_EV_HELD_MEGA.md` lines
  136-138. Their battle effect is ASSUMED to follow Showdown, as that document says. The items:

  | Kind | Items |
  |---|---|
  | Weather, terrain, screens | `smooth_rock`, `damp_rock`, `light_clay`, `terrain_extender` |
  | Herbs and orbs | `white_herb`, `mental_herb`, `toxic_orb`, `air_balloon` |
  | Boosters and lenses | `punching_glove`, `scope_lens`, `wise_glasses`, `black_glasses` |
  | Choice items and sash | `choice_specs`, `choice_scarf`, `focus_sash` |
  | Others | `heavy_duty_boots`, `assault_vest`, `life_orb`, `leftovers`, `eviolite`, `expert_belt`, `rocky_helmet`, `weakness_policy`, `black_sludge` |
  | Berries | `sitrus_berry`, `lum_berry` (already used by the existing teams) |

  No type-resist berry outside those the file already used.
- **Species implemented in the 1.8 jar: ASSUMED** for the species that appear in no spawn table here:

  | Leader | Species |
  |---|---|
  | Bruno | Conkeldurr, Annihilape |
  | Agatha | Cofagrigus, Sableye |
  | Lance | Tyrantrum, Kingdra, Hydreigon, Garchomp |
  | Lorelei | Crabominable |
  | Blaine | Scovillain |
  | Blue | Magnezone |

  Every other species spawns in `data/encounter_design.json` or is already in a team. Check with the jar before
  generating.
- **Battle mechanics through Showdown: ASSUMED.** The abilities and moves the new teams rely on:

  | Kind | Relied on |
  |---|---|
  | Abilities | Psychic Surge, Disguise, Toxic Debris, Storm Drain, Sharpness, Contrary, Defiant, Gooey, Ice Scales, Slush Rush |
  | Moves | Aurora Veil, Expanding Force, Rage Fist, Aqua Step |

  Cobblemon sends battles to Showdown. Form-change abilities (Mimikyu's Disguise) are the likeliest to differ.
- Indeedee is authored without a gender form. Both forms carry Psychic Surge; the move pool is the male form's.

## 9. Open questions for the owner

1. **Difficulty.** Several Challenge fights are now harder in kind, not only different: Erika's Swift Swim Life Orb
   Ludicolo at 35, Sabrina's terrain-powered Expanding Force, Lorelei's Veil. Playtest before tuning; the levers are
   the items (Life Orb to Sitrus, Light Clay off) and the AI profile, not the levels.
2. **Aces.** Eight aces changed species (Surge, Erika, Koga, Blaine, Giovanni, Bruno, Agatha, Blue; Brock, Misty,
   Sabrina, Lorelei and Lance keep their signature with a new set). Is a leader without a signature ace acceptable in
   Challenge?
3. **Route trainers and juniors.** Approve the `challenge_team_species` generator change and a follow-up unit for the
   77 non-boss fights?
