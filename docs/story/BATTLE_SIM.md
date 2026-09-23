# Gym battle simulation

**Status:** a design input, not a verdict. Regenerated 2026-09-24 against the rebuilt
`docs/story/AVAILABILITY.md` and a battle engine that now models items, abilities, weather, status and stat
stages. Run `python tools/battle_sim.py`.

## What it is simulating

**Our own rosters.** `data/trainers.json`, seven of eight `status: authored`. **Gym 8 (Giovanni) is `held` with
an empty team** and cannot be simulated at all.

**Every pool a player can reach**, not just the curated routes. `tools/availability.py` regenerates
`AVAILABILITY.md` and `derived/availability.json` from the compiled pools, and the simulator reads the JSON.
Species counts before each gym roughly doubled: 19 / 24 / 44 / 74 / 91 / 110 / 146 / 184.

**No bag items on either side**, which is correct rather than a simplification: every authored leader sets
`rct.battleRules.maxItemUses: 0` and carries an empty `bag`.

## The numbers

| Gym | Leader | Cap | Candidates | Sweep 1v1 | Beat ace | Families that can hit the ace super-effectively | Informed six | Walked six |
|---|---|---|---|---|---|---|---|---|
| 1 | Brock (Rock) | 20 | 19 | 6 | 7 | 12 | WIN, 2 lost | LOSS, 3 of 4, next on 2% |
| 2 | Misty (Water) | 25 | 24 | 4 | 4 | 12 | WIN, 1 lost | WIN, 3 lost |
| 3 | Surge (Electric) | 30 | 44 | 2 | 10 | **3** | WIN, 3 lost | LOSS, 3 of 4 |
| 4 | Erika (Grass) | 35 | 74 | 8 | 8 | 24 | WIN, 2 lost | LOSS, 3 of 4 |
| 5 | Koga (Poison) | 40 | 91 | 1 | 26 | 22 | WIN, 3 lost | WIN, 4 lost |
| 6 | Sabrina (Psychic) | 45 | 110 | 2 | 13 | 15 | WIN, 4 lost | LOSS, 4 of 5 |
| 7 | Blaine (Fire) | 50 | 146 | 2 | 21 | 36 | **LOSS, 5 of 6** | LOSS, 3 of 6 |
| 8 | Giovanni | — | — | — | — | — | no roster | no roster |

**Gym 7 is still the wall, and now for a reason the tool can name.** Blaine leads a **Drought** Torkoal. Sun
multiplies Fire by 1.5 and halves Water, which is the entire natural answer to a Fire gym. Before the engine
modelled weather, the best six won losing nobody; with sun on, they lose having downed five of six. The
strategy line in `data/trainers.json` said so all along — "Drought Torkoal sets hazards and sun ... Charizard
exploits sun" — and the tool could not see it.

**Gym 3 is not thin.** All four of Surge's are Electric, so the gym is weak to Ground and nothing else, and that
is still the narrowest in the game. But there are three Ground families before it, not one, and ten catchable
species beat Raichu. See the review at the head of `GYM_SUFFICIENCY_AUDIT.md`.

**Three of Surge's four have Lightning Rod.** An Electric answer to the Electric gym does exactly zero damage.
The tool now knows that; it did not before.

## What the engine models now

Damage on the mainline formula with stat stages; weather from Drought, Drizzle, Sand Stream, Snow Warning and the
weather moves; Focus Sash, Weakness Policy, Sitrus and Oran, Leftovers, Black Sludge, Life Orb with its recoil,
Choice Band/Specs/Scarf, Assault Vest, Eviolite, Rocky Helmet, Air Balloon, the resist berries; Sturdy, Levitate,
Mold Breaker, Thick Fat, Filter, Multiscale, Adaptability, Tinted Lens, Huge and Pure Power, Guts, Magic Guard,
Intimidate, and the type absorbers Lightning Rod, Motor Drive, Volt and Water Absorb, Dry Skin, Flash Fire, Sap
Sipper; paralysis, burn, poison, toxic and sleep; stat-stage moves both ways, screens, weather moves, recovery.

It also fixes a silent disarmament: Showdown stores **Grass Knot, Low Kick and Gyro Ball with basePower 0**
because their power is computed, and reading that as "status move" had left Raichu swinging a zero-power Grass
Knot. They are now computed from the defender's weight and the speed ratio.

## Tractability, for the fights you are about to write

| | Verdict |
|---|---|
| **Held items** | **Done.** The ones that change a matchup are deterministic and cheap. Focus Sash was the big one — seven leader Pokemon hold it, and it turns every clean one-shot into a two-turn kill. |
| **Matchup-changing abilities** | **Done, and the highest-value change of the lot.** Type absorbers and weather setters are the ones that flip a fight; Lightning Rod and Drought between them moved two gyms' verdicts. |
| **Status moves** | **Done for what the leaders carry.** Stat stages were the enabling piece; once stages exist, boosts, drops, screens and the status conditions are all cheap. |
| **Healing items** | **Not needed.** `maxItemUses: 0` on every authored leader. If you give a boss a Full Restore in the rewrite this becomes the top priority, because it roughly doubles an effective HP pool and nothing else in the model compensates. |
| **Switching** | **Attempted and NOT sound. Off by default.** See below. |

**On switching, plainly:** I implemented a player-side bound and it came out *worse than never switching at two
of seven gyms*. Every switch hands the foe a free hit, and a greedy "who wins this matchup" rule spends those
hits badly. A bound that can fall below the thing it is bounding is measuring its own policy, not the fight, so
it is behind `--switching` and should not be quoted. Making it sound needs a real policy — lookahead over the
remaining team, or a search rather than a heuristic — and that is a different and much larger tool. The leader
does not switch at all, although `data/trainers.json` declares `switchBias: 0.65` for every gym leader, so a
fight designed around the AI pivoting is invisible here.

**Hazards are in the same bucket.** Stealth Rock and Toxic Spikes only pay off against switching, so they are
counted as unmodelled and do nothing. If the rewritten fights lean on hazards, the tool will understate them.

## Defects found in this tool and fixed

A separate session wrote the tests and reviewed the engine, and found ten defects in it. Eight changed a number
or were footguns; all are fixed. They are listed because they say what to distrust in an engine of this kind.

| Defect | Which way it biased |
|---|---|
| `choose_moveset` dropped every move with basePower 0, so no player candidate could ever carry Grass Knot, Low Kick or Gyro Ball. Machop's Low Kick into Brock's Onix — 120 power, super-effective — was unreachable. | against the player |
| `DROP_MOVES` and `HEAL_MOVES` were unreachable in `best_action`, so **Starmie's Recover did nothing**, along with Scary Face, Tearful Look and Smokescreen. | against the leader |
| The type absorbers recorded a payoff nobody read: Lightning Rod's +1 SpA, Water and Volt Absorb's heal, Sap Sipper and Motor Drive. Three of Surge's four hold Lightning Rod. | against the leader |
| No type-based status immunities at all. Thunder Wave landed on Raichu and Magnezone, Will-O-Wisp on Torkoal and Arcanine, Toxic on Weezing and Crobat — a single status move shut down three whole gyms. | against the leader |
| Magic Guard was given status immunity, which is not a thing, and it also cancelled Leftovers. | both |
| Contact was approximated as "is it physical", so Weezing's Rocky Helmet taxed Earthquake and Rock Slide, which touch nothing. Now read from the move's own flag: 272 of 930 moves make contact. | against the player |
| `damage()` returned a silent 0 for a variable-power move when the caller forgot to pass the dex. The dex now travels on the Pokemon. | latent |
| `availability.py` re-implemented `battle_sim.key()` instead of importing it — two copies of the normalisation that must agree, which is the exact shape of the bug that dropped the gendered Nidoran. | latent |

One review finding needed no change: Mold Breaker bypassing *every* absorber including Levitate is correct, and
there is now a test that will fail if someone "fixes" it.

The net effect on the table above was small — Surge got harder (2 sweepers, not 3) and Koga easier by one
Pokemon — but the direction matters more than the size: four of the eight were flattering the player against the
leaders' own gimmicks, which is precisely the failure mode for a tool you are about to design gimmick fights
against.

## What it still cannot judge

Whether a fight is fun, how long it takes, whether the answer is discoverable, and whether a player would enjoy
finding it. Secondary effects, crits, Protect, Substitute, Encore, Taunt and Trick Room. Abilities outside the
list above. The player's moves are the level-up list only while every leader has a hand-picked set including TM
moves, and TMCraft is in the pack — **this biases the whole simulation against the player** and is the largest
single distortion left.

### And the one it cannot check at all

**Whether Cobblemon's own embedded Showdown computes damage the way the mainline formula does at these levels.**
The tests prove this tool agrees with the published formula; they cannot prove the game agrees with either.

Settling it needs a battle run in a real server:

1. Boot the staging server under the coordination lock and place two Pokemon of known species, level, nature,
   IVs and item — `/spawnpokemon` with explicit properties, so nothing is rolled.
2. Force one known move and read the damage back. The tractable read is the battle log: Cobblemon's battle
   messages carry the HP fraction remaining, and `/pokemoneditor` or NBT on a stopped world gives exact current
   HP. Repeat enough times to see the 85-100% roll spread rather than one sample.
3. Compare against `battle_sim.damage` with the random factor disabled. Ten matchups spanning physical/special,
   STAB, a resist, a 4x weakness and a Focus Sash would settle it.
4. What would invalidate the tool: a different stat formula at these levels, a different rounding order, or
   Cobbleverse altering damage through a config or datapack nobody has read.

Filed as an experiment in `docs/research/EXPERIMENT_BACKLOG.md`. Until it runs, every number here is
"consistent with the published formula", not "what the game does".

## Starters

`useConfigStarters: false` does **not** disable the config list. It is Cobblemon's own default and only governs
whether a *datapack* list is merged with the config one; with no starter datapack present — and the server has
none, checked directly — `CobblemonStarterHandler.getStarterList` falls straight back to the config. So the
offer is **13 categories, 36 species**, not the Kanto three. Details and sources in
`docs/research/notes/starter-selection.md`.

Leader Pokemon beaten one on one, summed across the seven simulated gyms:

| Band | Starters | Total |
|---|---|---|
| Strong | Mudkip 25, Turtwig 22 | 22-25 |
| Solid | Litten, Rowlet, Fennekin 18; Oshawott, Popplio 17; Chimchar, Squirtle, Fuecoco 16 | 16-18 |
| Middling | Charmander, Torchic, Scorbunny, Quaxly, Grookey 15; Bulbasaur, Piplup, Sobble 14; Treecko, Sprigatito, Totodile 13 | 13-15 |
| Weak | Chespin, Froakie, Chikorita, Cyndaquil 12, Bagon 10, Tepig 9, Snivy 8 | 8-12 |
| Barely a starter | Budew 4, Pikachu 3, Eevee 2, Pichu 1, Azurill 1 | 1-4 |

Cyndaquil beats **nothing at all** in the first three gyms; so do Tepig, Scorbunny and Eevee. Mudkip is the only
starter that answers Surge by itself (Swampert is Water/Ground: Electric-immune and super-effective back).

**One caveat that lifts the bottom band.** Pichu, Azurill and Budew evolve by friendship, and Eevee by stone —
neither of which the simulation's level-only rule allows, so those four are understated. They are still the
weakest offer on the board, but not 1-versus-25 weak.

### The options, as asked — no change made

1. **Narrow the list to one generation's trio.** Restores the intended three-way choice, makes the campaign's
   difficulty legible, and is a one-line config edit. Costs the variety the pack advertises.
2. **Narrow to a band.** Keep every trio but drop the Pallet, Lumya and Cosplay categories — Pikachu, Eevee,
   Pichu, Azurill, Budew and the Cosplay variants are the entire bottom of the table and are singles or
   friendship-gated, not starters in the sense the other twelve categories mean. Nine trios remain, spread 8-25.
3. **Rebalance rather than cut**, by moving the early availability rather than the list: the first three gyms
   are where the spread hurts (Cyndaquil, Tepig, Scorbunny and Eevee score zero across all three), and that is a
   Route 1-3 availability question, not a starter question.
4. **Accept it as intentional.** A defensible reading: the pack is a sandbox, the starter is a flavour pick, and
   a player who takes Pichu has chosen a hard run. Worth choosing deliberately rather than by default — right
   now it is by default, because the flag was assumed to make the list inert.

Nothing here is a recommendation to act. The number that should decide it is how visible the choice's
consequence is to a player at the moment they make it, and this tool cannot measure that.

## The run

```
Cobblemon jar: Cobblemon-fabric-1.8.0+1.21.1.jar
species 1025, moves 930, types 18; IVs 15, EVs 0, level only evolutions
level cap from rctmod-server.toml: initial 20, relative +5

====================================================================================================
GYM 1  kanto_brock (Rock)   leader status: authored
  cap 20, roster: geodude L18, bonsly L18, cranidos L19, onix L20
  19 catchable candidates: 6 beat the whole roster 1v1, 3 beat some, 10 beat none
  beat the ace (onix): 7
  the ace is weak to: fighting, grass, ground, ice, steel, water; 12 catchable families can attack on one of those types
    bibarel (normal/water, first wild L9), buizel (water, first wild L9), eldegoss (grass, first wild L12), shellder (water, first wild L7), staryu (water, first wild L7), krabby (water, first wild L7), fomantis (grass, first wild L12), surskit (bug/water, first wild L9), applin (grass/dragon, first wild L12), deerling (normal/grass, first wild L9)
  most health taken off the ace by one Pokemon: staryu 100%, shellder 100%, noctowl 100%, krabby 100%, eldegoss 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team bibarel, buizel, eldegoss, noctowl, shellder, staryu
      no switching    WIN  -- 4 of 4 downed, 2 lost
  gauntlet, walked   team flaaffy, pidgeotto, raticate, wooloo, krabby, shellder
      no switching    LOSS -- 3 of 4 downed, 6 lost, next foe on 2%
    bidoof       as bibarel      normal/water     4/4  first wild L9   geodude,bonsly,cranidos,onix
    buizel       as buizel       water            4/4  first wild L9   geodude,bonsly,cranidos,onix
    gossifleur   as eldegoss     grass            4/4  first wild L12  geodude,bonsly,cranidos,onix
    hoothoot     as noctowl      normal/flying    4/4  first wild L12  geodude,bonsly,cranidos,onix
    shellder     as shellder     water            4/4  first wild L7   geodude,bonsly,cranidos,onix
    staryu       as staryu       water            4/4  first wild L7   geodude,bonsly,cranidos,onix
    krabby       as krabby       water            3/4  first wild L7   geodude,bonsly,onix
    fomantis     as fomantis     grass            1/4  first wild L12  geodude

====================================================================================================
GYM 2  kanto_misty (Water)   leader status: authored
  cap 25, roster: horsea L22, lombre L23, goldeen L24, starmie L25
  24 catchable candidates: 4 beat the whole roster 1v1, 18 beat some, 2 beat none
  beat the ace (starmie): 4
  the ace is weak to: bug, dark, electric, ghost, grass; 12 catchable families can attack on one of those types
    eldegoss (grass, first wild L12), illumise (bug, first wild L18), volbeat (bug, first wild L18), deerling (normal/grass, first wild L9), kilowattrel (electric/flying, first wild L7), masquerain (bug/flying, first wild L9), combee (bug/flying, first wild L12), flaaffy (electric, first wild L5), fomantis (grass, first wild L12), lombre (water/grass, first wild L18)
  most health taken off the ace by one Pokemon: volbeat 100%, noctowl 100%, illumise 100%, eldegoss 100%, dubwool 99%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team eldegoss, illumise, noctowl, volbeat, bibarel, deerling
      no switching    WIN  -- 4 of 4 downed, 1 lost
  gauntlet, walked   team flaaffy, pidgeotto, raticate, dubwool, krabby, shellder
      no switching    WIN  -- 4 of 4 downed, 3 lost
    gossifleur   as eldegoss     grass            4/4  first wild L12  horsea,lombre,goldeen,starmie
    illumise     as illumise     bug              4/4  first wild L18  horsea,lombre,goldeen,starmie
    hoothoot     as noctowl      normal/flying    4/4  first wild L12  horsea,lombre,goldeen,starmie
    volbeat      as volbeat      bug              4/4  first wild L18  horsea,lombre,goldeen,starmie
    bidoof       as bibarel      normal/water     3/4  first wild L9   horsea,lombre,goldeen
    deerling     as deerling     normal/grass     3/4  first wild L9   horsea,lombre,goldeen
    wooloo       as dubwool      normal           3/4  first wild L5   horsea,lombre,goldeen
    wattrel      as kilowattrel  electric/flying  3/4  first wild L7   horsea,lombre,goldeen

====================================================================================================
GYM 3  kanto_ltsurge (Electric)   leader status: authored
  cap 30, roster: electabuzz L27, magnezone L28, boltund L29, raichu L30
  44 catchable candidates: 2 beat the whole roster 1v1, 12 beat some, 30 beat none
  beat the ace (raichu): 10
  the ace is weak to: ground; 3 catchable families can attack on one of those types
    diggersby (normal/ground, first wild L21), clodsire (poison/ground, first wild L24), quagsire (water/ground, first wild L24)
  most health taken off the ace by one Pokemon: ursaring 100%, skiddo 100%, pawmo 100%, heracross 100%, hariyama 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team diggersby, hariyama, ampharos, clodsire, dubwool, heracross
      no switching    WIN  -- 4 of 4 downed, 3 lost
  gauntlet, walked   team ampharos, pidgeotto, raticate, dubwool, kingler, shellder
      no switching    LOSS -- 3 of 4 downed, 6 lost, next foe on 47%
    bunnelby     as diggersby    normal/ground    4/4  first wild L21  electabuzz,magnezone,boltund,raichu
    makuhita     as hariyama     fighting         4/4  first wild L22  electabuzz,magnezone,boltund,raichu
    mareep       as ampharos     electric         3/4  first wild L5   electabuzz,magnezone,boltund
    clodsire     as clodsire     poison/ground    3/4  first wild L24  electabuzz,magnezone,raichu
    wooloo       as dubwool      normal           3/4  first wild L5   electabuzz,boltund,raichu
    heracross    as heracross    bug/fighting     3/4  first wild L21  electabuzz,magnezone,raichu
    pawmi        as pawmo        electric/fighting 3/4  first wild L9   electabuzz,magnezone,raichu
    quagsire     as quagsire     water/ground     3/4  first wild L24  electabuzz,magnezone,boltund

====================================================================================================
GYM 4  kanto_erika (Grass)   leader status: authored
  cap 35, roster: bellossom L33, roserade L33, victreebel L34, vileplume L35
  74 catchable candidates: 8 beat the whole roster 1v1, 34 beat some, 32 beat none
  beat the ace (vileplume): 8
  the ace is weak to: fire, flying, ice, psychic; 24 catchable families can attack on one of those types
    bronzong (steel/psychic, first wild L28), cryogonal (ice, first wild L27), jynx (ice/psychic, first wild L27), noctowl (normal/flying, first wild L12), skarmory (steel/flying, first wild L28), talonflame (fire/flying, first wild L30), emolga (electric/flying, first wild L30), kilowattrel (electric/flying, first wild L7), scyther (bug/flying, first wild L21), staraptor (normal/flying, first wild L32)
  most health taken off the ace by one Pokemon: talonflame 100%, skuntank 100%, skarmory 100%, noctowl 100%, noctowl 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team bronzong, cryogonal, jynx, noctowl, skarmory, skuntank
      no switching    WIN  -- 4 of 4 downed, 2 lost
  gauntlet, walked   team ampharos, pidgeotto, raticate, dubwool, kingler, shellder
      no switching    LOSS -- 3 of 4 downed, 6 lost, next foe on 37%
    bronzor      as bronzong     steel/psychic    4/4  first wild L28  bellossom,roserade,victreebel,vileplume
    cryogonal    as cryogonal    ice              4/4  first wild L27  bellossom,roserade,victreebel,vileplume
    smoochum     as jynx         ice/psychic      4/4  first wild L27  bellossom,roserade,victreebel,vileplume
    hoothoot     as noctowl      normal/flying    4/4  first wild L12  bellossom,roserade,victreebel,vileplume
    noctowl      as noctowl      normal/flying    4/4  first wild L21  bellossom,roserade,victreebel,vileplume
    skarmory     as skarmory     steel/flying     4/4  first wild L28  bellossom,roserade,victreebel,vileplume
    stunky       as skuntank     poison/dark      4/4  first wild L32  bellossom,roserade,victreebel,vileplume
    fletchling   as talonflame   fire/flying      4/4  first wild L30  bellossom,roserade,victreebel,vileplume

====================================================================================================
GYM 5  kanto_koga (Poison)   leader status: authored
  cap 40, roster: crobat L38, weezing L38, drapion L39, toxtricity L39, venomoth L40
  91 catchable candidates: 1 beat the whole roster 1v1, 56 beat some, 34 beat none
  beat the ace (venomoth): 26
  the ace is weak to: fire, flying, psychic, rock; 22 catchable families can attack on one of those types
    altaria (dragon/flying, first wild L22), bronzong (steel/psychic, first wild L28), medicham (fighting/psychic, first wild L24), corviknight (flying/steel, first wild L24), jynx (ice/psychic, first wild L27), kilowattrel (electric/flying, first wild L7), noctowl (normal/flying, first wild L12), pidgeot (normal/flying, first wild L5), skarmory (steel/flying, first wild L28), staraptor (normal/flying, first wild L32)
  most health taken off the ace by one Pokemon: ursaring 100%, ursaring 100%, talonflame 100%, staraptor 100%, staraptor 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team drampa, altaria, bronzong, cryogonal, medicham, ampharos
      no switching    WIN  -- 5 of 5 downed, 3 lost
  gauntlet, walked   team ampharos, pidgeot, raticate, dubwool, kingler, shellder
      no switching    WIN  -- 5 of 5 downed, 4 lost
    drampa       as drampa       normal/dragon    5/5  first wild L24  crobat,weezing,drapion,toxtricity,venomoth
    swablu       as altaria      dragon/flying    4/5  first wild L22  crobat,weezing,toxtricity,venomoth
    bronzor      as bronzong     steel/psychic    4/5  first wild L28  crobat,weezing,toxtricity,venomoth
    cryogonal    as cryogonal    ice              4/5  first wild L27  crobat,weezing,toxtricity,venomoth
    meditite     as medicham     fighting/psychic 4/5  first wild L24  weezing,drapion,toxtricity,venomoth
    mareep       as ampharos     electric         3/5  first wild L5   crobat,weezing,venomoth
    ampharos     as ampharos     electric         3/5  first wild L30  crobat,weezing,venomoth
    flaaffy      as ampharos     electric         3/5  first wild L30  crobat,weezing,venomoth

====================================================================================================
GYM 6  kanto_sabrina (Psychic)   leader status: authored
  cap 45, roster: hatterene L42, mrmime L43, bronzong L43, rapidash L44, alakazam L45
  110 catchable candidates: 2 beat the whole roster 1v1, 67 beat some, 41 beat none
  beat the ace (alakazam): 13
  the ace is weak to: bug, dark, ghost; 15 catchable families can attack on one of those types
    scyther (bug/flying, first wild L21), skuntank (poison/dark, first wild L32), masquerain (bug/flying, first wild L9), absol (dark, first wild L24), crawdaunt (water/dark, first wild L18), heracross (bug/fighting, first wild L21), spidops (bug, first wild L34), volbeat (bug, first wild L18), combee (bug/flying, first wild L12), illumise (bug, first wild L18)
  most health taken off the ace by one Pokemon: ursaring 100%, ursaring 100%, skuntank 100%, scyther 100%, sawsbuck 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team ursaring, beartic, corviknight, floatzel, scyther, skarmory
      no switching    WIN  -- 5 of 5 downed, 4 lost
  gauntlet, walked   team ampharos, pidgeot, raticate, dubwool, kingler, shellder
      no switching    LOSS -- 4 of 5 downed, 6 lost, next foe on 100%
    teddiursa    as ursaring     normal           5/5  first wild L21  hatterene,mrmime,bronzong,rapidash,alakazam
    ursaring     as ursaring     normal           5/5  first wild L30  hatterene,mrmime,bronzong,rapidash,alakazam
    cubchoo      as beartic      ice              4/5  first wild L29  hatterene,mrmime,rapidash,alakazam
    corvisquire  as corviknight  flying/steel     4/5  first wild L24  hatterene,mrmime,rapidash,alakazam
    rookidee     as corviknight  flying/steel     4/5  first wild L24  hatterene,mrmime,rapidash,alakazam
    buizel       as floatzel     water            4/5  first wild L9   hatterene,mrmime,bronzong,rapidash
    floatzel     as floatzel     water            4/5  first wild L27  hatterene,mrmime,bronzong,rapidash
    scyther      as scyther      bug/flying       4/5  first wild L21  hatterene,mrmime,bronzong,alakazam

====================================================================================================
GYM 7  kanto_blaine (Fire)   leader status: authored
  cap 50, roster: torkoal L47, arcanine L48, magcargo L48, magmortar L49, typhlosion L49, charizard L50
  146 catchable candidates: 2 beat the whole roster 1v1, 93 beat some, 51 beat none
  beat the ace (charizard): 21
  the ace is weak to: electric, rock, water; 36 catchable families can attack on one of those types
    barraskewda (water, first wild L39), basculegion (water/ghost, first wild L39), rhydon (ground/rock, first wild L44), basculin (water, first wild L39), coalossal (rock/fire, first wild L44), golduck (water, first wild L39), gyarados (water/flying, first wild L39), quagsire (water/ground, first wild L24), whiscash (water/ground, first wild L37), aggron (steel/rock, first wild L28)
  most health taken off the ace by one Pokemon: kilowattrel 100%, hatterene 100%, hatterene 100%, gyarados 100%, gyarados 100%
  Pokemon needed to bring the ace down: 1
  gauntlet, informed team barraskewda, basculegion, flygon, rhydon, basculin, clodsire
      no switching    LOSS -- 5 of 6 downed, 6 lost, next foe on 50%
  gauntlet, walked   team ampharos, pidgeot, raticate, dubwool, kingler, shellder
      no switching    LOSS -- 3 of 6 downed, 6 lost, next foe on 100%
    arrokuda     as barraskewda  water            6/6  first wild L39  torkoal,arcanine,magcargo,magmortar,typhlosion,charizard
    barraskewda  as barraskewda  water            6/6  first wild L39  torkoal,arcanine,magcargo,magmortar,typhlosion,charizard
    basculegion  as basculegion  water/ghost      5/6  first wild L39  torkoal,magcargo,magmortar,typhlosion,charizard
    trapinch     as flygon       ground/dragon    5/6  first wild L25  torkoal,arcanine,magcargo,magmortar,typhlosion
    rhydon       as rhydon       ground/rock      5/6  first wild L44  torkoal,arcanine,magcargo,magmortar,typhlosion
    rhyhorn      as rhydon       ground/rock      5/6  first wild L44  torkoal,arcanine,magcargo,magmortar,typhlosion
    basculin     as basculin     water            4/6  first wild L39  torkoal,magcargo,magmortar,typhlosion
    clodsire     as clodsire     poison/ground    4/6  first wild L24  torkoal,magcargo,magmortar,typhlosion

====================================================================================================
GYM 8  kanto_giovanni (Ground)   leader status: held
  NO ROSTER IN data/trainers.json. Nothing to simulate.

====================================================================================================
STARTERS
  starter       G1  G2  G3  G4  G5  G6  G7
  charmander    0/4  1/4  2/4  3/4  5/5  3/5  1/6   (final form at cap: charizard)
  squirtle      4/4  3/4  0/4  0/4  2/5  4/5  3/6   (final form at cap: blastoise)
  bulbasaur     4/4  3/4  2/4  1/4  1/5  1/5  1/6   (final form at cap: venusaur)
  cyndaquil     0/4  0/4  0/4  2/4  5/5  3/5  2/6   (final form at cap: typhlosion)
  totodile      4/4  3/4  0/4  0/4  1/5  3/5  2/6   (final form at cap: feraligatr)
  chikorita     4/4  3/4  1/4  1/4  0/5  2/5  1/6   (final form at cap: meganium)
  torchic       3/4  1/4  1/4  3/4  3/5  1/5  3/6   (final form at cap: blaziken)
  mudkip        4/4  2/4  4/4  0/4  5/5  5/5  5/6   (final form at cap: swampert)
  treecko       4/4  4/4  2/4  1/4  0/5  2/5  0/6   (final form at cap: sceptile)
  chimchar      2/4  0/4  0/4  3/4  4/5  2/5  5/6   (final form at cap: infernape)
  piplup        4/4  3/4  0/4  0/4  2/5  2/5  3/6   (final form at cap: empoleon)
  turtwig       4/4  3/4  2/4  4/4  2/5  5/5  2/6   (final form at cap: torterra)
  tepig         0/4  0/4  0/4  2/4  0/5  1/5  6/6   (final form at cap: emboar)
  oshawott      4/4  3/4  0/4  0/4  2/5  4/5  4/6   (final form at cap: samurott)
  snivy         4/4  3/4  0/4  0/4  0/5  1/5  0/6   (final form at cap: serperior)
  fennekin      1/4  1/4  0/4  2/4  5/5  3/5  6/6   (final form at cap: delphox)
  froakie       4/4  2/4  0/4  0/4  2/5  2/5  2/6   (final form at cap: greninja)
  chespin       4/4  3/4  3/4  0/4  0/5  1/5  1/6   (final form at cap: chesnaught)
  litten        0/4  1/4  1/4  4/4  4/5  4/5  4/6   (final form at cap: incineroar)
  popplio       3/4  2/4  0/4  1/4  2/5  4/5  5/6   (final form at cap: primarina)
  rowlet        2/4  3/4  0/4  4/4  4/5  4/5  1/6   (final form at cap: decidueye)
  scorbunny     0/4  0/4  0/4  4/4  5/5  4/5  2/6   (final form at cap: cinderace)
  sobble        4/4  2/4  0/4  0/4  2/5  3/5  3/6   (final form at cap: inteleon)
  grookey       4/4  3/4  2/4  1/4  0/5  4/5  1/6   (final form at cap: rillaboom)
  fuecoco       1/4  1/4  1/4  2/4  5/5  3/5  3/6   (final form at cap: skeledirge)
  quaxly        4/4  3/4  0/4  0/4  1/5  2/5  5/6   (final form at cap: quaquaval)
  sprigatito    4/4  4/4  2/4  1/4  0/5  2/5  0/6   (final form at cap: meowscarada)
  pikachu       0/4  2/4  0/4  0/4  1/5  0/5  0/6   (final form at cap: pikachu)
  eevee         0/4  2/4  0/4  0/4  0/5  0/5  0/6   (final form at cap: eevee)
  pichu         0/4  1/4  0/4  0/4  0/5  0/5  0/6   (final form at cap: pichu)
  bagon         1/4  2/4  1/4  0/4  1/5  1/5  4/6   (final form at cap: salamence)
  azurill       1/4  0/4  0/4  0/4  0/5  0/5  0/6   (final form at cap: azurill)
  budew         2/4  2/4  0/4  0/4  0/5  0/5  0/6   (final form at cap: budew)
```
