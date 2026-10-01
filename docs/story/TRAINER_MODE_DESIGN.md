# Trainer themes and difficulty modes

> **Superseded for Gym Challenge rosters, Oak selection, and Victory Road:** see
> `docs/story/CHALLENGE_GYM_DESIGN.md`. The route curriculum and reference-hack notes below remain useful;
> its older proportional Challenge gym tables do not.

**Status:** authored as generated campaign data; Normal is the generated default. Runtime mode selection and the revised leader installation are not implemented or proven.

## The two modes

Both modes use the same level caps: `20 / 25 / 30 / 35 / 40 / 45 / 50 / 55`. Challenge never gains levels merely to inflate damage.

- **Normal** teaches one readable interaction at a time. Teams are shorter, items mostly sustain, and every gym has at least two plausible answer lines from the established availability curve.
- **Challenge** now uses the six-member contract in `CHALLENGE_GYM_DESIGN.md`; the older proportional rule below is retained only as design history for the route curriculum.
- Route trainers use the same local species in both modes. Challenge gives the final teaching roles a fuller team and gives one Pokémon a modest held item. Trainer density does not increase.
- Each route teaches the next gym's engine in pieces. The gym combines those pieces once; it does not reveal an unrelated ruleset.

The target shape is **one engine plus one answer-check**. Weather, speed control, status, or field order is the engine. A berry, immunity, or guaranteed turn may check one obvious answer. Stacking weather, hazards, Focus Sash, setup, priority, and broad counter-coverage into one fight is outside the design.

## Route curriculum

| Route | Theme | What Normal teaches | Challenge version | Gym connection |
| --- | --- | --- | --- | --- |
| 1 — Pallet to Brock | **First Ascent** | Roles, switching, speed loss, and preserving two separate Rock answers. | One berry threshold; only the final rehearsal gains another member. | Brock's Rock Tomb and Sturdy Onix. |
| 2 — Brock to Misty | **Lake Tempo** | Taunt, recovery pressure, and separate Electric and Grass plans around Lake Viltri. | Sharper move choice and a fuller final rehearsal; no rain lock. | Misty's rain tempo and Lightning Rod interruption. |
| 3 — Misty to Surge | **Mountain Circuit** | Ground immunity, resistance, priority, and recovering after paralysis costs tempo. | A status-curing berry and fuller late teams; no hidden Ground counters. | Surge's paralysis and one-turn Balloon delay. |
| 4 — Surge to Erika | **Alpine Sunbreak** | Ice and Flying offense across the massif, then a setter and Fire beneficiary near Erika. | Late trainers combine weather with one beneficiary; no hazards or sleep chain. | Erika's sun engine. |
| 5 — Erika to Koga | **Venom Clock** | Direct poison creates a clock; Psychic needs a second line when Dark blocks it. | Fuller poison-payoff teams with one held threshold; still no hazard attrition. | Koga's poison into Venoshock. |
| 6 — Koga to Sabrina | **Wrong Clock** | Trick Room reverses speed; priority, bulk, and Dark immunity remain dependable. | The final rehearsals gain one slow beneficiary, without terrain or doubles. | Sabrina's slow phase and fast closer. |
| 7 — Sabrina to Blaine | **Weather Front** | Contest sun through Water, Ground, Rock, or replacement weather. | One extra weather beneficiary and one held threshold; Water is checked once. | Blaine's sun damage race. |
| 8 — Blaine to Giovanni | **Fault Lines** | Break Ground cores through split Water/Grass offense, immunity, Fighting, and priority. | Sand changes thresholds and final teams gain one member; no trapping or doubles. | Giovanni's sand and visible Rock Polish turn. |
| Victory Road | **League Examination** | Short fights test one known tool apiece before a final examiner. | Same density and caps; sharper teams rather than more attrition. | League-wide review. |

Routes 4–8 use explicit teams rather than allowing generic pool rotation to claim lessons the teams do not demonstrate. Victory Road now uses ten fixed cave stands in a four/rest/six sequence; see `CHALLENGE_GYM_DESIGN.md`.

## Gym 1 — Brock: Fault Line

Rock Tomb is the engine. The fight teaches that a super-effective move is an opening, not an automatic win.

| Mode | Team | Interaction |
| --- | --- | --- |
| Normal | Geodude 18, Bonsly 18, **Onix 20** | Rock Tomb taxes speed. Sturdy guarantees Onix one action; ordinary sustain leaves Water and Grass fully valid. |
| Challenge | Geodude 18, Bonsly 18, Cranidos 19, **Onix 20** | Cranidos exploits the speed tax. Weakness Policy Onix asks the player to preserve a second answer or priority. |

**Fair answers:** Wingull, Krabby, Staryu, Surskit, Buizel, Fomantis, and Gossifleur. Challenge changes sequencing, not the answer list.

## Gym 2 — Misty: Lake Tempo

Rain changes damage and speed. Starmie's Icy Wind keeps the fight about tempo after rain ends.

| Mode | Team | Interaction |
| --- | --- | --- |
| Normal | Horsea 22, Lombre 23, **Starmie 25** | Horsea starts five-turn rain, Lombre exploits it, and Starmie controls speed and recovery. |
| Challenge | Horsea 22, Lombre 23, Goldeen 24, **Starmie 25** | Lightning Rod Goldeen interrupts an Electric-only sweep. It carries no Grass counter, so the independent plan remains clean. |

**Fair answers:** Mareep/Flaaffy, Pawmi/Pawmo, Fomantis, Gossifleur, and Lotad/Lombre. Combee or Volbeat can pressure Lombre when Goldeen interrupts Electric offense.

## Gym 3 — Lt. Surge: Closed Circuit

Paralysis is the engine. The route teaches both a Ground plan and a plan that still functions after losing speed.

| Mode | Team | Interaction |
| --- | --- | --- |
| Normal | Electabuzz 27, Magneton 28, Boltund 29, **Raichu 30** | Paralysis and mixed physical/special pressure punish one-wall teams. Raichu has no Ground coverage. |
| Challenge | Electabuzz 27, Magneton 28, Boltund 29, **Raichu 30** | Electabuzz adds Light Screen. Air Balloon delays Ground for one hit; Raichu still has no Grass Knot. |

**Fair answers:** Diggersby, Wooper/Quagsire/Clodsire, Skiddo, and Makuhita/Hariyama. Magneton replaces the illegal level-28 Magnezone from the former roster.

## Gym 4 — Erika: Glasshouse Sun

Sun is the only engine. The former sleep, hazards, Focus Sash, Life Orb, sun, and setup pile has been removed.

| Mode | Team | Interaction |
| --- | --- | --- |
| Normal | Bellossom 33, Roserade 33, Victreebel 34, **Vileplume 35** | Bellossom starts sun; Victreebel and Vileplume exploit it. Coba Berry buys the ace one turn against Flying. |
| Challenge | Bellossom 33, Roserade 33, Tangrowth 34, Victreebel 34, **Vileplume 35** | Heat Rock and Tangrowth deepen the same public sun plan. No sleep chain, hazards, or second counter berry appears. |

**Fair answers:** Scyther, Noctowl, Altaria, Bergmite, Cryogonal, and Jynx. Coba delays Flying once; Ice and Fire are untouched.

## Gym 5 — Koga: Venom Clock

Direct poison is the engine. Venoshock rewards Koga for maintaining the condition, while Drapion checks an all-Psychic plan.

| Mode | Team | Interaction |
| --- | --- | --- |
| Normal | Crobat 38, Weezing 38, Toxtricity 39, Drapion 40, **Venomoth 40** | Poison creates the clock; Venoshock cashes it in. Tinted Lens prevents passive resistance from being the whole answer. |
| Challenge | Crobat 38, Weezing 38, Toxtricity 39, Dragalge 39, Drapion 40, **Venomoth 40** | Dragalge is another payoff user. Hazards, Tailwind, Quiver Dance, Focus Sash, Shuca Berry, and Throat Spray stay out. |

**Fair answers:** Diggersby or Quagsire plus Ampharos or Lycanroc; or Jynx/Hattrem/Bronzong with Ground reserved for Drapion.

## Gym 6 — Sabrina: Wrong Clock

Trick Room creates a slow phase; Alakazam closes when the clock returns to normal.

| Mode | Team | Interaction |
| --- | --- | --- |
| Normal | Hatterene 42, Slowbro 43, Bronzong 43, Exeggutor 44, **Alakazam 45** | Hatterene and Bronzong establish the slow phase. Alakazam is deliberately fast and carries no Fairy or Fighting coverage. |
| Challenge | Hatterene 42, Slowbro 43, Bronzong 43, Exeggutor 44, Reuniclus 44, **Alakazam 45** | Reuniclus adds a durable beneficiary. The fight gains no Psychic Terrain, doubles rule, or second Dark check. |

**Fair answers:** Skuntank, Absol, or Nuzleaf with Bronzong support; or Scyther/Heracross/Masquerain/Yanma backed by bulk or priority. Mansion Ghosts remain outside the fairness contract until their Habitat is proven.

## Gym 7 — Blaine: Pressure Front

Sun is the engine. It makes Water less automatic while leaving Ground and Rock as independent plans.

| Mode | Team | Interaction |
| --- | --- | --- |
| Normal | Torkoal 47, Arcanine 48, Magcargo 48, Typhlosion 49, **Charizard 50** | Arcanine is the one Water check. Solar Power Charizard creates a visible damage race without Solar Beam. |
| Challenge | Torkoal 47, Arcanine 48, Magcargo 48, Magmortar 49, Typhlosion 49, **Charizard 50** | Magmortar becomes the sole Water check; Magcargo gains a visible Shell Smash plus White Herb turn. No hazards or Scarf Eruption. |

**Fair answers:** Whiscash, Lycanroc, Floatzel, Crawdaunt, Golduck, and other locally earned Water/Ground/Rock combinations.

## Gym 8 — Giovanni: Fault Command

Giovanni is authored as singles until RCT doubles and multiplayer isolation are proven. Sand changes thresholds; it does not define six copies of one attacker.

| Mode | Team | Interaction |
| --- | --- | --- |
| Normal | Hippowdon 52, Persian 52, Mudsdale 53, Nidoqueen 53, Krookodile 54, **Rhyperior 55** | Persian breaks tempo, Mudsdale anchors physical offense, and Rhyperior advertises Rock Polish before it attacks. |
| Challenge | Same species and levels | Smooth Rock lengthens sand, Persian gains Taunt, and Rhyperior gains one disclosed Rindo Berry. No hazards, trapping, or hidden doubles conversion. |

**Fair answers:** split Water/Grass offense; or Ground immunity plus Fighting and priority. The pool includes Golduck, Floatzel, Clawitzer, Cacturne, Lurantis, Gogoat, Swanna, Kilowattrel, Hariyama, and Heracross.

## What came from the reference hacks

The local workbooks in `docs/rom_hack_docs/` are reference material, not roster templates:

- **Radical Red, Kanto Leaders:** one guaranteed action on Brock's Onix, Misty's speed control and sustain, Surge's terrain-led team, Blaine's coherent sun engine. Cobblers keeps the readable interaction and removes the surrounding premium-item stack.
- **Emerald Imperium, Hoenn Gyms Only:** Wattson's single Ground-immunity interruption and Flannery's setter-to-beneficiary sequence. Cobblers uses one interruption rather than turning every member into coverage.
- **Inclement Emerald, Gym Leaders:** useful examples of unified Volt Switch and weather teams, and a clear warning about giving every member the same oppressive tool.
- **Null, Roxanne Split:** ordinary route trainers demonstrate sun and Trick Room before bosses. Cobblers copies that teaching structure at campaign-appropriate levels.
- **Trainer Battles, Brawly and Victory Road splits:** direct poison into payoff and a clear speed-tax/breaker/priority sequence. Cobblers distributes those lessons across short trainers instead of one attrition wall.

## Runtime and data boundary

- `docs/story/TRAINER_RULES.json` is the editable source. `data/trainers.json` is generated.
- Every active gym and Route 1–9 trainer contains `modes.normal` and `modes.challenge`. The legacy top-level `team` and `rct` mirror Normal so existing placement tooling remains safe.
- Challenge selection is intended to be one server-wide campaign setting. No selector or RCT sidecar compiler currently switches variants.
- AI switching, weather/support move choice, held-item activation, Trick Room sequencing, and two-player isolation remain runtime tests. No design here depends on successful pivot loops.
- Victory Road's generated records now use the built ten-fight cave network. World placement and per-player defeat-state integration remain unimplemented.
