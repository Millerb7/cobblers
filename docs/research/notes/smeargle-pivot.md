# Smeargle as a fast pivot: U-turn, the entry hit, the threat, and the total

**Status:** research and simulation only (2026-10-08). No data changed. The owner decides.
**Premise (the owner, 2026-10-08):** Smeargle is a fast pivot, not a set-up sweeper. It leads with an attacking
move for Protean STAB, U-turns out, and comes back as a different type. **The Sketch cap was removed the same day**
(kept as `superseded_sketch_cap` in `data/mythical_starters.json`, commit e25882e), so nothing below spends Sketches
against a budget.
**Read:** jars in `C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/` (Cobblemon 1.8.0,
TMCraft 1.4.19), read only. **Ran:** `tools/mythical_starters.py measure`, and the scratch script `pivot_sim.py`
(session scratchpad; it monkeypatches `tools/battle_sim.py` the same way the earlier `smeargle_sim.py` did and
writes nothing in the repo). Labels: **VERIFIED** read in a jar or data file; **MEASURED** a battle_sim number;
**PROXY** sim numbers combined by hand (see section 3); **ASSUMED** not checked.

## 1. How it gets U-turn

- **Not by learnset.** The jar's Smeargle learnset is `1:sketch` plus tutor, legacy and special entries; no `tm:`
  entry, no U-turn, Volt Switch or Flip Turn (VERIFIED, `generation2/smeargle.json`). Our starter forms carry
  `data/mythical_starters.json` `starter_smeargle.moves`, which has none either.
- **Not by TM or tutor as things stand.**
  - Cobblemon's native TM (`data/cobblemon/tms/uturn.json`: 7 bug gems and a Shed Shell, `cobblemon:unlockable`)
    is refused unless `pokemon.getForm().getMoves().tmLearnableMoves()` contains the move (VERIFIED,
    `TechnicalMachineItem`, offsets 42-66, else `tms.cannot_learn`).
  - TMCraft `tm_uturn` needs `isLearnedByLevelUp` or `isLearnedByTM`; `tutor_` needs level-up or tutor (VERIFIED,
    `TMMoveTeachingItem` and `TutorMoveTeachingItem`).
  - TMCraft `star_<move>` teaches anything (`StarMoveTeachingItem.isPokemonAbleToLearnMove` is `iconst_1; ireturn`,
    VERIFIED). But no recipe makes a star or a blank star, and the villager trades sell only tutor and egg items
    (VERIFIED: jar recipes and the trade-offer classes). That matches `docs/research/OBTAINABILITY_MODS.md` P3.
  - **A lever we own:** the native TM reads the FORM's learnset. A `tm:uturn` entry on the three Smeargle forms
    would let the gym-gem TM teach it. ASSUMED that `tmLearnableMoves()` is the `tm:` entries (named so, body not
    read). Today `mythical_starters.py check` would refuse the entry: it accepts only `level:move` entries that are
    in Smeargle's own 1.8.0 learnset.
- **By Sketch, which copies `target.lastMove`.** The target must have USED the move in that battle. A target that
  switched has `lastMove = null` (VERIFIED, `sim/pokemon.js:1137` in `clearVolatile`). Sources, all VERIFIED from
  data:
  - **Wild** (`data/spawns.json`, weight > 0; the jar learnset at the spawn's top level, and the move among the
    last four learnt; that wild Pokemon know their last four level-up moves is ASSUMED):
    - Gligar 25-30 (U-turn at 30), common;
    - Mienfoo 25-32 (U-turn at 30), uncommon;
    - Dedenne 33-43 (Volt Switch at 30), rare;
    - Drizzile 38-39 and Inteleon 38-48 (U-turn at 30). The 2026-10-06 availability table puts these on route 7,
      the gym 7 leg. Gligar and Mienfoo are not in that table, so their leg is not confirmed.

    Only a level-30-or-higher Gligar or Mienfoo knows the move.
  - **Trainers:** Giovanni's Persian (52, gym 8), route 9 trainer 10's Crobat (58), Lance's Flygon (58), Blue's
    Pidgeot (58); Challenge-mode Surge's Vikavolt (28, Volt Switch); arena sets.
  - **Co-op:** any friend's Pokemon that knows it, in a PvP battle without level adjustment (the earlier note,
    section 2).

  **So the pivot comes online between cap 30 (a level-30 wild Gligar or Mienfoo) and gym 7 (route 7 Drizzile).
  It does not come at gym 8.** With the cap gone, U-turn costs nothing to keep alongside the attacks.

## 2. Mechanics that shape the role (VERIFIED)

- **It always comes in as Normal.** A Pokemon switching out runs `clearVolatile` (`sim/battle-actions.js:120`).
  That ends in `setSpecies(this.baseSpecies)` (`sim/pokemon.js:1150`), which runs `setType(species.types)`
  (`:1008`). Protean's lock clears on switch-in (the earlier note, section 1). So "comes back as something else"
  happens on its first move, never on entry. **The hit coming in always lands on a Normal type:** weak to Fighting,
  immune to Ghost.
- **U-turn** is 70 BP, Bug, physical, `selfSwitch: true` (`data/moves.js`). If U-turn is its first move after
  entering, Protean makes it Bug and U-turn gets STAB.
- **Only a slow U-turn gives a free switch.** When Smeargle is faster, it U-turns first and the partner comes in
  under the foe's move, which the foe chose against Smeargle. When it is slower, it takes the hit, U-turns, and the
  partner enters free. At 92-100 base speed it outspeeds 26-28 of the 46. **Most of its U-turns are therefore
  "chip, then the partner takes the hit", not a free switch.**

## 3. Method

- **Opponents:** the 46 of gyms 6-8 (caps 45/50/55), the Elite Four (60) and Blue (62), `data/trainers.json`. IVs
  15, EVs 0, held items and abilities as authored, Blaine's sun.
- **Smeargle:** at the cap, Gen 9 Protean (patched as in `smeargle_sim.py`). It uses the "fought" pool: every move
  a trainer below the cap carries, four chosen per opponent team. Sketch is unlimited, so re-tooling per fight is
  allowed. A run that held it to 10 Sketches moved the duels by 0-1 (29 vs 29 at 450, 36 vs 37 at 500).
- **The sim cannot model pivoting.** `battle_sim` has no U-turn switch: `selfSwitch` moves are excluded from the
  pools, and its switching mode is untrustworthy by its own docstring. So survival, threat and the partner gain are
  **PROXIES**: battle_sim's own `damage` (the top roll backed out of its average-times-accuracy, and the bottom roll
  at 0.85; no crits) and `duel`, combined by hand. Only the band (section 6) is a plain simulation.
- **Hits survived.** "Free entry" is a lead or a switch-in after a faint: attack then U-turn when faster, U-turn at
  once when slower. Either way it must survive one top-roll hit. "Hard entry" is switching in on a hit; that adds
  one, so two.

## 4. Survival on entry (PROXY)

| spread | BST | survives 1 hit (free entry) /46 | survives 2 (hard entry) /46 | outspeeds /46 | median entry hit, top roll |
|---|---|---|---|---|---|
| current 74/79/60/79/60/98 | 450 | 26 | **3** | 27 | 89.6% |
| fast-mixed 82/88/67/88/67/108 | 500 | 31 | 7 | 33 | 78.5% |
| pivot 90/80/75/80/75/100 | 500 | 38 | 13 | 28 | 67.4% |
| **proposed 92/68/78/68/78/92** | **476** | **38** | **15** | 26 | 63.2% |
| tank 95/78/80/78/80/89 | 500 | 38 | 16 | 26 | 61.0% |

- **At 450 it is not a pivot by the owner's test.** It dies on entry to 20 of 46, and survives a hard switch-in
  plus one more hit against 3.
- **Bulk, not total, fixes it, and it saturates at 38.** The eight that still kill it at 500 are type, not stats:
  Close Combat from Hitmontop, Machamp, Hariyama, Heracross and Hitmonlee (110-168% at 500); Lucario's Aura Sphere;
  Gengar's Focus Blast; Typhlosion's sun Eruption. **Never bring it in on a Fighting user** (all of Bruno).
- Arena tiers 4-7 (65-76), at the proposed spread: free entry 19/20 at level parity, 20/20 at level 80.

## 5. The threat (PROXY)

Its best Protean-STAB hit from the kit, as % of the foe's HP, gyms 6-8, Elite Four and Champion, /46:

| spread | sure OHKO (bottom roll, no Sash/Sturdy) | 2HKO (bottom roll >= 50%) | median bottom roll | U-turn alone, no STAB / Bug STAB (median) |
|---|---|---|---|---|
| 450 current | 14 | 44 | 84.5% | 14.2% / 21.3% |
| 500 pivot | 15 | 44 | 85.0% | 14.5% / 21.8% |
| 476 proposed | 13 | 42 | 74.1% | 12.6% / 18.9% |

- **U-turn alone is chip: about 13-15%, or about 20% with Bug STAB.** The threat is the lead attack, a 2HKO on
  42-44 of 46.
- Its own attack plus U-turn removes 7 (476) to 15 (500 pivot) of the 46 outright, before anything comes in.
- **"Level 80" does not exist in our campaign.** Caps are 45/50/55, 60, 62 and then 100
  (`docs/mechanics/LEAGUE_LEVEL_CAP.md`). The highest authored fight is arena tier 7, ace 76. Arena tiers 4-7 with
  the full fought pool, at the proposed spread:
  - at parity: 4/20 sure OHKO, 19/20 2HKO;
  - at level 80: 10/20 sure OHKO, 20/20 2HKO.

## 6. What comes in behind it (PROXY)

The partners are every catchable family in `derived/availability.json` (2026-10-06, read from the integration
worktree): 141-197 per opponent, with `battle_sim`'s own level-up movesets. Each partner fought each foe 1v1 in
three ways:
- as a lead;
- after a hard switch (taking the foe's best hit on it);
- behind the pivot: the foe has taken Smeargle's attack and U-turn, and the partner takes the hit aimed at Smeargle
  if Smeargle was faster.

At the 476 spread: Smeargle kills 7 foes itself, dies before it can U-turn against 16, and pivots on 23. On those
23, partner wins are 1,685 as a lead, 885 after a hard switch, and **2,707 behind the pivot** (of 4,290).

- **It roughly triples what a hard switch gets in and adds 60% to a lead.** Almost all of that is the chip. The
  free switch happens only against the four faster foes it survives: Froslass, Mismagius, Aerodactyl and Pidgeot.
- **It unlocks no foe.** Every foe it pivots on is already beaten by more than five partners as a lead.
- **What gains most is frail or weak:** Illumise, Emolga, Xatu, Pidgeot, Volbeat, Glalie, Altaria, Jumpluff.
- **The foes it works on are the slow, bulky ones:** Bronzong, Torkoal, Hippowdon, Mudsdale, Walrein, Lapras,
  Spiritomb, Dusknoir, Dragonite, Blastoise.
- **The fast attackers (Alakazam, Arcanine, Typhlosion, Charizard, Weavile, Gengar, Chandelure) kill it first.**
  These are the ones where a free switch would matter.

## 7. The band (MEASURED)

Eight native finals: Lunala, Solgaleo, Urshifu, Silvally, Naganadel, Melmetal, Volcarona and Flutter Mane. The
first five reproduce the earlier note's table exactly.

| | duels g6-8 /16 | League /30 | all /46 | solo g6-8 | solo League | `measure` g6-8 | `measure` total /35 |
|---|---|---|---|---|---|---|---|
| band of the eight | 8-14 | 12-26 | 22-38 | 2.9-7.4 | 6.7-15.9 | 9-15 | **15-20** |
| 450 current | 12 | 17 | 29 | 3.6 | 8.4 | 10 | 19 |
| 480 fast-mixed | **15** | 20 | 35 | 3.8 | 9.3 | 14 | **23** |
| 500 pivot 90/80/75/80/75/100 | 14 | 23 | 37 | 4.1 | 9.0 | 13 | **22** |
| 500 tank 95/78/80/78/80/89 | 13 | 22 | 35 | 4.3 | 9.8 | 12 | **21** |
| 480 92/70/78/70/78/92 | 13 | 22 | 35 | 4.2 | 8.0 | 12 | **21** |
| **476 92/68/78/68/78/92** | 13 | 22 | 35 | 4.2 | 7.8 | 11 | **20** |
| 470 88/66/76/66/76/98 | 13 | 22 | 35 | 4.1 | 6.9 | 11 | 20 |
| 464 82/74/68/74/68/98 | 13 | 19 | 32 | 4.2 | 7.6 | 11 | 20 |

**Verdict.**
- **500 is inside the 46-fight band but above the `measure` band:** 22 of 35 against a top of 20. On the 46 it
  ties Lunala's 14 of 16 at gyms 6-8. Every 500 tried and every 480 is at 21 to 23.
- **476 is the highest total found inside both,** with the spread 92/68/78/68/78/92. It sits on the top edge (20
  of 35, tied with Cosmog and Misdreavus). The edge is one duel wide: the same shape at 480 is 21.
- **Why 500 cannot fit:** Smeargle's stage 1 and 2 forms already score 9 at gyms 1-5, joint top with Misdreavus.
  So the final has only 11 duels of room at gyms 6-8 before the total passes 20. A lighter stage 2 would open room
  for a heavier final. That is not measured.
- **What 476 buys over 500:** the same 38 free entries and more hard entries (15 against 13). The cost is attack
  (68 against 80, 13 sure OHKOs against 15) and speed. Speed 92 against 100 loses two outspeeds at these caps: 26
  against 28.
- If the owner wants speed 98 kept, 88/66/76/66/76/98 (470) is also in band: free entry 37, hard entry 11.

## 8. In-game test: what to watch for

Fight Sabrina, then Lorelei and Agatha, with the 476 form, U-turn Sketched, and three attacks of different types.

1. **Entry type.** On every switch-in, Smeargle shows as Normal. After its first move it shows the move's type,
   and only one change per stay. (Verify `-start typechange` in the battle log, and no second change.)
2. **U-turn first.** Used as its first move, U-turn turns it Bug and hits for STAB. Compare the chip with one used
   after an attack.
3. **Speed order.** Against a slower foe, the partner takes the foe's hit that turn. Against a faster foe that it
   survives (Froslass, Mismagius), the partner comes in free. Note which happened.
4. **The entry hit.** Hard-switch into a Psychic from Sabrina and a Lorelei Ice move, and record the % lost.
   Predicted top rolls at 476 (no crits):
   - Sabrina's Alakazam, Psychic: 83%;
   - Hatterene, Psychic: 58%;
   - Mamoswine, Earthquake: 89%;
   - Jynx, Focus Blast: 89%;
   - Froslass, Icy Wind: 21%.

   Never test a switch into Bruno.
5. **The return.** Bring it back after the partner and check that it is Normal again, and that its next attack
   picks a new type with STAB.
6. **Sketch.** Copy U-turn from a level-30 Gligar or Mienfoo, or from Giovanni's Persian. It works only after the
   target has used U-turn in that battle. Check that the move is still there after the battle, and that it can be
   re-slotted from the bench.
7. **The RCT AI.** Does the leader switch out against a type it reads as bad? `battle_sim` never switches the
   leader, and every leader declares `switchBias` 0.65.

## Repository disagreements found

- The brief's "threaten anything at level 80": no authored fight is at 80. The real caps are used here, and level
  80 only for the post-Champion arena.
- "The other seven finals" are eight Pokemon, because Cosmog has two. Volcarona lowers the League solo floor to 6.7.
- The two bands disagree. Every 500 is inside the 46-fight set and outside `measure`'s 15-20, because `measure`'s
  total includes the stage-1 and stage-2 forms.
- `tools/mythical_starters.py check` refuses any `tm:` entry or any move outside Smeargle's own learnset. Giving the
  forms `tm:uturn` would need that rule changed.
- `tools/battle_sim.py` still reads the unused Showdown copy (earlier note, section 0). No move used here differs
  between the copies.
