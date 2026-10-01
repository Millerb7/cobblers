# Realistic-team gym stress test

**Generated:** `python tools/battle_stress.py --markdown docs/story/BATTLE_STRESS.md`

This is a deterministic structural stress test, not play evidence. It runs 108 sampled profiles per gym
and mode against the exact committed rosters, using the fixed-order/no-switch engine in
`tools/battle_sim.py`. No roster is changed.

## Sample

The seed is `20260929`. All 27 configured starter species appear exactly four times. The archetypes are:

| Archetype | Teams | Selection and levelling |
| --- | ---: | --- |
| Collector | 24 | Broad catches; only two slots deliberately seek a positive matchup; even levels. |
| Loyal six | 18 | Starter plus five early catches retained; nearly even levels. |
| Favourite-heavy | 18 | Early core retained; favourite at cap, four members trail by 4-7 levels. |
| Type-blind | 18 | Rarity-weighted catches with no matchup check; even levels. |
| Critical-path only | 15 | Route pools only; one modestly informed answer, no optional subregions. |
| Nuzlocke-shaped | 15 | One random catch per named pool, no matchup selection; early teams may have fewer than six. |

Common encounters are 4.2 times as likely to be selected as rare encounters and 14.3 times as likely
as ultra-rare encounters. This is a design assumption, not player telemetry. Only 39 of 108 profiles
prepare for the leader at all, preventing the sample from quietly becoming 108 informed teams.
Each profile uses the exact same party against Normal and Challenge. Modest preparation reads the Normal
presentation of the gym so Challenge does not receive a secretly hand-picked comparison sample.

`Sampled reorder` means at least one of 36 deterministic pre-battle orders of the same team wins. It
does not model switching and is not an exhaustive ceiling. `Cap sampled reorder` also raises every
straggler to the cap and is used only to separate level failures from composition failures.

## Results

| Gym | Mode | First-order wins | Avg losses on win | Prepared wins | Sampled reorder | Cap sampled reorder | Blind wins | Nuzlocke wins (clean) | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | Normal | 94.4% | 1.33 | 100.0% | 96.3% | 100.0% | 18/18 | 12/15 (6) | **trivial** |
| 1 | Challenge | 22.2% | 4.38 | 38.5% | 46.3% | 95.4% | 6/18 | 1/15 (0) | **unwinnable risk** |
| 2 | Normal | 82.4% | 2.38 | 94.9% | 86.1% | 98.1% | 17/18 | 12/15 (0) | **fair** |
| 2 | Challenge | 1.9% | 5.00 | 2.6% | 5.6% | 29.6% | 1/18 | 0/15 (0) | **unwinnable risk** |
| 3 | Normal | 35.2% | 2.34 | 51.3% | 49.1% | 64.8% | 9/18 | 9/15 (0) | **unwinnable risk** |
| 3 | Challenge | 2.8% | 3.67 | 2.6% | 14.8% | 18.5% | 2/18 | 0/15 (0) | **unwinnable risk** |
| 4 | Normal | 53.7% | 3.07 | 79.5% | 75.9% | 87.0% | 10/18 | 10/15 (0) | **punishing but fair** |
| 4 | Challenge | 9.3% | 4.20 | 17.9% | 29.6% | 52.8% | 2/18 | 1/15 (0) | **unwinnable risk** |
| 5 | Normal | 24.1% | 3.92 | 48.7% | 56.5% | 81.5% | 4/18 | 3/15 (0) | **unwinnable risk** |
| 5 | Challenge | 5.6% | 4.17 | 7.7% | 23.1% | 43.5% | 3/18 | 0/15 (0) | **unwinnable risk** |
| 6 | Normal | 29.6% | 3.88 | 38.5% | 75.9% | 89.8% | 8/18 | 4/15 (0) | **punishing but fair** |
| 6 | Challenge | 9.3% | 4.60 | 10.3% | 45.4% | 60.2% | 4/18 | 1/15 (0) | **unwinnable risk** |
| 7 | Normal | 2.8% | 4.33 | 5.1% | 13.9% | 21.3% | 0/18 | 0/15 (0) | **unwinnable risk** |
| 7 | Challenge | 0.0% | — | 0.0% | 1.9% | 5.6% | 0/18 | 0/15 (0) | **unwinnable risk** |
| 8 | Normal | 22.2% | 4.33 | 28.2% | 64.8% | 79.6% | 4/18 | 3/15 (0) | **unwinnable risk** |
| 8 | Challenge | 10.2% | 4.82 | 15.4% | 36.1% | 57.4% | 2/18 | 1/15 (0) | **unwinnable risk** |

## Loss diagnosis

The engine has no random rolls, critical hits, secondary effects, or move-choice variance, so it
assigns **zero losses to bad luck**. That is a simulator limitation, not a claim that bad luck
cannot decide the real fight.

### Gym 1

- **Normal:** wrong levels 6. Representative losses: bulbasaur L19, applin L19, pidgey L19, mareep L18, wooloo L19, hoothoot L19 (loyal_six; wrong levels); chimchar L17, hoothoot L19, magikarp L18, wingull L17 (nuzlocke; wrong levels); litten L18, magikarp L19, rattata L19, mareep L19, wooloo L20, fomantis L19 (loyal_six; wrong levels).
- **Challenge:** gimmick 5, gimmick or order 12, wrong levels 43, wrong levels and order 24. Representative losses: surskit L19, charmander L19, gossifleur L20, shellder L19, rattata L20, wingull L20 (type_blind; gimmick or order); buizel L20, hoothoot L18, bidoof L20, fomantis L19, squirtle L19, rattata L20 (critical_path_only; wrong levels); bulbasaur L20, wingull L18, combee L19, surskit L20, pidgey L19, wooloo L20 (loyal_six; wrong levels and order).

### Gym 2

- **Normal:** gimmick or order 1, no answer in model 2, wrong levels 14, wrong levels and order 2. Representative losses: shellder L25, totodile L23, combee L21, wattrel L20, wingull L19, gossifleur L18 (favourite_heavy; wrong levels); torchic L23, pidgey L23, goldeen L24, krabby L24, lombre L25, barboach L25 (nuzlocke; no answer in model); mareep L25, pawmi L23, deerling L25, barboach L24, piplup L25, krabby L24 (collector; gimmick or order).
- **Challenge:** gimmick 32, gimmick or order 3, no answer in model 44, wrong levels 4, wrong levels and order 23. Representative losses: barboach L24, chinchou L24, deerling L24, charmander L25, hoothoot L24, fomantis L23 (type_blind; no answer in model); illumise L24, wooloo L24, bidoof L24, corphish L24, squirtle L25, applin L25 (critical_path_only; no answer in model); bulbasaur L24, wingull L23, combee L24, surskit L24, pidgey L24, wooloo L25 (loyal_six; wrong levels and order).

### Gym 3

- **Normal:** gimmick 22, gimmick or order 8, no answer in model 16, wrong levels 10, wrong levels and order 14. Representative losses: absol L35, swablu L29, rockruff L29, magikarp L29, fomantis L30, charmander L30 (type_blind; gimmick or order); mareep L28, gossifleur L29, squirtle L29, hoothoot L29, corphish L30, fomantis L30 (critical_path_only; wrong levels and order); bulbasaur L29, wingull L29, combee L30, surskit L30, pidgey L29, wooloo L30 (loyal_six; no answer in model).
- **Challenge:** gimmick 23, gimmick or order 11, no answer in model 65, wrong levels 2, wrong levels and order 4. Representative losses: absol L35, swablu L29, rockruff L29, magikarp L29, fomantis L30, charmander L30 (type_blind; no answer in model); mareep L28, gossifleur L29, squirtle L29, hoothoot L29, corphish L30, fomantis L30 (critical_path_only; no answer in model); bulbasaur L29, wingull L29, combee L30, surskit L30, pidgey L29, wooloo L30 (loyal_six; no answer in model).

### Gym 4

- **Normal:** gimmick 8, gimmick or order 11, no answer in model 6, wrong levels 19, wrong levels and order 6. Representative losses: shellder L35, totodile L33, combee L31, wattrel L30, wingull L29, gossifleur L28 (favourite_heavy; wrong levels and order); deerling L35, chikorita L33, magikarp L31, goldeen L30, wingull L29, shellder L28 (favourite_heavy; wrong levels); torchic L34, applin L32, chinchou L33, stunky L34, skiddo L35, goldeen L32 (nuzlocke; wrong levels).
- **Challenge:** gimmick 24, gimmick or order 15, no answer in model 27, wrong levels 13, wrong levels and order 19. Representative losses: mareep L35, basculin L33, barboach L35, hoothoot L34, charmander L33, aron L35 (type_blind; wrong levels and order); hoothoot L34, skiddo L35, illumise L35, makuhita L35, squirtle L33, fomantis L34 (critical_path_only; gimmick or order); bulbasaur L34, wingull L35, combee L34, surskit L34, pidgey L34, wooloo L34 (loyal_six; gimmick).

### Gym 5

- **Normal:** gimmick 10, gimmick or order 24, no answer in model 10, wrong levels 18, wrong levels and order 20. Representative losses: buneary L40, rufflet L39, makuhita L40, charmander L39, skiddo L40, bidoof L38 (type_blind; gimmick or order); bulbasaur L39, wingull L39, combee L39, surskit L38, pidgey L39, wooloo L39 (loyal_six; gimmick); shellder L40, totodile L38, combee L36, wattrel L35, wingull L34, gossifleur L33 (favourite_heavy; no answer in model).
- **Challenge:** gimmick 17, gimmick or order 16, no answer in model 44, wrong levels 4, wrong levels and order 21. Representative losses: buneary L40, rufflet L39, makuhita L40, charmander L39, skiddo L40, bidoof L38 (type_blind; no answer in model); nosepass L40, bunnelby L40, surskit L40, scyther L40, squirtle L39, illumise L40 (critical_path_only; gimmick or order); bulbasaur L39, wingull L39, combee L39, surskit L38, pidgey L39, wooloo L39 (loyal_six; gimmick).

### Gym 6

- **Normal:** gimmick 6, gimmick or order 42, no answer in model 5, wrong levels 11, wrong levels and order 12. Representative losses: golduck L45, poliwag L45, charmander L45, shellder L45, croagunk L44, piplup L44 (type_blind; gimmick or order); deerling L44, hoothoot L45, vanillite L44, squirtle L45, bunnelby L45, yanma L43 (critical_path_only; gimmick or order); basculin L45, bergmite L44, sewaddle L45, drampa L44, cyndaquil L45, rockruff L44 (collector; gimmick or order).
- **Challenge:** gimmick 20, gimmick or order 34, no answer in model 23, wrong levels 5, wrong levels and order 16. Representative losses: golduck L45, poliwag L45, charmander L45, shellder L45, croagunk L44, piplup L44 (type_blind; no answer in model); deerling L44, hoothoot L45, vanillite L44, squirtle L45, bunnelby L45, yanma L43 (critical_path_only; gimmick); bulbasaur L44, wingull L43, combee L44, surskit L45, pidgey L45, wooloo L44 (loyal_six; wrong levels and order).

### Gym 7

- **Normal:** gimmick 72, gimmick or order 10, no answer in model 13, wrong levels 6, wrong levels and order 4. Representative losses: charmander L48, mareep L50, shellder L50, cryogonal L49, toxel L48, pawmi L50 (type_blind; gimmick); buizel L49, corphish L50, squirtle L48, bergmite L48, applin L50, volbeat L49 (critical_path_only; gimmick); bulbasaur L48, wingull L50, combee L49, surskit L49, pidgey L50, wooloo L50 (loyal_six; no answer in model).
- **Challenge:** gimmick 73, gimmick or order 2, no answer in model 29, wrong levels and order 4. Representative losses: charmander L48, mareep L50, shellder L50, cryogonal L49, toxel L48, pawmi L50 (type_blind; no answer in model); buizel L49, corphish L50, squirtle L48, bergmite L48, applin L50, volbeat L49 (critical_path_only; gimmick); bulbasaur L48, wingull L50, combee L49, surskit L49, pidgey L50, wooloo L50 (loyal_six; no answer in model).

### Gym 8

- **Normal:** gimmick 11, gimmick or order 28, no answer in model 11, wrong levels 19, wrong levels and order 15. Representative losses: pincurchin L54, vullaby L55, salandit L55, drapion L55, klawf L54, charmander L54 (type_blind; no answer in model); makuhita L54, surskit L54, scyther L54, machop L55, squirtle L54, salandit L54 (critical_path_only; gimmick or order); bulbasaur L54, wingull L54, combee L54, surskit L53, pidgey L54, wooloo L55 (loyal_six; wrong levels).
- **Challenge:** gimmick 22, gimmick or order 21, no answer in model 24, wrong levels 13, wrong levels and order 17. Representative losses: pincurchin L54, vullaby L55, salandit L55, drapion L55, klawf L54, charmander L54 (type_blind; no answer in model); makuhita L54, surskit L54, scyther L54, machop L55, squirtle L54, salandit L54 (critical_path_only; gimmick); bulbasaur L54, wingull L54, combee L54, surskit L53, pidgey L54, wooloo L55 (loyal_six; gimmick or order).

## Nuzlocke reading

A Nuzlocke win with fainted members is recorded as a win here but those members are permanent deaths.
The table's clean count is therefore the only run that advances without attrition. These are independent
gym snapshots; deaths are not carried from one gym into the next, so the report is optimistic for a full
campaign Nuzlocke.

## What the simulator cannot settle

- **No switching:** the percentages are fixed-order first attempts. Any-order tests scouting and lead order,
  but neither player switching nor the leaders' configured switch bias runs. A team marked unable to win
  may still win through intelligent switches; hazards and Intimidate may also make switching worse.
- **No player items:** the authored rules set max item uses to zero, so this matches the current roster data,
  but any runtime rule that permits bag items would raise player results.
- **No battle RNG:** accuracy is averaged into damage; crits, flinches, confusion, secondary status and damage
  rolls do not exist. The tool cannot measure luck and overstates the certainty of close outcomes.
- **Incomplete mechanics:** hazards, Protect, Substitute, Encore, Taunt, Pain Split, Trick Room, Tailwind,
  Baton Pass and many abilities are inert. Gym-specific sensitivity must be read beside these numbers.
- **Player moves:** player sets use level-up moves only and no held items. TMs and deliberate player items
  would improve real prepared teams, so the results lean against the player.
- **Stats:** both sides use IV 15 and EV 0. Real captures and trained teams vary.
- **Engine parity:** the mainline damage formula used here has never been checked against Cobblemon's embedded
  Showdown at these levels. A result resting on one surviving hit is not a verdict until EXP-010 runs.
