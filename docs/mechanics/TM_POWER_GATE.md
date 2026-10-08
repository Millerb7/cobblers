# TM gate by power

**Status: accepted and wired (the owner, 2026-10-08: "TAKE THE POWER RULE, with all 17 outlier groups applied as
proposed ... SHELF WINS where it disagrees ... Then switch the gate to the power rule").** `tools/tm_gate.py` now
places every TM by this rule; section 9 is what it places. Sections 1-8 are the proposal as the owner read it. The
per-TM table is `docs/mechanics/TM_POWER_GATE.json`, written by `tools/tm_power_score.py` and committed: the gate
reads it. Its "today" and "with the shelf" columns were dropped when it became the gate's input (they described the
type/grade rule, which is gone, and would have made the table stale whenever a shelf line moved).

The owner's direction (2026-10-08): gate a TM by what it does, not by its type or which leader teaches it, so a
player's options grow with progress whatever the type; base power drives it, but accuracy, PP, side effects,
priority and status moves must count too; the bands should make a curve; the 23 shelf TMs keep their authored
badges, and every disagreement is listed rather than resolved silently.

## 1. Inputs (measured 2026-10-08)

- **The TMs**: the 802 TMCraft TMs `tools/tm_gate.py` finds on the server snapshot
  `C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05` (TMCraft 1.4.19). Today's badges from the same
  run: {1: 134, 2: 23, 3: 47, 4: 39, 5: 78, 6: 65, 7: 89, 8: 327}. This matches the figure in the brief.
- **The moves**: `mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar!assets/mega_showdown/showdown/moves.js`, 952
  moves. Mega Showdown's ShowdownPatcher copies this file over Cobblemon's `data/moves.js` at startup
  (`docs/research/notes/sketch-cap-1.8.0.md` section 2), so this is the copy battles run. Its `mods/moves.js` is
  empty (`const Moves = {}`), and the Cobblemon 1.8.0 jar has no move registry data that would override it. Every
  one of the 802 TMs is a move id in it (`tmcraft:tm_<id>`).
- **Battle format**: every authored fight is singles. Measured: `data/trainers.json` 540 `battleFormat` and 180
  `format` entries, all `GEN_9_SINGLES`; `data/gym_trainers.json` 8 and `data/league_trainers.json` 5, all
  `GEN_9_SINGLES`. So doubles-only moves are valued near zero.
- **Level caps** (`docs/mechanics/PROGRESSION_LADDER.md` 4.1): a TM at badge B is available from the cap after the
  B-th leader: badge 1 = cap 25, 2 = 30, 3 = 35, 4 = 40, 5 = 45, 6 = 50, 7 = 55, 8 = the Elite Four.

A finding while reading the data: **Chloroblast's recoil is not in its move fields** (`moves.js:2570`, "Recoil
implemented in battle-actions.ts"); Mind Blown and Steel Beam carry `mindBlownRecoil`. The scorer applies it by hand.

## 2. The score

One number per move, in **power points**: a plain 80-power, 100%-accurate move with no effect scores 80, and
everything else is put on that scale. The score is meant to say "this is worth about an N-power hit".

### 2.1 Damaging moves

`score = accuracy x (power x hits x multipliers + side effects) + flat bonuses`

| Term | Value | Why |
|---|---|---|
| power | `basePower` | the data's own number |
| power, when it is 0 or computed | a nominal value per move (49 entries, 48 of them TMs, `NOMINAL` in the tool, each with its reason) | Low Kick, Gyro Ball, Seismic Toss, Magnitude, Eruption ... have no usable stated power. Magnitude is the weighted mean of Showdown's table, 71; one-hit KOs are 200 ("a KO") before their 30% accuracy; level-damage moves assume a level-50 user |
| power that only doubles in a condition | **left as stated** | Hex, Venoshock, Facade, Acrobatics, Knock Off, Weather Ball. Valuing the condition is a judgement per move; they are in the outliers instead |
| accuracy | `accuracy / 100`; `true` (never misses) = 1.0 | the expected share of uses that land; multiplies the side effects too, since they need a hit |
| hits | fixed n = n; 2-5 = 3.1 | Showdown's 2-5 distribution is 35/35/15/15 % |
| charge turn (`flags.charge`) | x0.5 | Solar Beam, Sky Attack, Meteor Beam: two turns per hit |
| recharge (`flags.recharge`) | x0.5 | Hyper Beam: two turns per hit |
| recoil | x(1 - half the recoil fraction): 1/3 = x0.83, 1/2 = x0.75 | HP lost is worth about half the damage dealt |
| half-HP recoil (`mindBlownRecoil`, and Chloroblast by hand) | x0.6 | |
| crash on miss (`hasCrashDamage`) | x0.9 | High Jump Kick |
| the user faints (`selfdestruct`) | x0.35 | Explosion trades a Pokemon for a hit |
| self stat drops | -7.5% per attack/sp.atk stage, -5% per defence/speed stage | Overheat x0.85, Close Combat x0.9: the next use is weaker |
| locked in, then confused (`self.volatileStatus: lockedmove`) | x0.85 | Outrage, Thrash, Petal Dance |
| cannot be used twice in a row (`cantusetwice`) | x0.75 | Gigaton Hammer, Blood Moon |
| conditional (27 moves, `CONDITIONAL`) | x0 to x0.9, each with its reason | Sucker Punch fails against a status move, Fake Out works only on the first turn, Future Sight lands two turns late, Aura Wheel fails for anyone but Morpeko (x0) |
| 5 PP or fewer | x0.95 | runs dry in a gauntlet; see 2.4 |
| always crits (`willCrit`) | x1.5; high crit ratio x1.04 | |
| side effect: status | chance x par 30, brn 30, frz 30, slp 40, psn 15, tox 25 | a 30% paralysis on Body Slam is worth +9 |
| side effect: flinch / confusion | chance x 15 / 12 | flinch needs the user to move first |
| side effect: target stat drop | chance x 8 per stage (speed 10) | Rock Tomb's guaranteed -1 speed is +10 |
| side effect: user stat raise | chance x 12 per attack/sp.atk/speed stage, 8 per defence | Flame Charge +12 |
| side effect only code describes | by hand for 8 moves (Tri Attack, Dire Claw, Anchor Shot ...), else 0 | |
| drain | 0.4 x the drained fraction x power | a point healed is worth 0.4 of a point dealt: Giga Drain 75 -> 90 |
| priority | +15 per level above 0 (at most 2 counted); -10 for negative | Extreme Speed +30, Quick Attack +15 |
| pivot (`selfSwitch`) | +20 | U-turn, Volt Switch, Flip Turn |
| forces a switch | +10 | Dragon Tail, Circle Throw |
| other code (`onAfterHit`, `onBasePower` ...) | **not valued**, and the record says "also code: not valued" | Knock Off's item removal, Bug Bite's berry: listed as outliers, not guessed |

### 2.2 Status moves

`score = accuracy x V`. V comes from the move's mechanic fields, added together:

| Field | Value | Why |
|---|---|---|
| inflicts paralysis / sleep / burn / bad poison / poison | 100 / 110 / 85 / 95 / 50 | the anchor the owner gave: Thunder Wave is worth more than most 60-power hits. At 100 x 90% it scores 90, a Surf |
| raises the user's attack or sp.atk | 35 a stage for two stages, half beyond; a second offensive stat at half | one +2 is worth about a 70-power hit. A Pokemon uses one attacking stat, so Shell Smash's sp.atk counts half for a physical user and vice versa |
| raises speed / evasion / defence or sp.def / accuracy | 30 / 30 / 20 / 10 a stage | |
| lowers the target's stats | 15 a stage (evasion 5) | Growl 15, Charm and Screech 30 before accuracy |
| raises the target's attack (Swagger, Flatter) | -15 a stage | the confusion is valued; the boost is a cost |
| hazards | Stealth Rock 85, Sticky Web 70, Spikes 65, Toxic Spikes 60 | |
| screens and side effects | Aurora Veil 90, Reflect / Light Screen 65, Tailwind 60, Safeguard 25 | |
| weather / terrain | rain, sun 50; sand, snow 35; hail 30 / terrain 45 | |
| field | Trick Room 80, Gravity 25, Magic Room and Wonder Room 15 | |
| volatile effects | Yawn 70, Leech Seed 60, Taunt and Encore 55, Substitute 50, Destiny Bond 45, Confusion 40, ... (`VOLATILE`) | |
| protect | Protect, Detect 45; the shields that also punish contact 55 | |
| heals half / a quarter | 75 / 40 | Roost, Slack Off, Soft-Boiled |
| forces a switch / pivots / Baton Pass | 45 / 25 / 40 | |
| slot effects | Revival Blessing 100, Healing Wish and Lunar Dance 90, Wish 60 | |
| the user faints | -30 | Memento, Healing Wish |
| ally-only boosts | x0.15 | every fight is singles |
| a charge turn | x0.5 | Geomancy |
| 5 PP or fewer | x0.95 | |
| a status move whose effect is only code | **by hand**, 88 moves in `STATUS_HAND`, each with a one-line reason; the record has `valued_by_hand: true` | Belly Drum, Strength Sap, Trick, Defog, Moonlight, Rest ... have no field the rule can read. Without a value they would all score 0 |

Of the 802 records, **136 carry `valued_by_hand: true`**: the 88 hand-valued status moves and the 48 nominal-power damaging moves.

### 2.3 Accuracy, PP, side effects, priority, status: the short answer

- **Accuracy** multiplies everything the move does when it lands (power and effects). It is the expected value of
  one use. Thunder (110, 70%) scores 83; Fire Blast (110, 85%) 91.
- **Side effects** are added as `chance x value`, in the same power points, so a 100% speed drop or a 30%
  paralysis is a few points and a guaranteed self-faint is a large multiplier.
- **Priority** is a flat bonus of 15 a level: it is worth the turn it wins, not a share of the damage.
- **Status moves** have no power, so they are valued directly on the same scale; the anchor is Thunder Wave at 90.
- **PP** gets only a small penalty, 5% at 5 PP or fewer, and nothing above that. Within the move list PP already
  falls as power rises (the 5-PP moves are the strongest), and between fights a party is healed, so PP only bites
  in a gauntlet or a long fight. A larger term would mostly shave the strongest moves a second time.

## 3. The bands

**Badge 1 below 35. After that, each badge is one step of ten base power plus up to four points of side effects:
badge 3 holds the 60-power moves (54 < score <= 64), badge 5 the 80s, badge 6 the 90s, badge 7 the 100s, and
badge 8 everything above 104.**

The tops sit four points above the round numbers because base powers cluster on them. With the first version's tops
exactly on 80 and 90, Crunch and Shadow Ball (80 plus a 20% drop, 81.6) came out a badge later than Dragon Claw (80),
and Thunderbolt (93) a badge later than Surf (90). Four points take in the common 10-30% side effects without
merging two steps.

| Badge | Cap it opens at | Score band | TMs by power | TMs with the shelf | Today |
|---:|---:|---|---:|---:|---:|
| 1 | 25 | < 35 | 163 | 166 | 134 |
| 2 | 30 | 35 - 54 | 122 | 122 | 23 |
| 3 | 35 | 54.1 - 64 | 110 | 107 | 47 |
| 4 | 40 | 64.1 - 74 | 104 | 103 | 39 |
| 5 | 45 | 74.1 - 84 | 107 | 109 | 78 |
| 6 | 50 | 84.1 - 94 | 99 | 96 | 65 |
| 7 | 55 | 94.1 - 104 | 66 | 66 | 89 |
| 8 | E4 | > 104 | 31 | 33 | 327 |

"With the shelf" is the proposal as it would run: a shelf TM keeps its authored badge, every other TM takes its
power badge. It is a curve that falls gently: about a hundred options a badge from 2 to 6, fewer and stronger at 7
and 8. Badge 1 is the largest because it is mostly junk: **141 of its 163 are status moves** (Growl, Splash, the
doubles-only moves), and 22 are damaging moves weaker than 35. Nothing in it changes a fight.

Against today, **517 TMs would unlock earlier, 167 later and 118 at the same badge.** The 300 TMs of the nine types
no leader teaches stop waiting for badge 8.

## 4. The strongest TM at each badge

By the power rule alone, the top of each band (signature moves included, so the strongest is often a move only one
species learns):

| Badge | Strongest damaging | Strongest status | Familiar TMs that land here |
|---:|---|---|---|
| 1 | Astonish 34.5 | Perish Song, Heal Bell 33.2 | Growl, Leer, Sand Attack, Splash |
| 2 | Rollout, Meteor Beam 54 | Leech Seed 54 | Ember, Water Gun, Thunder Shock, Dig, Protect, Substitute, Nuzzle, Dragon Rage, False Swipe |
| 3 | Steel Wing 63.7 | Synthesis, Morning Sun 61.8 | Quick Attack, Aerial Ace, Shock Wave, Bug Bite, Icy Wind, Solar Beam, Rest, Calm Mind, Taunt |
| 4 | Spark 74 | Will-O-Wisp 72.2 | Bite, Shadow Claw, Rock Slide, Rock Tomb, Bulldoze, Knock Off, Facade, Hyper Beam, Swords Dance, Nasty Plot, Dragon Dance, Roost, Reflect |
| 5 | First Impression 84 | Sleep Powder, Lovely Kiss 82.5 | Dragon Claw, X-Scissor, Shadow Ball, Crunch, Dark Pulse, Flash Cannon, Play Rough, Stone Edge, Hydro Pump, Blizzard, Hurricane, Focus Blast, Brick Break, Waterfall, Explosion, Trick Room |
| 6 | Body Slam, Dire Claw 94 | Thunder Wave, Belly Drum 90 | Thunderbolt, Flamethrower, Ice Beam, Surf, Psychic, Earth Power, Energy Ball, Bug Buzz, Scald, U-turn, Volt Switch, Poison Jab, Iron Head, Toxic, Stealth Rock, Quiver Dance |
| 7 | Searing Shot, Oblivion Wing 104 | Glare 100 | Earthquake, Close Combat, Flare Blitz, Brave Bird, Superpower, Outrage, Moonblast, Sludge Bomb, Draco Meteor, Leaf Storm, Gunk Shot, Return |
| 8 | Boomburst 140, V-create 139.3 | Shell Smash 125 | Extreme Speed, Spore, Double Iron Bash, Multi-Attack |

**With the shelf, the strongest TM a player can own is earlier than the rule alone says**, because the shelf sells
its gym's type early: Headbutt (74.5) and Rock Slide (71.5) at badge 1, **Scald (89) at badge 2, Thunderbolt (93)
and Thunder at badge 3**, Giga Drain (90) at badge 4. Those are shelf lines the owner authored; the power rule does
not move them.

## 5. The shelf TMs against the power rule

Two of the 23 agree. **Twenty-one disagree; none was adjusted.** The proposal keeps the shelf badge for all 23.

| Shelf TM | Type | Score | Shelf badge | Power badge | Direction |
|---|---|---:|---:|---:|---|
| Bide | Normal | 50.0 | 1 | 2 | shelf 1 earlier |
| Headbutt | Normal | 74.5 | 1 | 5 | shelf 4 earlier |
| Rock Slide | Rock | 71.5 | 1 | 4 | shelf 3 earlier |
| Rock Tomb | Rock | 66.5 | 1 | 4 | shelf 3 earlier |
| Bubble Beam | Water | 66.0 | 2 | 4 | shelf 2 earlier |
| Scald | Water | 89.0 | 2 | 6 | shelf 4 earlier |
| Water Pulse | Water | 62.4 | 2 | 3 | shelf 1 earlier |
| Shock Wave | Electric | 60.0 | 3 | 3 | agree |
| Thunder | Electric | 83.3 | 3 | 5 | shelf 2 earlier |
| Thunderbolt | Electric | 93.0 | 3 | 6 | shelf 3 earlier |
| Giga Drain | Grass | 90.0 | 4 | 6 | shelf 2 earlier |
| Mega Drain | Grass | 48.0 | 4 | 2 | shelf 2 later |
| Poison Fang | Poison | 62.5 | 5 | 3 | shelf 2 later |
| Poison Gas | Poison | 45.0 | 5 | 2 | shelf 3 later |
| Poison Jab | Poison | 84.5 | 5 | 6 | shelf 1 earlier |
| Toxic | Poison | 85.5 | 5 | 6 | shelf 1 earlier |
| Calm Mind | Psychic | 55.0 | 6 | 3 | shelf 3 later |
| Psywave | Psychic | 60.0 | 6 | 3 | shelf 3 later |
| Skill Swap | Psychic | 30.0 | 6 | 1 | shelf 5 later |
| Fire Blast | Fire | 91.4 | 7 | 6 | shelf 1 later |
| Overheat | Fire | 94.5 | 7 | 7 | agree |
| Earthquake | Ground | 100.0 | 8 | 7 | shelf 1 later |
| Fissure | Ground | 57.0 | 8 | 3 | shelf 5 later |

The pattern is the shelf's design, not noise. The shelf is laid out **by gym type**: each town sells its leader's
type, the strong and the weak together. So the early gyms' strong moves (Scald, Thunderbolt, Headbutt, Rock Slide)
are sold far earlier than their power says, and the late gyms' weak moves (Skill Swap, Psywave, Poison Gas, Mega
Drain) far later. **Twelve shelf lines are earlier than the rule, nine later.** The biggest gaps are Headbutt, Scald
and Skill Swap/Fissure (four or five badges). What the owner may want to decide per line:

- **Shelf earlier than the rule** (Scald at 2, Thunderbolt at 3): the shelf price is what gates it (the income gate in
  `data/markets.json`). The crafted recipe follows the shelf badge, as today. If the owner thinks Thunderbolt at
  badge 3 is too early, the fix is the shelf line, not this rule.
- **Shelf later than the rule** (Skill Swap at 6, Fissure at 8): holding the crafted recipe at the shelf badge keeps
  today's promise that crafting is never earlier than the shelf. Fissure at 8 is right for its own reason (outlier 12).

## 6. The outliers: where the number is wrong

A pure number misjudges these. Each has a suggested hand placement; all are applied (the owner, 2026-10-08; section 9).

| # | TM(s) | Score -> rule badge | What the rule misses | Suggested |
|---:|---|---|---|---:|
| 1 | Thunder Wave | 90 -> 6 | Valued as a Surf, which is the anchor working as asked. But a mid-game status move should not wait for the badge that also brings Thunderbolt; Toxic's shelf line is 5 | 5 |
| 2 | Will-O-Wisp | 72.2 -> 4 | Burn is valued at 85 x 85%; it halves every physical attacker for the rest of the fight. Keep the three status inducers together with Toxic | 5 |
| 3 | Nuzzle | 50 -> 2 | **An inconsistency in the rule**: a guaranteed paralysis on a damaging move is a 100% secondary worth 30, while the status move gets 100. Nuzzle is a Thunder Wave that also deals damage. Inferno and Zap Cannon (100% burn / paralysis, 50% accuracy, 62.5 and 72) have the same gap | 5 (Inferno and Zap Cannon too, the owner, 2026-10-08) |
| 4 | Trick Room | 76 -> 5 | Its value is the team's: on a slow team it decides fights, on a fast one it is negative. The AI does not play around it | 6 |
| 5 | U-turn, Volt Switch (90 -> 6); Flip Turn (80 -> 5); Parting Shot (55 -> 3) | The pivot's +20 puts a 70-power move level with Surf. Pivoting is good in singles, but not a 90-power move's worth | 5 for all four |
| 6 | Knock Off | 65 -> 4 | Its 1.5x against a held item (97.5) and the item removal are both code. Trainers here hold items | 6 |
| 7 | Set-up: Swords Dance, Nasty Plot (70 -> 4), Dragon Dance (65 -> 4), Bulk Up (55 -> 3), Calm Mind (55 -> 3, shelf 6), Quiver Dance (85 -> 6), Shift Gear (95 -> 7), Belly Drum (90 -> 6), Shell Smash (125 -> 8) | A +2 is valued as one 70-power hit, but it multiplies every hit after it: set-up is what sweeps a gym. The rule prices one turn, not the fight | SD, NP, DD, BU, CM at 6 (Calm Mind's shelf line); QD, Shift Gear, Belly Drum at 7; Shell Smash stays 8 |
| 8 | Earthquake vs Magnitude | 100 -> 7 vs 71 -> 4 | The rule gets the ratio right (Magnitude's mean is 71) but not the variance: 5% of Magnitudes are 150. EQ's shelf line is 8, one later than the rule | EQ 8 (shelf); Magnitude 5 |
| 9 | Recharge moves: Hyper Beam, Giga Impact, Blast Burn, Frenzy Plant, Hydro Cannon, Rock Wrecker (64.1 -> 4), Eternabeam (68.4 -> 4); Meteor Assault (71.2 -> 4), Prismatic Laser (80 -> 5), Roar of Time (64.1 -> 4), added by the owner 2026-10-08 | Averaging over two turns halves them, but a gate is about the biggest single hit: 150 power deletes a leader's ace and the recharge never comes | 7 |
| 10 | Explosion (83.1 -> 5), Self-Destruct (66.5 -> 4) | The same: the faint is priced as a cost per turn, the 250/200-power hit as a burst it is | 7 / 6 |
| 11 | Solar Beam (60 -> 3), Solar Blade (62.5 -> 3) | The charge turn halves them, but in sun (Sunny Day is badge 2) there is no charge: a 120-power move | 5 |
| 12 | One-hit KOs: Fissure, Sheer Cold, Horn Drill (57 -> 3) | Under the level caps the player's Pokemon is the ace's level, so 30% applies: a 30% chance to delete a gym ace in one turn. A cheese, not a 57-power move | 8 (Fissure's shelf line already is) |
| 13 | Fixed damage: Dragon Rage (40 -> 2), Sonic Boom (18 -> 1); Seismic Toss, Night Shade (65 -> 4) | Fixed damage is strongest early: Dragon Rage's 40 HP two-shots most Pokemon at cap 25-30. The nominal values assume a level-50 user | Dragon Rage 4, Sonic Boom 2; Seismic Toss and Night Shade stay 4 |
| 14 | Conditional doublers: Hex, Venoshock (65 -> 4), Facade (70 -> 4), Acrobatics (55 -> 3), Weather Ball (50 -> 2) | Left at stated power on purpose (2.1). Each doubles in a condition a player can set up: 130, 130, 140, 110, 100 | Hex, Venoshock, Facade, Acrobatics 5; Weather Ball 4 |
| 15 | Band edges: Sludge Bomb (94.5 -> 7) vs Psychic (90.8 -> 6); Poison Jab (84.5 -> 6, shelf 5), Iron Head (84.5 -> 6) vs X-Scissor (80 -> 5) | A 30% side effect pushes a 90 or an 80 over the four-point allowance. Any edge cuts somewhere | Sludge Bomb 6; Iron Head 5 (Poison Jab keeps its shelf 5) |
| 16 | Return, Frustration | 100 -> 7 | Nominal 100 assumes full (or zero) friendship. Measured 2026-10-08 (section 9.1): full power is a purchase at badge 4 for Return and the starting point for Frustration | ~~6, or measure first~~ 7 (measured) |
| 17 | Signature and one-species TMs: V-create, Double Iron Bash, Multi-Attack, Revival Blessing, Spore, Glare (100 -> 7) ... | The score ignores who can learn it. A badge-8 Sunsteel Strike matters to one species. Harmless in either direction; Glare beating Thunder Wave is correct | leave; ~~if Thunder Wave moves to 5, Glare to 6~~ Glare 5 (the owner, 2026-10-08: a sure paralysis must not open after Spore's sure sleep) (Spore: moved by 18) |
| 18 | Spore (110 -> 8) | Nothing in its own score. Spore is also an **input**: TMCraft's Stun Spore recipe takes the Spore TM, so the chain rule (9.2) held Stun Spore (75 -> 5) at 8 with it. The owner, 2026-10-08: "lower Spore rather than leaving Stun Spore at 8" | 5 (Stun Spore's own band) |

What the rule cannot see at all, and does not try to: **learnsets** (outlier 17), **the disc grade** (crafting cost,
below), **combos** (Rain Dance + Thunder, Sunny Day + Solar Beam, Toxic + Hex), and **the level caps**: a score is
the same at cap 25 and cap 55, though fixed damage and one-hit KOs are not (outliers 12, 13).

## 7. The disc grade

Today's rule also gates by TMCraft's disc grade (copper to netherite). The power rule does not: a TM's badge is
what it does. The disc stays a **price**: a badge-1 TM on an emerald disc still costs an emerald disc to craft.
Measured: badge 1 holds 42 emerald-disc TMs (status moves), badge 3 holds 10 netherite-disc TMs (the one-hit KOs,
Solar Beam). If the owner wants crafting cost and badge to agree, that is a separate rule, max(power badge, grade
badge), and it would bring back the cliff the owner rejected.

## 8. How it is wired

- `data/tm_gate.json` `badge_rule`: `shelf` unchanged and first; `unlisted` is the power rule; `power.bands` are the
  bands of section 3, not retuned; `power.outliers` the 17 groups of section 6, each a named, reasoned record with its
  `place` (hand badges), `shelf_agrees` (the shelf lines the group also names) and `not_placed` (TMs the group's text
  mentions that its suggestion does not place); `shelf_disagreements` the 21 lines of section 5, each kept at its
  shelf badge. The type/grade rule is kept under `superseded_unlisted`.
- `badge_rule.chain` (the owner, 2026-10-08: "A craft that unlocks before its input is a dead recipe"): after the
  shelf, the groups and the bands, a TM crafted from another TM is raised to its input's badge, never the input
  lowered (`tm_gate.chain_order`). Every raise is listed in `chain.raises` with its reason or the plan fails, and
  the plan fails if any recipe still opens before its input (a shelf TM is never raised: it would fail instead).
- **A committed table, not a call.** `tools/tm_gate.py` reads `docs/mechanics/TM_POWER_GATE.json` and does not score:
  scoring needs `node` to read `moves.js`, which prepare does not otherwise need. The table records the sha256 of the
  `moves.js` it was scored from; the gate fails closed when the server's differs, when the table lacks a TM the
  server crafts, when a row's `power_badge` is not its score's band, or when the shelf disagreements are no longer
  exactly the 21 listed. Both tools band with one function, `tm_gate.band`, over the bands in the data.
- `python tools/tm_power_score.py --server-dir <snapshot> --check` exits 1 when the committed table is not what the
  scorer would write now.

Reproduce (about a minute, needs `node` for the moves file):

```
python tools/tm_power_score.py --server-dir C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05 [--check]
python tools/tm_gate.py --server-dir C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05 [--check]
```

Never point either at `C:/Users/wnd/Documents/github/cobblers-server/`, the running server.

## 9. What the gate places (the snapshot of 2026-10-05, measured 2026-10-08)

802 TMs: 23 by the shelf, 51 by an outlier group (7 of them hold a TM at its own band: Flip Turn, Shift Gear, Shell
Smash, Seismic Toss, Night Shade, Return, Frustration), 728 by their band; then 3 chain TMs raised to their input's
badge (9.2). Measured: `python tools/tm_gate.py --server-dir <snapshot>`, 2026-10-08.

| Badge | With the shelf (section 3) | Shelf and outliers | And the chain raises (the plan) | Delta |
|---:|---:|---:|---:|---:|
| 1 | 166 | 165 | 164 | -2 |
| 2 | 122 | 120 | 120 | -2 |
| 3 | 107 | 99 | 99 | -8 |
| 4 | 103 | 85 | 85 | -18 |
| 5 | 109 | 123 | 123 | +14 |
| 6 | 96 | 99 | 100 | +4 |
| 7 | 66 | 77 | 77 | +11 |
| 8 | 33 | 34 | 34 | +1 |

The owner's calls of 2026-10-08 moved eight TMs and raised three: Inferno 3 -> 5 and Zap Cannon 4 -> 5 (group 3);
Meteor Assault 4 -> 7, Prismatic Laser 5 -> 7, Roar of Time 4 -> 7 (group 9); Return and Frustration 6 -> 7 (group
16, measured in 9.1); Spore 8 -> 5 (group 18, 9.2); the chain raises of 9.2. Spore's move changed the plan's
distribution by two TMs: 5 from 121 to 123 and 8 from 36 to 34 (Spore and Stun Spore, both now at 5).

The strongest TM at each badge as applied, by score (a placed outlier keeps its score, so Hyper Beam at 7 reads 64.1):

| Badge | Damaging | Status |
|---:|---|---|
| 1 | Headbutt 74.5 (shelf) | Perish Song, Heal Bell 33.2 |
| 2 | Scald 89 (shelf) | Leech Seed 54 |
| 3 | Thunderbolt 93 (shelf) | Synthesis, Morning Sun 61.8 |
| 4 | Giga Drain 90 (shelf); by the rule, Spark 74 | Soft-Boiled, Slack Off 71.2 |
| 5 | U-turn, Volt Switch 90 (outlier 5) | Spore 110 (outlier 18); Glare 100 (outlier 17); Thunder Wave 90 (outlier 1) |
| 6 | Sludge Bomb 94.5 (outlier 15); Body Slam, Dire Claw 94 | |
| 7 | Searing Shot, Oblivion Wing 104; Return, Frustration 100 (102 at full or zero friendship, outlier 16) | Shift Gear 95 (outlier 7) |
| 8 | Boomburst 140 | Shell Smash 125 |

### 9.1 Friendship, measured (Cobblemon 1.8.0, for group 16)

Read from `Cobblemon-fabric-1.8.0+1.21.1.jar` and Mega Showdown's `moves.js` in the 2026-10-05 snapshot (javap and
zipfile, 2026-10-08; nothing run in game). The full record, with the class each fact is read from, is
`data/tm_gate.json` outlier 16 `measured`.

- **Power**: Return = floor(friendship x 10 / 25), Frustration the same of (255 - friendship): 102 at 255 or 0.
  Cobblemon packs the friendship into the Showdown team. `maxPokemonFriendship` is 255; no rate multiplier exists.
- **Start**: a wild Pokemon from a natural spawn takes its species' base friendship: 837 species at 50, 79 at 0.
  ~~Four of our eight starters start at 0 (Cosmog, Type: Null, Poipole, Meltan).~~ **Corrected 2026-10-08 (section
  10.1): a starter does not take its own species' base**; it takes a random species'. The Friend Ball sets 150; the
  Luxury Ball's boost does nothing in 1.8.0.
- **Level-up**: +3 below 100, +2 below 200, **+0 from 200**. Levels alone stop at about 200: Return 80.
- **Walking**: +1 every 120 seconds to a party Pokemon sent out or shouldered, **only below 160** (30 an hour).
- **Battles**: nothing. An X item used in battle gives +1.
- **Soothe Bell**: every gain x1.5, rounded. Craftable from iron and wool from the start.
- **Items**: friendship berries +10 / +5 / +1 by the same thresholds (55 berries from 200 to 255);
  CobbleCuisine's malasada +12 and Poke Puff +6 (its config; that the gain is flat is not read from its code).

Return for a base-50 starter levelled to each badge's cap (badges 1-7: caps 25-55), by level-ups alone: 42, 46, 50,
54, 58, 62, 66; holding a Soothe Bell: 52, 58, 64, 70, 76, 80, 80. **But 102 is a purchase**: walk the Pokemon to
160 (3.7 hours out, 1.8 with the bell), then 8 malasadas (6 with the bell) from greenhollow's badge-4 counter (900
each) or steepside's (700). Frustration is cheaper still: a base-0 Pokemon has it at 102 when taught, and a
base-0 Pokemon caught at level 5 and levelled to cap 25 still has 78. Full power is reachable three badges before badge 7, so the proposal's
nominal 100 stands, and 102 sits in the badge-7 band (94.1-104): **both at 7**, their own band.

### 9.2 Chain TMs (the owner, 2026-10-08: "A craft that unlocks before its input is a dead recipe")

Four TMCraft recipes take another TM, and opened before it. Three chain TMs are raised to their input's badge; the
chain rule moves no input (`data/tm_gate.json` `badge_rule.chain.raises`):

| Chain TM | Input TM | Badge before | Raised to |
|---|---|---:|---:|
| Bone Club (56.5) | Bonemerang (90) | 3 | 6 |
| Noble Roar (30) | Roar (45) | 1 | 2 |
| ~~Stun Spore (75)~~ | ~~Spore (110)~~ | ~~5~~ | ~~8~~: no raise; Spore placed at 5 by group 18 |
| Triple Kick (46.8) | Double Kick (60) | 2 | 3 |

**Stun Spore and Spore (the owner, 2026-10-08: "lower Spore rather than leaving Stun Spore at 8").** Stun Spore at 8
was the costliest raise, a badge-5 status move waiting three badges for its input. Spore is now placed by hand at **5**,
Stun Spore's own band, by its own outlier group 18; the chain rule then finds Stun Spore (5) no earlier than Spore
(5) and raises nothing. The chain rule was not bent: the input moved by a named placement, and the rule still checks
it. The overruled raise is kept as `badge_rule.chain.superseded_raises`.

*Is Spore in Thunder Wave's group?* No, and that is deliberate. (The brief called Thunder Wave's group "group 3";
in the data it is **group 1**, Thunder Wave alone at 5. Group 3 is Nuzzle, Inferno and Zap Cannon: damaging moves
with a guaranteed status, also at 5.) Spore shares their **badge** but none of their **reasons**: groups 1 and 3 move
a move the score misjudges, while Spore's score (a 100% sleep, 110) is right, and Spore moves for a reason outside it,
the recipe that takes it. Sleep is not paralysis either: a sleeping target does not act for its sleep turns, while a
paralysed one acts three times in four, and the score table already values them apart (110 against 100, 2.2). So if
sleep "belonged" anywhere by its own merit it would be with the other sleep moves by score, Sleep Powder and Lovely
Kiss (75% sleep, 82.5, band 5), which is where Spore now opens. **What it cost:** a guaranteed sleep (Spore, 5) opened
a badge before a guaranteed paralysis (Glare, then 6, group 17), the inverse of their scores. The owner closed it on
2026-10-08 by moving Glare to 5 (group 17's `placed_2026_10_08`): the two now open together.

The rule holds for every TM: the plan fails when a raise is not listed, when a listed raise no longer matches, and
when any recipe still opens before its input.

## 10. Frustration: higher, off the shelf, or 7? (analysis for the owner, 2026-10-08; NOT applied)

The owner, 2026-10-08: *"FRUSTRATION: full power from the start for 79 species including four of our starters is a
real problem. A max-power move at badge 7 that is already max for a quarter of the dex is not gated at all. Say
whether Frustration should go higher, or come off the shelf entirely."* Frustration stays at 7 (group 16) until the
owner decides. Everything below is read from the 2026-10-05 snapshot's jars (`Cobblemon-fabric-1.8.0+1.21.1.jar`,
`tmcraft-1.4.19+1.8.0.jar`, Mega Showdown and `COBBLEVERSE-DP-v31.zip`) with zipfile and javap; **nothing was run in
game.**

### 10.1 What was measured

**Three of the premise's figures do not hold.** They came from group 16's record (9.1), which this section corrects.

| The premise | Measured |
|---|---|
| "79 species start at 0" | **True for a natural wild spawn**: 79 of 1,025 species have base friendship 0 after every species file and species_addition in the snapshot is merged, and `PokemonSpawnAction.createEntity` sets a spawned Pokemon's friendship to its form's base. A trade resets to the base too (`TradeManager.performTrade`). |
| "a quarter of the dex" | **7.7%** (79 / 1,025). And only **40** of the 79 can learn Frustration at all, nearly all legendaries, Ultra Beasts and mythicals. The one ordinary catchable species among them is **Buneary** (`data/encounter_design.json` `arrow_lake_shores`, tier 3, and `south_pine_isle`; the Lopunny cellar's habitat block). |
| "four of our starters" start at 0 | **Not by the bytecode.** A starter is built by `PokemonProperties.create` (`CobblemonStarterHandler.chooseStarter`). `new Pokemon()` sets friendship to the base of `PokemonSpecies.random()`, a random implemented species; `apply()` then sets the real species and `initialize()` runs, and **neither writes friendship** (the only writes in `Pokemon` are the constructor, `setFriendship`, increment/decrement, `restoreFriendship` and `copyFrom`). So a starter starts at a random species' base: 50 with chance 837/1,025 (82%), 0 with chance 79/1,025 (7.7%), whatever its own species. And of the four base-0 starters, **Cosmog and Meltan cannot learn Frustration at all**; Type: Null and Poipole can (legacy learnset), as can Silvally, Naganadel, Solgaleo and Lunala. |

**Who the crafted TM can teach.** `tmcraft:tm_frustration` is a `TMMoveTeachingItem`, which teaches a Pokemon that
learns the move by level-up or by TM (`isLearnedByLevelUp`, `isLearnedByTM`). **No species lists `tm:frustration`**
in the loaded data; by level-up only Buneary and Lopunny (`1:frustration`), who have it without the TM. Everyone else
learns it as `legacy:frustration` (789 species in the Cobblemon jar), and TMCraft reaches them through the furnace:
`tmcraft:legacy_frustration_from_smelting_tm_frustration` (`minecraft:smelting`, so outside doLimitedCrafting) turns the
crafted TM into `tmcraft:legacy_frustration`, a `LegacyMoveTeachingItem`. A second recipe,
`to_cobblemon_tm_frustration`, turns it into Cobblemon's own TM item. Both need the crafted TM first, so **the badge
gates all three routes**. Cobblemon's TM Machine does not print Frustration (no `data/cobblemon/tms/frustration.json`).

**Where full power comes from.** Not from the starting value, for anyone but a wild base-0 catch. Friendship rises +3
per level below 100 and +2 below 200, and +1 every two minutes while sent out, below 160 (9.1); a base-50 Pokemon caught
at level 5 and levelled to cap 55 is at about 167 (Return 66, Frustration 35). Going down: **bitter remedies**,
`data/cobblemon/mechanics/remedies.json` `friendshipDrop`: Remedy 5, Fine and Superb Remedy 5, Energy Root 10, Revival
Herb 15, Heal Powder 5, on any Pokemon not at full HP (`RemedyItem.canUseOnPokemon` reads `isFullHealth`). From 167
that is 17 Energy Roots. **The Frustration recipe itself takes an Energy Root** (`tmcraft:recipe/tm_frustration`: a
gold blank disc, a normal gem, an energy root), so whoever can craft the TM has the means to zero a Pokemon. Under
the level caps a capped Pokemon gains no levels, so once at 0 it stays near 0 while kept in its ball. No counter sells
remedies (`data/markets.json`); where Energy Roots and Big Roots grow in our world is **not measured**.

**Shelf or craft.** **Frustration has no shelf line**: `data/markets.json` names neither `tm_frustration` nor
`tm_return`. "Off the shelf" can therefore only mean the crafting route.

### 10.2 The three options

| | Keep at 7 (today) | Badge 8 | Off the craftable set |
|---|---|---|---|
| What it means | the power rule's band for 102 (94.1-104), with Return | placed by hand one badge late (data only: group 16 `place`) | the gate never gives `tmcraft:tm_frustration`; with it go the furnace's legacy item and the Cobblemon-TM conversion. **No mechanism exists today**: tools/tm_gate.py has badges 1-8 and no "never"; it needs a new withheld list in the generator (or a datapack override of the recipe at its own path that the gate's plan must also know about), plus tests |
| Full power when it opens | yes, for anyone with Energy Roots or a wild base-0 catch | the same, a badge later | n/a |
| Return | same badge, same 102, reached by walking plus 6-8 malasadas from badge 4 (9.1) | Return 7 and Frustration 8: two halves of one move at different badges, though both are at full power before either opens | Return stays, so the pair is broken: the friendship-0 half is removed and the friendship-255 half kept |
| What it does not touch | Buneary and Lopunny's level-1 Frustration (no TM involved), loot, trades | the same | the same; and TMCraft's Move Tutor Table and tutor/egg items, which this gate never read (`does_not_cover`) |
| Cost | none | one data line, a test | generator change, new tests, an ADR-sized exception to "every TM unlocks at a badge" |

### 10.3 Recommendation: keep Frustration at 7

1. **The badge gates when a move arrives, not how strong it is.** The owner's "already max, so not gated" holds for a
   move whose power grows with badges; a 102-power move that opens at the badge where the 100-power moves open
   (Searing Shot and Oblivion Wing 104, Hyper Beam class 150 by group 9) is gated exactly like them. Badge 6 holds the
   90s and badge 8 Boomburst's 140: neither is where a 102 belongs.
2. **At badge 7 Frustration and Return are the same move.** Both reach 102 before 7: Return by a purchase from badge 4,
   Frustration by Energy Roots the recipe already makes the player gather. Moving one alone puts a difference between
   them that does not exist when they open. If the owner wants both later, raise **both** to 8 together; that is a
   decision about Normal-type 102s, not about Frustration.
3. **Removing it is new machinery for a problem the badge already solves**, and it removes the furnace route for 789
   species while leaving Return. Principle 6: a datapack value (the badge) suffices; a never-unlock list is not needed.
4. **The early full-power Frustration the owner is worried about is not the TM's.** The one real case is **Buneary**:
   wild, base 0, Frustration at level 1, no TM, in a tier-3 zone. A wild Buneary is caught at friendship 0, so
   Frustration 102 for the first gyms, falling 1.2 power per level gained (+3 friendship a level). No TM badge
   reaches it. If that is a problem, it is an encounter-table question (`data/encounter_design.json`, Buneary is an
   anchor of `south_pine_isle` and common in `arrow_lake_shores`), for `trainer-balance-designer`.

### 10.4 What to verify in game (not done)

- A picked Cosmog's friendship: 50 most of the time, as the bytecode says, or 0 (EXP to be numbered).
- A wild Buneary's friendship (0) and whether a caught Buneary can select its level-1 Frustration from the summary.
- That smelting a crafted `tm_frustration` gives `legacy_frustration`, and that it teaches, say, Poipole.
