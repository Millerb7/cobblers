# Challenge mode's 77 non-boss fights, re-aimed at the redesigned leaders

**Status: authored, not generated, not run** (2026-10-21, worktree at 9a92ee38). Source:
`docs/story/TRAINER_RULES.json`. `data/trainers.json` is stale until the main session implements
`challenge_team_species` and runs the generator. No battle was simulated; nothing was played.

Follow-up to `CHALLENGE_MODE_TEAMS.md` sections 6-7. Counted in the rules file, not relayed: **41 route trainers**
(4+4+5+6+4+5+6+7, Routes 1-8), **10 Victory Road** examiners (`route_09_trainer_01..10`), **26 gym juniors**
(3+2+3+3+3+4+4+4). 77 confirmed.

## 1. What changed, and the rules kept

| Group | Field | Old Challenge | Now |
|---|---|---|---|
| Routes 1-8 | placement `challenge_team_species` (new, section 6 spec) | Normal's species, +1 ambient member on `gym_prep`/`strategist`, one berry | a full species list per fight, kit keys only |
| Routes 1-8 | route `challenge` | old block | new `intent`, `extra_member_roles: []`, same `held_item`; old block under route `superseded_challenge` |
| Route 5 Trail Warden | `challenge_held_item` (existing field) | sitrus | `black_sludge` |
| Victory Road | `teams.challenge` (explicit) | Normal + one item | new team; old under placement `superseded_challenge` (beside `teams`, which must hold exactly normal and challenge) |
| Gym juniors | `teams.challenge` (explicit) | Normal + one member | new team; old under `teams.superseded_challenge` (beside it, as the bosses' `modes`) |

- **Normal is untouched**: no `team_species`, `movesets`, kit or Normal team was edited. New kits were added; no
  existing kit's moves changed (routes 4-8 Normal teams read kit moves).
- **Density**: each Challenge list is Normal's length, or Normal's + 1 exactly where the old Challenge added a member
  (14 fights: R1 t4, R2 t4, R3 t4-t5, R4 t4/t6, R5 t4, R6 t4-t5, R7 t4/t6, R8 t4/t6/t7). Juniors are Normal + 1,
  Victory Road keeps its old sizes (2, and 5 for the examiner).
- **Levels**: juniors and Victory Road keep the old Challenge level vector slot by slot, item on the top member for
  juniors. Routes: see section 4.
- **Theme**: every junior member carries its gym's type (`tests/test_gym_trainers.py` jar check).
- **At most one Normal species per fight** (the bosses' rule); most share none.

## 2. Routes 1-8: the leader's Challenge answer and what each fight teaches

Levels are the generator's (route band and distance); `+` marks the added member. The ace is last.

### Route 1 to Brock (sand, Sturdy, Storm Drain; answer: multi-hit, physical, status)
| Fight | Team | Teaches |
|---|---|---|
| Trail Novice 7 | Roggenrola | Rock that takes a hit and throws sand: two hits or a Fighting move |
| Meadow Apiarist 9-10 | Combee, Dwebble | Bug/Rock Withdraw: multi-hit (Bullet Seed, Double Kick, Fury Attack) or Krabby's Metal Claw |
| Vale Naturalist 13-14 | Lotad, Wooper | Water at a quarter on Lotad: Flying/Bug for it, Grass for Wooper; Water alone stalls |
| Plateau Guide 15-17 | Hippopotas, Rolycoly, +Dwebble, Nosepass | a small Brock: Sand Stream, Rapid Spin, Thunder Wave. Machop, Pawmo, Krabby, Mareep |

### Route 2 to Misty (Lightning Rod, Liquid Ooze; answer: split Electric, non-draining Grass, Ground, Dark)
| Fight | Team | Teaches |
|---|---|---|
| Ravine Scrapper 18 | Tentacool | draining Grass meets Liquid Ooze and a Poison resist: Ground or Electric |
| Glowbug Keeper 19-20 | Illumise, Chinchou | Water/Electric takes Electric at half: Ground (Bunnelby, Wooper) |
| North Bank Angler 20-21 | Goldeen, Shellder | Drill Run for Electric, Icicle Spear for Grass: an Electric flier (Wattrel) |
| Lake Surveyor 20-22 | Slowpoke, Tentacool, +Marill, Starmie | a small Misty: Dark (Nuzleaf) for the Psychics, Ground for Tentacool, Razor Leaf |

### Route 3 to Surge (fliers, Levitate, Water/Grass coverage; answer: Rock, Ground only into the grounded)
| Fight | Team | Teaches |
|---|---|---|
| Climbing Novice 21 | Wattrel | Ground cannot touch a flier: Rock Slide (badge 1 TM), Rockruff |
| Grove Ranger 22-23 | Joltik, Emolga | Bug/Electric takes Ground neutrally; Rock hits both twice over |
| Groundkeeper 23-24 | Chinchou, Pikachu | Bubble Beam, Grass Knot, Surf punish the Ground switch-in: Makuhita, or Ground on a free turn |
| Signal Watcher 25-26 | Emolga, +Pachirisu, Kilowattrel | two fliers and Tailwind: Rock, Pachirisu's Volt Absorb |
| Vessu Ranger 25-27 | Kilowattrel, Chinchou, +Joltik, Pikachu | a small Surge: Rhyhorn, Lycanroc, Hariyama, Quagsire |

### Route 4 to Erika (rain, Prankster; answer: Poison, Dark, bulky Flying, Fighting/Fire for Steel)
| Fight | Team | Teaches |
|---|---|---|
| Snowfield Novice 26 | Cottonee | Prankster status fails on Dark; Poison hits it four times over |
| Alpine Ranger 26-27 | Lotad, Shroomish | Water/Grass shrugs Ice and Fire: Flying or Poison |
| Campfire Keeper 29-30 | Pelipper, Lombre | Rain Dance halves the Fire answer; Lombre takes Fire neutrally |
| Ridge Scout 28-30 | Cottonee, Ferroseed, +Lileep, Breloom | the engine: Iron Barbs, Steel immune to Poison, Rock for Flying, Mach Punch for Ice/Dark |
| Bird Watcher 31-32 | Lileep, Ludicolo | the Flying answer must survive Rock and Icy Wind (Staraptor, Noctowl) |
| Naturalist 31-33 | Whimsicott, Ferroseed, +Breloom, Ludicolo | a small Erika: Tentacruel, Skuntank, Houndoom, Scyther |

### Route 5 to Koga (Toxic Spikes; answer: Steel, then Psychic/Ground partners)
| Fight | Team | Teaches |
|---|---|---|
| Field Hand 32 | Skorupi | Toxic Spikes on entry: Steel and grounded Poison are immune |
| Field Medic 33-34 | Ariados, Skuntank | Skuntank blocks Psychic and Sucker Punches: Steel walls both |
| Mind Reader 34-35 | Qwilfish, Weepinbell | Water and Grass hit the Ground switch; Steel takes neither |
| Trail Warden 34-36 | Ariados, Tentacruel, +Skuntank, Toxicroak (Black Sludge) | a small Koga: Bronzong, Excadrill (Drilbur), Empoleon (Piplup), then Xatu/Medicham |

### Route 6 to Sabrina (Psychic Terrain; answer: Ghost and Poison, Dark after the terrain)
| Fight | Team | Teaches |
|---|---|---|
| Marsh Novice 37 | Kirlia | Fairy half: Dark is neutral, Poison and Ghost are super effective |
| Marsh Ranger 37-38 | Medicham, Hattrem | Fighting punishes Dark: Ghost (Banette) |
| Night Courier 39-40 | Indeedee, Gallade | Psychic Terrain stops Sucker Punch; Gallade punishes Dark |
| Lake Pathfinder 39-41 | Hattrem, Espeon, +Xatu, Reuniclus | Focus Blast for the Dark switch: Ghost, Bug (Pinsir), Poison (Scolipede) |
| Displaced Archivist 41-43 | Indeedee, Gardevoir, +Gallade, Alakazam | a small Sabrina: Banette, Skuntank, Scolipede, Houndoom late |

### Route 7 to Blaine (Tailwind, Grass coverage; answer: Rock and Stealth Rock)
| Fight | Team | Teaches |
|---|---|---|
| Expedition Novice 41 | Talonflame | Tailwind and Will-O-Wisp: Rock is four times over |
| Bridge Hand 41-42 | Lampent, Centiskorch | Energy Ball hits the Water switch; Rock hits both |
| Shore Battler 43-44 | Monferno, Rapidash | Grass Knot and Wild Charge for Water: Rock, Flygon, bulky Gyarados |
| Crater Geologist 43-45 | Fletchinder, Ninetales, +Magmar, Charizard | Tailwind lead, burn, Thunder Punch: Stealth Rock (badge 6 TM) |
| Ash-Path Ranger 46-47 | Houndoom, Magmortar | Thunder Fang and Thunderbolt for Water: Rock and Ground |
| Prospector 46-48 | Talonflame, Chandelure, +Infernape, Volcarona | a small Blaine: Rhydon, Lycanroc, Coalossal, Stealth Rock |

### Route 8 to Giovanni (Storm Drain, Ice coverage, Mold Breaker; answer: Ice and Fairy)
| Fight | Team | Teaches |
|---|---|---|
| Crater Novice 46 | Gliscor | Ground/Flying: Ice four times over, Grass only neutral |
| Crater Scout 45-46 | Gastrodon, Donphan | Water/Ground eats Water; Ice Shard and Ice Beam hit Grass: Ice for Donphan |
| Grassland Keeper 47-48 | Claydol, Excadrill | Ice Beam for Grass, Steel/Ground for Fairy: Ice/Ghost for Claydol, Water for Excadrill |
| Sand Runner 47-49 | Palossand, Gastrodon, +Gliscor, Flygon | Giga Drain for Water, two Ground-immunes: Ice |
| Plateau Ranger 49-50 | Krookodile, Mamoswine | Gunk Shot for Fairy, Ice for Flying/Grass: Water/Fighting for Mamoswine, Fairy for Krookodile |
| Rift Surveyor 50-52 | Dugtrio, Donphan, +Palossand, Gliscor | the Ground core without sand: Ice, Fairy, Gyarados |
| Final Warden 51-53 | Claydol, Gastrodon, +Excadrill, Flygon | a small Giovanni: Abomasnow, Tinkaton, Gyarados, Swampert |

Answer check: every named answer is one of the bosses' `open_line` species or its pre-evolution, whose sources
`CHALLENGE_MODE_TEAMS.md` section 4 tabulates against `data/encounter_design.json`; each route names at least two.

## 3. Victory Road (levels unchanged) and the gym juniors

| Examiner | Challenge team (one held item) | League engine |
|---|---|---|
| 1 Applicant | Abomasnow (Snow Warning, Aurora Veil, Light Clay), Cetitan (Slush Rush) | Lorelei: break the Veil |
| 2 Rift Hiker | Gengar (Black Sludge), Jellicent: Toxic then Hex | Agatha's Ghosts |
| 3 Slagworks | No Guard Machamp, Iron Fist Hitmonchan (Punching Glove) | Bruno |
| 4 Cartographer | Intimidate Scrafty, Mudsdale (Sitrus) | Bruno |
| 5 Trench | Tyranitar (Sand Stream, Smooth Rock), Technician Scizor | Blue |
| 6 Field Medic | Dusknoir Trick Room (Mental Herb), No Guard Golurk | Agatha's Trick Room |
| 7 Tactician | Drizzle Pelipper (Damp Rock), Swift Swim Kingdra with Flash Cannon | Lance's dragons |
| 8 Cut Foreman | Duraludon Stealth Rock, Multiscale Dragonite (Boots) | Lance's Steel-dragons |
| 9 Veteran | Trevenant Trick Room (Mental Herb), Disguise Mimikyu | Agatha's Trick Room |
| 10 Examiner | Sash Tailwind Crobat (kept: dialogue names it), Aerodactyl, Veil Abomasnow, Goodra, Defiant Kingambit | the League |

Juniors rehearse their leader's Challenge, one or two new members plus one Normal member (usually the top):
Gym 1 Sturdy/sand/Storm Drain (Nosepass, Dwebble, Lileep, Tyrunt, Onix, Flame Body Carkol); Gym 2 Lightning Rod
Goldeen, Liquid Ooze Tentacool, Skill Link Shellder, Regenerator Slowpoke, Huge Power Marill, Scald Staryu; Gym 3
Wattrel, Motor Drive Emolga, Volt Absorb Chinchou/Lanturn, Joltik, Lightning Rod Pikachu, Levitate Vikavolt; Gym 4
Prankster Cottonee/Whimsicott, Swift Swim Lombre, Iron Barbs Ferroseed, Lileep, Contrary Lurantis, Technician
Breloom; Gym 5 Ariados, Liquid Ooze Tentacruel, Drapion, Roserade, Toxic Debris Glimmora, Dry Skin Toxicroak; Gym 6
Psychic Surge Indeedee, Magic Bounce Espeon, Sharpness Gallade, Magic Guard Reuniclus/Alakazam, Gardevoir, Xatu; Gym
7 Ninetales, Lampent, Infernape, Magmortar, Volcarona, Charizard, Chandelure, Houndoom, Gale Wings Talonflame (Boots);
Gym 8 Storm Drain Gastrodon, Claydol, Mold Breaker Excadrill, Palossand, Poison Heal Gliscor (Toxic Orb), Flygon,
Krookodile, Mamoswine, Nidoqueen.

## 4. For the main session: implementing `challenge_team_species`

1. **Levels for a Normal+1 list (decide; it moves the budget).** Section 6 says "computed exactly as Normal's".
   - Reading A (the formula over the list's own length) keeps the ceiling but lowers each extended fight's sum by
     N-1 levels: **-27 levels over the 14 fights**, which moves `tools/income_model.py` Challenge figures.
   - Reading B reproduces the old Challenge vector exactly: Normal's levels, the second-to-last entry at ceiling-1,
     the last at the ceiling.
   - The lists are ordered for B (the added member is second-to-last). **Recommend B**: the budget and income are
     unchanged by construction.
2. **Do not apply Normal's `movesets` to the Challenge list** (Routes 1-3 carry them; wrong species and length). The
   Challenge team uses kit moves, or `challenge_movesets` if given.
3. `extra_member_roles` is now `[]` on all eight routes. That is required: `build_route_mode` would otherwise add a
   second extra on top of a Normal+1 list (test limit +1).
4. Then run `generate_trainers.py --write-active`, `tests/test_trainer_modes.py`, `tests/test_gym_trainers.py` (with
   `COBBLERS_JAR_DIR` for the learnset and type check), `tests/test_challenge_mode.py`, `income_model.py --check`,
   `challenge_voucher.py --check`, and the two guides.

## 5. Assumed, and findings

- **ASSUMED: learnsets.** No move was checked against the jar. The juniors' are tested only with `COBBLERS_JAR_DIR`.
  The likeliest misses are Goldeen Drill Run, Nosepass Sandstorm, Tyrunt Dragon Tail, Indeedee Shadow Ball,
  Ferroseed Leech Seed, Kirlia/Indeedee Psychic Terrain, Glimmora Energy Ball and Houndoom Sucker Punch. Swap a
  failing move; do not change the species.
- **ASSUMED: abilities.** Explicit abilities (juniors, Victory Road) include hidden ones: Lightning Rod, Storm Drain,
  Regenerator, Motor Drive, Prankster, Contrary, Technician, Psychic Surge, Magic Bounce, Sharpness, Mold Breaker,
  Poison Heal, Intimidate on Scrafty, Drizzle, Swift Swim and Multiscale. Their acceptance follows the bosses'
  precedent and is not proven. Route kits cannot carry an ability, so route members roll a regular one (ASSUMED
  Cobblemon behaviour). The route lessons therefore rest on typing and moves; the abilities a route can count on are
  only-abilities (Ferroseed Iron Barbs, Claydol and Flygon Levitate, Hippopotas Sand Stream).
- **ASSUMED: species in the 1.8 jar.** Kingdra (Victory Road 7) is in trainer data (Lance), but section 8 lists it
  ASSUMED. Every other species is in `data/encounter_design.json` or `data/spawns.json` (Monferno), or already in a
  team.
- **Items:** all VERIFIED (section 8) or already in trainer data (oran, cheri, sitrus, lum, black_sludge).
- **Finding: dialogue is shared between modes**, and some lines name what Challenge no longer fields:
  - R1 Trail Novice (Quick Attack) and Meadow Apiarist (Surskit);
  - R2 Ravine Scrapper (Corphish) and North Bank Angler (Krabby);
  - R3 Climbing Novice (Rock Tomb);
  - Victory Road 3 (sun) and 4 (burn).
  Two lines actively teach the wrong lesson in Challenge: R3 Groundkeeper ("Catch a Bunnelby") and Vessu Ranger
  ("Wooper ... Bunnelby. Catch one"). A per-mode dialogue field would need a generator change; none was invented.
- **Finding:** the `mudsdale` kit's move `heavy_slam` is not Showdown's id (`heavyslam`, as Victory Road uses). It
  affects Normal Route 8 and was left alone.
- **Finding:** CHALLENGE_MODE_TEAMS.md section 8 says Annihilape is in no spawn table. `data/encounter_design.json`
  `northgate_west` heart has it.
- **Not checked:** damage, AI use of setup and hazards, arena or hall clearance for new junior species.
