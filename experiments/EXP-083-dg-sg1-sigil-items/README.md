# EXP-083: SG1, sigils: the clear takes one and nothing else; the recipe's result keeps its components; `recipe give` under `doLimitedCrafting`

**Status: RCON PART PASSED; owner part OPEN (2026-10-08).** Probe SG1 (new) of `docs/mechanics/DUNGEONS.md` section 14, pack
`cobblers_dg_probes`, staging only.

## Objective
Every rip takes a sigil at entry (7.4): a pottery sherd carrying `minecraft:custom_data {cobblers_dg_sigil:<band>}`,
crafted (shapeless), and the recipes given by a `minecraft:tick` advancement running `recipe give @s` because the server
runs `doLimitedCrafting` (F7). Three things are ASSUMED: the item-predicate form `clear @s
minecraft:miner_pottery_sherd[minecraft:custom_data~{cobblers_dg_sigil:1}] 1` (the R2 class: syntax unread); that the
recipe's result keeps its components (EXP-059 X3 crafted a Tower Ash, one case); and that the advancement makes the
recipe craftable for a player who was known to the server before the pack went in. SG1 settles all three, two of them
with no player.

## Success criteria
- RCON: the `clear` line parses ("No player was found" for an absent name, not a syntax error); `execute if items`
  with the predicate counts exactly 1 in a chest holding a band-1 sigil, a plain sherd, a same-item band-2-tagged sherd
  and a band-2 sigil; a crafter powered by redstone makes a Soot Sigil whose `data get` shows all four components.
- Owner: the `clear` takes one band-1 sigil and leaves the other three; the sigil cannot be crafted before the grant
  and can after it.

## Dependencies
Vanilla 1.21.1 item predicates, the Crafter block, recipes, advancements; `doLimitedCrafting` true on staging (read
in step 1).

## Implementation
`cobblers_dg_probes:sg1/*`; objectives `dpsg1.st`, `dpsg1.r`. Area x 4352..4607; pen at (4384, 96, -640): a stock chest
(4387, 96, -637), a crafter `orientation=east_up` (4381, 96, -637) with its output chest in front (4382, 96, -637),
and the redstone spot behind it (4380, 96, -637).
- Recipes `cobblers_dg_probes:sg1_band1` (3 iron ingots + 3 coal -> `miner_pottery_sherd`) and `sg1_band2` (1 gold +
  4 iron + 2 redstone -> `prize_pottery_sherd`), each result with `custom_data`, `item_name`, two `lore` lines and
  rarity `rare` (7.4's text).
- Advancements `sg1/opt` (impossible: the session grants it to the owner) and `sg1/sync` (`minecraft:tick` while
  holding `opt`; reward `sg1/recipes`: `recipe give @s` both). The opt-in keeps the probe from touching any other
  player on staging.
- `stock` (the four sherds into the stock chest), `count` (the predicate's count there), `craft` (the crafter's six
  inputs, a redstone block for 10 ticks), `give_owner` (the same four to the owner). Each component-syntax line sits
  in its own small function, so one that fails to parse is dropped alone and named in the boot log.

## Test instructions
### (a) RCON, no player
| # | Command | PASS | FAIL |
|---|---|---|---|
| 1 | `gamerule doLimitedCrafting` | `... is currently set to: true` | false: the F7 half of this probe tests nothing; record it |
| 2 | grep the boot log for `cobblers_dg_probes:sg1/` and for recipe or advancement errors naming `cobblers_dg_probes` | none | the named file's syntax is wrong (record the line) |
| 3 | `function cobblers_dg_probes:sg1/setup`; wait 15 s; `function cobblers_dg_probes:sg1/stock` | `returned 1` | |
| 4 | `clear NoDgProbe minecraft:miner_pottery_sherd[minecraft:custom_data~{cobblers_dg_sigil:1}] 1` | `No player was found` (the predicate parsed) | a syntax error pointing into the brackets |
| 5 | `execute in cobblers:pocket if items block 4387 96 -637 container.* minecraft:miner_pottery_sherd[minecraft:custom_data~{cobblers_dg_sigil:1}]` | `Test passed, count: 1` | count 2 or 3: the predicate also matches the plain sherd or the band-2 tag |
| 6 | `function cobblers_dg_probes:sg1/count` | `returned 1` | |
| 7 | `function cobblers_dg_probes:sg1/craft`; 2 s later `execute in cobblers:pocket run data get block 4382 96 -637 Items` | one `minecraft:miner_pottery_sherd` with `components` holding `"minecraft:custom_data":{cobblers_dg_sigil:1}`, `item_name` "Soot Sigil", two `lore` lines and `rarity` `"rare"` | empty: `execute in cobblers:pocket run data get block 4381 96 -637 Items` shows the inputs still there (no recipe matched, or the crafter did not fire); an item entity on the floor instead means it dropped rather than filled the chest (record it); a sherd without components fails the criterion |

### (b) The owner in game (he must have joined the server before the pack was installed)
| # | The owner does | The session runs | PASS |
|---|---|---|---|
| 1 | stands in the overworld | `execute as <owner> at @s run function cobblers_dg_probes:sg1/enter`, `execute as <owner> run function cobblers_dg_probes:sg1/give_owner` | four sherds in his inventory |
| 2 | | `clear <owner> minecraft:miner_pottery_sherd[minecraft:custom_data~{cobblers_dg_sigil:1}] 1` | `Removed 1 item(s) from player <owner>` |
| 3 | opens his inventory | `execute if items entity <owner> container.* minecraft:miner_pottery_sherd[minecraft:custom_data~{cobblers_dg_sigil:1}]` | `Test failed`; he still holds the plain miner sherd, the miner sherd tagged band 2, and the prize sherd tagged band 2 |
| 4 | gets 3 iron ingots and 3 coal (the session may `give` them), opens a crafting table and the recipe book, puts the six in the grid | | no Soot Sigil (the recipe is locked under `doLimitedCrafting`) |
| 5 | | `advancement grant <owner> only cobblers_dg_probes:sg1/opt`; then `execute if entity <owner>[advancements={cobblers_dg_probes:sg1/sync=true}]` | `Test passed` within a second (the tick advancement fired) |
| 6 | puts the six in the grid again | | a Soot Sigil appears; its tooltip shows the name in grey, the two lore lines, rare |
| 7 | | `recipe take <owner> cobblers_dg_probes:sg1_band1`, `recipe take <owner> cobblers_dg_probes:sg1_band2`, `advancement revoke <owner> only cobblers_dg_probes:sg1/sync`, `advancement revoke <owner> only cobblers_dg_probes:sg1/opt`, `execute as <owner> run function cobblers_dg_probes:sg1/leave`, `function cobblers_dg_probes:sg1/cleanup` | |

## Results

### RCON, no player (2026-10-08, main session)

Run 2026-10-08 22:46-22:58 by the main session over RCON, staging-2026-10-01 (staging only), pack `cobblers_dg_probes` from `tools/dungeon_probes.py` (installed by hand, plain restart, no /reload), no player online. Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0+1.21.1, rctmod 0.19.0-beta / rctapi 0.16.1-beta, Mega Showdown 1.0.2, the server's full mod set (MobsBeGone 0.0.7 among it), Java 21, -Xmx16G.

| Step | Reading |
|---|---|
| 1 | `doLimitedCrafting` true |
| 2 | no load error for `cobblers_dg_probes:sg1/` or for any recipe or advancement of the pack in the boot log |
| 3 | `sg1/stock` returned 1 |
| 4 | **as written the step cannot pass**: `NoSuchPlayerDgProbe` is 19 characters, so it fails "Invalid name or UUID" (a name over 16). With `NoDgProbe`: **"No player was found": the predicate parsed: PASS**; a control with the brace missing fails "Expected '}'" |
| 5 | `execute if items block ... container.* ...[minecraft:custom_data~{cobblers_dg_sigil:1}]`: `count: 1` (not the plain sherd, not band 2): **PASS** |
| 6 | `sg1/count` returned 1 |
| 7 | **a Crafter crafted the Soot Sigil with no player**: one `minecraft:miner_pottery_sherd` with `custom_data {cobblers_dg_sigil: 1b}`, `item_name` "Soot Sigil", two `lore` lines and `rarity` "rare"; the input chest emptied: **PASS** |

The `recipe give` / `doLimitedCrafting` half (F7) needs the owner. The builder notes the TM gate's sync runs
`recipe give @s *` for new or re-keyed players, which unlocks the sigil recipes too.

## Limitations
- While installed the recipes exist for every player on staging; `doLimitedCrafting` keeps them locked except for whoever
  is granted `opt`, and a crafter block crafts them for anyone (the crafter ignores the gamerule).
- **The TM gate interacts** (`tools/tm_gate.py`, read 2026-10-08): its `sync` runs `recipe give @s *` once for every
  player whose `cobblers.tmgate` score is not the current plan's key, then takes back the badge-gated TMs. A player
  synced before this pack went in keeps the old key and does NOT get the sigil recipes (the F7 case this probe runs);
  a new player, or everyone after the TM plan's key changes, DOES get them from the TM gate, sigils included, with no
  dungeon advancement. If (b) step 4 already shows the sigil craftable, check `scoreboard players get <owner>
  cobblers.tmgate` and record that the TM gate's sync re-ran. The TM gate also closes the Crafter's own recipe for
  players (it never asks the recipe book); this probe places one by `setblock`, which that does not touch.
- Bands 1 and 2 only; the other four sherd ids are not checked here (the validator's job, 7.4).
- The free first entry, the threshold refund loot table, and `door_click`'s band choice are engine pieces, not probed.

## Decision
Gates the sigil step of `door_click` (7.4) and the recipes' delivery. Step (a) 4-5 FAIL: the sigil step counts and
takes by `execute if items` per slot and `item replace ... with air` on the first matching slot (one function per
slot), never by `clear` with a predicate. Step (a) 7 FAIL: the recipe gives a plain sherd and the sigil is made by a
crafting-advancement that swaps it for the full item, re-probed. Step (b) 6 FAIL: the dungeon pack gives the recipes
from its keeper's first pass that finds a player, not from an advancement.

## Follow-up
V16 (the validator) for the six sherd ids and the bank's reach.

### Added 2026-10-08 (main session, RCON, same server): the predicate's TYPE matters

The crafted Soot Sigil stores `cobblers_dg_sigil: 1b` (a byte, from the recipe's result); the hand-stocked chest's
holds `1` (an int). On the crafted one in the output chest (4382, 96, -637):
`...[minecraft:custom_data~{cobblers_dg_sigil:1}]` **Test failed**; `...[minecraft:custom_data~{cobblers_dg_sigil:1b}]`
**Test passed, count: 1**. Partial NBT matching compares tag types, so step 5's PASS above held only for the int stock.
**Every predicate against a crafted sigil must use the byte form** (the engine, `tools/dungeon.py`, does).
