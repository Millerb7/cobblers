# Trainer roster generation

**Status:** generated design data; RCT 0.19.0-beta shape validated; not compiled into a datapack, installed, spawned, or runtime-proven.

The editable source is `TRAINER_RULES.json`. Run:

```text
python docs/story/generate_trainers.py --write
python docs/story/generate_trainers.py --check
python docs/story/generate_trainers.py --write-early
python docs/story/generate_trainers.py --check-early
```

The generator writes `data/trainers.json`. It currently emits 13 boss slots, 12 concrete boss rosters, one deliberately held Giovanni slot, and 50 proposed route trainers. Required route trainers use existing `routes.json` polyline vertices; optional destination trainers retain a verified route anchor plus an explicit measured off-route coordinate. Nothing is placed in the world.

## Difficulty rule set

| Rule | Current value | Cost of changing it |
| --- | --- | --- |
| Gym ace curve | `20/25/30/35/40/45/50/55` | Edit one curve and the affected boss offsets; rerun generation and availability review. |
| Cap offset | `0` | Config-only in this design, but runtime behavior remains an EXP-003 proof. |
| Gym members | `4/4/4/4/5/5/6/held` | Add or remove entries in one boss member list. |
| League members | Six each | Add or remove entries in one boss member list. |
| League ceilings | Elite Four `60`; Champion `62` | Edit `league_ace_levels` and boss ace levels; all member levels derive from offsets. |
| Moves and items | Per species/member loadout | Edit one member or reusable route species kit. |
| Ace | Exactly one per concrete boss | Mark one member `ace`; the generator rejects zero or multiple aces. |
| AI | Six named profiles | Tune `moveBias`, `switchBias`, `statusMoveBias`, `itemBias`, and `maxSelectMargin`; all affected trainers regenerate. |
| Route density | 49 required distance pins plus 1 optional shore placement | Add or remove a pin; required pins resolve to the route polyline, while an optional placement must record and verify its anchor and off-route gap. |
| Route team size | Archetypes of 1, 2, or 3 members | Edit `route_archetypes`; every route team using that archetype regenerates. |

`maxSelectMargin` is kept positive because RCT passes it as a random bound. The requested conceptual `stat_move_bias` maps to RCT's exact field name `statusMoveBias`; `statMoveBias` is not valid in the target API.

## Gym leaders

| Gym | Team levels | Strategy | Ace and changed maths | Availability verdict |
| ---: | --- | --- | --- | --- |
| Brock | Geodude 18, Bonsly 18, Cranidos 19, Onix 20 | Rocks and speed control into a breaker and durable closer. | Onix: Sturdy guarantees an action; Weakness Policy converts the expected super-effective hit into a damage race. | Satisfied by common Water and Grass families. |
| Misty | Horsea 22, Lombre 23, Goldeen 24, Starmie 25 | Rain tempo, a Lightning Rod disruption, then broad special coverage. | Starmie: Life Orb changes neutral damage thresholds while rain changes Water damage and turn order. | Satisfied by Electric and Grass families. |
| Lt. Surge | Electabuzz 27, Magnezone 28, Boltund 29, Raichu 30 | Paralysis and screen support into Volt Switch pressure and a fast closer. | Raichu: Air Balloon removes Ground immunity for one hit and forces the player to break it deliberately. | **Thin:** Diggersby is the one dependable ambient Ground family. |
| Erika | Bellossom 33, Roserade 33, Victreebel 34, Vileplume 35 | Sun, sleep and hazards create openings for two different attackers. | Vileplume: Coba Berry removes the certainty of one Flying knockout and can buy a Growth turn. | Satisfied by independent Flying, Ice and Fire lines. |
| Koga | Crobat 38, Weezing 38, Drapion 39, Toxtricity 39, Venomoth 40 | Tailwind and poison hazards support mixed breakers; Levitate prevents a Ground sweep. | Venomoth: Tinted Lens plus Quiver Dance invalidates passive type resistance as the whole answer. | Satisfied by a split Electric/Psychic/Ground composition. |
| Sabrina | Hatterene 42, Mr. Mime 43, Bronzong 43, Galarian Rapidash 44, Alakazam 45 | Trick Room speed inversion, disruption, a physical breaker and fast special closer. | Alakazam: Magic Guard removes Life Orb recoil. | **Conditional:** one ambient Dark/Steel/Bug plan exists; the mansion Ghost plan is not runtime-proven. |
| Blaine | Torkoal 47, Arcanine 48, Magcargo 48, Magmortar 49, Typhlosion 49, Charizard 50 | Drought and hazards amplify varied Fire offense rather than six copies of the same attack. | Charizard: Solar Power changes thresholds; Power Herb preserves one immediate Solar Beam if weather changes. | Satisfied by Water, Ground and Rock families. |
| Giovanni | Held at ace 55 | Doubles recommended; no team is generated until runtime proof. | A Ground-centred partner strategy, not a Ground-only list. | Direction is in `GIOVANNI_FORMAT.md`; roster waits on RCT doubles and multiplayer proof. |

Every leader has stable `pre`, `win`, and `loss` dialogue IDs. RCT does not accept those IDs in a team file: its dialogue is a separate `data/rctmod/dialogs/trainers/single/<id>.json` sidecar. `trainers.json` therefore retains the IDs as campaign metadata for the future compiler instead of inventing inline dialogue.

## Route trainers

The count rule is three required teaching roles, plus one trainer per full 1,000 walked blocks, plus a late-game density step. This yields 49 required trainers across 21,849 walked blocks. One optional Lake Viltri trainer brings the generated total to 50 without increasing critical-path density. Every route includes a one-Pokémon novice, a specialist or observer, and a trainer that rehearses the next major fight.

| Leg | Walked length | Level band | Count | Proposed `(x,z)` positions |
| --- | ---: | --- | ---: | --- |
| Pallet → Brock | 1,978 | 5–20 | 4 | `(1468,5018)`, `(1385,4714)`, `(1581,4291)`, `(1594,3867)` |
| Brock → Misty | 944 | 15–25 | 3 required + 1 optional | `(1762,3372)`, `(1773,3159)`, `(1774,2926)`; north-bank spur `(1604,3068)` |
| Misty → Surge | 2,120 | 20–30 | 5 | `(1747,2613)`, `(1876,2306)`, `(2034,1950)`, `(2199,1606)`, `(1978,1606)` |
| Surge → Erika | 3,453 | 25–35 | 6 | `(1900,1571)`, `(2370,1301)`, `(3072,1368)`, `(3226,1561)`, `(3570,1886)`, `(3993,1844)` |
| Erika → Koga | 1,051 | 30–40 | 4 | `(4383,1812)`, `(4358,1962)`, `(4366,2133)`, `(4434,2217)` |
| Koga → Sabrina | 1,944 | 35–45 | 5 | `(4923,2689)`, `(5146,2860)`, `(5453,2942)`, `(5754,3080)`, `(5962,3219)` |
| Sabrina → Blaine | 2,061 | 40–50 | 6 | `(6248,3546)`, `(6423,3711)`, `(6585,4056)`, `(6531,4358)`, `(6433,4606)`, `(6215,4833)` |
| Blaine → Giovanni | 3,050 | 45–55 | 7 | `(5853,5087)`, `(5661,5186)`, `(5295,5285)`, `(5018,5387)`, `(4615,5607)`, `(4158,6045)`, `(3894,6250)` |
| Victory Road | 5,248 | 50–60 | 9 | `(3643,6214)`, `(3601,5591)`, `(3839,4895)`, `(4174,4496)`, `(4293,4076)`, `(3952,3623)`, `(3615,3259)`, `(3541,2766)`, `(3598,2575)` |

The final data records the exact distance, progress fraction, route vertex or verified anchor, sampled elevation, lesson, archetype, generated team, AI and dialogue IDs for each trainer. Routes 1–3 also carry exact pre-, player-win-, and player-loss text. Their collision-aware build positions are in `EARLY_ROUTE_BUILD_HANDOFF.md`; none is placed in the world. Route 1's third trainer is a Vale Naturalist because the planned River of Shrews is dry terrain, while `route_02_shore_trainer_01` is explicitly optional and 184.1 blocks off its Route 2 anchor.

## Elite Four and Champion

All five are full six-member fights. Their shared level range makes the sequence a resource and team-depth test instead of five more level gates.

| Fight | Ceiling | Capstone identity | Ace |
| --- | ---: | --- | --- |
| Lorelei | 60 | Snow, hazards, speed denial and bulky special play test preservation. | Assault Vest Lapras uses Freeze-Dry to reverse the usual Water answer. |
| Bruno | 60 | Fake Out, removal, priority and physical tempo test positioning. | White Herb Hitmonlee clears Close Combat drops and activates Unburden. |
| Agatha | 60 | Burn, Taunt, Trick and priority test status and setup discipline. | Focus Sash Gengar guarantees a response unless hazards or priority are prepared. |
| Lance | 60 | Tailwind and varied Dragon-adjacent coverage test whether Ice/Fairy is a plan rather than a button. | Multiscale plus Weakness Policy Dragonite punishes an undisciplined super-effective opener. |
| Champion Blue | 62 | Mixed tempo, sleep, hazards, Intimidate, special setup and a physical pivot recombine the campaign's lessons. | White Herb Blastoise erases Shell Smash's defensive cost. |

## Plausible player teams

These are availability examples, not prescribed solutions.

| Gym | Plausible six | Fairness reading |
| ---: | --- | --- |
| 1 | Wingull, Krabby, Fomantis, Mareep, Pidgey, Bidoof | Several common super-effective answers. |
| 2 | Flaaffy, Pawmo, Lombre, Fomantis, Corphish, Noctowl | Independent Electric and Grass lines. |
| 3 | Diggersby, Hariyama, Skiddo, Lycanroc, Drampa, Lombre | Viable, but Diggersby carries too much of the immunity contract. |
| 4 | Scyther, Noctowl, Altaria, Bergmite, Cryogonal, Magby | Three distinct offensive routes. |
| 5 | Ampharos, Jynx, Diggersby, Bronzong, Quagsire, Lycanroc | Split offense covers Koga's immunities. |
| 6 | Skuntank, Bronzong, Heracross, Scyther, Toxtricity, Quagsire | One coherent ambient plan; optional mansion Ghosts cannot yet be guaranteed. |
| 7 | Whiscash, Lycanroc, Floatzel, Crawdaunt, Golduck, Altaria | Several geographically earned Fire answers. |
| 8 | Swanna, Seismitoad, Gogoat, Hariyama, Drapion, Cacturne | Broad availability, but no fairness verdict without Giovanni's roster and format. |

## Availability failures

- **Gym 3 now has two place-driven plans.** Bunnelby is on the critical path and the Wooper shore event offers a separate Ground immunity beside the route; Route 3 trainers teach both without adding Geodude to the ambient pool.
- **Gym 6 has one dependable ambient composition.** A second strong Ghost composition depends on the authored haunted-mansion Habitat, which is neither placed nor runtime-proven. Sabrina's roster uses no assumption that it exists, but the matchup remains conditional until that proof.
- **Gym 8 is deliberately unresolved.** Doubles is the recommended design, but Giovanni remains held until RCT lead order, targeting, switching, callbacks, and multiplayer isolation are proven. Generating a temporary team would hide that dependency.

No other gym failed the availability constraint at its new level ceiling.

## Validation boundary

The generator checks deterministic output, exact gym ace curve, one ace per concrete boss, team size, level bounds, move count, IV/EV bounds, exact target RCT AI keys, positive selection margin, ordered route pins, and that each required coordinate is an existing route-polyline vertex. Explicit optional placements must have stable IDs and a measured gap matching their route anchor. The thirteen revised early trainers pass the bounded `--check-early` generation check and use species available on their route or an earlier critical-path leg. Their revised move lists still need the Cobblemon 1.8/RCT resolution pass.

Full `--write`/`--check` currently stops on the stale Victory Road trainer pins: the trainer source still describes the former 5,248-block surface route while `data/routes.json` now contains the 666-block cave gauntlet. The bounded early mode exists so this pass does not weaken that failure or rewrite the later route; the Victory Road trainer owner must reconcile it separately.

RCT 0.19.0-beta accepts the emitted team fields: `identity`, `name`, `battleFormat`, `battleRules`, `ai`, `bag`, and `team`; Pokémon entries use its supported species, level, nature, ability, moveset and held-item fields. This is format evidence, not runtime evidence. AI behavior, item use, switching, multiplayer battles, dialogue sidecars and trainer spawning remain unproven until EXP-002.
