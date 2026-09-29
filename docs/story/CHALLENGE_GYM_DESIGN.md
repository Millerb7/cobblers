# Full-Team Challenge gyms

**Status:** authored as generated campaign data. Normal remains unchanged. Runtime selection and RCT behavior are not proven.

## Contract

Both modes keep the caps `20 / 25 / 30 / 35 / 40 / 45 / 50 / 55`.

- Normal keeps its existing shorter teams and restrained item pressure.
- Challenge gives every Gym Leader exactly six Pokémon, a complete engine, and meaningful held items.
- Every Challenge fight must retain one six-Pokémon preparation line from the established availability curve. The line may be narrow and require scouting; the roster may not erase every available answer.
- `docs/story/TRAINER_RULES.json` is the editable source. `data/trainers.json` is generated. The top-level compatibility payload still mirrors Normal.

## Oak's world-wide choice

The mode cannot vary per player with current RCT trainers. A shared trainer entity has one synchronized trainer identity and resolves one team when battle begins. Per-player state can remember two different choices, but it cannot make that entity serve two rosters.

Oak therefore records one permanent world choice. The first accepted choice applies to every player; later players inherit it. Switching later is unsupported.

The exact dialogue remains here until the proven dialogue compiler can read and compare world-scoped state:

> Before I send you out, we need to record the League rules this campaign will follow.

> Under Standard rules, Gym Leaders use focused teams. Their plans are clear, and their held items support the lesson without filling every slot.

> Under Full-Team rules, every Gym Leader brings six. Their combinations are tighter, their held items matter, and a prepared answer may need help from the rest of your party.

> The level limits are identical. This changes what each battle asks of you, not how far you may train.

> This record belongs to the whole campaign. Once I enter it, everyone uses it and it cannot be changed. Which rules should I enter?

Responses:

- `Use Standard rules.` → `Record Standard rules for this world? This cannot be changed later.`
- `Use Full-Team rules.` → `Record Full-Team rules for this world? This cannot be changed later.`
- `Let me think.` → close without writing anything.

Later players hear: `The League rules for this campaign are already recorded: <Standard / Full-Team> rules.`

Runtime proof must cover simultaneous first choices, restart persistence, and confirmation that only the selected trainer variants exist.

## Simulation contract

The results below use the exact cap, 15 IVs, no EVs, level-up moves for the player, fixed leader moves, and no switching. Each result uses the authored line in the listed order. This checks structural survival only. The simulator omits or simplifies leader switching, secondary effects, flinching, hazards, Trick Room, Tailwind, Volt Switch, U-turn, several abilities, and several held items.

## Gym 1 — Brock: Fault Line

| Pokémon | Item | Engine role |
| --- | --- | --- |
| Geodude 19 | Berry Juice | Sturdy guarantees the first Rock Tomb speed tax; Thunder Punch checks a careless Water lead. |
| Lileep 19 | Eviolite | Bulky Water interruption that leaves Grass and neutral pressure intact. |
| Dwebble 19 | White Herb | Visible Shell Smash threat exploiting the speed tax. |
| Cranidos 19 | Muscle Band | Immediate breaker after the player spends resources on the opening core. |
| Bonsly 20 | Oran Berry | Tearful Look and Rock Tomb extend attrition before the ace. |
| **Onix 20** | **Weakness Policy** | Sturdy turns the obvious super-effective hit into one dangerous ace turn. |

**Open line:** Eldegoss → Krabby → Staryu → Wingull → Surskit → Buizel. Preserve a fresh Water attacker for Onix. **Obviousness:** moderate; Route 1 supplies Water and Grass, while Lileep visibly says Water alone is insufficient.

**Simulator:** win, 2 fainted. Two available species can beat all six in isolated 1v1s, making this the most forgiving Challenge gym.

## Gym 2 — Misty: Lake Tempo

| Pokémon | Item | Engine role |
| --- | --- | --- |
| Pelipper 23 | Damp Rock | Drizzle begins the tempo engine and resists the first Grass attempt. |
| Lombre 24 | Mystic Water | Swift Swim pressure plus a Grass mirror asking for Bug or Flying damage. |
| Goldeen 24 | Eviolite | First Lightning Rod interruption. |
| Barboach 24 | Eviolite | Second Electric interruption with a four-times Grass weakness. |
| Floatzel 25 | Muscle Band | Fast physical rain breaking and Quick Attack cleanup. |
| **Starmie 25** | **Sitrus Berry** | Recovery and Icy Wind extend the tempo fight; Thunderbolt stops a free Gyarados finish. |

**Open line:** Kilowattrel → Deerling → Illumise → Eldegoss → Lombre → Pawmo. **Obviousness:** clear after scouting; both Electric interruptions visibly lose to Grass, while Lombre asks for Bug.

**Simulator:** win, 4 fainted. No available species beats all six alone.

## Gym 3 — Lt. Surge: Closed Circuit

| Pokémon | Item | Engine role |
| --- | --- | --- |
| Electabuzz 28 | Eviolite | Thunder Wave and Light Screen establish the speed and special-pressure tax. |
| Vikavolt 28 | Occa Berry | Single Ground-immunity interruption; Energy Ball checks Water/Ground without erasing ordinary Ground. |
| Magneton 29 | Eviolite | Sturdy guarantees one action from the Steel anchor. |
| Boltund 29 | Muscle Band | Fast physical coverage punishes Grass and one-wall plans. |
| Pawmot 30 | Expert Belt | Fighting pressure and Mach Punch force Ground answers to arrive healthy. |
| **Raichu 30** | **Sitrus Berry** | Nasty Plot threatens a close; it deliberately carries no Ground coverage. |

**Open line:** Lycanroc → Hariyama → Heracross → Clodsire → Quagsire → Diggersby. **Obviousness:** clear from preview and Route 3; remove the flying immunity, break the Steel/Fighting core, then use Ground.

**Simulator:** win, 4 fainted. No available species beats all six alone.

## Gym 4 — Erika: Glasshouse Sun

| Pokémon | Item | Engine role |
| --- | --- | --- |
| Bellossom 33 | Heat Rock | Sunny Day starts the only field engine; Weather Ball prevents a passive Steel/Flying lead. |
| Roserade 34 | Black Sludge | Fast special pressure and paralysis. |
| Cradily 34 | Leftovers | Disclosed Flying interruption and durable midpoint. |
| Tangrowth 34 | Assault Vest | Bulky pivot and second source of limited Rock pressure. |
| Victreebel 35 | Life Orb | Physical Chlorophyll breaking and Sucker Punch. |
| **Vileplume 35** | **Coba Berry** | Growth is the visible ace turn; Coba delays Flying once while Ice and Fire remain open. |

**Open line:** Talonflame → Skarmory → Cryogonal → Jynx → Scyther → Noctowl. **Obviousness:** moderate; Route 4 teaches sun and exposes Rock coverage, so the answer is a mixed Fire/Flying/Ice line.

**Simulator:** win, 3 fainted. This probably understates Erika because Chlorophyll, weather-typed Weather Ball, and Regenerator switching are not faithfully modelled.

## Gym 5 — Koga: Venom Clock

| Pokémon | Item | Engine role |
| --- | --- | --- |
| Crobat 40 | Black Sludge | Fast Toxic and Venoshock start the clock. |
| Weezing 40 | Rocky Helmet | Levitate blocks the first Ground plan; burn and contact punishment attack physical teams. |
| Toxtricity 40 | Throat Spray | Immediate special breaking and poison payoff. |
| Dragalge 40 | Assault Vest | Special sponge with Adaptability-powered neutral damage. |
| Drapion 40 | Shuca Berry | Psychic immunity and one delayed Ground hit split the obvious answers. |
| **Venomoth 40** | **Focus Sash** | Guaranteed Quiver Dance turn creates the final priority/Rock check. |

**Open line:** Ampharos → Jynx → Diggersby → Bronzong → Quagsire → Lycanroc. **Obviousness:** moderate; Route 5 teaches Levitate and mixed Poison typings, but every answer has a specific job.

**Simulator:** win, 5 fainted. No available species beats all six alone.

## Gym 6 — Sabrina: Wrong Clock

| Pokémon | Item | Engine role |
| --- | --- | --- |
| Hatterene 45 | Focus Sash | Guarantees the first Trick Room and reflects simple status plans. |
| Slowbro 45 | Colbur Berry | Durable slow beneficiary that delays Dark once. |
| Bronzong 45 | Leftovers | Second setter and physical Dark check. |
| Exeggutor 45 | Sitrus Berry | Slow status pressure with a deliberate four-times Bug weakness. |
| Reuniclus 45 | Life Orb | Main Trick Room special breaker. |
| **Alakazam 45** | **Focus Sash** | Fast Nasty Plot closer after Trick Room expires. |

**Open line:** Bronzong → Scyther → Heracross → Skuntank → Toxtricity → Quagsire. **Obviousness:** clear; Route 6 teaches Dark offense, priority, and waiting out Trick Room.

**Simulator:** win, 3 fainted. No Mansion Ghost is required.

## Gym 7 — Blaine: Pressure Front

| Pokémon | Item | Engine role |
| --- | --- | --- |
| Torkoal 50 | Heat Rock | Drought, Stealth Rock, and Yawn start the damage race. |
| Arcanine 50 | Choice Band | Intimidate, immediate physical breaking, and Extreme Speed. |
| Magcargo 50 | White Herb | Visible Shell Smash threat that Water/Ground or Rock can stop. |
| Magmortar 50 | Assault Vest | The roster's sole direct Water check. |
| Typhlosion 50 | Choice Scarf | Eruption supplies immediate speed and damage pressure. |
| **Charizard 50** | **Life Orb** | Solar Power creates the closing race; it deliberately lacks Solar Beam. |

**Open line:** Dondozo → Pelipper → Floatzel → Whiscash → Crawdaunt → Lycanroc. **Obviousness:** moderate; Route 7 teaches bulky Water, weather replacement, fast Water, Ground, and Rock, but the winning order needs scouting.

**Simulator:** win, 5 fainted. The generic informed picker loses with five opponents down; the authored order wins. This is the narrowest structural line.

## Gym 8 — Giovanni: Fault Command

| Pokémon | Item | Engine role |
| --- | --- | --- |
| Hippowdon 55 | Smooth Rock | Sand changes thresholds while Yawn and Slack Off resist brute force. |
| Persian 55 | Focus Sash | Fake Out, Taunt, and U-turn disrupt setup and sequencing. |
| Mudsdale 55 | Assault Vest | Stamina makes careless physical trading progressively worse. |
| Nidoqueen 55 | Life Orb | Sheer Force coverage breaks one-answer Water/Grass/Flying cores. |
| Krookodile 55 | Choice Scarf | Speed control and a possible Moxie snowball. |
| **Rhyperior 55** | **Rindo Berry** | Visible Rock Polish ace delays Grass once while Water remains open. |

**Open line:** Swanna → Seismitoad → Gogoat → Hariyama → Heracross → Cacturne. **Obviousness:** moderate; Route 8 teaches immunity, Fighting, Grass, priority, and Tailwind, while Nidoqueen forces rotation.

**Simulator:** win, 5 fainted. Several Water species test too well in isolated 1v1s, so runtime switching and Sheer Force behavior matter.

## Verdict

- **Genuinely nasty:** Misty, Surge, Koga, Blaine, and Giovanni. Misty and Surge demand split early teams; Koga leaves one survivor; Blaine defeats the generic informed picker; Giovanni combines six complete roles.
- **Hard but more forgiving:** Brock, Erika, and Sabrina. Brock has abundant Water/Grass supply, Erika has several natural offensive types, and Sabrina broadcasts its clock.
- **Crossed into unfair:** none in the deterministic check. Koga, Blaine, and Giovanni are closest because the authored line loses five members. Erika may be harder than its number once Chlorophyll and switching work. All four need in-game threshold tests before installation.

## Victory Road reconciliation

The retired nine surface pins are replaced by the ten deterministic cave stands from the built 713-block route. The topology is four fights, one rest station, then six fights.

| # | Trainer | Position | Lesson | Normal / Challenge |
| ---: | --- | --- | --- | --- |
| 1 | League Applicant | `(3563, 2, 3009)` | Speed tax into priority | Lycanroc + Heracross / Lycanroc gains Sitrus Berry |
| 2 | Rift Hiker | `(3597, 8, 2985)` | Poison into payoff | Drapion + Toxapex / Toxapex gains Sitrus Berry |
| 3 | Slagworks Keeper | `(3604, 17, 2928)` | Sun pressure | Torkoal + Coalossal / Torkoal gains Heat Rock |
| 4 | Rift Cartographer | `(3620, 19, 2880)` | Burn and damage split | Weezing + Mudsdale / Mudsdale gains Sitrus Berry |
| — | Rest station | `(3606, 23, 2835)` to `(3620, 23, 2849)` | One safe room | No automatic healing service authored |
| 5 | Trench Climber | `(3616, 25, 2822)` | Sand thresholds | Gigalith + Excadrill / Gigalith gains Smooth Rock |
| 6 | Field Medic | `(3607, 31, 2766)` | Trick Room | Bronzong + Hariyama / Hariyama gains Sitrus Berry |
| 7 | Veteran Tactician | `(3621, 42, 2716)` | Rain tempo | Politoed + Lanturn / Politoed gains Mystic Water |
| 8 | Cut Foreman | `(3642, 48, 2673)` | Switch cost and immunity | Aggron + Crobat / Aggron gains Sitrus Berry |
| 9 | League Veteran | `(3641, 55, 2614)` | Setup denial and race | Mismagius + Klinklang / Mismagius gains Colbur Berry |
| 10 | League Examiner | `(3655, 65, 2564)` | Tailwind final | Four members / Crobat gains Focus Sash and Cacturne joins |

The exact teams and dialogue hooks are generated in `data/trainers.json`. World placement and per-player defeat-state integration remain unimplemented.

## Runtime boundary

- RCT data carries teams, moves, abilities, items, AI profiles, and formats.
- Oak's selector needs an atomic persistent world value plus placement logic that creates only the chosen variants.
- Challenge AI switching, held-item activation, weather/support sequencing, Trick Room, co-op isolation, and the ten Victory Road seats require runtime proof.
- Illegal evolution levels are intentional where used.
