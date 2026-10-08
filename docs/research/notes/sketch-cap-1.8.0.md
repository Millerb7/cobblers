# Capping Sketch at 10 uses per Pokemon on Cobblemon 1.8.0

**Status:** research only (2026-10-08). Nothing built, no data changed. The owner decides.
**Follows:** `docs/research/notes/smeargle-protean-sketch-1.8.0.md` section 2, which says Sketch is unlimited.
**Read:** the snapshot jars in `C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/`, read-only:
`Cobblemon-fabric-1.8.0+1.21.1.jar` (Showdown paths are inside its `data/cobblemon/showdown.zip`) and
`mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar`. Kotlin "offsets" are `javap -c` bytecode offsets. Nothing
was run in game: every claim about behaviour below is from code, and is "not verified in game".

## Verdict

**Cheap: a datapack, no mod.** It sits on the datapack rung of principle 6. Use the Pokemon's own **Dynamax Level**
(`dmax_level`, 0 to 10) as the count of Sketches spent:

1. **Refuse:** a datapack file `data/<ns>/moves/sketch.js` replaces Showdown's Sketch. It is the stock move with one
   added guard: fail when `source.dynamaxLevel >= 10`.
2. **Count:** three Molang callbacks, also datapack files, add one to `dmax_level` after a battle in which Sketch
   was used.

The count lives on the Pokemon. It moves with the Pokemon through the PC, a trade, a restart and the re-export carry.
At the cap, Sketch stays in the move list, and using it shows "But it failed!". Ten is also the most this channel
can carry: the number reaching Showdown is clamped to 0..10.

Expected cost: one narrow builder, about **2.6M** (the move file, three callbacks, pack wiring, unit tests). Add an
independent audit at about **3M** if the owner wants one. One in-game experiment on staging, in the main session,
is what turns "from code" into "works". Total: about 3 to 6M plus that one staging session. No ADR is needed for a
datapack, but the shared Dynamax Level is a cross-system contract (see "Interactions").

## 1. Is there a uses-remaining concept? (VERIFIED: no)

- **PP:** Sketch is `pp: 1, noPPBoosts` (`showdown.zip:data/moves.js:17465-17512`). When Sketch goes to the bench it
  becomes a `BenchedMove`, which holds only `(MoveTemplate, ppRaisedStages)`: `Pokemon.exchangeMove` offsets 117-127
  build `new BenchedMove(template, raisedPpStages)`. Nothing counts uses.
- **`Pokemon.persistentData`** (a `CompoundTag`) exists. It is saved under the codec key `PersistentData`
  (`util/codec/internal/PokemonP2`), but the only classes that call `getPersistentData` are `Pokemon` and the
  codecs (grep over every class). No Molang function, command or Showdown field reaches it, so a datapack cannot
  use it.
- **Removing Sketch at the cap does not hold.** `Pokemon.getAllAccessibleMoves` is
  `form.moves.getLevelUpMovesUpTo(level)` plus `benchedMoves`, and Smeargle's learnset has `1:sketch`. Molang
  `unlearn_move` calls `Pokemon.unlearnMove`, which clears the move slot and the bench entry
  (`unlearnMove$lambda$0` and `$lambda$0$0`). Even so, Sketch can be put back from the summary screen. Making it
  disappear for good would mean removing `1:sketch` from Smeargle's species data. Then a new Smeargle has no
  level-up moves at all. That is rejected here.

## 2. Showdown can refuse a spent Sketch (VERIFIED)

**What reaches Showdown per Pokemon.** `BattleRegistry.packTeam` sends, in order:
- `showdownId`, `uuid`, current HP, status, held item, ability;
- moves and their PP, nature, EVs, gender, IVs;
- shiny, level, friendship, ball, Hidden Power type, `gmaxFactor`;
- **`dmaxLevel`**, written as the number when it is `< 10` and as empty at 10 (offsets 885-915: `bipush 10;
  if_icmpge`);
- tera type.

No aspects, no custom data. `sim/teams.js:242` unpacks it (`set.dynamaxLevel = misc[4] ? Number(misc[4]) : 10`),
and `sim/pokemon.js:118` sets `this.dynamaxLevel`, clamped to 0..10. Its only other reader is the Dynamax HP ratio
(`data/conditions.js:775`, `1.5 + dynamaxLevel * 0.05`).

**Why it is the right field:**
- A new Pokemon starts at 0. `Pokemon.dmaxLevel` has no initializer, and its only writer is `setDmaxLevel`, which
  clamps to `[0, config.maxDynamaxLevel]`.
- That config value is 10 in both `modpack/config/cobblemon/main.json:81` and the snapshot server's config.
- `PokemonProperties` reads and writes it as `dmax_level`: `commonApply` offset 1129 calls `setDmaxLevel`, and
  `commonMatches` offset 1500 reads it. So `/pokemonedit … dmax_level=N`, Molang `pokemon.apply('dmax_level=N')`
  and `pokemon.matches('dmax_level=N')` all reach it.
- The codec saves it under `DmaxLevel` (`PokemonP2`).

**A datapack can replace Showdown's Sketch:**
- `api/moves/Moves.reload` lists the `moves` resource folder for files ending in `.js` (`reload$lambda$1`). It
  keys each file by its name without the extension and calls `ShowdownService.sendRegistryData(map, "move")`.
  `getType` is `SERVER_DATA` (`class_3264.field_14190`), so the files come from datapacks.
- `GraalShowdownService.sendRegistryData` joins the files as `"key": value` with **every newline removed**
  (`Regex("[\r\n]+")`), then calls `receiveData`. That function `eval`s the result as an object
  (`showdown/index.js:75-89`) and registers each entry.
- `sim/dex-moves.js:173` looks in `Cobblemon.registries.move` **before** the base data, so a registered `sketch`
  wins for every dex.
- Cobblemon's jar ships no `data/*/moves/*.js`. The shipped `data/cobblemon/bag_items/*.js` use the same loose
  object form (`dire_hit.js`).
- **The trap in the format:** newlines are stripped, so a `//` comment comments out everything after it. The file
  must use `/* */` comments and explicit semicolons.

**The swap needs Showdown's message.** `ActivateInstruction.invoke` (offsets 106-301) calls `exchangeMove` only for
an `-activate` whose effect id is `sketch`, and Sketch's `onHit` sends that message only when it succeeds. A failed
Sketch therefore changes nothing on the real Pokemon. `exchangeMove` fires no event: its bytecode makes no
`CobblemonEvents` or callback call.

**The override** is the stock Sketch body (`moves.js:17465-17512`) with its first line inside `onHit` changed to
`if (source.dynamaxLevel >= 10) return false;`. A cap below 10 is the same line with a smaller number. A cap above
10 is impossible on this channel.

**Mega Showdown overwrites the running Showdown (a finding).** `mega_showdown/utils/ShowdownPatcher` copies 13 files
over `./showdown` while `showdownFilesLoading` is true, and the snapshot config has it true. The files are
`data/moves.js`, `sim/pokemon.js`, `sim/battle.js`, `index.js`, `data/mods/cobblemon/*.js` and others. So
`smeargle-protean-sketch-1.8.0.md` section 0 is incomplete. It changes nothing here:
- its Sketch (`assets/mega_showdown/showdown/moves.js:17489-17536`) is the same code;
- its `index.js:87-101` keeps `receiveData`;
- its `pokemon.js:118` keeps the `dynamaxLevel` line;
- it does not replace `sim/dex-moves.js`, so registry entries still win.

## 3. Counting after the battle (VERIFIED hooks; the Molang is ASSUMED until it runs)

Cobblemon runs every `data/<ns>/callbacks/<event>/*.molang` on its event (`events/CallbackHandler`). The repo
already uses `battle_victory` and `battle_fainted` this way (`tools/arena_runtime.py:1134`,
`tools/blackout_pack.py:1038`). There is **no move-learned, exchange or Sketch event**. The full list of event
names in `CallbackHandler` has none, so the count has to be inferred from the battle. One Smeargle can Sketch at
most once per battle: the copy replaces the Sketch slot (`moves.js` `onHit`), so each battle adds at most one.

- **`battle_started_post`** (context `battle, npcs, players, wild_pokemon`): for each `c.players` actor, look at
  `actor.player.party.get_pokemon(i)` for i 0 to 5 (`BattleActorMoLangFunctions` `player`, `PlayerMoLangFunctions`
  `party`, `PartyMoLangFunctions` `get_pokemon`). Take each Pokemon that `matches('moves=sketch')`. Properties
  matching reads `getMoveSet`, the active moves only (`commonMatches` offsets 1775-1946). Mark it with
  `add_aspects('cobblers_sketch_armed')`. That writes `forcedAspects`, which are saved (`PokemonP3`
  `ForcedAspects`).
  Before re-arming, settle any mark left behind (below), so a battle that ended without a callback is still counted.
- **`battle_victory`** (context includes `players`, `player_winners`, `player_losers`) and **`battle_fled`**
  (`players`): for each armed party Pokemon, remove the mark. If it no longer `matches('moves=sketch')`, Sketch was
  used: read n with `matches('dmax_level=n')` and `apply('dmax_level=' + (n+1))`. At 10, `player.tell` a line such
  as "Smeargle's brush is worn out".
- Battles that write nothing to the real Pokemon are counted correctly as no use. That covers a cloned RCT team or a
  level-adjusted PvP battle: Sketch stays in the real moveset.

ASSUMED, for the experiment: the exact Molang syntax; that `c.players` holds every player actor on both sides; and
that a disconnect or forfeit ends in `battle_victory`. The leak case: a battle that ends with no callback
(`/stopbattle`, a crash), after which the player re-slots Sketch from the summary before the next battle. That
Sketch goes uncounted. Rare, and in the player's favour.

## 4. Survival (VERIFIED from code unless marked)

| Path | Count (`DmaxLevel`) | Showdown override |
|---|---|---|
| PC | Stored with the Pokemon (`PokemonP2`) | datapack |
| Trade | `TradeManager.performTrade` removes the same `Pokemon` object from one party and adds it to the other (offsets 264-432), so every field goes with it. A traded Smeargle keeps its count. | datapack |
| Restart | Saved field | Reloaded on every datapack load (`Moves.reload`) |
| Re-export | `tools/carry_players.py:20,72` carries `pokemon/**/*`, the party and PC stores. | Must be installed in the new world's datapacks; `install_check` covers it. |
| Breeding | An egg is a new Pokemon with count 0 (ASSUMED for Cobbreeding) | |

## 5. What the player sees

- **Below the cap:** nothing changes until the 10th copy.
- **At the cap:** Sketch stays in the move list and can still be chosen. Using it spends its 1 PP and shows the
  generic "But it failed!". `FailInstruction` has no Sketch-specific text, and Cobblemon has no instruction for
  `-message` or `-hint`.
- **Seeing the count:** there are two ways.
  - Mega Showdown already shows a "Dynamax Level" bar in the Stats tab while `dynamax` is on. Its
    `DynamaxLevelHandler` registers an int species feature `dynamax_level` that mirrors `dmaxLevel`, with
    `setVisible(MegaShowdownConfig.dynamax)`. The snapshot has it on. The bar is the count, under the wrong label.
  - Or a Smeargle-only integer feature, `data/<ns>/species_features/sketch_uses.json` plus a
    `species_feature_assignments` entry for `smeargle`, written by the same callback. `blocks_traveled.json` in
    the jar is the template. It needs a client lang key.

## 6. Interactions and edge cases

- **Mega Showdown's Dynamax Candy** (`item/custom/dynamax/DynamaxCandy`: `setDmaxLevel(getDmaxLevel() + 1)`, plus a
  `dynamax_candy_max` variant) adds to the count. That only spends the player's own Sketches. Nothing a player can
  reach lowers it; `/pokemonedit` is for operators. Whether the candy can be obtained here was not checked.
- **If Dynamax is kept** (Q6, `docs/mechanics/ITEM_ROUTES.md:177`), a Dynamaxed Smeargle gets 1.5x to 2.0x HP as
  its count rises. That is negligible. If Dynamax is turned off, the mechanism still works: `dmaxLevel` is core
  Cobblemon and is packed regardless. Only Mega Showdown's bar disappears.
- **Pin the config:** if `maxDynamaxLevel` is ever lowered below 10, `setDmaxLevel` clamps the count and the cap is
  never reached. A test should assert it is 10.
- **Co-op:** a friendly PvP battle without level adjustment writes the copy and counts it, for both players'
  Smeargles. An NPC trainer's Smeargle starts at 0 each time and is never counted.

## 7. Ruled out

| Mechanism | Why |
|---|---|
| Aspect counter read by Showdown | Aspects are not in the packed team (`packTeam`). Aspects work only as the Cobblemon-side marker. |
| Held-item gate | It reaches Showdown, but it is a gate the player controls, not a count. |
| Count kept in Showdown keyed by UUID | The UUID is packed, but the Graal JS heap is lost on a restart and on `/reloadshowdown`. Persisting it from JS would mean file IO from the battle engine. Not pursued. |
| `Pokemon.persistentData` | No datapack or command access (section 1). |
| Player or server Molang `data` keyed by the Pokemon's UUID | It would work for counting, but Showdown cannot see it. The player's own data also stays with the old owner on a trade. `playermolangdata` is carried, but marked not required (`carry_players.py:25`). |
| A custom Fabric mod | Not needed. |

## Repository disagreements found

- `smeargle-protean-sketch-1.8.0.md` section 0 says battles run the `showdown.zip` copy. Mega Showdown's
  `ShowdownPatcher` overwrites 13 of its files at startup (section 2 above). The Sketch and Protean conclusions
  still hold: the code is the same.
