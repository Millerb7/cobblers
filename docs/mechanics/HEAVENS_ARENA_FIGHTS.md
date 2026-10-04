# Heaven's Arena: the list of fights

**Status:** DRAFT, 2026-10-03. This is a design only. No mechanism has been chosen, nothing is generated, and nothing
has been seen in game. The data is `data/arena_fights.json`, and this document explains it. The champions' teams stay
in `data/arena_trainers.json`. They are referenced by id and never copied.

**The owner, 2026-10-03:** "Heaven's Arena should be a battle zone where a player can go in and always find a cool
battle or gauntlet to match up against. I think early levels will be single battles then transition into more back to
back. ... each player will have their own progress and their opponent will be spawned in front of them. We might need
to make a list of fights a player can get."

## 1. Who it serves, and why from badge 8

The arena belongs to the Deep, and the Deep is inside Rift zone Z2. The Z2 pass is eight badges
(`docs/mechanics/RIFT_ZONES.md` section 2). So today nobody stands in the arena before `gym8_cleared`. That puts
everyone in it at an rctmod cap of at least 60 (`docs/mechanics/LEAGUE_LEVEL_CAP.md` section 2):

| Beaten | Cap |
|---|---|
| gym 8 | 60 |
| Lance | 62 |
| Blue | 100 (no next trainer) |

The ladder is built on those three caps. A rank's band never tops out above the lowest cap that a player admitted to
the rank can have.

Note: the claim that the Deep's empty north is inside Z2 comes from the brief. RIFT_ZONES lists Z2's area without
naming the Deep, so this was not measured here. If the door moves somewhere reachable earlier, see Q1. The sets are
level-free, so lower ranks would only need an earlier-stage species list.

## 2. The ladder

| Rank | Name | Band (cap) | Format | Opponent | Levels | To advance | Rank-up fight |
|---|---|---|---|---|---|---|---|
| 1 | The Floor | league_eve (60) | single | 3 | 54-57 | 3 wins | Odell (tier 1, ace 56) |
| 2 | The Shaft | league_eve (60) | single | 4 | 56-59 | 3 wins | Nessa (tier 2, ace 59) |
| 3 | The Relay | league_eve (60) | gauntlet x2, no heal | 3 each | 57-60 | 2 clears | Odell then Nessa, no heal |
| 4 | The Champion's Door | champion_door (62) | single | 4 | 59-62 | 2 wins | Veyl (tier 3, ace 62) |
| 5 | The Sluice | postgame (100) | gauntlet x3, no heal | 2 each | 61-65 | 2 clears | Marro (tier 4, ace 65) |
| 6 | The Terrace | postgame | gauntlet x3, no heal | 3 each | 64-68 | 2 clears | Ilse (tier 5, ace 68) |
| 7 | The Tear | postgame | gauntlet x5, no heal | 2 each | 67-72 | 2 clears | Quell (tier 6, ace 72) |
| 8 | The Crown | postgame | gauntlet x5, heal after leg 3 | 3 each | 71-76 | 1 clear | Oryx (tier 7, ace 76) |
| 9 | Above the Crown | postgame | endless streak | 3, rising to 6 | 78, rising to 100 | none | none (best streak is the score) |

**Why this shape:**

- **Singles first, then back to back.** This follows the owner's brief.
  - Ranks 1, 2 and 4 are single battles.
  - Rank 3 is the gentlest gauntlet: 2 x 3 = six opposing Pokemon. That is the Elite Four's own member count, at the
    League's own level.
  - Gauntlets then grow by legs before they grow by team size. Rank 5 is three legs of two, which is a lead-and-switch
    test rather than an attrition test. Rank 7 is five legs of two. Rank 8 is five legs of three.
  - Rank 8 has one heal after leg 3. Fifteen Pokemon against six with no heal is a wall that team building cannot
    answer. With the heal it is two halves, each the League's size.
- **Rank 4 is the Blue rehearsal.** Its bouts and Veyl sit exactly at the Champion's 62. That is why the rank waits for
  Lance, and Veyl is the one champion whose ace needs cap 62.
- **Rank 9 is the "always find a fight" rank.**
  - Level 78 to start, +2 every 3 wins, so it reaches 100 at win 33.
  - After that the team grows by one member every 6 wins, up to six.
  - The party is healed every 3 wins.
- **Playing down is always open.** Every rank at or below the player's own is repeatable, so the arena is never
  empty-handed.
- **Postgame newcomers skip the grind.** A player who has beaten Blue can challenge each of the first four rank-up
  fights directly (`wins_waived_by`). The rank-up fights themselves are never waived.

## 3. How the seven champions sit in it

Each champion is the exam at the top of a rank. The ranks keep their tier numbers, shifted by one from rank 3:

- Odell and Nessa close ranks 1 and 2.
- Rank 3's exam is the two of them **back to back with no heal**. These are teams the player has already beaten, at
  their own levels (54-59, under cap 60), now as one run. No new team was invented for it.
- Veyl closes rank 4.
- Marro, Ilse, Quell and Oryx close ranks 5 to 8.

The levels and member counts from `arena_trainers.json` (`level_band`) are unchanged. `arena_trainers.json`'s
argument that tiers above 62 "may exceed the cap" is no longer needed: under this ladder no player meets a champion
above their own cap.

## 4. How it stays fresh

**Pool bouts are drawn, not authored.**
- `set_pool` holds 47 level-free sets in `data/trainers.json`'s team-member format. Each has `min_rank`, `types` and
  `role`.
  - 30 sets are open at rank 1.
  - 13 postgame sets (Garchomp, Hydreigon, Dragonite, Volcarona, Mimikyu and others) join at rank 5.
- A draw takes `members` sets.
  - The ace gets the band's top level, and each earlier member is one level lower.
  - Constraints: no species repeated in one opponent or one gauntlet run; at most two members sharing a type; at most
    one setup set at ranks 1-2; a `lead` set goes first.
  - From rank 5, one bout in four is a mono-type theme draw.
  - A player's last two bouts' sets are excluded from the next draw.
- Unconstrained, that is 4,060 three-member teams at rank 1 and 16,215 from rank 5. The constraints cut those numbers
  by an amount that has not been measured.
- Opponents are named and skinned from a list of 24 names, a title per rank, and 11 rctmod skins already used by
  seated trainers.

**Prebake fallback.** If the chosen mechanism only takes static teams (rctmod's model), the generator draws 24 bouts
per rank and 12 per streak step, from a recorded seed. That makes 336 fixed fights, and a function picks one at
random.

## 5. Prizes

**The purse formula is 13 x the sum of the opponent's levels, rounded to 50.**
- 13 is `docs/research/INCOME_MEASUREMENT.md`'s model B coefficient. It comes from Brock's one measured payout and is
  ASSUMED there.
- So an arena win pays what a trainer of that size pays anywhere else in the campaign.
- Typical purses:

| Fight | Purse |
|---|---|
| Rank 1 win | 2,200 |
| Rank 4 win | 3,150 |
| Rank 3 clear | 6,600 |
| Rank 8 clear | about 22,000 |
| Oryx | 5,800 |

**Bonuses** are paid on top: a clear bonus for each gauntlet (2,000 to 7,500), and 3,000 for every 5th streak win.

**If the mechanism is an rctmod trainer**, CobbleDollars already pays every win. That is VERIFIED
(`earnCobbleDollarsFromNPC`, `data/arena_trainers.json` `repeatability.why_1`). In that case the arena pays only the
bonuses, or a win pays twice.

**Exhibition.** At two or more ranks below your own, a bout pays 25% of the purse and no bonus.

**For scale**, against the badge-8 shelves in `data/markets.json`: a rank 1 win buys a Max Revive (2,500), and a rank 8
clear buys a Diamond backpack (10,000) plus two Gold Bottle Caps (6,000 each).

**First-clear items, once per player:**

| Prize | Item | Id verified? |
|---|---|---|
| Rank 1 | Choice Band | yes |
| Rank 2 | Leftovers | yes |
| Rank 3 | Gold Bottle Cap | yes |
| Rank 4 | Choice Scarf | **no** |
| Rank 5 | 2 Gold Bottle Caps | yes |
| Rank 6 | Life Orb | **no** |
| Rank 7 | Ability Patch | **no** |
| Rank 8 | 3 Gold Bottle Caps | yes |
| Streak 10 | 1 Gold Bottle Cap | yes |
| Streak 25 | 3 Gold Bottle Caps | yes |
| Streak 50 | 2 Ability Patches | **no** |

"Yes" means the id is VERIFIED by `data/rewards.json`'s jar asset paths. The four marked "no" were not verified.

## 6. Multiplayer

**Everything is per player:**
- rank, wins, run state and streak;
- every purse and every prize;
- the band, because caps come from each player's own rctmod series.

Nothing in the arena is once per server, and no player "holds" a rank. Each player has one bout at a time, so the
number of venues bounds how many bouts can run at once. Co-op is Q5.

## 7. What the data needs from a mechanism

These are listed in full as `mechanism_needs` in the data file:

- **N1** Spawn an opponent for one player only. No other player may battle or steal it.
- **N2** A team from data at bout time, or a pick among prebaked teams.
- **N3** Start the battle under the bout's rules.
- **N4** Read the result (win, loss, flee or disconnect) per player.
- **N5** Heal on command, and NOT heal between gauntlet legs.
- **N6** Despawn the opponent, and clean up after a logout.
- **N7** Per-player persistent state.
- **N8** Pay money and give items.
- **N9** Read `gym8_cleared` and `champion_cleared`, plus "Lance beaten", which no flag records today.
- **N10** Randomness.
- **N11** A legality check of every set against the Cobblemon 1.8.0 jar.
- **N12** Exempt arena losses from the blackout.

## 8. Answer check

Every rank-up fight has at least two counter-strategies built from species whose base forms are in
`data/spawns.json`. The full list is `answer_checks` in the data file. The broad strokes:

| Champion | Counters |
|---|---|
| Odell | Fairy/Flying (Togekiss, Staraptor) or Ghost (Chandelure) |
| Nessa | Grass (Venusaur, Torterra, Serperior), or Taunt plus Psychic |
| Veyl | Fire and Ground, or slow hitters inside his own Trick Room |
| Marro | Electric, or priority to break Cloyster's sash |
| Ilse | Fire in her sun, or a weather change (Tyranitar, Pelipper, Hippowdon) |
| Quell | Dark, or Ghost |
| Oryx | Fairy/Ice plus priority for the dragons, Water/Fighting for Tyranitar and Excadrill |

For every species the base form is present in the spawn tables. Which zone or habitat holds it was not checked species
by species.

## 9. Not verified

- **Learnsets.** That each species learns each move in its set. The jar is not in this worktree, so no learnset was
  read. Moves were chosen from level-up and TM learnsets, avoiding moves that are only egg moves. This is N11, and it
  blocks generation.
- **Some prize item ids.** `cobblemon:choice_scarf`, `cobblemon:life_orb` and `cobblemon:ability_patch` as item ids.
- **Payout and difficulty.** The purse coefficient is ASSUMED, and so is any win rate: no battle was simulated.

## 10. Open questions for the owner

1. **Q1** Should a lower rank exist somewhere reachable before badge 8?
2. **Q2** Rank 4 needs "Lance beaten". Add a flag for it, or fold rank 4 into postgame?
3. **Q3** Should the venue heal the party at the start of each bout? Recommended: yes.
4. **Q4** Should an arena loss be exempt from the $600 blackout charge and the teleport? Recommended: yes.
5. **Q5** Should there be a co-op doubles venue?
6. **Q6** Should legendaries and Megas be allowed in bouts, banned, or allowed only at rank 9?
7. **Q7** Is the money the right size: about 2,200 for a rank 1 win and 22,000 for a rank 8 clear?
8. **Q8** Should the ranks keep the old tower's floor names, or be renamed for the dome's venues?
