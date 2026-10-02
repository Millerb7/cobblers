# Five native-evolving starters against Cobblemon 1.8.0: Cosmog, Kubfu, Type: Null, Poipole, Meltan

**Date:** 2026-10-02. **Research only:** nothing in `data/`, configs, tools or tests was changed, and no server,
world or lock was touched.

**Answered for:** Cobblemon 1.8.0+1.21.1, Mega Showdown 1.0.2+1.8, TMCraft 1.4.19+1.8.0, COBBLEVERSE-DP-v31. These are
the overlay's versions (`modpack/manifest/overlay.json`).

**Companion:** `docs/mechanics/NATIVE_STARTERS_COST.md` (the options costed against each other) and
`experiments/EXP-049-native-starter-evolution/README.md` (designed, not run).

**A second reading exists.** `origin/research/2026-10-02-mythical-starters` (commit `194330c`,
`docs/research/MYTHICAL_STARTERS.md`) is unmerged and answers the same brief. It was found after this note's
measurements were taken, then read for comparison. §9 lists where the two agree and where they differ. Every simulator
figure for option (b) reproduces exactly between the two.

## Sources

| Short name | What it is | Read how |
|---|---|---|
| **jar** | `Cobblemon-fabric-1.8.0+1.21.1.jar`, sha256 prefix `a6228f3291c70ed6` | the client copy at `C:/Users/wnd/AppData/Roaming/ModrinthApp/profiles/Fabric 1.21.10/mods/`, which is outside the server tree, so no lock was needed. The same copy was used by `docs/research/notes/starter-stat-mechanics.md` |
| **src:** | Cobblemon source at tag `1.8.0`, under `https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/` | fetched raw with curl and read verbatim (not summarised) |
| **MSD** | `mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar` | same client profile |
| **TMC** | `tmcraft-1.4.19+1.8.0.jar` | same client profile |
| **CV-DP** | `COBBLEVERSE-DP-v31.zip`, `COBBLEVERSE-Loot-DP-v11.zip` | local copy at `C:/Users/wnd/Documents/github/cobblers/COBBLEVERSE/datapacks/`, not the server's. **ASSUMED** to match the server's: same file name, and no change is recorded in STATE |
| **sim** | `tools/battle_sim.py`'s own `load_pack`, `build_leader`, `Mon` and `duel`, run from a scratch script that changes nothing in the repo | IVs 15, EVs 0, level-up moves only, 1v1 against each of the 35 leader Pokémon of gyms 1 to 8, at each gym's cap |

The Cobbleverse datapacks are no-redistribution, so this note states facts from them and quotes no file.

---

## 1. The five lines in the jar (VERIFIED, jar `data/cobblemon/species/<gen>/<name>.json`)

| Line | Stage BSTs | Native method | `baseFriendship` | Labels | `implemented` in the jar |
|---|---|---|---|---|---|
| Cosmog → Cosmoem → Solgaleo / Lunala | **200 → 400 → 680 / 680** | `level` **43**; then `level` **53** plus `time_range` day (Solgaleo) or night (Lunala) | 0 | legendary, restricted | no (MSD and CV-DP set it) |
| Kubfu → Urshifu | **385 → 550** | `item_interact` with `cobblemon:scroll_of_darkness` (Single Strike) or `cobblemon:scroll_of_waters` (Rapid Strike), no requirements | 50 | legendary | no (MSD, CV-DP) |
| Type: Null → Silvally | **534 → 570** | `level_up`, `friendship` **160** | 0 | legendary | no (MSD) |
| Poipole → Naganadel | **420 → 540** | `level_up`, `has_move` **dragonpulse**; drops a Shed Shell | 0 | ultra_beast | **yes** (the only line with a model in the jar) |
| Meltan → Melmetal | **300 → 600** | **none in the jar.** CV-DP adds one (§3b) | 0 | mythical | no (MSD, CV-DP) |

**The owner's four figures are right:** Cosmog 200, Solgaleo 680, Type: Null 534 and Silvally 570 all match the jar.

Other facts from the same files:
- Every one of the five has egg group `undiscovered`, experience group `slow` and catch rate 3, except Poipole (45).
  None can breed, so a starter cannot be duplicated through Cobbreeding.
- **MSD replaces two species files outright**: `species/generation8/kubfu.json` and `species/generation7b/melmetal.json`.
  - Kubfu's differs from the jar in `implemented`, the hitbox, a missing `behaviour`, and `consumeHeldItem: true` on
    both scroll evolutions.
  - Melmetal's adds riding and scale fields to its Gmax form.
  - The base stats are identical in both. Which copy wins between two mods is ASSUMED to follow mod load order.

## 2. Learnsets that matter (VERIFIED, jar `moves`)

- **Cosmog:** `1:splash` and `1:teleport`. No TM, tutor or egg entries.
- **Cosmoem:** adds only `1:cosmicpower` and `tm:cosmicpower`.
- **So the Cosmog line has no damaging move until Solgaleo or Lunala.** Natively that is level 53. MEASURED: the sim
  scores native Cosmog 0 of 35 at gyms 1 to 8.
- **Poipole:** `1:dragonpulse` is one of its five level-1 moves (acid, dragonpulse, growl, helpinghand, peck), and it
  also has `tm:dragonpulse` and `tutor:dragonpulse`.
- **Meltan:** level-up moves harden, thundershock, tailwhip (8), headbutt (16), thunderwave (24), acidarmor (32) and
  flashcannon (40); 14 TMs.
- **Type: Null:** a full level-up list through doubleedge at 55 (tackle, aerialace, scaryface, doublehit, metalsound
  ...); 40 TMs.
- **Kubfu:** a full fighting list through focuspunch at 52; 40 TMs.

## 3. The brief's four specific checks

### 3a. Type: Null's friendship threshold, and how friendship is gained here

The threshold is **160** (VERIFIED, jar `typenull.json`). `FriendshipRequirement.check` is `pokemon.friendship >= amount`
(src:`pokemon/requirements/FriendshipRequirement.kt`). Friendship starts at the form's `baseFriendship`, which is **0**
for Type: Null (src:`pokemon/Pokemon.kt` `var friendship = this.form.baseFriendship`). The maximum is 255
(`modpack/config/cobblemon/main.json:4`).

| Gain or loss | Amount | Source (1.8.0) |
|---|---|---|
| Level-up, when experience is gained with a player | +3 at 0–99, +2 at 100–199, +0 from 200, per level gained | src:`pokemon/Pokemon.kt` `addExperienceWithPlayer`, with `LEVEL_UP_FRIENDSHIP_CALCULATOR = SWORD_AND_SHIELD_LEVEL_UP` (src:`api/pokemon/friendship/FriendshipMutationCalculator.kt`) |
| Time out of the ball | **+1 every 120 s while sent out or shouldered, only while friendship < 160** | src:`api/storage/party/PlayerPartyStore.kt` `onSecondPassed`, lines 171–182 |
| Fainting | −1 | src:`pokemon/Pokemon.kt` (the `currentHealth` setter) |
| Berries (Pomeg, Kelpsy, Qualot, Hondew, Grepa, Tamato), X items, Dire Hit, Guard Spec. | raise it (amounts not read) | callers of `incrementFriendship` in the jar's classes: `FriendshipRaisingBerryItem`, `XStatItem`, `DireHitItem`, `GuardSpecItem`; lang tooltips |
| Poké Puffs | + or − by nature | `PokePuffItem` calls `setFriendship`; lang `tooltip.cobblemon.poke_puff.*` |
| Soothe Bell, Luxury Ball | boost gains | lang tooltips; `FriendshipEarningBoostEffect`. The mechanism was not read |
| Friend Ball | caught at 150 | lang tooltip. It does not apply to a starter, which is not caught |
| Remedies, Energy Root, Revival Herb, Heal Powder | lower it | lang tooltips |

**What that means (arithmetic from the table, ASSUMED nothing else intervenes):**
- **Time alone reaches exactly 160**, because the passive gain stops there. 160 × 120 s is **5 h 20 min** sent out or
  on the shoulder.
- **Levels alone** need 34 levels at +3 and then 29 at +2. From level 5 that is about **level 68**, past every cap
  (the Champion's ace is 62, measured from `data/trainers.json`).
- **In practice it is a mix.** Levels 5 to 30 give about 75, so roughly 2 h 50 min out of the ball reaches 160 by
  gym 3. Berries shorten it further.
- **The native method therefore evolves Type: Null at a time set by play style**, anywhere from gym 2 to the endgame.
  It cannot give identical evolution points.

### 3b. What Cobblemon substitutes for Meltan's candy threshold

- **Nothing.** The jar's `meltan.json` has **no `evolutions` entry**, and `melmetal.json` has no `preEvolution`
  (VERIFIED).
- **Cobbleverse supplies one.** CV-DP's `data/cobblemon/species_additions/meltan.json` appends `level_up` →
  `melmetal` with requirements `held_item` `minecraft:anvil` **and** `level` **70** (VERIFIED, local CV-DP).
  - Level 70 is above every cap in the campaign: gym aces end at 55, the Elite Four at 60 and the Champion at 62
    (`data/trainers.json`).
  - **So a Meltan starter would never evolve in our campaign.**
- **A collision to know about:** MSD also ships `data/cobblemon/species_additions/meltan.json`, without the evolution.
  Same namespace and name means the same id, so only one of the two applies (`JsonDataRegistry` keying,
  `docs/research/notes/starter-stat-mechanics.md` §1).
  - ASSUMED: the world datapack sits above mod data, so Cobbleverse's wins. EXP-049 step 1 reads it off a running
    server.

### 3c. Kubfu's Tower of Darkness and Tower of Waters

- **They do not exist.** No structure, worldgen file or `structure` requirement touches Kubfu in the jar, MSD, TMC
  or any Cobbleverse datapack. The only "tower" files are unrelated: Gimmighoul tower loot, Cobbleverse's Dawn, Dusk
  and Rocket towers, and the Johto pack's (VERIFIED by entry-name search).
- **The branch is item based.** It is the two scroll items (`item.cobblemon.scroll_of_darkness`, tooltip "Evolves
  Kubfu into Single Strike Style Urshifu"; the same for waters) used on Kubfu (VERIFIED, jar lang and species file).
- **Where the scrolls come from** (VERIFIED, files that name them):
  - COBBLEVERSE-Loot-DP-v11: archaeology loot (`desert_pyramid`, `ocean_ruin_warm`) and Urshifu raid loot.
  - `cobblemon-additions-4.1.6`: an `evolution_items` loot group.
  - The jar's `#cobblemon:evolution_items` tag.
  - No recipe.
- `data/blackout.json:118` already excludes the two scrolls from its consumables.
- ASSUMED: the archaeology sources are rare or absent in a pre-exported WorldPainter world, so the campaign would
  have to hand the scrolls out.

### 3d. Poipole and Dragon Pulse today

- `has_move` is `MoveSetRequirement`. It passes when Dragon Pulse is among the **four active moves**
  (`pokemon.moveSet.getMoves()`, src:`pokemon/requirements/MoveSetRequirement.kt`).
- **Any level-up move at or below the current level can be swapped in at any time** (src:`pokemon/Pokemon.kt`
  `allAccessibleMoves = form.moves.getLevelUpMovesUpTo(level) + benchedMoves + evolutionMoves`, and
  `relearnableMoves`).
- **Passive evolutions are attempted every second** for every party Pokémon (src:`api/storage/party/PlayerPartyStore.kt:146`,
  `lockedEvolutions.filterIsInstance<PassiveEvolution>().forEach { it.attemptEvolution(pokemon) }`, inside
  `onSecondPassed`).
- **So a level-5 Poipole can become Naganadel within seconds of the player slotting Dragon Pulse in.** The evolution
  is offered rather than forced (§4c).
- This also settles the old question in `starter-stat-mechanics.md` §3a (E3, "when is a `level_up` evolution
  tested"): every second, not only on level-up. A badge earned after the level is reached is seen within a second.

---

## 4. Can evolution methods be overridden from a datapack?

### 4a. The four routes

| Route | Removes the native method? | Scope | Evidence |
|---|---|---|---|
| `species_additions` `evolutions` | **No.** It appends | every member of the species | `SpeciesAdditions.reload`: `appendKeywordsCollection = listOf("forms", "evolutions")` (`starter-stat-mechanics.md` §1, VERIFIED there) |
| Full species file at the jar's exact path | **Yes** | every member | `JsonDataRegistry` keys by namespace + file name (same note §1). Two catches: additions still apply on top (CV-DP's Meltan rule re-appends), and MSD ships its own `kubfu.json` |
| **A form with its own `evolutions`, selected by an aspect** | **Yes, for that Pokémon only** | per instance | src:`pokemon/FormData.kt:210-211` `val evolutions get() = _evolutions ?: mutableSetOf()`: a non-standard form never falls back to the species list. src:`pokemon/Species.kt:129`: only `standardForm` is built with `_evolutions = this.evolutions` |
| **A MoLang callback on `evolution_tested`** that vetoes a native evolution | **Yes, per instance, conditionally** | per instance | src:`api/events/pokemon/evolution/EvolutionTestedEvent.kt`: the event carries `pokemon` and `evolution` and exposes `set_result`; `Evolution.test` posts it and returns `event.result` (src:`api/pokemon/evolution/Evolution.kt:94-99`). Callbacks fire from `data/cobblemon/callbacks/<event>/cobblers_*.molang` (EXP-042). **ASSUMED:** the field names on `q.evolution` (its id), never read |

The veto route is new here: neither earlier note lists it. With it, our replacement evolution is appended through
`species_additions` with a requirement on our starter aspect (requirement variant `properties`, ASSUMED name; the
`PokemonPropertiesRequirement` class exists, `starter-stat-mechanics.md` §3a). The callback then refuses the native one
for any Pokémon carrying that aspect. Wild Kubfu, Cosmog and Meltan, and raid bosses, keep their native methods. It
changes **no stats**, so it serves option (b), not (a).

### 4b. A forced aspect survives evolution (VERIFIED by source, never run)

- An evolution applies its `result` to the **same object** (`starter-stat-mechanics.md` §3a).
- The `species` setter (src:`pokemon/Pokemon.kt:182-205`) rebuilds `features` but **never touches `forcedAspects`**.
  It then calls `updateAspects()` and `updateForm()`.
- So a Cosmog carrying `aspect=cobblers_starter` arrives as a Cosmoem still carrying it, and the form is re-chosen by
  `Species.getForm(aspects)`.
- Every stage therefore needs its own form with that aspect, or it falls back to the standard form.

### 4c. Evolutions are offered, not forced (VERIFIED)

- `LevelUpEvolution`'s no-argument constructor defaults `optional = true` (src:`pokemon/evolution/variants/LevelUpEvolution.kt`).
  None of the five lines' JSON sets `optional`.
- `Evolution.evolve`: when `optional` is true, the evolution goes into the evolution proxy, so the player is offered it.
  Otherwise `forceEvolve` runs at once (src:`api/pokemon/evolution/Evolution.kt:107-117`).
- **"Identical evolution points" are therefore identical earliest points.** A player can decline or postpone. Set
  `"optional": false` to force it (ASSUMED that the JSON key deserialises; the field is a `var`).

### 4d. Two evolutions on a two-stage line

- **Only Cosmog has two native evolutions.** Kubfu, Type: Null, Poipole and Meltan evolve once.
- So two identical points for all five need the second step to be a **same-species stage**: an aspect change that
  selects a stronger form. That exists only on the form route (option a in the cost note).
- Without forms, the four two-stage lines get one evolution, at one of the two points.

## 5. Can a learnset be edited from a datapack?

- **Species-wide, by `species_additions` `moves`: admissible, never loaded anywhere in our stack.**
  - `moves` is a mutable `Species` property (src:`pokemon/Species.kt:87`, `var moves = Learnset()`). It is not in the
    append list, so an addition **replaces the whole learnset**.
  - Not one of the 495 shipped addition files in CV-DP or the client profile's mods sets a top-level `moves` or
    `baseStats`. There is no precedent (measured by key count over every `species_additions` file).
  - It would change every Poipole, wild ones included. CV-DP spawns those at level 40 (`0803_poipole.json`), which is
    already past a gym-3 level.
- **Per instance, by a form's own `moves`: admissible, with heavy precedent.**
  - `FormData.moves get() = _moves ?: species.moves` (src:`pokemon/FormData.kt:163-164`).
  - **CV-DP ships 16 forms with their own `moves`, 69 with their own `baseStats` and 20 with their own `evolutions`**,
    all through `species_additions` (Primal Dialga, Shadow Mewtwo, Shadow Lugia and others). Measured by key count.
  - This is the strongest evidence yet that the form route loads. It is still not proof that **our** forms behave
    (EXP-049).
- **By a full species file:** yes, species-wide. The parallel note says copies of Cobblemon's species files must not
  be committed (its §4a, citing MPL-2.0). That claim is **relayed**, not re-checked here.

**For Poipole, a learnset edit is the hard way.** Dragon Pulse leaks through three other channels besides the
level-1 entry:
- the native 1.8 TM (`data/cobblemon/tms/dragonpulse.json`, unlockable, recipe 8 Dragon Gems + 1 Dragon Scale);
- TMCraft (`tmcraft:tm_dragonpulse`: gold blank disc + Dragon Gem + bell);
- `tutor:dragonpulse`.

A gate on the move needs all three removed. A `level` requirement leaks nowhere.

**The alternative the cap provides for free:** a level requirement **is** a badge gate here (§6). The move gate (and
"something similar for Meltan") is not needed. Meltan's only move worth gating, Flash Cannon (40), has the same TM and
tutor leaks.

## 6. Where "around gym 3" and "around gym 6" fall

**The caps are confirmed:** 20/25/30/35/40/45/50/55 are exactly the gym 1–8 aces (MEASURED from `data/trainers.json`,
`generation_contract.gym_ace_levels`). Then come the Elite Four at 60 and the Champion at 62. The rules are
`initialLevelCap = 20` and `relativeLevelCap = 0` (`modpack/config/rctmod-server.toml:144,153`).

The cap is the next required trainer's strongest Pokémon (the same file's comment), so a player is capped at **N's ace
on the way to gym N**:

| Level | First reachable | Reads as |
|---|---|---|
| 26 | after gym 2 is beaten | the moment gym 2 falls |
| **30** | on the leg to gym 3, at its cap | evolves *for* the gym 3 fight |
| **31** | after gym 3 is beaten | evolves as gym 3's reward |
| **45** | on the leg to gym 6, at its cap | evolves *for* gym 6 |
| **46** | after gym 6 is beaten | evolves as gym 6's reward |

- **This depends on the cap holding experience.** That is VERIFIED as rctmod's behaviour in play
  (`experiments/EXP-035-first-playtest/README.md:34`, relayed through `docs/research/notes/level-cap-catch-block.md:3`).
- **ASSUMED: Rare Candies and `/pokeedit level` are not capped.** If a Rare Candy ignores the cap, the level gate
  leaks. Add an `advancement` requirement on our badge flag (`cobblers:flag/gymN_cleared`,
  `docs/mechanics/STARTER_DESIGN_COMPARISON.md:40-41`) to close it. EXP-049 step 4.

**Normal starters do not reach their second stage at gym 3** (MEASURED from the jar, all 27 configured starters):
- The middle stage comes at **14 to 18, median 16**: on the leg to gym 1, under cap 20.
- The final stage comes at **30 to 36, median 36**: Totodile at 30, three at 32, three at 34, three at 35 and
  seventeen at 36. That is legs 3 to 5, typically after gym 4.
- **BST medians:** 310, 405 and 530.

So gym 3 and gym 6 are each roughly one stage behind a normal starter: deliberately late. That matches "the final form
does not carry the midgame". To track a normal starter instead, the points are about 16 and 36.

## 7. Rendering (relevant because only Poipole has a model in the jar)

- MSD 1.0.2 ships species resolvers for Cosmog, Cosmoem, Solgaleo, Lunala, Kubfu, Urshifu, Type: Null, Silvally,
  Meltan and Melmetal (VERIFIED, entry names). Its `species_additions` set `implemented: true` on all of them.
- They were not in the 2026-09-26 doll audit, which covered spawnable species only (`docs/research/CLIENT_MODEL_FIXES.md:88-104`).
- **ASSUMED:** they render. A custom aspect with no variation of its own should fall back to the base variation.
  EXP-049 step 1 checks both.

## 8. What the simulator says (MEASURED; lower bounds, not predictions)

The measure is wins out of 35 leader Pokémon. Today's 27 starters measure **9 to 27, median 17** (reproduced this
session). Full tables are in `docs/mechanics/NATIVE_STARTERS_COST.md` §3.

- **Native, as the sim sees them: 0 to 16.** The sim cannot follow `has_move`, `friendship`, `item_interact` or a
  two-requirement level rule.
- **Native species, our points:**
  - at 31/46: 3 (Cosmog) to 26 (Type: Null);
  - at 30/45: 8 to 29.
- **Normalised stats alone do not close the spread.** Typing and the level-up movepool dominate. **Meltan is last in
  every scenario measured (2 to 14).** Melmetal has Speed 34 and a thin level-up list.

## 9. Cross-check with the parallel note (`194330c`)

**Agrees, independently measured:**
- Every stat and method in §1.
- The 160 threshold and its arithmetic.
- Meltan's missing evolution and Cobbleverse's anvil + 70.
- The towers' absence.
- Poipole's level-1 Dragon Pulse and the every-second check.
- The 31/46 cap reasoning.
- The normal starters' 16/36.
- Option (b)'s sim figures, identical to the unit: 3/22/26/20/12 at 31/46 and 8/24/29/23/14 at 30/45.
- The stress-test breakage.

**Differs or adds:**
1. **The `evolution_tested` veto route** (§4a). It gives option (b) per-instance replacement **without copying any
   species file**. That sidesteps both catches the parallel note raises against full files: CV-DP's re-appended Meltan
   rule and MSD's duplicate `kubfu.json`.
2. **"Normalised" option (a) depends on the authoring.** The parallel note scaled each line to its final form's shape
   and learnset, and got Type: Null 31–32. This session scaled each stage's own shape and learnset, and got Type: Null
   16–21. Neither is the answer: option (a)'s outcome is whatever movepools are authored. "Does not narrow the spread"
   is true of *stats alone*, not of the form route.
3. **A lighter option (a)**, with forms on the first two stages only and a native final stage, removes the
   Silvally ×17 and Urshifu ×2 fan-out that dominates the parallel note's 5–7-session estimate. Measured in the cost
   note.
4. **The CV-DP precedent count** (16 forms with `moves`, 69 with `baseStats`, 20 with `evolutions`). It strengthens the
   form route's prior.

## 10. Not checked

- The exact friendship amounts from berries, X items and Soothe Bell.
- The field names on `q.evolution` in MoLang.
- Whether `optional: false` deserialises.
- Rare Candy against the cap.
- Pack order on the server: the world datapacks against MSD's data, and global `datapacks/` against world ones.
- Whether the server's `COBBLEVERSE-DP-v31.zip` is byte-identical to the local copy.
- Whether any shipped Cobbleverse form addition loads cleanly on our server; the boot log was not read, because that
  needs the lock.
- The Cobblemon data licence, relayed.
