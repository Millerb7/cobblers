# Gym battle simulation

**Status:** a structural filter, run 2026-09-24 from committed data and the Cobblemon 1.8 jar. No server, no
Minecraft, no play. It is not a verdict on any fight; see *What this cannot tell you*.

Run it with `python tools/battle_sim.py`. Every number below is reproducible from that command.

## What is being simulated

**Our own rosters, not the stock pack.** `data/trainers.json` carries authored gym leaders with species,
movesets, abilities, held items, natures and levels: 7 of the 8 are `status: authored`. **Gym 8 (Giovanni) is
`status: held` with an empty team**, so it cannot be simulated at all and is excluded from every number here.

The player is capped at exactly the gym's ace level, which is what
`base-pack/cobbleverse/config/rctmod-server.toml` produces: `initialLevelCap 20`, `relativeLevelCap 5`, so the
cap after each gym is that gym's top level plus 5, which is the next gym's ace.

Candidate Pokemon come from `docs/story/AVAILABILITY.md` — what the curated route pools put in front of a player
before that gym — evolved as far as their level takes them and given the best four damaging moves they learn by
level.

## The headline numbers

| Gym | Leader | Cap | Candidates | Sweep 1v1 | Beat the ace | Families that can hit the ace super-effectively | Informed six | Walked six |
|---|---|---|---|---|---|---|---|---|
| 1 | Brock (Rock) | 20 | 19 | 6 (32%) | 8 | 12 | WIN, 1 lost | LOSS, 3 of 4 |
| 2 | Misty (Water) | 25 | 24 | 1 (4%) | 1 | 12 | WIN, 3 lost | WIN, 3 lost |
| 3 | Surge (Electric) | 30 | 36 | 3 (8%) | 9 | **1** | WIN, 1 lost | LOSS, 3 of 4 |
| 4 | Erika (Grass) | 35 | 47 | 4 (9%) | 5 | 17 | WIN, 1 lost | LOSS, 3 of 4 |
| 5 | Koga (Poison) | 40 | 63 | 1 (2%) | 23 | 18 | WIN, 4 lost | WIN, 4 lost |
| 6 | Sabrina (Psychic) | 45 | 75 | 1 (1%) | 4 | 12 | WIN, 2 lost | LOSS, 4 of 5 |
| 7 | Blaine (Fire) | 50 | 88 | 0 (0%) | 8 | 24 | **LOSS, 5 of 6** | LOSS, 3 of 6 |
| 8 | Giovanni (Ground) | — | — | — | — | — | no roster | no roster |

*Sweep 1v1* is how many catchable species beat every member of the leader's team one on one from full health.
*Informed six* is a team of the six species this simulation itself ranks highest — a player who looked the answer
up. *Walked six* is the six earliest-available species, one per family — a player who kept what they walked past.
Both run the leader's team in order with no switching, no healing and no items, damage carried forward on both
sides.

## What it says

**Difficulty rises monotonically and the curve is clean.** The share of catchable species that can sweep a gym
falls 32% → 4% → 8% → 9% → 2% → 1% → 0%. Nothing is out of order.

**Gym 7 (Blaine) is the hard wall, and it is right on the boundary.** It is the only gym the informed six lose,
and they lose it having downed 5 of 6 with the last foe on 16% health. That result is fragile in both directions:
at perfect IVs on both sides the informed six win (losing 5), and with evolution stones allowed they win losing 2.
Six leader Pokemon against a capped team with no healing is the thing to look at.

**Gym 3 (Surge) is the narrowest by type and is NOT thin in practice.** Every one of Surge's four is Electric, so
the whole gym is weak to Ground and nothing else. Against the route pools alone there is exactly one Ground
family — Bunnelby to Diggersby, first wild L21, common at `foothill_woods`. That is the fault
`AVAILABILITY.md` already flags. But it is not the only answer: nine catchable species beat Raichu, and
Ampharos, Hariyama and Diggersby each sweep the whole gym, because Electric is poor into Ground, Grass and
Normal bulk and Raichu is frail. **And see the waterway finding below: there are actually three Ground families,
not one.**

**No other gym is narrow the same way.** The next-narrowest are Misty, Sabrina and Brock at 12 families each,
which is comfortable. Surge's 1 is an outlier by a factor of twelve.

**No gym is trivial**, on the walked-six measure. The two the walked six win — Misty and Koga — both cost 3 and 4
Pokemon of 6.

**Nothing has no answer.** Every simulated gym has at least one species that beats its ace, and every ace can be
brought down by a single Pokemon in one run. Gym 8 is the only "no viable answer", and only because it has no
roster to answer.

## The starter matters more than it should

Beating the leader's team one on one, by starter, across the seven simulated gyms:

| Starter | Final form at cap | G1 | G2 | G3 | G4 | G5 | G6 | G7 | total |
|---|---|---|---|---|---|---|---|---|---|
| Mudkip | Swampert | 4/4 | 2/4 | 4/4 | 0/4 | 5/5 | 5/5 | 5/6 | **25** |
| Squirtle | Blastoise | 4/4 | 3/4 | 0/4 | 0/4 | 3/5 | 4/5 | 3/6 | 17 |
| Charmander | Charizard | 1/4 | 1/4 | 2/4 | 3/4 | 5/5 | 3/5 | 1/6 | 16 |
| Bulbasaur | Venusaur | 4/4 | 3/4 | 2/4 | 1/4 | 2/5 | 2/5 | 1/6 | 15 |
| Torchic | Blaziken | 3/4 | 1/4 | 1/4 | 2/4 | 3/5 | 1/5 | 4/6 | 15 |
| Totodile | Feraligatr | 4/4 | 3/4 | 0/4 | 0/4 | 1/5 | 3/5 | 2/6 | 13 |
| Chikorita | Meganium | 4/4 | 3/4 | 1/4 | 1/4 | 0/5 | 3/5 | 1/6 | 13 |
| Treecko | Sceptile | 4/4 | 3/4 | 2/4 | 1/4 | 0/5 | 2/5 | 0/6 | 12 |
| Cyndaquil | Typhlosion | 0/4 | 0/4 | 0/4 | 2/4 | 5/5 | 3/5 | 2/6 | 12 |

Mudkip is worth roughly twice Cyndaquil or Treecko over the run, and it is the only starter that answers Surge
on its own (Swampert is Water/Ground: Electric-immune and super-effective back). Cyndaquil contributes nothing at
all to the first three gyms. The starter is not a tiebreaker here; it is a difficulty setting.

`starters.json` in the pack offers all nine but sets `useConfigStarters: false`, so what a player is actually
offered in game has not been checked and may differ.

## Finding: AVAILABILITY.md omits the waterway pools

The compiled pack ships route pools, sub-region pools, habitat pools **and waterway pools**.
`docs/story/AVAILABILITY.md` says in its own header that it covers the curated route compilation only, so the
waterways are missing from every one of its tables.

There is one waterway pool, `mt_clay_outflow`, spanning x704-1999, z1760-2111. Route 3 (Misty to Surge) spans
x1544-2287, z1408-2855: **they overlap**, so a player walking to the third gym walks along it. It carries, at
levels 24-30:

| Species | Types | Against Surge |
|---|---|---|
| Wooper → Quagsire (L20) | Water/Ground | beats 4 of 4 one on one; alone, downs 2 of 4 in a single run |
| Quagsire (spawns directly) | Water/Ground | the same |
| Clodsire | Poison/Ground | beats 3 of 4 |

Ground types are immune to Electric outright, so any of these walls the entire gym. **Surge has three Ground
families available, not one** — the thinness is in the document, not in the world. `AVAILABILITY.md` should be
regenerated to include waterway pools before its assessments are trusted, and `GYM_SUFFICIENCY_AUDIT.md`'s
verdict on Gym 3 rests on the same omission.

## A defect found and fixed in the tool

The gendered Nidoran rows of `AVAILABILITY.md` did not reach a species: `key()` stripped the ♀ and ♂ signs, which
collapsed two species onto one id the jar does not have, and the row regex could not match the signs at all. The
candidate was then dropped with no message, so a shrinking pool looked exactly like a narrow one -- the very thing
this tool exists to tell apart. All three are fixed: the signs map to "f" and "m", the regex accepts them, and an
unresolved row is now counted and named in the report. No number above changed, because both rows belonged only to
Gym 8, which has no roster to fight.

## What this cannot tell you

The model is two Pokemon at full health hitting each other with their best damaging move until one faints.

- **No TMs.** The player's moves are the level-up list only, while every leader carries a hand-picked moveset
  including TM moves. TMCraft is in the pack. This biases the whole simulation **against the player**, and by a
  lot: Diggersby fights Surge here with Dig, Tackle and Double Kick.
- **No items, no healing, no revives.** A player with twenty potions is not modelled. Gym 7's loss is by 16% of
  one Pokemon; one potion reverses it.
- **No switching**, so a team that wins by pivoting is invisible, and so is a gym that punishes pivoting.
- **No status moves at all.** Every leader's hazards, screens, boosts and debuffs are dropped. Stealth Rock,
  Scary Face, Tearful Look and Protect are worth nothing here and are worth a great deal in play. This biases
  **towards the player**, in the opposite direction to the TM gap.
- **No secondary effects**: no flinch, burn, paralysis, confusion or critical hits.
- **Abilities**: only Sturdy, Levitate, Mold Breaker, Thick Fat and Filter are modelled. Intimidate, Drought,
  Chlorophyll, Swift Swim, Static, Lightning Rod and Analytic all do nothing here.
- **Held items**: only Eviolite, Life Orb, Muscle Band, Choice Band, Assault Vest and the resist berries are
  modelled. Focus Sash, Weakness Policy, Oran Berry, Sitrus Berry and Leftovers are not, which **understates
  every leader that holds one** — and seven leader Pokemon hold a Focus Sash.
- **IVs 15, EVs 0 on both sides.** At 31 the picture moves: Gym 7's informed six flip from loss to win, Gym 6's
  cost rises from 2 to 5.
- **Damage is the average roll** (×0.925) and is multiplied by accuracy rather than missing.
- **It says nothing about whether a fight is fun**, how long it takes, whether the answer is discoverable, or
  whether a player would enjoy finding it.
- **No spawn pool has been runtime-proven.** Availability rests on compiled data, not on a caught Pokemon.

Read it for shape: how many answers a gym has, how narrow the narrowest is, and which gyms change character
under a different assumption. Not for the result of any single battle.

## The run

```
Cobblemon jar: Cobblemon-fabric-1.8.0+1.21.1.jar
species 1025, moves 930, types 18; IVs 15, EVs 0, level only evolutions
level cap from rctmod-server.toml: initial 20, relative +5

====================================================================================================
GYM 1  kanto_brock (Rock)   leader status: authored
  cap 20, roster: geodude L18, bonsly L18, cranidos L19, onix L20
  19 catchable candidates: 6 beat the whole roster 1v1, 4 beat some, 9 beat none
  beat the ace (onix): 8
  the ace is weak to: fighting, grass, ground, ice, steel, water; 12 catchable families can attack on one of those types
    bibarel (normal/water, first wild L9), buizel (water, first wild L9), eldegoss (grass, first wild L12), shellder (water, first wild L7), staryu (water, first wild L7), krabby (water, first wild L7), fomantis (grass, first wild L12), pawmo (electric/fighting, first wild L9), surskit (bug/water, first wild L9), applin (grass/dragon, first wild L12)
  most health taken off the ace by one Pokemon: staryu 100%, shellder 100%, noctowl 100%, krabby 100%, fomantis 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team bibarel, buizel, eldegoss, noctowl, shellder, staryu
      WIN -- 4 of 4 leader Pokemon downed, 1 player Pokemon lost
  gauntlet, walked   team flaaffy, pidgeotto, raticate, wooloo, krabby, shellder
      LOSS -- 3 of 4 leader Pokemon downed, 6 player Pokemon lost, next foe on 2% health
    Bidoof       as bibarel      normal/water     4/4  first wild L9   geodude,bonsly,cranidos,onix
    Buizel       as buizel       water            4/4  first wild L9   geodude,bonsly,cranidos,onix
    Gossifleur   as eldegoss     grass            4/4  first wild L12  geodude,bonsly,cranidos,onix
    Hoothoot     as noctowl      normal/flying    4/4  first wild L12  geodude,bonsly,cranidos,onix
    Shellder     as shellder     water            4/4  first wild L7   geodude,bonsly,cranidos,onix
    Staryu       as staryu       water            4/4  first wild L7   geodude,bonsly,cranidos,onix
    Krabby       as krabby       water            3/4  first wild L7   geodude,bonsly,onix
    Fomantis     as fomantis     grass            2/4  first wild L12  geodude,onix

====================================================================================================
GYM 2  kanto_misty (Water)   leader status: authored
  cap 25, roster: horsea L22, lombre L23, goldeen L24, starmie L25
  24 catchable candidates: 1 beat the whole roster 1v1, 21 beat some, 2 beat none
  beat the ace (starmie): 1
  the ace is weak to: bug, dark, electric, ghost, grass; 12 catchable families can attack on one of those types
    eldegoss (grass, first wild L12), deerling (normal/grass, first wild L9), flaaffy (electric, first wild L5), illumise (bug, first wild L18), kilowattrel (electric/flying, first wild L7), masquerain (bug/flying, first wild L9), pawmo (electric/fighting, first wild L9), volbeat (bug, first wild L18), combee (bug/flying, first wild L12), fomantis (grass, first wild L12)
  most health taken off the ace by one Pokemon: eldegoss 100%, illumise 98%, noctowl 84%, volbeat 73%, dubwool 69%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team eldegoss, bibarel, deerling, dubwool, flaaffy, illumise
      WIN -- 4 of 4 leader Pokemon downed, 3 player Pokemon lost
  gauntlet, walked   team flaaffy, pidgeotto, raticate, dubwool, krabby, shellder
      WIN -- 4 of 4 leader Pokemon downed, 3 player Pokemon lost
    Gossifleur   as eldegoss     grass            4/4  first wild L12  horsea,lombre,goldeen,starmie
    Bidoof       as bibarel      normal/water     3/4  first wild L9   horsea,lombre,goldeen
    Deerling     as deerling     normal/grass     3/4  first wild L9   horsea,lombre,goldeen
    Wooloo       as dubwool      normal           3/4  first wild L5   horsea,lombre,goldeen
    Mareep       as flaaffy      electric         3/4  first wild L5   horsea,lombre,goldeen
    Illumise     as illumise     bug              3/4  first wild L18  horsea,lombre,goldeen
    Wattrel      as kilowattrel  electric/flying  3/4  first wild L7   horsea,lombre,goldeen
    Surskit      as masquerain   bug/flying       3/4  first wild L9   horsea,lombre,goldeen

====================================================================================================
GYM 3  kanto_ltsurge (Electric)   leader status: authored
  cap 30, roster: electabuzz L27, magnezone L28, boltund L29, raichu L30
  36 catchable candidates: 3 beat the whole roster 1v1, 7 beat some, 26 beat none
  beat the ace (raichu): 9
  the ace is weak to: ground; 1 catchable families can attack on one of those types
    diggersby (normal/ground, first wild L21)
  most health taken off the ace by one Pokemon: skiddo 100%, pawmo 100%, heracross 100%, hariyama 100%, eldegoss 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team ampharos, diggersby, hariyama, dubwool, heracross, pawmo
      WIN -- 4 of 4 leader Pokemon downed, 1 player Pokemon lost
  gauntlet, walked   team ampharos, pidgeotto, raticate, dubwool, kingler, shellder
      LOSS -- 3 of 4 leader Pokemon downed, 6 player Pokemon lost, next foe on 47% health
    Mareep       as ampharos     electric         4/4  first wild L5   electabuzz,magnezone,boltund,raichu
    Bunnelby     as diggersby    normal/ground    4/4  first wild L21  electabuzz,magnezone,boltund,raichu
    Makuhita     as hariyama     fighting         4/4  first wild L22  electabuzz,magnezone,boltund,raichu
    Wooloo       as dubwool      normal           3/4  first wild L5   electabuzz,boltund,raichu
    Heracross    as heracross    bug/fighting     3/4  first wild L21  electabuzz,magnezone,raichu
    Pawmi        as pawmo        electric/fighting 3/4  first wild L9   electabuzz,magnezone,raichu
    Drampa       as drampa       normal/dragon    2/4  first wild L24  electabuzz,raichu
    Gossifleur   as eldegoss     grass            2/4  first wild L12  electabuzz,raichu

====================================================================================================
GYM 4  kanto_erika (Grass)   leader status: authored
  cap 35, roster: bellossom L33, roserade L33, victreebel L34, vileplume L35
  47 catchable candidates: 4 beat the whole roster 1v1, 20 beat some, 23 beat none
  beat the ace (vileplume): 5
  the ace is weak to: fire, flying, ice, psychic; 17 catchable families can attack on one of those types
    cryogonal (ice, first wild L27), jynx (ice/psychic, first wild L27), noctowl (normal/flying, first wild L12), bronzong (steel/psychic, first wild L28), kilowattrel (electric/flying, first wild L7), scyther (bug/flying, first wild L21), altaria (dragon/flying, first wild L22), masquerain (bug/flying, first wild L9), pelipper (water/flying, first wild L7), rufflet (normal/flying, first wild L22)
  most health taken off the ace by one Pokemon: noctowl 100%, noctowl 100%, jynx 100%, cryogonal 100%, bronzong 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team cryogonal, jynx, noctowl, bronzong, kilowattrel, scyther
      WIN -- 4 of 4 leader Pokemon downed, 1 player Pokemon lost
  gauntlet, walked   team ampharos, pidgeotto, raticate, dubwool, kingler, shellder
      LOSS -- 3 of 4 leader Pokemon downed, 6 player Pokemon lost, next foe on 37% health
    Cryogonal    as cryogonal    ice              4/4  first wild L27  bellossom,roserade,victreebel,vileplume
    Smoochum     as jynx         ice/psychic      4/4  first wild L27  bellossom,roserade,victreebel,vileplume
    Hoothoot     as noctowl      normal/flying    4/4  first wild L12  bellossom,roserade,victreebel,vileplume
    Noctowl      as noctowl      normal/flying    4/4  first wild L21  bellossom,roserade,victreebel,vileplume
    Bronzor      as bronzong     steel/psychic    3/4  first wild L28  bellossom,roserade,vileplume
    Wattrel      as kilowattrel  electric/flying  3/4  first wild L7   bellossom,roserade,victreebel
    Scyther      as scyther      bug/flying       3/4  first wild L21  bellossom,roserade,victreebel
    Swablu       as altaria      dragon/flying    2/4  first wild L22  bellossom,victreebel

====================================================================================================
GYM 5  kanto_koga (Poison)   leader status: authored
  cap 40, roster: crobat L38, weezing L38, drapion L39, toxtricity L39, venomoth L40
  63 catchable candidates: 1 beat the whole roster 1v1, 39 beat some, 23 beat none
  beat the ace (venomoth): 23
  the ace is weak to: fire, flying, psychic, rock; 18 catchable families can attack on one of those types
    altaria (dragon/flying, first wild L22), bronzong (steel/psychic, first wild L28), jynx (ice/psychic, first wild L27), staraptor (normal/flying, first wild L32), kilowattrel (electric/flying, first wild L7), noctowl (normal/flying, first wild L12), pidgeot (normal/flying, first wild L5), emolga (electric/flying, first wild L30), lairon (steel/rock, first wild L28), masquerain (bug/flying, first wild L9)
  most health taken off the ace by one Pokemon: volbeat 100%, ursaring 100%, staraptor 100%, staraptor 100%, skuntank 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team drampa, altaria, bronzong, cryogonal, jynx, quagsire
      WIN -- 5 of 5 leader Pokemon downed, 4 player Pokemon lost
  gauntlet, walked   team ampharos, pidgeot, raticate, dubwool, kingler, shellder
      WIN -- 5 of 5 leader Pokemon downed, 4 player Pokemon lost
    Drampa       as drampa       normal/dragon    5/5  first wild L24  crobat,weezing,drapion,toxtricity,venomoth
    Swablu       as altaria      dragon/flying    4/5  first wild L22  crobat,weezing,toxtricity,venomoth
    Bronzor      as bronzong     steel/psychic    4/5  first wild L28  crobat,weezing,toxtricity,venomoth
    Cryogonal    as cryogonal    ice              4/5  first wild L27  crobat,weezing,toxtricity,venomoth
    Smoochum     as jynx         ice/psychic      4/5  first wild L27  crobat,weezing,toxtricity,venomoth
    Wooper       as quagsire     water/ground     4/5  first wild L34  crobat,weezing,toxtricity,venomoth
    Starly       as staraptor    normal/flying    4/5  first wild L32  crobat,weezing,drapion,venomoth
    Staravia     as staraptor    normal/flying    4/5  first wild L32  crobat,weezing,drapion,venomoth

====================================================================================================
GYM 6  kanto_sabrina (Psychic)   leader status: authored
  cap 45, roster: hatterene L42, mrmime L43, bronzong L43, rapidash L44, alakazam L45
  75 catchable candidates: 1 beat the whole roster 1v1, 47 beat some, 27 beat none
  beat the ace (alakazam): 4
  the ace is weak to: bug, dark, ghost; 12 catchable families can attack on one of those types
    scyther (bug/flying, first wild L21), skuntank (poison/dark, first wild L32), crawdaunt (water/dark, first wild L18), heracross (bug/fighting, first wild L21), masquerain (bug/flying, first wild L9), volbeat (bug, first wild L18), illumise (bug, first wild L18), spidops (bug, first wild L34), yanma (bug/flying, first wild L39), combee (bug/flying, first wild L12)
  most health taken off the ace by one Pokemon: ursaring 100%, skuntank 100%, scyther 100%, sawsbuck 100%, masquerain 98%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team ursaring, floatzel, scyther, skuntank, staraptor, whiscash
      WIN -- 5 of 5 leader Pokemon downed, 2 player Pokemon lost
  gauntlet, walked   team ampharos, pidgeot, raticate, dubwool, kingler, shellder
      LOSS -- 4 of 5 leader Pokemon downed, 6 player Pokemon lost, next foe on 100% health
    Teddiursa    as ursaring     normal           5/5  first wild L30  hatterene,mrmime,bronzong,rapidash,alakazam
    Buizel       as floatzel     water            4/5  first wild L9   hatterene,mrmime,bronzong,rapidash
    Scyther      as scyther      bug/flying       4/5  first wild L21  hatterene,mrmime,bronzong,alakazam
    Stunky       as skuntank     poison/dark      4/5  first wild L32  hatterene,mrmime,bronzong,alakazam
    Starly       as staraptor    normal/flying    4/5  first wild L32  hatterene,mrmime,bronzong,rapidash
    Staravia     as staraptor    normal/flying    4/5  first wild L32  hatterene,mrmime,bronzong,rapidash
    Barboach     as whiscash     water/ground     4/5  first wild L37  hatterene,mrmime,bronzong,rapidash
    Aron         as aggron       steel/rock       3/5  first wild L28  hatterene,mrmime,rapidash

====================================================================================================
GYM 7  kanto_blaine (Fire)   leader status: authored
  cap 50, roster: torkoal L47, arcanine L48, magcargo L48, magmortar L49, typhlosion L49, charizard L50
  88 catchable candidates: 0 beat the whole roster 1v1, 62 beat some, 26 beat none
  beat the ace (charizard): 8
  the ace is weak to: electric, rock, water; 24 catchable families can attack on one of those types
    floatzel (water, first wild L9), quagsire (water/ground, first wild L34), whiscash (water/ground, first wild L37), golduck (water, first wild L39), seismitoad (water/ground, first wild L37), aggron (steel/rock, first wild L28), ampharos (electric, first wild L5), kilowattrel (electric/flying, first wild L7), kingler (water, first wild L7), swanna (water/flying, first wild L39)
  most health taken off the ace by one Pokemon: kilowattrel 100%, hatterene 100%, hatterene 100%, dubwool 100%, ampharos 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team floatzel, hariyama, quagsire, whiscash, golduck, seismitoad
      LOSS -- 5 of 6 leader Pokemon downed, 6 player Pokemon lost, next foe on 16% health
  gauntlet, walked   team ampharos, pidgeot, raticate, dubwool, kingler, shellder
      LOSS -- 3 of 6 leader Pokemon downed, 6 player Pokemon lost, next foe on 36% health
    Buizel       as floatzel     water            5/6  first wild L9   torkoal,arcanine,magcargo,magmortar,typhlosion
    Makuhita     as hariyama     fighting         5/6  first wild L22  torkoal,arcanine,magcargo,magmortar,typhlosion
    Wooper       as quagsire     water/ground     5/6  first wild L34  torkoal,arcanine,magcargo,magmortar,typhlosion
    Barboach     as whiscash     water/ground     5/6  first wild L37  torkoal,arcanine,magcargo,magmortar,typhlosion
    Psyduck      as golduck      water            4/6  first wild L39  torkoal,magcargo,magmortar,typhlosion
    Golduck      as golduck      water            4/6  first wild L39  torkoal,magcargo,magmortar,typhlosion
    Tympole      as seismitoad   water/ground     4/6  first wild L37  torkoal,arcanine,magcargo,typhlosion
    Palpitoad    as seismitoad   water/ground     4/6  first wild L37  torkoal,arcanine,magcargo,typhlosion

====================================================================================================
GYM 8  kanto_giovanni (Ground)   leader status: held
  NO ROSTER IN data/trainers.json. Nothing to simulate.

====================================================================================================
STARTERS
  starter       G1  G2  G3  G4  G5  G6  G7
  charmander    1/4  1/4  2/4  3/4  5/5  3/5  1/6   (final form at cap: charizard)
  squirtle      4/4  3/4  0/4  0/4  3/5  4/5  3/6   (final form at cap: blastoise)
  bulbasaur     4/4  3/4  2/4  1/4  2/5  2/5  1/6   (final form at cap: venusaur)
  cyndaquil     0/4  0/4  0/4  2/4  5/5  3/5  2/6   (final form at cap: typhlosion)
  totodile      4/4  3/4  0/4  0/4  1/5  3/5  2/6   (final form at cap: feraligatr)
  chikorita     4/4  3/4  1/4  1/4  0/5  3/5  1/6   (final form at cap: meganium)
  torchic       3/4  1/4  1/4  2/4  3/5  1/5  4/6   (final form at cap: blaziken)
  mudkip        4/4  2/4  4/4  0/4  5/5  5/5  5/6   (final form at cap: swampert)
  treecko       4/4  3/4  2/4  1/4  0/5  2/5  0/6   (final form at cap: sceptile)
```
