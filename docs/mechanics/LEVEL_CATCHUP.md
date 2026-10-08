# The levelling catch-up: a training ground per gym town

**Status:** built as data and a generator, 2026-10-06. Planned, not placed, not run in game.
**Owner's brief (2026-10-06):** "A player should not have to grind levels. Build a per-gym catch-up: rare candies, an
EXP source, a training area -- whatever fits. It should make reaching the cap for the next gym straightforward without
letting anyone exceed it. The cap already holds the ceiling; this is about the floor."

**Data:** `data/training_grounds.json` (design). **Generator:** `tools/training_grounds.py`. **Tests:**
`tests/test_training_grounds.py`. **Shared records it owns:** the eight `training_ground_gym<N>_block` records in
`data/habitat_blocks.json` and the eight `training_ground_gym<N>` pools (habitat + entries) in `data/spawns.json`.

## 1. The decision

One **training ground** per gym town: an activated Habitat Block, 70-133 blocks from the town centre and 51-112 from
the nearest route path. It keeps up to six high-EXP-yield wild Pokemon alive within 16 blocks, at **cap - 3 to cap - 1**,
where the cap is the one the player holds on reaching that town. A standing sign beside it says what it is.

- **Why a ground and not candies first:** battle EXP is clamped at the cap by rctmod, the ground costs the economy
  nothing, and it serves every Pokemon in the party. One knock-out at a ground is worth about 4.4 Exp. Candy S at gym 1
  (3,527 EXP, an L18 Audino against an L14) and 3.5 Exp. Candy M at gym 8 (10,475 EXP, the roster's weighted yield at
  L53 against an L49).
- **Candies are safe but are not built** (section 5): the markets' curve has no room for them at badges 1-3, and the
  stalls' rule forbids them. That is the owner's choice to make.

## 2. Does the cap stop candies? (VERIFIED, from source and bytecode; not run in game)

| Source of EXP | Path in Cobblemon 1.8.0 | Clamped by rctmod? |
|---|---|---|
| Wild and trainer battles | `PokemonBattle` -> `addExperienceWithPlayer` -> `addExperience` | **yes** |
| Exp. Share (held item, `cobblemon:exp_share`, tag `held/experience_share`) | the same battle path, x `experienceShareMultiplier` 0.5 | **yes** |
| Rare Candy (`getExperienceToNextLevel()`), Exp. Candy XS/S/M/L/XL (100/800/3000/10000/30000) | `CandyItem.applyToPokemon` -> `addExperienceWithPlayer` | **yes**, and **the candy is not used up** when 0 EXP is added (`if (result.experienceAdded > 0) stack.consume(1, player)`) |
| Capture XP mod (`capturexp-fabric-1.8.0-1.3.0`) | `CaptureOutOfBattleHandler` -> `addExperienceWithPlayer` | **yes** |
| **cobblecuisine EXP-boost food** (`expBoostMultiplier` 2.0, 6000 ticks) | its own `EXPERIENCE_GAINED_EVENT_PRE` handler at `Priority.NORMAL`, **after** rctmod's at `HIGHEST`; it multiplies the already-clamped amount | **NO: a cap bypass** (defect D1) |
| **cobblecuisine Fancy Shake** | `FancyShakeItem` calls `Pokemon.setLevel` and posts `LEVEL_UP_EVENT`; the level setter posts no EXP event | **NO, if it raises the level** (defect D2, read from bytecode strings only) |

Sources:
- **rctmod 0.19.0-beta** `ModServer.java`
  (https://gitlab.com/srcmc/rct/mod/-/raw/v0.19.0-beta/common/src/main/java/com/gitlab/srcmc/rctmod/server/ModServer.java):
  `CobblemonEvents.EXPERIENCE_GAINED_EVENT_PRE.subscribe(Priority.HIGHEST, ModServer::onExperienceGained)`.
  - The handler sets `event.setExperience(Math.min(event.getExperience(), maxExp))`, where `maxExp` is
    `getExperienceToLevel(levelCap)`, unless `allowOverLeveling`.
  - It does not look at the source.
  - The same names are in the jar's `ModServer.class` (snapshot `server-snapshot-2026-10-05/mods`).
  - Our config keeps `allowOverLeveling = false` (`modpack/config/rctmod-server.toml:167`).
- **Cobblemon 1.8.0** `Pokemon.kt`: `addExperience` posts `ExperienceGainedEvent.Pre` and adds `it.experience`.
  `getExperienceToLevel(level)` is 0 when `level <= this.level`, so a Pokemon at or over the cap gains nothing.
  - `CandyItem.kt` and `CobblemonItems.kt`: every candy is a `CandyItem`.
  - Priority order: `PrioritizedList.reorder` walks `Priority.values()`, HIGHEST first (`javap`, jar).
- **cobblecuisine 2.0.1** `ExpGainPreEvent.class` (`javap -c`): it subscribes at `Priority.NORMAL`. If the owner has the
  `EXP_BOOST` effect, it does `setExperience(getExperience() * expBoostMultiplier)`.
  - The multiplier is 2.0 in `base-pack/cobbleverse/config/cobblecuisine.json`, and our overlay does not change it.
  - **Worked consequence:** a Pokemon 5 levels under the cap, under the effect, that earns a large gain is clamped to
    the EXP to the cap and then doubled. It lands about as far past the cap as it started under it. Once it is over,
    `getExperienceToLevel` is 0, so further gains are 0 (`0 x 2`).
  - So the overshoot is bounded at one gain, but it is real.

**The premise "the cap already holds the ceiling" is therefore true for every EXP source but these two cobblecuisine
items.** Neither is touched by this work, and the training ground adds no new way to use them.

## 3. The EXP model (VERIFIED from the jar unless marked)

`StandardExperienceCalculator.calculate` (Cobblemon 1.8.0, `javap -c`):

`round((base * L / 5 * participation * ((2L + 10) / (L + Lp + 10))^2.5 + 1) * notOT * luckyEgg * evo * affection * experienceMultiplier)`

| Term | Value |
|---|---|
| `base` | the foe's species `baseExperienceYield` |
| `L` | the foe's level |
| `Lp` | the earner's level |
| `participation` | 1, or `experienceShareMultiplier` 0.5 for an Exp. Share holder |
| `notOT` | 1.5 for a traded Pokemon |
| `luckyEgg` | 1.5 |
| `evo` | 1.2 past a level evolution |
| `affection` | 1.2 at friendship 220 |
| `experienceMultiplier` | **2.0** (`modpack/config/cobblemon/main.json:41`) |

**Yields** (jar species data):

| Species | Yield | Group | Note |
|---|---|---|---|
| Blissey | 635 | fast | |
| Chansey | 395 | fast | |
| Audino | 390 | fast | no evolution |

The next non-legendary is 300: the pseudo-legendary finals.

**Experience groups:** `MediumSlow` was read from the jar: `max(0, 6n^3/5 - 15n^2 + 100n - 140)`. Slow (`5n^3/4`) and
medium-fast (`n^3`) are ASSUMED to be the main series' formulas.

**Worked knock-out:** Audino L17 against a L12 gives 1326 x 1.3519 + 1 = 1793.6, x 2.0 = **3587 EXP**. This is pinned in
`tests/test_training_grounds.py`.

## 4. The grounds

| Gym | Ground | Block (x, y, z) | From town | From path | From building | Roster | Levels |
|---|---|---|---|---|---|---|---|
| 1 | Stoneford Training Ground | (1833, 139, 3618) | 91 | 81 | 37 | Audino | 17-19 |
| 2 | Viltri Quay Training Ground | (1543, 106, 2759) | 75 | 75 | 40 | Audino | 22-24 |
| 3 | Highwire Training Ground | (1586, 140, 1436) | 105 | 103 | 75 | Audino | 27-29 |
| 4 | Greenhollow Training Ground | (4391, 110, 1505) | 96 | 93 | 36 | Audino | 32-34 |
| 5 | Fenhide Training Ground | (4644, 118, 2516) | 70 | 51 | 37 | Audino | 37-39 |
| 6 | Tilpey Cross Training Ground | (6170, 97, 3268) | 133 | 112 | 40 | Audino/Chansey/Blissey | 42-44 |
| 7 | Cinderlee Training Ground | (6108, 105, 4885) | 115 | 54 | 37 | Audino/Chansey/Blissey | 47-49 |
| 8 | Holdfast Training Ground | (3717, 111, 6535) | 80 | 76 | 33 | Audino/Chansey/Blissey | 52-54 |

All distances are in blocks.

**Caps.** They are not stored in the data: `rct_caps()` (`tools/legendaries_audit.py`) computes 20/25/.../55 before
gyms 1-8 from `data/trainers.json`.

**Rosters.** Audino has weight 24. From gym 6, Chansey and Blissey have 12 each, all in the common bucket.
- Chansey and Blissey stand only from gym 6: `data/spawns.json` evolution_policy allows evolutions not by level only
  from tier 6, and the test reads that from the jar.
- Every ground's Pokemon is catchable, because none is over the cap. That makes Audino available from gym 1 and Blissey
  common from gym 6 (today it is uncommon at tier 7 in tilpey_west_meadows). **This is a design choice for the owner**
  (decision LC-2).

**Siting.** All rules are in `data/training_grounds.json` `rules`:
- 60-150 blocks from the town centre.
- 40 or more from every route path.
- 40 or more from every coordinate in any `data/*.json`, the host town's centre aside: a sweep, not a list.
- 32 or more from every building footprint, as `tools/place_donor.py` seats it.
- Clear of every other Habitat Block's spawns.
- Relief of 6 or less within 12 blocks.
- No sea, lake or river column within 20 blocks, using the painted masks.
- WorldPainter GRASS terrain under the block, which mimics `minecraft:grass_block`.
- The straight walk from each town centre steps at most 2 blocks per half-block sample. Highwire's ground is 34 blocks
  below its town, down a 1-in-3 slope. Walkability itself is not checked.

**Time to cap.** `python tools/training_grounds.py estimate` makes these assumptions:
- A party of six reaches the town four at the band top (cap - 6) and two recent catches at the band middle (cap - 11).
- Each knock-out counts the roster's weighted yield at the band's middle level.
- One participant takes each knock-out (lead rotated).
- Every gain is clamped as rctmod clamps it.
- **ASSUMED:** 60 seconds per wild battle. Six Pokemon are always up, so there is no search time.

| Gym | Medium-slow: KOs (min) to cap - 2 | Medium-slow: to cap | Slow: to cap - 2 | Slow: to cap |
|---|---|---|---|---|
| 1 | 6 (6) | 12 (12) | 12 (12) | 18 (18) |
| 2 | 8 (8) | 14 (14) | 14 (14) | 20 (20) |
| 3 | 14 (14) | 20 (20) | 20 (20) | 26 (26) |
| 4 | 16 (16) | 26 (26) | 22 (22) | 34 (34) |
| 5 | 22 (22) | 28 (28) | 28 (28) | 36 (36) |
| 6 | 22 (22) | 28 (28) | 24 (24) | 36 (36) |
| 7 | 24 (24) | 34 (34) | 30 (30) | 42 (42) |
| 8 | 28 (28) | 36 (36) | 32 (32) | 48 (48) |

**The brief's target ("within ~2 levels after ~15 minutes") is met for gyms 1-3. It is not met for gyms 4-8 when the
whole party is six levels behind.** That is 16-28 minutes, or about 3-5 knock-outs per Pokemon. Per Pokemon it is
straightforward; for a full party behind, it is a session.

**The lever that closes it** is Exp. Share on the bench. Five holders turn each knock-out into a party-wide gain. The
same model then brings all six to cap - 2 in this many knock-outs:

| Gym | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| KOs | 2 | 3 | 4 | 5 | 7 | 6 | 8 | 8 |

That is under 10 minutes at every gym. `cobblemon:exp_share` is sold nowhere today (decision LC-1).

## 5. Candies: safe, not built, and why

- **Safe against the cap:** VERIFIED (section 2), apart from the cobblecuisine boost, which affects every EXP source
  alike.
- **No home without a decision.**
  - The counters' curve (`tools/markets_audit.py`, PROGRESSION_LADDER 0.3) holds the cumulative ask at 0.65-0.70 of
    income at every badge.
  - Measured 2026-10-06 from `data/markets.json`, the room under 0.70 is **129 at badge 1, 551 at badge 2 and 201 at
    badge 3**, cumulative.
  - Any candy line priced as a convenience fails the curve at badge 1 or 3.
  - Stalls take only vanilla provisions (`stalls_basis.budget`).
  - `docs/mechanics/TIERED_GOODS.md` 2.6 says candies are "deliberately never sold", on the reading that the cap is the
    pacing. The cap does clamp them, so that reason does not hold. The rule itself is still the markets' to change.
- **Decision LC-3 for the owner:** leave them out (the grounds suffice), re-derive the curve with candies in it, or
  exempt consumable conveniences from the curve.

## 6. Re-apply (steps named; `tools/reapply.py` not edited)

1. prepare job `compile_spawns` (`tools/compile_spawns.py`): it already compiles every habitat in `data/spawns.json`
   into `build/datapacks/cobblers_spawns/data/cobblers/habitat_pools/training_ground_gym<N>.json`.
2. prepare job `habitat_blocks:function` (`tools/habitat_blocks.py function`): it already writes every manifest block.
   The eight are in it (359 blocks).
3. apply step **R9E** places them.
4. **NEW, needs adding to `tools/reapply.py` by its owner:**
   - a prepare job `python tools/training_grounds.py build` writing `build/datapacks/cobblers_training_grounds`;
   - an apply step after R9E that runs `function cobblers:training_grounds/build` (eight standing oak signs, each under
     its own forceload).
   - Suggested id: **R9TG**. Until it exists the grounds work but are unsigned.
5. After a data change: `python tools/training_grounds.py site --write` (only if the rules or the world's features
   moved), then `records --write`, then the steps above.

## 7. What an audit must check

An independent auditor should not reuse `Site`, `records` or `merged` from the tool.
1. **The clamp, in game** (EXP-candidate, staging only):
   - a Pokemon two levels under its cap, given an Exp. Candy L, stops at the cap and keeps the candy;
   - a Rare Candy at the cap is not used up;
   - a knock-out at a ground stops at the cap;
   - **and** the same with the cobblecuisine EXP-boost effect active. This is expected to overshoot (D1); record by how
     much.
2. **Each ground's Pokemon level never exceeds the cap before its gym.** Derive the cap from rctmod's rule over
   `data/trainers.json` and the toml, not from `data/training_grounds.json`.
3. **No Habitat Block's spawn sphere overlaps a ground's.** Sweep the whole manifest, including blocks added after
   today.
4. **No building, lot, NPC, trainer seat, cache or dressing lies within 32 blocks.** Read the world's features from
   every source, including `derived/` (signposts, lamps, dressing) and the templates' own NPC spawners. The sweep here
   reads `data/` only.
5. **The block is in the world** after R9E, at `(x, y, z)` with `PoolId` `cobblers:training_ground_gym<N>`
   (`python tools/habitat_blocks.py verify --world <stopped copy>` or `--rcon`). The surface there matches the
   heightmap: town earthworks could have moved it, so check this by reading the world, never by deciding from it.
6. **Reachability:** the ground can be walked to from the town without crossing water or a cliff.
7. **Generator mutation:** change `band()` in `tools/training_grounds.py` to `cap + 1`, run `records --write` into a
   scratch copy, and confirm the auditor's level check fails while `data/training_grounds.json` is untouched.
8. **The time estimate** in a real session: knock-outs per minute at one ground, against the 60-second assumption.

## 8. Defects found (recorded, not chased)

- **D1:** cobblecuisine's EXP-boost food multiplies EXP after rctmod's clamp, so a Pokemon can pass the cap by up to
  about its starting deficit (section 2).
- **D2:** cobblecuisine's Fancy Shake sets the level directly and bypasses the EXP event. Read from bytecode strings,
  not run: whether it raises a level, and by how much, is unknown.
- Both are obtainable only if their recipes are craftable on the server, which was not checked.
