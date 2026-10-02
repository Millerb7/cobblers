# The level cap after gym 8 and after the League: the numbers, what they unblock, what they break

**Status:** PROPOSAL, research only (2026-10-02). Nothing is built. The owner's instruction (2026-10-02):
- after gym 8, the cap rises to just under the Elite Four;
- after the Elite Four, there is no cap.

## 1. How the cap is computed (VERIFIED in rctmod v0.19.0-beta source)

`LevelUtils.levelCap(player)`
(`https://gitlab.com/srcmc/rct/mod/-/raw/v0.19.0-beta/common/src/main/java/com/gitlab/srcmc/rctmod/api/utils/LevelUtils.java`):
- **The cap** is `max(initialLevelCap, min over the player's NEXT trainers in their series of trainerLevel)`.
  - With **no next trainer**, it is `maxLevel()`, which is **100**.
  - The exception is the special series `"empty"`, where it is `max(initialLevelCap, 1)`.
- **A trainer's level** is `trainerLevel = max(min(100, max(0, team's highest level + relativeLevelCap)), max over its
  requiredDefeats of their trainerLevel)`. So a trainer's level can never fall below that of a trainer that must be
  beaten before it.
- **`relativeLevelCap` is per trainer first.** `TrainerManager.getData(trainerId).getRelativeLevelCap()` comes first,
  then the series metadata, then the server config.
  - The field is `TrainerMobData.relativeLevelCap`, an optional integer
    (`.../api/data/pack/TrainerMobData.java:72`), so the key goes in the trainer's **mob** file.
  - Its valid range is −100 to 100 (`.../api/config/IServerConfig.java:326-327`). Out-of-range values are clamped with a
    warning (`TrainerMobData.java:176-185`).
- **Completing a series does not reset it.** `TrainerPlayerData.updateCurrentSeries` records the completion and sends
  a title. Nothing sets the series back to `"empty"` (`.../api/data/save/TrainerPlayerData.java:195-206`). So after
  the last trainer the next set is empty and **the cap is 100**.
- **The trainer-level cache is not cleared on `/reload`** (`LevelUtils.java`: `TRAINER_LEVEL_CACHE ... // TODO: clear
  after server reload`). A changed `relativeLevelCap` takes effect only after a **restart**.

Our inputs:
- `initialLevelCap = 20`, `relativeLevelCap = 0`, `initialSeries = "kanto"`
  (`modpack/config/rctmod-server.toml:144,153,159`).
- The Kanto series is **13 trainers in one chain** (COBBLEVERSE-RCT-DP-v20, local copy, `mobs/trainers/single/*.json`
  `requiredDefeats`): `kanto_brock` → ... → `kanto_giovanni` → `kanto_league_lorelei` → `_bruno` → `_agatha` →
  `_lance` → `kanto_champion_blue`.
- Our seated route and arena trainers carry `series: []` (`tools/route_trainers.py:316`) and never enter the
  calculation.
- Our teams sit on those upstream ids (`data/gym_trainers.json`, `data/league_trainers.json`). The levels below are
  ours, from `data/trainers.json`.

## 2. The cap today (MEASURED from the data, through the code above)

| Beaten | Next | Cap |
|---|---|---|
| gyms 1–7 | gym N+1 | 25 ... 55 |
| gym 8 (Giovanni) | Lorelei, ace 60 | **60** |
| Lorelei, Bruno, Agatha | the next Elite Four member, ace 60 | **60** |
| Lance | Blue, ace 62 | **62** |
| Blue | nothing | **100**: no cap in effect |

**A correction to the brief.** The Elite Four aces are **60, 60, 60 and 60**. 57/58/59/60 is the spread *inside*
each member's team (57, 58, 58, 59, 59, 60, the same for all four; `data/trainers.json`, `data/league_trainers.json`
`levels [57, 60]`). The Champion is 58–62, ace 62.

So the cap already rises after gym 8, to 60: level with every Elite Four ace, as each gym's cap is level with its
leader's. **And the cap already disappears after the Champion.**

## 3. The numbers the instruction asks for

**After gym 8: "just under", so that a player can train toward the Elite Four without out-levelling them.**

| Cap | Against an Elite Four team (57, 58, 58, 59, 59, 60) | `relativeLevelCap` on each of the four | What must be re-levelled to stay catchable |
|---|---|---|---|
| 60 (today) | level with the ace, above 3 | none | nothing |
| **59 (recommended)** | one under the ace, above 3, level with 2 | **−1** | 234 spawn entries in 15 habitats, VR cave prizes, Regigigas and Groudon (§5) |
| 58 | two under the ace, above 1, level with 2 | −2 | the above, plus 26 Rift-depths entries topping at 59 |
| 57 | out-levels no Elite Four Pokémon | −3 | the above, plus everything at 58 |

**Recommended: 59.**
- It is "just under" in the ladder's own terms: every gym arrives level with its ace, and the League arrives one
  under.
- 57 is the strict reading of "without out-levelling them". It costs more re-levelling and makes Victory Road's 57–59
  trainers (`data/vr_trainers.json:295`) fights above the player.
- The floor in `trainerLevel` (Giovanni's 55) is never reached, so the value is exactly `60 + relativeLevelCap`.
  Setting it on all four keeps the cap at 59 through the whole Elite Four.

**After the Elite Four: none.** Two readings, and they differ for the Champion:

| Reading | How | The Champion's fight |
|---|---|---|
| **Literal**: no cap from Lance's defeat | `relativeLevelCap` **+38** on `kanto_champion_blue` (62 + 38 = 100; within −100..100) | **can be out-levelled**: a player may train to 100 before facing Blue |
| **League as one gauntlet**: Blue keeps a cap, none after him | `relativeLevelCap` **−1** on Blue (cap 61 before him), or leave it at 62; "after" is already 100 | stays the hardest fight, on the same "one under" terms |

**This is the owner's call** (decision L2). The second reading needs no new mechanism for the "no cap" half: it is
today's behaviour.

## 4. What it unblocks (with no change, or with the literal reading, as marked)

| Item | Before | After | Source |
|---|---|---|---|
| **Lugia** (gate `champion_cleared`) | "the champion's cap is unknown", so a band of 65 was invented as the ladder's "next rung" | **the cap after Blue is 100. VERIFIED, true today.** Lugia can return to its original 75, or any level ≤ 100 | `data/legendaries.json` `level_caps.upper_bound_why` / `champion_band_why` / `above_the_bound_why` |
| **Mew** from the adopted temple's altar, 75–90 | "uncatchable, above the 65 upper bound at champion" | catchable after Blue (today), or after Lance (literal) | `data/adopted_legendary_sites.json:46`; still depends on the altar working (EXP-048) |
| **Calyrex** from the Crown Cemetery altar, 70 | the same | the same | the same |
| **Arena tiers 4–7** (65 → 76) | the cap held players at 62 until Blue | players can train up to them after Blue (or Lance) | `data/arena_trainers.json:26-27` |
| **The `upper_bound_by_badges` table** | "8": 60, "champion": 65 (invented) | "8": 59 (or the chosen value), "champion": 100 / none | `data/legendaries.json` |

**Re-levelling** that a post-gym-8 cap below 60 *creates*. These are not unblocked; they need moving down:
- **Regigigas and Groudon**, 60 behind the eighth badge.
- **Articuno and Zapdos** from their altars roll 50–60, so a 60 roll would be uncatchable until the League.

## 5. Does anything break? (checked)

| System | Assumes a cap? | Verdict |
|---|---|---|
| **Catch block** (`tools/levelcap_pack.py:56-64`, `cobblers_levelcap`) | compares the target's `Pokemon.Level` with `rctmod player get level_cap`; a read of 0 lets the catch through | **no break.** At 100 nothing is over the cap. At 59, a Pokémon at 60 breaks free, as designed; that is the re-levelling above |
| **Trainer refusal** (rctmod's `over_level_cap`, a party member strictly over the player's cap) | yes, it is the cap | **no break with no cap.** With a lower post-gym-8 cap, a player who **already** holds a Pokémon above it (a 60 caught before the change) is refused by **every** rctmod trainer, the seriesless Victory Road and arena seats included, until that Pokémon is boxed. A migration note, only if a player is already past gym 8 |
| **Experience stop at the cap** (rctmod) | yes | no break; it moves with the cap |
| **Blackout** (`data/blackout.json`) | **no.** Its `cap` is the CobbleDollars charge cap (3,000, `:8`), not a level | no break |
| **Stress tests and `battle_sim`** | caps for gyms 1–8 only (`tools/battle_sim.py:884-894`, `tests/test_rct_config_overlay.py:61-62` reads the config's 20/0) | **no break.** Neither models the League, and per-trainer mob values leave the config untouched |
| **`tests/test_vr_caves.py:64-66`** | `PRIZE_LEVELS = (57, 60)`, "Victory Road's cap of 60" | **breaks at 59**: the prizes and band (`data/vr_caves.json` `spawns.band [54, 60]`) move to 59 |
| **`data/spawns.json`** | **234** entries top out at 60: Victory Road caves (11 habitats, core and rim) and four Rift habitats (`rift_trunk`, `rift_west_spur`, `rift_south_east_arm`, `rift_south_west_arm`) | at 59 they need their band top lowered in the generators' inputs. MEASURED by walking every `level` range. Whether the four Rift habitats are post-gym-8 was not checked; if they sit under an earlier cap, they are already over it |
| **`tools/legendaries_audit.py:215-217`** | checks `level <= cap_at_gate`, but the records' `cap_at_gate` still holds the old invented table (Regigigas 70, Lugia 80) | no break, and no protection: it would pass a 60 Regigigas under a 59 cap. Fix `cap_at_gate` from the real ladder at the same time |
| **`tools/route_trainers.py:434-445`** (no rematch of the League once beaten) | it calls a refightable Blue "a level-cap bypass at the top of the ladder" | still right under a cap; moot with none |
| **A-lite starters** (`NATIVE_STARTERS_COST.md`) | evolution points 30 and 45 | no change |

## 6. What it takes

- **The data:** `relativeLevelCap` on four (or five) Kanto League mob files, `data/rctmod/mobs/trainers/single/kanto_league_*.json`
  (and `kanto_champion_blue.json`).
- **That means overriding Cobbleverse's whole mob file at the upstream path.** A datapack file replaces, it does not
  merge. The override must carry every field Cobbleverse sets: `type`, `series`, `requiredDefeats`, `maxTrainerWins`,
  `maxTrainerDefeats`, `battleCooldownTicks`, `signatureItem`, `spawnWeightFactor` and the biome tag lists. Those
  keys were listed from the local zip; their values were not copied here.
  - **ASSUMED:** an authored file stating these facts is ours to commit. The Lumyverse packs are no-redistribution.
    This is a licence question for the owner (decision L3).
  - The generator would be `tools/route_trainers.py`, which already writes the League's team files.
- **The re-levelling**, at 59: the Victory Road and Rift band tops, the VR prize constant, Regigigas and Groudon, the
  `upper_bound_by_badges` table, `cap_at_gate` on every record, and Lugia's level (now free).
- **A restart**, not a `/reload`.
- **The proof:** a staging check with `rctmod player set progress after kanto_giovanni` (the literal exists in
  `.../commands/PlayerCommands.java`; argument order ASSUMED), then `rctmod player get level_cap`. Expect 59. Then the
  same after `kanto_league_lance` (expect 62/61, or 100 under the literal reading) and after Blue (expect 100).
- **Effort:** about one session including the re-levelling, plus the staging check. It could share EXP-049's staging
  session.

## 7. Decisions for the owner

1. **L1, the post-gym-8 number:** 59 (recommended), 58 or 57.
2. **L2, the Champion:** uncapped from Lance's defeat (literal), or capped until Blue and none after (today's
   behaviour after him)?
3. **L3:** may we commit an authored override of Cobbleverse's League mob files, to carry `relativeLevelCap`?
4. **Lugia:** back to 75, or another level, now that its band is known to be uncapped?
