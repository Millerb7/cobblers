# Gym battle simulation

**Challenge snapshot, 2026-09-29.** This report was produced by loading each
`modes.challenge` payload directly into the existing deterministic simulator at
cap offset zero. `tools/battle_sim.py` remains Normal-only because this task's
write scope excludes `tools/`; the snapshot is therefore evidence, not a
currently reproducible CLI mode. Runtime battle behavior remains unverified.

```
Cobblemon jar: Cobblemon-fabric-1.8.0+1.21.1.jar
trainer mode: challenge
species 1025, moves 930, types 18; IVs 15, EVs 0, level only evolutions
level cap: initial 20, relative +0 -- so the player meets each gym at its ace +0

====================================================================================================
GYM 1  kanto_brock (Rock)   leader status: authored
  cap 20, roster: geodude L19, lileep L19, dwebble L19, cranidos L19, bonsly L20, onix L20
  21 catchable candidates: 2 beat the whole roster 1v1, 12 beat some, 7 beat none
  beat the ace (onix): 9
  the ace is weak to: fighting, grass, ground, ice, steel, water; 14 catchable families can attack on one of those types
    gyarados (water/flying, first wild L9), bibarel (normal/water, first wild L9), goldeen (water, first wild L9), shellder (water, first wild L7), staryu (water, first wild L7), buizel (water, first wild L9), eldegoss (grass, first wild L12), krabby (water, first wild L7), surskit (bug/water, first wild L9), fomantis (grass, first wild L7)
  most health taken off the ace by one Pokemon: staryu 100%, shellder 100%, noctowl 100%, krabby 100%, gyarados 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team gyarados, noctowl, bibarel, goldeen, shellder, staryu
      no switching    WIN  -- 6 of 6 downed, 3 lost
  gauntlet, walked   team flaaffy, pidgeotto, raticate, wooloo, applin, combee
      no switching    LOSS -- 2 of 6 downed, 6 lost, next foe on 75%
  authored line: eldegoss, krabby, staryu, wingull, surskit, buizel
      no switching    WIN  -- 6 of 6 downed, 2 lost
      discoverability: moderate: Route 1 teaches Rock Tomb and supplies both Grass and Water; Lileep visibly signals that Water alone is insufficient.
    magikarp     as gyarados     water/flying     6/6  first wild L9   geodude,lileep,dwebble,cranidos,bonsly,onix
    hoothoot     as noctowl      normal/flying    6/6  first wild L7   geodude,lileep,dwebble,cranidos,bonsly,onix
    bidoof       as bibarel      normal/water     5/6  first wild L9   geodude,dwebble,cranidos,bonsly,onix
    goldeen      as goldeen      water            5/6  first wild L9   geodude,dwebble,cranidos,bonsly,onix
    shellder     as shellder     water            5/6  first wild L7   geodude,dwebble,cranidos,bonsly,onix
    staryu       as staryu       water            5/6  first wild L7   geodude,dwebble,cranidos,bonsly,onix
    buizel       as buizel       water            4/6  first wild L9   geodude,dwebble,cranidos,onix
    gossifleur   as eldegoss     grass            4/6  first wild L12  geodude,cranidos,bonsly,onix

====================================================================================================
GYM 2  kanto_misty (Water)   leader status: authored
  cap 25, roster: pelipper L23, lombre L24, goldeen L24, barboach L24, floatzel L25, starmie L25
  28 catchable candidates: 0 beat the whole roster 1v1, 24 beat some, 4 beat none
  beat the ace (starmie): 1
  the ace is weak to: bug, dark, electric, ghost, grass; 13 catchable families can attack on one of those types
    eldegoss (grass, first wild L12), kilowattrel (electric/flying, first wild L7), deerling (normal/grass, first wild L7), illumise (bug, first wild L18), lombre (water/grass, first wild L18), masquerain (bug/flying, first wild L9), chinchou (water/electric, first wild L18), pawmo (electric/fighting, first wild L7), volbeat (bug, first wild L18), combee (bug/flying, first wild L7)
  most health taken off the ace by one Pokemon: chinchou 100%, eldegoss 93%, raticate 84%, dubwool 79%, illumise 73%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team gyarados, pelipper, bibarel, eldegoss, kilowattrel, noctowl
      no switching    WIN  -- 6 of 6 downed, 3 lost
  gauntlet, walked   team flaaffy, pidgeotto, raticate, dubwool, applin, combee
      no switching    LOSS -- 4 of 6 downed, 6 lost, next foe on 100%
  authored line: kilowattrel, deerling, illumise, eldegoss, lombre, pawmo
      no switching    WIN  -- 6 of 6 downed, 4 lost
      discoverability: clear after scouting: Goldeen and Barboach advertise Electric immunity while both remain vulnerable to Grass.
    magikarp     as gyarados     water/flying     5/6  first wild L9   pelipper,lombre,goldeen,barboach,floatzel
    wingull      as pelipper     water/flying     5/6  first wild L7   pelipper,lombre,goldeen,barboach,floatzel
    bidoof       as bibarel      normal/water     4/6  first wild L9   pelipper,lombre,goldeen,barboach
    gossifleur   as eldegoss     grass            4/6  first wild L12  lombre,goldeen,barboach,floatzel
    wattrel      as kilowattrel  electric/flying  4/6  first wild L7   pelipper,lombre,goldeen,barboach
    hoothoot     as noctowl      normal/flying    4/6  first wild L7   pelipper,lombre,goldeen,barboach
    deerling     as deerling     normal/grass     3/6  first wild L7   lombre,goldeen,barboach
    wooloo       as dubwool      normal           3/6  first wild L5   lombre,goldeen,barboach

====================================================================================================
GYM 3  kanto_ltsurge (Electric)   leader status: authored
  cap 30, roster: electabuzz L28, vikavolt L28, magneton L29, boltund L29, pawmot L30, raichu L30
  49 catchable candidates: 0 beat the whole roster 1v1, 16 beat some, 33 beat none
  beat the ace (raichu): 14
  the ace is weak to: ground; 4 catchable families can attack on one of those types
    clodsire (poison/ground, first wild L24), quagsire (water/ground, first wild L24), whiscash (water/ground, first wild L18), diggersby (normal/ground, first wild L21)
  most health taken off the ace by one Pokemon: whiscash 100%, ursaring 100%, skiddo 100%, quagsire 100%, quagsire 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team clodsire, hariyama, lanturn, quagsire, whiscash, ampharos
      no switching    WIN  -- 6 of 6 downed, 2 lost
  gauntlet, walked   team ampharos, pidgeotto, raticate, dubwool, applin, combee
      no switching    LOSS -- 2 of 6 downed, 6 lost, next foe on 29%
  authored line: lycanroc, hariyama, heracross, clodsire, quagsire, diggersby
      no switching    WIN  -- 6 of 6 downed, 4 lost
      discoverability: clear from preview and Route 3: remove the flying Ground immunity, break the Steel core, then use Ground.
    clodsire     as clodsire     poison/ground    5/6  first wild L24  electabuzz,magneton,boltund,pawmot,raichu
    makuhita     as hariyama     fighting         5/6  first wild L22  electabuzz,magneton,boltund,pawmot,raichu
    chinchou     as lanturn      water/electric   5/6  first wild L18  electabuzz,magneton,boltund,pawmot,raichu
    quagsire     as quagsire     water/ground     5/6  first wild L24  electabuzz,magneton,boltund,pawmot,raichu
    wooper       as quagsire     water/ground     5/6  first wild L24  electabuzz,magneton,boltund,pawmot,raichu
    barboach     as whiscash     water/ground     5/6  first wild L18  electabuzz,magneton,boltund,pawmot,raichu
    mareep       as ampharos     electric         4/6  first wild L5   electabuzz,magneton,boltund,raichu
    bunnelby     as diggersby    normal/ground    4/6  first wild L21  electabuzz,magneton,boltund,raichu

====================================================================================================
GYM 4  kanto_erika (Grass)   leader status: authored
  cap 35, roster: bellossom L33, roserade L34, cradily L34, tangrowth L34, victreebel L35, vileplume L35
  81 catchable candidates: 1 beat the whole roster 1v1, 44 beat some, 36 beat none
  beat the ace (vileplume): 10
  the ace is weak to: fire, flying, ice, psychic; 25 catchable families can attack on one of those types
    skarmory (steel/flying, first wild L28), gyarados (water/flying, first wild L9), noctowl (normal/flying, first wild L7), talonflame (fire/flying, first wild L30), bronzong (steel/psychic, first wild L28), cryogonal (ice, first wild L27), jynx (ice/psychic, first wild L27), staraptor (normal/flying, first wild L32), emolga (electric/flying, first wild L30), kilowattrel (electric/flying, first wild L7)
  most health taken off the ace by one Pokemon: talonflame 100%, skuntank 100%, skarmory 100%, noctowl 100%, noctowl 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team skarmory, gyarados, noctowl, talonflame, bronzong, cryogonal
      no switching    WIN  -- 6 of 6 downed, 2 lost
  gauntlet, walked   team ampharos, pidgeotto, raticate, dubwool, applin, combee
      no switching    LOSS -- 2 of 6 downed, 6 lost, next foe on 32%
  authored line: talonflame, skarmory, cryogonal, jynx, scyther, noctowl
      no switching    WIN  -- 6 of 6 downed, 3 lost
      discoverability: moderate: the route teaches sun and exposes Rock coverage; the answer is a mixed Fire/Flying/Ice line, not six copies of one weakness.
    skarmory     as skarmory     steel/flying     6/6  first wild L28  bellossom,roserade,cradily,tangrowth,victreebel,vileplume
    magikarp     as gyarados     water/flying     5/6  first wild L9   bellossom,roserade,tangrowth,victreebel,vileplume
    gyarados     as gyarados     water/flying     5/6  first wild L21  bellossom,roserade,tangrowth,victreebel,vileplume
    hoothoot     as noctowl      normal/flying    5/6  first wild L7   bellossom,roserade,tangrowth,victreebel,vileplume
    noctowl      as noctowl      normal/flying    5/6  first wild L21  bellossom,roserade,tangrowth,victreebel,vileplume
    fletchling   as talonflame   fire/flying      5/6  first wild L30  bellossom,roserade,tangrowth,victreebel,vileplume
    bronzor      as bronzong     steel/psychic    4/6  first wild L28  bellossom,roserade,cradily,vileplume
    cryogonal    as cryogonal    ice              4/6  first wild L27  bellossom,roserade,tangrowth,vileplume

====================================================================================================
GYM 5  kanto_koga (Poison)   leader status: authored
  cap 40, roster: crobat L40, weezing L40, toxtricity L40, dragalge L40, drapion L40, venomoth L40
  102 catchable candidates: 0 beat the whole roster 1v1, 60 beat some, 42 beat none
  beat the ace (venomoth): 35
  the ace is weak to: fire, flying, psychic, rock; 23 catchable families can attack on one of those types
    bronzong (steel/psychic, first wild L28), altaria (dragon/flying, first wild L22), gyarados (water/flying, first wild L9), jynx (ice/psychic, first wild L27), corviknight (flying/steel, first wild L24), emolga (electric/flying, first wild L30), medicham (fighting/psychic, first wild L24), noctowl (normal/flying, first wild L7), pidgeot (normal/flying, first wild L5), skarmory (steel/flying, first wild L28)
  most health taken off the ace by one Pokemon: whiscash 100%, whiscash 100%, ursaring 100%, ursaring 100%, talonflame 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team bronzong, cryogonal, whiscash, altaria, drampa, gyarados
      no switching    WIN  -- 6 of 6 downed, 3 lost
  gauntlet, walked   team ampharos, pidgeot, raticate, dubwool, applin, combee
      no switching    LOSS -- 4 of 6 downed, 6 lost, next foe on 100%
  authored line: ampharos, jynx, diggersby, bronzong, quagsire, lycanroc
      no switching    WIN  -- 6 of 6 downed, 5 lost
      discoverability: moderate: Route 5 teaches Levitate and mixed Poison typings, but the player must assign a different answer to each role.
    bronzor      as bronzong     steel/psychic    5/6  first wild L28  crobat,weezing,toxtricity,dragalge,venomoth
    cryogonal    as cryogonal    ice              5/6  first wild L27  crobat,weezing,toxtricity,dragalge,venomoth
    barboach     as whiscash     water/ground     5/6  first wild L18  weezing,toxtricity,dragalge,drapion,venomoth
    whiscash     as whiscash     water/ground     5/6  first wild L30  weezing,toxtricity,dragalge,drapion,venomoth
    swablu       as altaria      dragon/flying    4/6  first wild L22  crobat,weezing,toxtricity,venomoth
    drampa       as drampa       normal/dragon    4/6  first wild L24  crobat,weezing,drapion,venomoth
    magikarp     as gyarados     water/flying     4/6  first wild L9   crobat,weezing,drapion,venomoth
    gyarados     as gyarados     water/flying     4/6  first wild L21  crobat,weezing,drapion,venomoth

====================================================================================================
GYM 6  kanto_sabrina (Psychic)   leader status: authored
  cap 45, roster: hatterene L45, slowbro L45, bronzong L45, exeggutor L45, reuniclus L45, alakazam L45
  120 catchable candidates: 0 beat the whole roster 1v1, 78 beat some, 42 beat none
  beat the ace (alakazam): 23
  the ace is weak to: bug, dark, ghost; 16 catchable families can attack on one of those types
    skuntank (poison/dark, first wild L32), absol (dark, first wild L24), masquerain (bug/flying, first wild L9), illumise (bug, first wild L18), scyther (bug/flying, first wild L21), sharpedo (water/dark, first wild L34), crawdaunt (water/dark, first wild L18), nuzleaf (grass/dark, first wild L41), volbeat (bug, first wild L18), heracross (bug/fighting, first wild L21)
  most health taken off the ace by one Pokemon: skuntank 100%, skarmory 100%, sharpedo 100%, sharpedo 100%, nuzleaf 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team skuntank, absol, gyarados, masquerain, sawsbuck, skarmory
      no switching    WIN  -- 6 of 6 downed, 4 lost
  gauntlet, walked   team ampharos, pidgeot, raticate, dubwool, applin, combee
      no switching    LOSS -- 2 of 6 downed, 6 lost, next foe on 41%
  authored line: bronzong, scyther, heracross, skuntank, toxtricity, quagsire
      no switching    WIN  -- 6 of 6 downed, 3 lost
      discoverability: clear after Route 6: Dark offense, priority, and surviving the Trick Room clock are all taught before the leader.
    stunky       as skuntank     poison/dark      5/6  first wild L32  hatterene,bronzong,exeggutor,reuniclus,alakazam
    absol        as absol        dark             4/6  first wild L24  bronzong,exeggutor,reuniclus,alakazam
    magikarp     as gyarados     water/flying     4/6  first wild L9   bronzong,exeggutor,reuniclus,alakazam
    gyarados     as gyarados     water/flying     4/6  first wild L21  bronzong,exeggutor,reuniclus,alakazam
    surskit      as masquerain   bug/flying       4/6  first wild L9   slowbro,bronzong,exeggutor,reuniclus
    masquerain   as masquerain   bug/flying       4/6  first wild L34  slowbro,bronzong,exeggutor,reuniclus
    deerling     as sawsbuck     normal/grass     4/6  first wild L7   hatterene,slowbro,exeggutor,reuniclus
    skarmory     as skarmory     steel/flying     4/6  first wild L28  hatterene,bronzong,exeggutor,alakazam

====================================================================================================
GYM 7  kanto_blaine (Fire)   leader status: authored
  cap 50, roster: torkoal L50, arcanine L50, magcargo L50, magmortar L50, typhlosion L50, charizard L50
  151 catchable candidates: 1 beat the whole roster 1v1, 92 beat some, 58 beat none
  beat the ace (charizard): 42
  the ace is weak to: electric, rock, water; 39 catchable families can attack on one of those types
    dondozo (water, first wild L27), barraskewda (water, first wild L39), basculegion (water/ghost, first wild L39), basculin (water, first wild L30), golduck (water, first wild L39), gyarados (water/flying, first wild L9), lanturn (water/electric, first wild L18), whiscash (water/ground, first wild L18), coalossal (rock/fire, first wild L44), floatzel (water, first wild L9)
  most health taken off the ace by one Pokemon: whiscash 100%, whiscash 100%, walrein 100%, sharpedo 100%, seismitoad 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team dondozo, barraskewda, basculegion, basculin, golduck, gyarados
      no switching    LOSS -- 5 of 6 downed, 6 lost, next foe on 90%
  gauntlet, walked   team ampharos, pidgeot, raticate, dubwool, applin, combee
      no switching    LOSS -- 1 of 6 downed, 6 lost, next foe on 100%
  authored line: dondozo, pelipper, floatzel, whiscash, crawdaunt, lycanroc
      no switching    WIN  -- 6 of 6 downed, 5 lost
      discoverability: moderate: Route 7 teaches bulky Water, weather replacement, fast Water, Ground and Rock pressure; the winning order still needs scouting.
    dondozo      as dondozo      water            6/6  first wild L27  torkoal,arcanine,magcargo,magmortar,typhlosion,charizard
    arrokuda     as barraskewda  water            5/6  first wild L39  arcanine,magcargo,magmortar,typhlosion,charizard
    barraskewda  as barraskewda  water            5/6  first wild L39  arcanine,magcargo,magmortar,typhlosion,charizard
    basculegion  as basculegion  water/ghost      5/6  first wild L39  torkoal,magcargo,magmortar,typhlosion,charizard
    basculin     as basculin     water            5/6  first wild L30  torkoal,magcargo,magmortar,typhlosion,charizard
    golduck      as golduck      water            5/6  first wild L39  torkoal,magcargo,magmortar,typhlosion,charizard
    psyduck      as golduck      water            5/6  first wild L39  torkoal,magcargo,magmortar,typhlosion,charizard
    magikarp     as gyarados     water/flying     5/6  first wild L9   torkoal,arcanine,magcargo,typhlosion,charizard

====================================================================================================
GYM 8  kanto_giovanni (Ground)   leader status: authored
  cap 55, roster: hippowdon L55, persian L55, mudsdale L55, nidoqueen L55, krookodile L55, rhyperior L55
  189 catchable candidates: 6 beat the whole roster 1v1, 160 beat some, 23 beat none
  beat the ace (rhyperior): 38
  the ace is weak to: fighting, grass, ground, ice, steel, water; 68 catchable families can attack on one of those types
    basculegion (water/ghost, first wild L39), basculin (water, first wild L30), dondozo (water, first wild L27), golisopod (bug/water, first wild L50), kingler (water, first wild L7), flygon (ground/dragon, first wild L25), gyarados (water/flying, first wild L9), hariyama (fighting, first wild L22), heracross (bug/fighting, first wild L21), maractus (grass, first wild L47)
  most health taken off the ace by one Pokemon: walrein 100%, swanna 100%, swanna 100%, seismitoad 100%, seismitoad 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team basculegion, basculin, dondozo, golisopod, kingler, flygon
      no switching    WIN  -- 6 of 6 downed, 2 lost
  gauntlet, walked   team ampharos, pidgeot, raticate, dubwool, applin, combee
      no switching    LOSS -- 3 of 6 downed, 6 lost, next foe on 26%
  authored line: swanna, seismitoad, gogoat, hariyama, heracross, cacturne
      no switching    WIN  -- 6 of 6 downed, 5 lost
      discoverability: moderate: Route 8 teaches immunity, Fighting, Grass, priority, and Tailwind, but Nidoqueen forces the player to rotate them.
    basculegion  as basculegion  water/ghost      6/6  first wild L39  hippowdon,persian,mudsdale,nidoqueen,krookodile,rhyperior
    basculin     as basculin     water            6/6  first wild L30  hippowdon,persian,mudsdale,nidoqueen,krookodile,rhyperior
    dondozo      as dondozo      water            6/6  first wild L27  hippowdon,persian,mudsdale,nidoqueen,krookodile,rhyperior
    golisopod    as golisopod    bug/water        6/6  first wild L50  hippowdon,persian,mudsdale,nidoqueen,krookodile,rhyperior
    wimpod       as golisopod    bug/water        6/6  first wild L50  hippowdon,persian,mudsdale,nidoqueen,krookodile,rhyperior
    krabby       as kingler      water            6/6  first wild L7   hippowdon,persian,mudsdale,nidoqueen,krookodile,rhyperior
    trapinch     as flygon       ground/dragon    5/6  first wild L25  hippowdon,persian,mudsdale,nidoqueen,krookodile
    magikarp     as gyarados     water/flying     5/6  first wild L9   hippowdon,persian,nidoqueen,krookodile,rhyperior

====================================================================================================
STARTERS
  starter       G1  G2  G3  G4  G5  G6  G7  G8
  charmander    2/6  0/6  2/6  4/6  5/6  1/6  1/6  2/6   (final form at cap: charizard)
  squirtle      5/6  3/6  0/6  0/6  3/6  2/6  4/6  6/6   (final form at cap: blastoise)
  bulbasaur     6/6  5/6  2/6  3/6  1/6  1/6  1/6  6/6   (final form at cap: venusaur)
  cyndaquil     0/6  0/6  0/6  2/6  5/6  4/6  2/6  2/6   (final form at cap: typhlosion)
  totodile      5/6  3/6  0/6  0/6  1/6  1/6  1/6  2/6   (final form at cap: feraligatr)
  chikorita     4/6  4/6  1/6  2/6  0/6  2/6  1/6  6/6   (final form at cap: meganium)
  torchic       5/6  2/6  2/6  5/6  2/6  1/6  2/6  1/6   (final form at cap: blaziken)
  mudkip        5/6  2/6  5/6  0/6  6/6  4/6  5/6  6/6   (final form at cap: swampert)
  treecko       6/6  5/6  2/6  1/6  0/6  2/6  0/6  3/6   (final form at cap: sceptile)
  chimchar      3/6  0/6  0/6  3/6  4/6  1/6  3/6  1/6   (final form at cap: infernape)
  piplup        5/6  2/6  0/6  0/6  2/6  3/6  2/6  2/6   (final form at cap: empoleon)
  turtwig       5/6  4/6  1/6  4/6  3/6  3/6  2/6  5/6   (final form at cap: torterra)
  tepig         1/6  0/6  0/6  2/6  0/6  1/6  4/6  1/6   (final form at cap: emboar)
  oshawott      5/6  2/6  0/6  0/6  1/6  3/6  5/6  3/6   (final form at cap: samurott)
  snivy         5/6  4/6  1/6  0/6  0/6  0/6  0/6  4/6   (final form at cap: serperior)
  fennekin      2/6  0/6  0/6  2/6  5/6  4/6  5/6  2/6   (final form at cap: delphox)
  froakie       5/6  2/6  0/6  0/6  1/6  2/6  2/6  3/6   (final form at cap: greninja)
  chespin       6/6  4/6  3/6  1/6  0/6  2/6  1/6  5/6   (final form at cap: chesnaught)
  litten        0/6  1/6  0/6  6/6  5/6  5/6  3/6  1/6   (final form at cap: incineroar)
  popplio       4/6  1/6  0/6  2/6  3/6  4/6  5/6  6/6   (final form at cap: primarina)
  rowlet        1/6  3/6  0/6  5/6  4/6  5/6  1/6  4/6   (final form at cap: decidueye)
  scorbunny     0/6  0/6  0/6  6/6  5/6  4/6  2/6  1/6   (final form at cap: cinderace)
  sobble        5/6  3/6  0/6  0/6  1/6  1/6  2/6  4/6   (final form at cap: inteleon)
  grookey       4/6  4/6  1/6  2/6  0/6  3/6  1/6  5/6   (final form at cap: rillaboom)
  fuecoco       1/6  0/6  1/6  3/6  4/6  5/6  3/6  1/6   (final form at cap: skeledirge)
  quaxly        6/6  3/6  0/6  0/6  1/6  1/6  4/6  5/6   (final form at cap: quaquaval)
  sprigatito    5/6  4/6  2/6  1/6  0/6  5/6  0/6  1/6   (final form at cap: meowscarada)

```
