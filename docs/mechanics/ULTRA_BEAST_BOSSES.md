# Ultra Beast bosses: nine unused Ultra Beasts as dungeon bosses

**Status: DESIGN ONLY (content-architect, 2026-10-09).** Nothing here is built, generated or run. It answers the
owner's instruction of 2026-10-09, relayed by the brief: **"each unused ultra beast should become a dungeon boss."** It
designs a boss for every one of them and says what may land in the Night Shift. Under the owner's standing rule, "build
nothing past the Night Shift until the owner has played it", everything else waits.

**It builds on these, and reopens none of them:**
- the dungeon engine and its staged boss (`docs/mechanics/DUNGEONS.md` 3.2; `tools/dungeon.py` as built);
- the dungeon list and its legendaries (`DUNGEONS.md` 8 and 10, D18);
- the Street (`DUNGEON_2_STREET.md`) and the Patriarch (`DUNGEON_3_PATRIARCH.md`);
- every catch after the Champion (D8; `DUNGEON_PLACEMENT.md` 3);
- the Beast Ball key (`data/key_ball.json`; `docs/research/notes/beast-ball-key-1.8.0.md`);
- the catch-loss design, which anchors a dungeon legendary by species (`DUNGEON_CATCHES.md` 9).

Labels as in `DUNGEONS.md`:
- **VERIFIED**: read in source or a file, with the citation.
- **ASSUMED**: inferred and not checked. *(memory)* marks Pokemon canon recalled, not read.
- ***relayed***: a number from another document, not re-measured here, with its source.
- ***computed***: worked here from a formula someone else verified.
- ***planning***: a value chosen so the arithmetic can be done, to be replaced by a timing.

---

## 1. The question

Which Ultra Beast bosses which dungeon or band? Nine Ultra Beasts go into six-plus dungeons, so some dungeons may hold
two and some bands may rotate. For each, the design must settle:
- where it sits in the spine;
- its level per band and the catch gate;
- how it is presented;
- its moveset and item intent;
- whether it is once per player or repeatable;
- what happens to its inherited wild spawns.

## 2. Findings (read before the design: two change what can be built)

| # | Finding | Evidence |
|---|---|---|
| F1 | **Seven of the nine render as the doll today.** Nihilego, Buzzwole, Pheromosa, Xurkitree, Guzzlord, Stakataka and Blacephalon have their only model in `ATMxMSD RP.zip`. Our overlay does not enable that pack: it is in the subset manifest, built but not delivered. **Only Kartana (MissingMons RP) and Celesteela (PlanetaCobblemon RP) render.** The brief's "models from three client resource packs" repeats `ultra-beasts-1.8.0.md`, which the later note corrects. The delivery decision is ADR-006 (Proposed), or the owner's v4.0 hash route (STATE "Client models", `docs/STATE.md:317-321`), which is "not adopted, not seen in game" | `docs/research/notes/unhomed-legendaries-1.8.0.md:65-76`, `:126-127`, `:209-216` (VERIFIED as a file check there; *relayed*) |
| F2 | **A tagged Ultra Beast would get the Beast Ball's x5 twice.** The jar's Beast Ball is `LabelModifier(5.0, true, "ultra_beast")`, applied as `ballBonus`. The key-ball callback separately multiplies `catch_rate` by 5 for a tagged target and a Beast Ball. The formula multiplies both: `a = ballMutator((3 maxHP - 2 HP) x catchRate x inBattle, ballBonus) / (3 maxHP) x ...`. The nine carry the `ultra_beast` label. So a tagged UB would be caught at **x25**: **100% a throw at full HP for catch rate 45** and 98.5% for catch rate 30 (section 8). Entei is not a UB, which is why this never arose | `beast-ball-key-1.8.0.md:32-39`, `:56-61`; `data/key_ball.json:11-12`; `ultra-beasts-1.8.0.md:10` (label). REASONED from VERIFIED parts; NOT RUN (probe UB3) |
| F3 | **The built boss chain is NPC-only, and its class takes species and level only.** `boss_classes` writes `"<ace> level=<n>"`, plus the escort at the last stage from band 4. It has no moves or held item, and no wild stage | `tools/dungeon.py:508-527` (VERIFIED, read). The wild stage is the Patriarch's E-P6, not built (`DUNGEON_3_PATRIARCH.md:327`) |
| F4 | **An NPC's Pokemon cannot be caught**: it is refused at the hit as `not_wild`. A pre-Champion boss is therefore fight-only by construction | `beast-ball-key-1.8.0.md:151-152` (VERIFIED as a refusal Cobblemon has; ASSUMED that an NPC's battler takes that path, U4) |
| F5 | **NPC battles use `StrongBattleAI`. Which AI a wild battle uses is not traced** (Strong or Random) | `docs/research/DUNGEON_MECHANISMS.md:229`; `docs/research/notes/dynamax-1.8.0.md:102` (VERIFIED: "not traced") |
| F6 | **Catch rates** (*relayed*, from the jar's species files via the note): 45 for Nihilego, Buzzwole, Pheromosa, Xurkitree, Guzzlord, Kartana and Celesteela; **30** for Stakataka and Blacephalon. Every one is 570 BST | `unhomed-legendaries-1.8.0.md:126-127`, `:209-216` |
| F7 | **The inherited wild spawns** (COBBLEVERSE-DP `spawn_pool_world`, all ultra-rare, *relayed*): | `unhomed-legendaries-1.8.0.md` (same rows); `:41-45` for what the suppression keeps |
| | - Blacephalon 55-62, `is_spooky`; | |
| | - Buzzwole 60-70, `is_jungle`; | |
| | - Nihilego 60-78, `is_ocean`; | |
| | - Pheromosa 55-65, `blooming_valley` and the End; | |
| | - Stakataka 60-72, `deep_dark`; | |
| | - Kartana 55-70, `cherry_grove`; | |
| | - Guzzlord, Xurkitree and Celesteela in the End only, which has no door in our world. | |
| | Outside the route boxes the suppression keeps defaults. **The live world has no suppression at all.** Whether each biome is painted was not sampled. | |
| F8 | **The mechanism to switch them off exists and is proven.** `data/spawn_suppression.json` `removed_species` drops every inherited detail naming a listed species, in every dimension, and fails closed on verify. It was written for the paradoxes (EXP-012 V4/V5, *relayed*) | `data/spawn_suppression.json:47-61` (VERIFIED, read) |
| F9 | **`DUNGEONS.md` 8 gives the Night Shift, the Street and the Cistern an NPC boss with "no catch".** The same section says those NPC characters "remain a proposal for `trainer-balance-designer`" (`:840-842`). This design changes all three. Owner to confirm (U-Q1) | `DUNGEONS.md:831-842` (read) |
| F10 | **`DUNGEONS.md` 8 lists Nihilego in group C, "unusable until the client pack ships"**, and says no dungeon takes one. That is F1 said once. This design takes them anyway, **gated on delivery**, and says so per boss | `DUNGEONS.md:826-829` |
| F11 | **The rip oval is one animated texture on an `item_display`**, sized to a 3 x 4 quad. It was drawn from the owner's description of an Ultra Wormhole | `tools/rip_art.py:2-23`; `data/dungeons.json:205-206` (read) |

---

## 3. The rule: what an Ultra Beast boss is

One shape for all nine, so one engine extension serves every dungeon.

1. **Bands 1-5: fight-only, an NPC-held Ultra Beast.**
   - The stage NPC is the dungeon's own human boss character, and its party is the Ultra Beast alone. From band 4 an
     escort joins the last stage (`DUNGEONS.md` 3.2, as built).
   - This is the built chain (F3) with the species changed, so it uses `StrongBattleAI` (F5) and cannot be caught (F4,
     D8).
   - The fiction is that each human has a bargain with the thing from the rip (section 4).
2. **Band 6: the last stage is the Ultra Beast itself, wild, a key boss** (the Patriarch's Yveltal pattern, E-P6).
   - It spawns by macro at **level 100**, which is the band-6 cap, so the cap never refuses the throw
     (`DUNGEON_PLACEMENT.md` Q8).
   - In the same function it is bound, leashed, tagged `cobblers.key_boss` **and `cobblers.key_native`** (section 8),
     and given the claims exempt tag.
   - The stage ends on its faint or its capture.
3. **The catch is once per player, per species.** An advancement is granted by `pokemon_captured`, as Entei's is. After
   it, that player's band-6 last stage is **farm mode**: still wild, still key-tagged, `uncatchable`, fought for the exit
   (Entei's and Yveltal's farm mode). **The fight itself repeats on every run, at every band.**
4. **The catch is anchored.** A caught dungeon UB is never held or forfeited by the catch-loss engine:
   `DUNGEON_CATCHES.md` 9 anchors every band-6 boss catch species. The nine join V-C1's anchor list.
5. **Two places in a spine** (section 4):
   - **the spine boss**, where the dungeon's boss is a human character and not a legendary;
   - **the wormhole leg**, an optional side room, where the spine boss is already an approved legendary (Yveltal,
     Dialga, Entei). No run has two required bosses.

**Why an NPC-held UB at bands 1-5 and not a wild `uncatchable` one.**
- The NPC chain is built, and probe C1 tests it. A wild chain is unbuilt at every stage.
- The NPC uses `StrongBattleAI`. A wild battler's AI is untraced (F5), and a random-move boss is no boss.
- The NPC's Pokemon is uncatchable by Cobblemon's own `not_wild` rule, with no extra property to keep right.
- Cost of this choice: the battle reads as a trainer battle ("The Foreman sent out Xurkitree"). The fiction carries it.
  An invisible NPC proxy named for the wormhole is the alternative (U-Q4), unproven (UB4).

---

## 4. Which Ultra Beast, where

Ultra Space homes and version pairs are *(memory)*, ASSUMED: flavour for the writer, not facts the design rests on.

| Dungeon | Role | Ultra Beast (type, catch rate) | Why it fits |
|---|---|---|---|
| 1 **The Night Shift** | spine boss, every band | **Xurkitree** (electric, 45) | The mine's lamps "are still lit" (`DUNGEONS.md:939-941`): something lives in the wiring. The run already has electric bones: the Powerhouse den holds the Electirizer, and the placeholder aces are Electabuzz and Electivire (`data/dungeons.json:230`). Ultra Plant *(memory)*. **The Foreman never came up because he stayed with it** |
| 2 **The Street That Ends at Nothing** | spine boss, every band | **Guzzlord** (dark/dragon, 45) | A city whose street ends at nothing: **it ate the rest.** Guzzlord's home is a ruined city (Ultra Ruin, *(memory)*). Dark/dragon sits against the Street's ghost, steel and psychic families and Palkia's space. **The Warden keeps it fed so it does not come for the last street** |
| 4 **The Last Cistern** | spine boss, every band | **Nihilego** (rock/poison, 45) | A reservoir the pumps still fill (`DUNGEONS.md:836`), and something poisonous in the water. Nihilego is the parasite UB that takes a host *(memory)*: **the waterworks keeper is its host**, and band 6's last stage is the moment it lets go of him. Its inherited spawn is the ocean (F7) |
| 3 **Under the Patriarch** | wormhole leg; the pair rotates | **Kartana** (grass/steel, 45) / **Celesteela** (steel/flying, 45) | Yveltal is the approved boss. The two "made from plants" *(memory: paper, bamboo)* came through the root mass: Kartana cuts the roots the Pruner fails to (`DUNGEON_3_PATRIARCH.md:203`), and Celesteela grows up through them. A version pair *(memory)*. **The only two that render today (F1)** |
| 5 **The Temple Calendar** | wormhole leg; the pair rotates | **Buzzwole** / **Pheromosa** (both bug/fighting, 45) | Dialga is the approved boss. In a jungle temple *(memory: Ultra Jungle and Ultra Desert)*, a version pair, and **the calendar picks which one comes through**, so the pair's rotation is the Temple's own conceit |
| 6 **The Tower After the Fire** | wormhole leg; the pair rotates; band 6 only | **Stakataka** (rock/steel, 30) / **Blacephalon** (fire/ghost, 30) | Entei is the boss. Stakataka is a walking stone wall: the tower's stones. Blacephalon is fire and ghost: what is left after the fire. A version pair *(memory)*. **Waits for the Tower's re-home onto the engine** (`DUNGEONS.md` 12), so it is the last to be built |
| later: The Crucible | none | none | Heatran's alone |

**Nine, each exactly once.** Three single spine bosses and three rotating pairs. Poipole and Naganadel are excluded,
since they are used (the starter and the two towers).

**The pair's pick** (one rule, read at the threshold, frozen for the run):
- At band 6: the first of the pair whose catch advancement this player lacks.
- At bands 1-5, or once both are caught: alternate by in-game day parity (`time query day`, stored at the threshold).
- The entry board names tonight's one ("Tonight the wormhole opens on Buzzwole"), so co-op partners see the same one.
- In co-op each member's band-6 pick is their own, spawned per member, like the den's spawn.

**Where in the spine.**
- **Spine boss:** the `boss_arena` segment, the run's last leg before the exit room (`DUNGEONS.md` 11.1 #12). It
  changes no geometry.
- **Wormhole leg:** a new optional segment kind, `wormhole`. It is a side room 15-20 blocks off the spine, after the
  second stand and before the parkour. **Its oval must be visible from the spine**, the "make it OBVIOUS" rule of 3.7.
  It costs only clock, like the den and the lake. `world-content-dev` places it per dungeon.

---

## 5. Levels per band and the catch gate

Levels are the built rule: the band's **lower** cap plus the stage offset, `stage_level_offsets [-2, -1, 0]`,
`level_basis: band_min_cap` (`data/dungeons.json:227-229`). The caps are `data/dungeons.json`'s bands (*relayed*,
`DUNGEONS.md` 4.2).

| Band (caps) | Spine boss stages 1 / 2 / 3 | Wormhole leg (2 stages: -1, 0) | Catchable? |
|---|---|---|---|
| 1 (20, 25) | 18 / 19 / 20, NPC | 19 / 20, NPC | no (D8) |
| 2 (30, 35) | 28 / 29 / 30, NPC | 29 / 30, NPC | no |
| 3 (40, 45) | 38 / 39 / 40, NPC | 39 / 40, NPC | no |
| 4 (50, 55) | 48 / 49 / 50 + escort, NPC | 49 / 50, NPC | no |
| 5 (60, 62) | 58 / 59 / 60 + escort, NPC | 59 / 60, NPC | no |
| 6 (100) | 98 / 99 NPC, then **100 wild** | 99 NPC, then **100 wild** | **yes, once per player, Beast Ball only** |

- **The gate is the level cap and D8 together.** A wild UB exists only at band 6, at 100, which is the band's lower and
  only cap, so the cap rule ("a catchable boss at or under the entering player's cap") holds by construction. A
  generator check repeats it: no wild stage below band 6, and no wild level above the band's lower cap (V-UB2).
- **The Temple's first entry is band 5** if its gate is `gym8_cleared` (OPEN, `DUNGEON_PLACEMENT.md` Q13). **The
  Tower is band 6 only.** Its pair is catch-or-farm on every run and never NPC-held.
- **A UB at level 18 is not over-tuned by its level.** The arena rule holds: nothing above the band's cap. What makes
  it hard is **Beast Boost** *(memory: each KO raises its highest stat)*. A lone ace against six members snowballs with
  every member it takes down. That is the identity of these fights and their main balance risk: `battle_sim` is 1v1
  (`DUNGEON_PLACEMENT.md` 1), so the snowball must be timed in game (XT1).

---

## 6. How it is presented: the wormhole moment

The rips already **are** the owner's Ultra Wormhole: the same oval (F11). A boss's wormhole is the same `item_display`,
scaled up. The scale is a display transformation (ASSUMED, vanilla; UB6). That adds no art and no dependency, and gives
one visual language: **a rip is how they get in.**

**Spine boss arena.**
1. **On entering:** the human figure stands at the far third. Behind it, a large oval is already open and dim: the
   display at scale 2-3, with keeper particles `reverse_portal` drawn inward.
2. **Each stage:** the figure sends the UB out of the oval, and the stage NPC spawns as built. Between stages the UB
   goes back through and the oval pulses. The title names the stage ("II of III"). The cue line per dungeon replaces
   "He gets up again.":
   - Night Shift: "The lamps come back on."
   - Street: "It is still hungry."
   - Cistern: "He stands up. It is not him standing."
3. **After the last stage at bands 1-5:** the UB goes back through and the oval shrinks shut. The line is **"It goes
   back through. It does not stay for you yet."** It is the same promise as the lake's "It does not stir for you yet."
   (`DUNGEONS.md` 3.7), and the player can see it.
4. **At band 6, after stage 2:** the figure falls for good, and the oval flares (a scale-up and a burst of particles).
   The wild UB is spawned by macro at the oval's foot, then bound and tagged.
   - On its capture or faint, the oval collapses: the display is removed and the exit gate opens.
   - Farm mode is the same, with a different closing line: "It will come through again."

**Wormhole leg.** A side room with the oval on its far wall, visible from the spine's doorway. Entering the room's box
starts stage 1, the way a stand starts. The room's figure is optional. Without one, the leg needs the invisible proxy
(U-Q4, UB4), so **the recommended form gives each leg a figure.** Suggested figures, for the writer:
- the Patriarch: a root-tender;
- the Temple: a calendar-keeper;
- the Tower: the last mourner's apprentice.

**What the player is told before.** The entry board gains one line per UB dungeon: "Something came through here. It
is not from anywhere." At band 6 it adds: "It can be held. Only by a ball made for things that do not belong." The key
ball's own refusal line stays the owner's wording (`data/key_ball.json:18`). Its phrase "a thing this old" fits a
legendary better than a UB. Rewording it is the owner's call (U-Q6).

---

## 7. Moveset and item intent (for `trainer-balance-designer`)

**Intent only.** The designer reads each species' 1.8.0 learnset from the jar and the DP's `species_additions` (plan
step 1) and picks moves legal at the stage's level where the data allows. Every move named below is a **candidate
recalled from memory, ASSUMED**, and must be checked against that data.

Shape for every boss (the built rule, `DUNGEONS.md` 3.2: a different set and item per stage):
- **stage 1, "the probe":** status and chip damage, no item or a berry;
- **stage 2, "the drain":** sustain or setup, a defensive item;
- **stage 3, "the full kit":** its best offence and an offensive item.

| UB | Identity | Stage 1 | Stage 2 | Stage 3 | Escort (bands 4-5) |
|---|---|---|---|---|---|
| Xurkitree | special glass-cannon electric; "the lit line" | paralysis spread (Thunder Wave), chip | a boosting setup (Tail Glow) behind a defensive item | Thunderbolt-class STAB plus coverage (grass, fairy); Choice Specs or Life Orb | Magnezone (placeholder, `data/dungeons.json:231`) |
| Guzzlord | enormous HP, slow; "eats" | item removal (Knock Off: **it eats your held item**) | sustain and attrition; Leftovers | heavy physical/special dragon and dark; Assault Vest or Life Orb | a scavenger (designer's) |
| Nihilego | special rock/poison wall-breaker; "the host" | Toxic or Toxic Spikes; the poison in the water | Acid Spray-type SpD drops; Black Sludge | Power Gem, Sludge Wave; Life Orb | the keeper's water types |
| Kartana | huge Attack and Defence, frail on the special side | Swords Dance behind a Focus Sash | Leaf Blade, Sacred Sword | Smart Strike-class STAB; Life Orb | n/a (a leg has no escort) |
| Celesteela | bulky mixed | Leech Seed and Protect stall | Heavy Slam, Air Slash | mixed with fire coverage; Leftovers | n/a |
| Buzzwole | bulky physical | Bulk Up | Drain Punch, Leech Life (sustain) | Ice Punch coverage; Leftovers | n/a |
| Pheromosa | very fast, frail | speed control or a Focus Sash | Quiver Dance | High Jump Kick, Ice Beam; Life Orb | n/a |
| Stakataka | Trick Room setter, very slow | Trick Room | Gyro Ball, Stone Edge | under Trick Room; Iron Ball or Life Orb | n/a |
| Blacephalon | self-damaging nuke | Calm Mind | Shadow Ball, Flamethrower | its signature nuke (Mind Blown), which costs it HP; Life Orb | n/a |

- **The band-6 wild stage** carries its stage-3 set and item through the spawn's properties string (`moves=`,
  `held_item=`; the property names are ASSUMED until read, plan step 1).
- **The engine gap (F3):** the class writes species and level only. Per-stage moves and items need `aces` to carry a
  properties string or a per-stage record. That is a small engine change (plan step 5).
- **No bag items in boss battles** (`DUNGEONS.md` 3.1, *stands*).
- **Rewards:** the spine boss pays the band's bundle as built (`DUNGEONS.md` 9.2). A wormhole leg pays one escrowed
  roll on the dungeon's battle-item table. **Never a Beast Ball:** it is sold at a counter, so the reward generator
  already refuses it (`DUNGEONS.md` 9.2). A run must not pay its own key.

---

## 8. The catch: rate, the double-multiplier fix, cost

**The fix (F2): a UB boss gets x5 once, from the jar.**
- Every UB boss's bind function adds a second tag, `cobblers.key_native`, beside `cobblers.key_boss`.
- The key-ball rate callback multiplies only when `cobblers.key_boss` is present **and** `cobblers.key_native` is
  absent.
- The refusal callback is unchanged: it still refuses every other ball at any `key_boss`.
- This keys on a tag and not a species label, the world-shaped predicate (`data/key_ball.json:9`). The label is not
  known to be readable from MoLang, so a species check is not available anyway.
- `data/key_ball.json` gains the tag and a `does_not_cover` line: an untagged wild UB, if any survives suppression,
  gets the jar's x5 from any Beast Ball, as Cobblemon ships it.

**Per-throw chance, a Beast Ball in battle, x5 total.** ***Computed*** from the note's formula
(`beast-ball-key-1.8.0.md:56-70`), with no status and no critical capture. Expected throws are in brackets.

| Boss state | Catch rate 45 (7 UBs) | Catch rate 30 (Stakataka, Blacephalon) | If x25 (the defect), rate 45 |
|---|---|---|---|
| full HP | 40% (2.5) | 29% (3.4) | **100% (1)** |
| half HP | 67% (1.5) | 50% (2.0) | 100% |
| 1 HP | 91% (1.1) | 67% (1.5) | 100% |

**Recommend the canonical rate (x5 once), not Entei's price.**
- At $5,000 a ball (`DUNGEON_CATCHES.md` F11, *relayed*), a UB played to half HP costs about $7.5k-$10k.
- All nine come to about $72k: seven at $7.5k plus two at $10k.
- At Entei's price ($21k-$95k each, `beast-ball-key-1.8.0.md:211-214`, *relayed*), nine would cost $189k-$855k. Total
  income through the League is $427,228 (Normal) to $572,051 (Challenge) (`:202-203`, *relayed*). **At that price a
  collection of nine is unaffordable.**
- UBs are 570 BST, below the 580-720 legendaries, so cheaper is right.
- The fight, the sigil and the clock remain the gate.

**Once per player, repeatable fight.** Each species has its own catch advancement (`cobblers:dungeons/ub/<species>`).
That advancement is what the pair's pick reads, and what turns the stage to farm mode. Two members in a co-op slot need
the ball-ownership check for the wild stage, as for the lake (`tools/hoopa_cradle.py:233-247`, `DUNGEONS.md` 3.7).

**Clock.** The wild stage adds about 3.0 minutes at band 6 (***planning***, the Patriarch's figure,
`DUNGEON_3_PATRIARCH.md:276`). The Night Shift's band 6 is 31.1 required (*relayed*, `DUNGEONS.md` 4.2) + 3.0 = 34.1.
The clock is ceil(34.1 x 1.25) = **43** (was 39), with 8.9 of slack. Each later dungeon recomputes its own. A wormhole
leg is optional: about 4.5 minutes at bands 1-5 and 5.5 at band 6 (***planning***: two stages, walk, cue, throws). It
takes most of a run's slack, so **it excludes greed, the lake and the den**: the dungeon's usual trade.

---

## 9. Their inherited wild spawns: recommend switching all nine off

**Recommendation: add all nine to `data/spawn_suppression.json` `removed_species`** ("never wild, anywhere"). The tool
and its fail-closed verify already exist (F8). **The owner decides.**

Why:
1. **A dungeon is then the only source**, and the fiction holds: a thing that came through a rip.
   - A Nihilego surfacing in an open ocean undoes it (F7).
   - So does a Kartana in a cherry grove at 55-62, catchable with **any** ball by a player at cap 60/62 before the
     Champion. That is a pre-Champion UB catch, against the spirit of D8.
2. **The key keeps its meaning.** An untagged wild UB takes a Master Ball, and the jar's x5 from any Beast Ball.
3. **These spawns do not make a place.** The owner welcomes above-cap wild Pokemon "where they make a place" (STATE).
   These are ultra-rare biome draws in unauthored wilderness.
4. **One rule is cheaper than nine judgements.** Three are End-only and unreachable today (F7). Listing them costs
   nothing and holds if an End door ever opens.
5. **It is the owner's own precedent:** the paradoxes ("dungeon content; the wild stays as it is" became "switch the
   inherited paradox spawns off", `data/spawn_suppression.json:49`).

**The case against**, for the owner: an ultra-rare wild UB is a story when it happens. Keeping them leaves a free
second source and costs nothing to build.

**Extend the list's `species_source`.** Today it names the paradox-labelled species. It should also name "the 9
`ultra_beast`-labelled species other than Poipole and Naganadel, which have no inherited spawn
(`ultra-beasts-1.8.0.md:8-9`)". Give the tool a matching fail-closed check: fail if the jar labels a UB that is neither
listed nor declared homed. **This reaches only the inherited pools.** It does not cover a UB a trainer, an event or a
player puts in the world, which is the existing `not_covered` (`:61`).

---

## 10. Options considered

| Option | Rung (principle 6) | Blast radius | Multiplayer | World-critical | Verdict |
|---|---|---|---|---|---|
| **A. NPC-held UB at bands 1-5; wild key UB at band 6's last stage; spine boss or wormhole leg** | native NPCs and callbacks, datapack functions | the built chain with new species; one engine extension (E-P6, shared with the Patriarch); one callback guard | per member; the co-op ball check as the lake's | none new; inherits COBBLEVERSE-DP and the client packs (below) | **Recommended** |
| B. Wild `uncatchable` UB at every stage and band | native + datapack | a wild chain at every stage; untraced AI (F5); the victory hook for wild battles unproven | same | same | Rejected for now: costs more and is unproven. Revisit if UB5 shows wild battles use `StrongBattleAI` |
| C. UB only at band 6 (sealed display at bands 1-5, as Yveltal's cocoon) | native + datapack | least | same | same | Rejected: at bands 1-5 the dungeon's boss would not be the UB, against "become a dungeon boss" |
| D. Nine single dungeons, one UB each | content | needs 2-3 dungeons beyond the decided list | n/a | n/a | Rejected: the dungeon list is decided (D18, D19) |
| E. A custom mod for a true wild boss AI | last rung | new code in battles | sync | a new dependency | Not proposed: A is unproven, not disproven (principle 5) |

**Dependencies.**
- A caught UB lives in a player's party or PC. **COBBLEVERSE-DP becomes save-critical for these species**, as it
  already is for the 36 DP-only species (`unhomed-legendaries-1.8.0.md:305-307`). What Cobblemon does with a stored
  Pokemon whose species vanished is ASSUMED to be bad.
- Seven bosses need the ATMxMSD models delivered (F1).
- **No ADR is proposed.** This is content inside ADR-008's architecture. The suppression is a cheap, reversible list.
  The wild stage is already the Patriarch's E-P6.

---

## 11. What lands in the Night Shift, and what waits

**Only Xurkitree lands in the Night Shift**, and even it has three gates:
1. **Model delivery** (F1, the owner): ADR-006, or the v4.0 route after its in-game look. **No UB boss ships as a
   doll.** V-UB5 fails closed on that.
2. **The owner's playtest of the Night Shift as it stands.** The current placeholder chain (Electabuzz/Electivire)
   proves C1 first.
3. **The probes** (section 13) on renderable stand-ins: Kartana and Celesteela today, the seven after delivery.

**What could move early, outside any dungeon:**
- research step 1;
- the key-ball double-multiplier guard (plan step 3). It is a correctness fix needed before **any** UB is tagged, and
  it changes no place;
- the suppression (plan step 4), if the owner approves it.

**The cheapest UB boss there is:** if the models are delivered before the playtest, bands 1-5 of the Night Shift
change `aces` to `xurkitree`, a data change, and play as Xurkitree with no new engine. Moves and items, and band 6's
wild stage, follow the playtest.

**Waits, in this order:**
- the Street's Guzzlord and the Cistern's Nihilego, with their dungeons;
- the Patriarch's pair, with its dungeon. **These render today**, so this is the first pair that could be built;
- the Temple's pair, with its dungeon and gate;
- the Tower's pair, with the Tower's re-home (`DUNGEONS.md` 12).

---

## 12. Data model (for the builder; `data/dungeons.json`, schema bump `cobblers.dungeons/3`)

- **`boss`** (per dungeon) gains:
  - `stages_by_band`: per band, per stage, `{kind: "npc"|"wild", species, level_offset, properties}`. `properties` is
    the moves and held item, as a Cobblemon properties string;
  - `ub`: `{species, catch_advancement, wild_band: 6, key_tags: ["cobblers.key_boss", "cobblers.key_native"], farm:
    true}`;
  - `wormhole`: `{display_scale, at: [dx, dy, dz], cues: {stage, fall, close_promise, close_farm}}`.

  `aces` stays readable for the placeholder until the stages are authored.
- **A new segment kind `wormhole`:**
  - `{pair: [a, b], pick: {band6: "first_uncaught", else: "day_parity"}, stages: 2, figure, board_line}`;
  - `world-content-dev` sets its length and its offset off the spine.
- **`data/key_ball.json`:**
  - a `native_tag` field (`cobblers.key_native`) and its `why`;
  - the dungeon engine in `bosses` (one entry, `tools/dungeon.py`, "every wild stage's spawn function");
  - a `does_not_cover` line for untagged wild UBs.
- **`data/spawn_suppression.json` `removed_species`:** the nine, plus the source line (section 9), if approved.
- **The catch-loss anchor (`DUNGEON_CATCHES.md` 9):** generated from every `ub.species`, never hand-kept.

## 13. Validation (for `test-author`; independent of the builder)

- **V-UB1.** The nine appear exactly once across all dungeons, Poipole and Naganadel never. The audit's list of the
  nine comes from the **jar's** `ultra_beast` labels minus the two homed, not from `dungeons.json`.
- **V-UB2.** A `wild` stage appears only at band 6, only as a dungeon's last stage or a wormhole leg's last stage, at
  a level at or under band 6's lower cap. Its spawn function also binds, adds both key tags and the exempt tag (V23
  generalised).
- **V-UB3.** Only if suppression is approved: every UB species used is in `removed_species`, and
  `verify_removed_species` passes.
- **V-UB4.** The key-ball rate callback never multiplies for a target carrying `cobblers.key_native`, and every
  boss whose species the jar labels `ultra_beast` gets that tag at bind.
  - The label is read from the jar, not from our data.
  - **Mutate the generator, not the record:** drop the guard line in `tools/key_ball.py`, and the audit must fail.
- **V-UB5.** A UB species may appear in a built dungeon only if its model resolves in what players get (the
  enabled-pack check `tools/client_model_fix.py scan` uses). This fails closed while ATMxMSD is not delivered.
- **V-UB6.** Each UB species has one catch advancement, and the pair's pick reads only those advancements.
- **V-UB7.** No reward table pays a `cobblemon:beast_ball` (already implied by the counter rule; state it).

A contract in `data/system_contracts.json`: **the key ball's multiplier must not stack with the jar's label
modifier.** Owner: `key_ball`. Consumers: every UB boss.

## 14. Unknowns, as probes (staging, never live; the main session runs them, `qa-reviewer` grades)

| Id | Probe | Settles |
|---|---|---|
| **UB1** | Each UB spawned by macro `spawnpokemonat`. It renders and animates: idle, walk, battle, faint and send-out from an NPC. Kartana and Celesteela now; the seven after delivery | F1; no doll boss |
| **UB2** | Each UB in a wild battle and as an NPC's ace. Its ability resolves: **Beast Boost raises its highest stat after a KO and says so**. Its candidate moves work. The log shows no Showdown error | 3, 5, 7 |
| **UB3** | The double multiplier. A tagged UB with **only** `key_boss`, and a Beast Ball at full HP, about 10 throws: expect about 100% (x25). With `key_native` as well: expect about 40%. Also log the callback's `catch_rate` | F2, section 8 |
| **UB4** | An NPC class whose party is a DP-added species (`xurkitree level=18`) spawns and battles. A ball at its Pokemon is refused `not_wild`. For U-Q4, an NPC with a hidden body still starts the battle, and its name shows in the battle UI | 3, U4 |
| **UB5** | *(research, `cobblemon-researcher`, jar read)* Which AI a wild battle uses. Does `battle_victory`, or only faint and capture, fire for a wild boss? | option B; E-P6 |
| **UB6** | The rip's oval `item_display` at scale 3 in an arena: it reads from the arena door, its scale can be interpolated, and a UB spawned at its foot reads as coming through | 6 |
| **UB7** | The pair's pick: the day parity stored at the threshold, and the uncaught-first override at band 6 | 4 |
| **YV1** | (the Patriarch's) The wild last stage after an NPC chain: faint ends it, Beast Ball capture ends it, a Great Ball is refused and returned, then catch-once and farm mode | 3, E-P6 |

## 15. Plan (ordered; each one experiment or one task; costs are estimates in CLAUDE.md's terms, none measured)

| # | Step | Agent | Cost |
|---|---|---|---|
| 0 | Owner decisions U-Q1 to U-Q7, and the model delivery route (ADR-006 or v4.0) | the owner | none |
| 1 | The nine species read from the jar and the DP: labels, abilities, learnsets, catch rates, the properties-string names for moves and items; and UB5 | `cobblemon-researcher` | ~0.6M |
| 2 | The probe pack for UB1-UB4, UB6 and UB7 on Kartana and Celesteela; run; graded | `minecraft-systems-dev` (narrow); main session runs; `qa-reviewer` | ~2.6M + 0.6M |
| 3 | The `key_native` guard in `tools/key_ball.py` and `data/key_ball.json`; its validator V-UB4 and the contract, written by a different agent | `minecraft-systems-dev` (or main session, small); `test-author` | ~1M + 1M |
| 4 | If approved: the nine in `removed_species`, the source line, the jar-label check | `datapack-content-dev` | small |
| 5 | **After the owner's Night Shift playtest and delivery:** Xurkitree's stages per band (moves, items, escort), and the engine's per-stage properties | `trainer-balance-designer` (opus); `minecraft-systems-dev` | ~1.5M; ~2.6M |
| 6 | E-P6, the wild last stage with the wormhole cue and catch-once and farm mode; shared with the Patriarch's Yveltal | `minecraft-systems-dev` | ~4M |
| 7 | V-UB1, 2, 5, 6 and 7, and an independent audit (escalation rule 1: a softlock or a free key) | `test-author` (opus) | ~3M |
| 8 | Staging: the Night Shift at caps 20 and 100 with Xurkitree; the owner looks | main session; the owner | main-session time |
| later | Each other dungeon's UB(s) with that dungeon's own unit (`DUNGEONS.md` 13: about 7M a dungeon); the wormhole leg kind with the first dungeon that needs it (+2.6M, "a new leg mechanic") | the dungeon's builders | per dungeon |

## 16. Questions for the owner

1. **U-Q1.** Xurkitree, Guzzlord and Nihilego replace the Night Shift, Street and Cistern bosses' "no catch" NPC aces.
   The human figure stays as the UB's keeper. *Recommend yes* (F9).
2. **U-Q2.** The Night Shift at band 1 reveals a UB in the tutorial dungeon. Xurkitree at every band is *recommended*:
   one identity, a promise visible from the first run. Or the Foreman's Electivire at bands 1-2 and Xurkitree from
   band 3.
3. **U-Q3.** Switch off all nine inherited wild spawns (*recommended*, section 9), or keep them as ultra-rare finds.
4. **U-Q4.** The UB's holder is a visible human character (*recommended*: built, proven path) or an invisible proxy
   named for the wormhole (UB4, unproven).
5. **U-Q5.** The canonical catch rate, x5 once, about $7.5k-$10k a UB (*recommended*), or a lower rate toward Entei's
   price.
6. **U-Q6.** The key ball's refusal line says "a thing this old", which fits a legendary better than a UB. Keep it,
   or make it neutral: "Whatever could hold a thing like this, it is not this."
7. **U-Q7.** The model delivery route: it gates seven of the nine (F1), and it also fixes the 11 doll species already
   in our spawn tables (STATE:318).
