# EXP-066: Do alphas pay type gems by level, both types of a dual type, and no candies?

**Status: designed 2026-10-08, NOT_EXECUTED.** Every case below needs a player in game on staging. Nothing here has
been observed; the pack is valid files and a callback written only in forms the jar's own callback uses.

## Objective

The owner, 2026-10-08: *"Option C for alphas. Candies out, gems in, paid by alpha level."* The world pack
`cobblers_alpha_spoils` (`tools/alpha_spoils.py`, `data/alpha_spoils.json`, design
`docs/mechanics/DROPS_PROGRESSION_SPLIT.md` section 3) empties the jar's four alpha tier loot tables (every Exp.
Candy, the Rare Candy and the six IV candies an alpha gave) and adds `cobblers_alpha_spoils.molang` beside the jar's
`pokemon_alpha_drops.molang`, which rolls the alpha's per-type tables more as its level rises and rolls the
**second** type of a dual-type alpha. This experiment answers four things:

1. **X5, first:** does the jar's own callback ever pay a dual-type alpha its second type? The design reasons it
   does not (`pokemon_alpha_drops.molang` tests `q.length(t.types)` on the one-entry list it has just built, so slot
   1 is always the primary type: 3.3, REASONED). The jar's `q.length` returns a struct's entry count
   (`GeneralMoLangFunctions holder$lambda$23`, javap 2026-10-08), which makes the reading stronger, not proven.
2. With the pack: no candy of the twelve drops from any alpha.
3. With the pack: the gems a KO follow the alpha's level band.
4. With the pack: a single-type alpha gets its extra rolls in its only type.

"Yes" to 2-4 lets the pack go to the live world. X5's answer decides nothing about installing (ours pays the second
type either way) but settles the reasoning in the design and in `docs/research/DROPS_AUDIT.md:161-162`.

## What a KO should drop (from the jar's tables; nothing here is observed)

A **type-table roll** gives the type's gem (75%: 1-2 at type tier 1, 2-3 at tier 2) or its resist berry (25%).
Type tier 2 starts at alpha level 51. So every type-table roll leaves **one stack**, and its item says which type
was rolled. For the Pokemon used below:

| Type | Gem | Resist berry |
|---|---|---|
| normal | `cobblemon:normal_gem` | `cobblemon:chilan_berry` |
| flying | `cobblemon:flying_gem` | `cobblemon:coba_berry` |
| steel | `cobblemon:steel_gem` | `cobblemon:babiri_berry` |

| Alpha level at the faint | Jar's rolls | Ours (certain) | Type-table stacks a KO | Expected gems a KO |
|---|---|---|---|---:|
| 1-30 | 2 at 1-in-2 | none | 0-2 | 1.125 |
| 31-50 | 2 at 1-in-2 | 1, second type | **at least 1**, 1-3 | 2.25 |
| 51-65 | 2 at 1-in-2 | 1, second type, tier 2 | **at least 1**, 1-3 | 3.75 |
| 66+ | 2 at 1-in-2 | 2, second and first type, tier 2 | **at least 2**, 2-4 | 5.625 |

Beside these, the alpha's own species drop and anything else Cobblemon gives a wild KO (a Tera Shard, the species
table) still drop; they are not counted here. Stock pack (ours off): the tier table also drops candies (tier 1:
Exp. Candy XS/S/M; tier 2: S/M/L; tier 3: M/L and IV candies; tier 4: L/XL, Rare Candy and IV candies).

## Success criteria

- **X5 (stock pack):** ten KOs of one dual-type alpha, every type-table stack recorded by item. If the jar pays the
  second type, P(no second-type stack in ten KOs) is 0.5^10, about 0.001. **Zero second-type stacks in ten KOs
  confirms the bug; any one refutes it.**
- **X5 (our pack):** the same alpha, at 31 or above: **every** KO leaves at least one second-type stack.
- **No candies:** across every KO with the pack on, zero of `exp_candy_xs`, `_s`, `_m`, `_l`, `_xl`, `rare_candy`,
  `health_candy`, `mighty_candy`, `tough_candy`, `smart_candy`, `courage_candy`, `quick_candy`.
- **Bands:** each KO's type-table stack count is inside its band's range above, the minimum always met; gem stacks
  are 1-2 under 51 and 2-3 from 51.
- **Single type:** at 66 or above, every KO leaves at least two stacks of its only type and none of any other.
- **Clean load (X6):** the server log after start shows no loot-table or MoLang error naming
  `cobblers_alpha_spoils` or `alpha_rewards_tier`, and Cobblemon's callback count (logged by
  `CobblemonCallbacks.reload`) is one higher with the pack than without it.

## Dependencies

- Staging only (never the live world). `cobblers_alpha_spoils` installed **world-local**
  (`tools/reapply.py install`, which copies it with the other world-local packs; it is in `SERVER_PACKS` and
  `WORLD_LOCAL`, built by prepare's `alpha_spoils:build` job).
- Cobblemon 1.8.0+1.21.1 (the jar the tool checks against).
- An op, to spawn and to toggle the pack.

## Implementation

- `data/alpha_spoils.json`: the four tier tables and the items read from them, the type-table pattern, the bands.
- `tools/alpha_spoils.py check|build` -> `build/datapacks/cobblers_alpha_spoils/`:
  - `data/cobblemon/loot_table/alpha/alpha_rewards_tier{1,2,3,4}.json`, each `{"type": "minecraft:chest", "pools": []}`;
  - `data/cobblemon/callbacks/battle_fainted/cobblers_alpha_spoils.molang`.

## Test instructions

**Which alpha.** Alpha level matching re-levels a wild alpha to the nearest player's highest party level plus 4 to
20 (`docs/mechanics/ENCOUNTER_DESIGN.md:344-361`, relayed), so the level that decides the band is **the level shown
in battle**, not the spawn table's. Record it for every KO. Choose the band by the tester's party level.

- **Dual-type (X5):** **Noctowl** (normal/flying). We spawn it as an alpha at Viltri's Path valley (heart x816
  z3536, levels 22-30) and the Route 1 maze forest (heart x1744 z4752, 20-25) (`data/spawns.json`
  `surface.viltris_path_valley.heart.noctowl`, `surface.route1_maze_forest.heart.noctowl`). For the 51+ bands,
  **Skarmory** (steel/flying, plateau east, heart x5744 z6224, 53-60, `surface.plateau_east.heart.skarmory`).
- **Single-type:** **Watchog** (normal), same Viltri's Path heart (`surface.viltris_path_valley.heart.watchog`).
- Waiting for wild alphas is slow. An op can spawn one: the property key `alpha` exists in the jar's
  `PokemonProperties` parser (string read 2026-10-08; its exact syntax is NOT verified), so try
  `/spawnpokemon noctowl alpha=true` and confirm the battle shows it as an alpha. If it does not parse, use the wild
  hearts above.

**Each KO.** Beat it in battle (a faint, not a catch: a catch fires no `battle_fainted`). Stand clear until the
items land, pick up everything, and write down each stack: item and count. Clear the inventory between KOs, or
count the difference.

1. **X5, stock pack.** `/datapack disable "file/cobblers_alpha_spoils"` in the staging world, `/reload`, and confirm
   the log's callback count dropped by one. Ten KOs of an alpha Noctowl at any level. Record normal (gem, chilan) and
   flying (gem, coba) stacks separately. Candies will drop here: that is the jar's tier table, expected.
2. **Pack on.** `/datapack enable "file/cobblers_alpha_spoils"`, `/reload`, confirm the count rose by one. If either
   reload leaves the count unchanged, restart the server instead and re-check.
3. **X5, our pack.** Ten KOs of an alpha Noctowl at level 31-50. Each must leave at least one flying stack.
4. **No candies.** Throughout steps 3-6, no candy of the twelve.
5. **Bands.** At least five KOs in each of 1-30, 31-50, 51-65 and 66+ (Noctowl below 51, Skarmory from 51). Record
   the stack count and gem counts against the table.
6. **Single type.** Five KOs of an alpha Watchog at 66 or above: at least two normal stacks each, nothing of
   another type.

## Results

Not run.

## Limitations

- A dual-type alpha **under 31** gets only the jar's rolls (both its first type, if X5 confirms the bug): the design
  keeps leg 1 at 1.125 gems a KO, and this experiment does not change that.
- Pasture Loot, catches and non-battle deaths are not covered: the callback is `battle_fainted` only.
- Multiplayer: items land at the alpha for whoever picks them up; not tested with two players.
- Expected gems a KO are means; ten or five KOs test the ranges and minimums, not the means.

## Decision

Pending the run.

## Follow-up

- `test-author`: the validator the design lists (3.5): the four tier tables empty, no progression id from 1.3 in our
  packs outside a dungeon reward table, `cobblers_alpha_spoils.molang` present and no file overriding
  `pokemon_alpha_drops.molang`, and the mutation (an `exp_candy_xs` back in the tier-1 override must fail).
- X3 (candies at the cap) is separate and still owed.
