# EXP-067: does a crafted TM unlock at its badge, per player, with no other recipe lost?

## Objective

The owner, 2026-10-08: "Gate the recipes by badge." `cobblers_tm_gate` (`tools/tm_gate.py`, `data/tm_gate.json`)
turns on `doLimitedCrafting`, gives every player every recipe once a plan, takes back the TMCraft TM recipes of
the badges they lack, and gives a badge's TMs when its flag is granted. Prove in a running server that:

1. a gated TM cannot be crafted before its badge and can be crafted after it;
2. ordinary recipes stay craftable for a fresh player: planks, a Poke Ball, a Cobblemon apricorn ball, a mod
   furniture block, a Cobblemon recipe with no unlock advancement of its own;
3. a player who joined before the change keeps every ordinary recipe and loses only the TMs of badges not held;
4. the crafting devices that ignore the recipe book are gated, and nothing else.

Run by someone other than the author of the pack (CLAUDE.md principle 16).

## What it relies on, and what is ASSUMED

Read from jars (2026-10-08), not run:

- Minecraft 1.21.1: `RecipeCraftingHolder.setRecipeUsed(Level, ServerPlayer, RecipeHolder)` refuses a non-special
  recipe the player's book lacks while `doLimitedCrafting` is true, and only `CraftingMenu.slotChangedCraftingGrid`
  (crafting table, the 2x2 grid) calls it (`data/tm_gate.json` `mechanism.verified_from_jar`).
- TMCraft's TMs are vanilla `crafting_shapeless` / `crafting_shaped` recipes; its unlock advancements
  (`tmcraft:recipes/misc/tm_*`) are closed by the pack.
- COBBLEVERSE's `cobblemon:root` (the starter pick) runs `cobbleverse:starter_pack`, which runs `recipe give @s *`;
  the pack's `cobblers:tm_gate/resync/1` re-syncs the player on the next tick.
- Tom's Storage's crafting terminal and the Crafter look recipes up without the book: their recipes are gated at the
  last TM badge. Sophisticated Core's crafting upgrade calls the vanilla check.
- ASSUMED: `recipe give @s *` gives every loaded recipe and a toast; the `minecraft:tick` earn advancement fires for a
  player holding the flag; a gamerule set in a load function persists.

The measured sweep (`python tools/tm_gate.py sweep --server-dir <snapshot> --vanilla-jar <1.21.1 jar>`, snapshot
2026-10-05): 9,691 loaded recipes; 5,342 crafting-grid recipes, of which **1,933 have no unlock advancement**
(tmcraft 1,400, of which 929 are TM conversions; cobblecuisine 177, beautify 56 because advancementdisable drops
beautify's advancements, mega_showdown 53, ironchest 45, lumymon 37, cobblemon 33, cobblenav 30, toms_storage 25, and
10 more namespaces; 533 outside tmcraft). `doLimitedCrafting` alone would strand those for any player who has not picked a starter. The pack's
`recipe give @s *` is what keeps them.

## Setup

Staging only, never the live world. Install as the other world-local packs (`tools/reapply.py install` after
`prepare`; the pack is `build/datapacks/cobblers_tm_gate`, built from the server's own jars by the `tm_gate` job).
Two players: A (fresh: no starter, no badges) and B (a player who joined BEFORE the pack: has a starter and the
Boulder Badge flag; record `recipe` state first with `/advancement` and the recipe book). Give both, in creative or
by `/give`, the inputs for each case. Check the gamerule: `/gamerule doLimitedCrafting` answers `true`.

## Cases

| # | Who | Does | Expected |
|---|---|---|---|
| 1 | A | joins; opens the recipe book | one "new recipes" toast; book lists planks, Poke Ball, Great Ball, a Handcrafted chair, Cobblemon's `bug_gem_block` (no unlock advancement of its own) |
| 2 | A | crafts oak planks, a Poke Ball, a Great Ball (apricorn), a Handcrafted oak chair, a CobbleFurnies or Cozy Home block at its own station | all craft |
| 3 | A | puts gold blank disc + rock gem + obsidian (Rock Tomb, badge 1) in a crafting table | **no result** |
| 4 | A | `advancement grant @s only cobblers:flag/gym1_cleared` (staging only), waits one second | Rock Tomb now crafts; Bubble Beam (badge 2) still does not |
| 5 | A | diamond disc + ground gem + crying obsidian (Earthquake, badge 8) | no result until `gym8_cleared` |
| 6 | A | picks a starter (Cobbleverse gives every recipe), waits one second | Earthquake still has no result |
| 7 | B | joins | keeps every ordinary recipe; Rock Tomb crafts; Thunder (badge 3) does not, even if it was in the book before |
| 8 | A, B | Crafter recipe (iron, redstone, crafting table, dropper) and Tom's crafting terminal | no result until `gym8_cleared` |
| 9 | A | a TMCraft TM into a Cobblemon TM (`to_cobblemon_tm_*`) | crafts (not gated) |
| 10 | A | smelts a TM into its legacy item | works (furnaces are never limited) |
| 11 | any | `/function cobblers:tm_gate/off` | `doLimitedCrafting` false; run before uninstalling |

## Record

Not run. Record each case's result, the server log lines of the boot (any `cobblers_tm_gate` parse error), and the
recipe count the toast of case 1 implies if visible.
