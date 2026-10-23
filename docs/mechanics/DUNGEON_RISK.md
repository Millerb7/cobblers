# Dungeon risk: the Run Stash, the Run Satchel, the exit's sale, the catch ledger

**Status: BUILT 2026-10-23 (`tools/dungeon_risk.py`, `data/dungeon_risk.json`, generated into the `cobblers_dungeons`
pack), NOT RUN IN GAME.** Catch REMOVAL is written and OFF: `catches.mode` is `dry_run`, which logs what it would take
and takes nothing. Proof plan: `experiments/EXP-098-dungeon-risk/README.md`.

## 1. The owner's rule

- 2026-10-23: "keep relics, i think theeasiest soluton would be some held item that would open a chest somehwere and
  show the collected itme to player, also it would be good to offer teh player a way to sell everything for money, so
  dungeons can be lucrative."
- 2026-10-23: "for the pokemon caught, we just log each one and then can remove it later, surely pokemon in the game have
  an unique id of some sort. or i guess we would just look at most recently added to the box somehow."
- Earlier: "everything you get should be risked, except cool catches" (shinies and the dungeon's reward Pokemon are
  kept); mini-bosses are losable.
- 2026-10-23 (relayed by the coordinator): "okay just choose best option and build it all, people might play tonight".
  Removal stays a dry run tonight.

So: **everything found in a run is at risk until a clean exit**, except relics (kept), shinies and a dungeon's prize
species (kept). A death, the timer or any other end costs the stash and the run's catches. "Most recently added to the
box" is rejected: a recency guess removes the wrong Pokemon when a gift, an egg or a trade lands in between
(`docs/research/notes/dungeon-catches-on-the-clock.md` approach C). Every removal here is by UUID.

## 2. Mechanisms, rung by rung (CLAUDE.md principle 6)

| Need | Rung used | Why the earlier rungs do not do it | Source |
|---|---|---|---|
| Hold a run's items away from the inventory | **datapack + commands**: command storage `cobblers:dg_risk s.p<dg.id>` | No Cobblemon or installed-mod store holds arbitrary items per player by command. The vanilla ender chest is per player but already holds the player's own things, so clearing it on death would destroy them | `tools/blackout_pack.py:700-717` (the recovery ledger keeps items in storage and gives them back by macro summon, the same shape) |
| Catch loose items before pickup | per-tick sweep of `minecraft:item` near a live member | an item entity is the only form a block drop, a wild Pokemon's on-entity drop (`modpack/config/cobblemon/main.json:6` `"defaultDropItemMethod": "on-entity"`) and a fished item have; nothing intercepts a pickup | 1.21.1 jar, ItemEntity (`cjh`): saved keys `Age`, `Health`, `Item`, `Owner`, `PickupDelay`, `Thrower` (VERIFIED, `javap`) |
| Catch chest and `loot give` items | a table-level `minecraft:set_custom_data {cobblers_dg_gain:1b}` on every dungeon loot table, and a per-tick move of every marked inventory stack | a chest's items go straight from its screen to the inventory; the mark makes them recognisable for the one tick before the sweep takes them | the dungeon tables are ours (`data/cobblers/loot_table/dungeons/**`, `tools/dungeon_puzzles.py:563`, `dungeon_extras.py:885`, `dungeon_resources.py:584`, `dungeon_extras2.py:672`) |
| Show the stash | **a vanilla wandering trader's trade screen** whose offers ARE the stash, each out of stock | see 2.2: nothing installed opens a container screen from an item or a command | Offers record shape: `tools/gulch_mine.py:1281-1291` |
| Open it from a held item | the `minecraft.used:minecraft.carrot_on_a_stick` statistic | Cobblemon 1.8.2's callback list (`events/CallbackHandler`) has `right_clicked_block` and `right_clicked_entity` and no item use | 1.21.1 jar, FoodOnAStickItem (`ctz`).use: when not riding a matching mount it calls `player.awardStat(Stats.ITEM_USED.get(this))` server-side and passes (VERIFIED, `javap`); the criterion form is EXP-073's `minecraft.mined:` form |
| The exit's choice | vanilla `/trigger` behind clickable chat | any player may run `/trigger` once the objective is enabled for them; no dialogue is open at the exit | vanilla |
| Sell | CobbleDollars' own `cobbledollars give` and `cobbledollars query`, at the bank's own unit prices | the Trading Post's sell-all (`tools/produce_buyer.py:570`) counts and clears the INVENTORY; the stash is in storage, so only its pay-and-verify step is reused | `tools/produce_buyer.py:456-469` (`pay_tail`), `tools/markets.py:536` (`bank_prices`) |
| Log a catch by its identity | Cobblemon's `pokemon_captured` MoLang callback, `q.pokemon.id` | n/a: native | 1.8.2 jar, `PokemonMoLangFunctions` `id` = `Pokemon.getUuid().toString()`, `is_shiny` = `Pokemon.getShiny()` (VERIFIED, `javap`) |
| Remove exactly that Pokemon | `runmolang` with `q.player.party.remove_by_id(uuid)` / `q.player.pc.remove_by_id(uuid)` | `takepokemon` and `pctake` are slot based (a slot is a guess) | 1.8.2 jar, `PokemonStoreMoLangFunctions`: `remove_by_id` parses the UUID, iterates the store for `Pokemon.getUuid()` equal to it, returns 0 when none, else `PokemonStore.remove`'s result; `find_by_id`, `pokemon` (each Pokemon as a struct), `count`; `PlayerMoLangFunctions` `party`, `pc`, `in_battle`, `uuid`; `PokemonMoLangFunctions` `held_item` (an ItemStack value), `ItemStackMoLangFunctions` `is_empty` (all VERIFIED as names, NOT RUN) |

### 2.1 What is risked, and how each source reaches the stash

| Source | Form | Reaches the stash by |
|---|---|---|
| Seam ores (the Rift Pick) | block drop item entity | the entity sweep |
| Vault, bank vault, resources cache chests | chest screen into the inventory | the mark, then the inventory sweep |
| Fossil bay (`loot give`) | straight into the inventory | the mark, then the inventory sweep |
| Wishing well, fishing room's treasure | fished item entity | the entity sweep (and the mark) |
| Wild Pokemon drops | on-entity item entity | the entity sweep, if Cobblemon sets no `Owner` or `Thrower` on it (ASSUMED; EXP-098 step S3) |
| Relics | `give` | **never**: kept (owner). Skipped by its `cobblers_relic` key even if it overflows onto the ground |
| A Poke Ball on the ground | the player's own ball handed back by a throw that could not catch | **never**: kept (`#cobblemon:poke_balls`, the 1.8.2 jar's item tag); a ball from a chest is still risked (marked) |
| Eggs (the egg vendor, `givepokemonegg`) | an item straight into the inventory, unmarked | **not covered** (hole H1): kept |
| Pokemon caught | party or PC | the catch ledger (section 4), not the stash |

A player's own items are never taken: an item they drop has a `Thrower`; a `give` overflow (the pick, a refund, a
relic) and every delivery of ours has an `Owner`; both are skipped. `keepInventory` stays set by the blackout (contract
C24), so a death in the pocket drops nothing for the sweep to see.

### 2.2 Why a trade screen, and not a chest screen

The owner asked how vanilla servers show clickable item screens. They use server-side code (plugins, or mods with a
server GUI library); a datapack cannot open a screen. Searched (read-only, Python `zipfile` over the server's 102 jars in
`C:/Users/wnd/Documents/cobblers-local/server-mods-1.8.2/`, nested jars included): **no server GUI library** (no
`eu/pb4/sgui`, no SimpleGui); one nested `LibGui` (CottonMC), which is a Java library with no command; Sophisticated
Backpacks/Storage, Lootr, Tom's Storage and Iron Chests have command classes but none opens an arbitrary or per-player
inventory for a player. CobbleDollars' merchant screen sells from a shop and cannot show items as payment
(`data/bank.json` `exchanges.barter_answer`). A new GUI mod would need Java to drive it (the coordinator's condition for
falling back), so the vanilla merchant screen is the choice: **a real clickable item screen**, each stash item an
offer with its real tooltip, every offer out of stock (`uses` = `maxUses` = 1), so nothing can be taken from it. Using
the satchel summons the screen's merchant 1.6 blocks in front of the player (NoAI, Invulnerable, Silent,
PersistenceRequired, `DespawnDelay:0`, `DeathLootTable:"minecraft:empty"`, named "Run Satchel"); right-clicking it opens
the screen. It closes itself after `satchel.view.life_ticks` (20 s).

## 3. The stash's life

```
arrival     the Rift Pick and the Run Satchel (given together; taken back together)
threshold   risk/begin: an unanswered satchel from the last run is delivered first; the stash emptied; old catch entries dropped (kept)
run         every tick: marked inventory stacks and loose items near the member -> s.p<id> {items:[exact stacks], counts:[{id,n}]}
clean exit  dungeon pay -> risk/won: catches kept; "holds N stacks, the bank pays $X"; [Take it all] [Sell it all] [List it]
            no answer in exit.choice_ticks (60 s online): Take it all
any other   risk/forfeit (first line of m/end and slot/s<g>/end): the stash deleted, marked residue cleared, the catch reaper
```

- **Fungible stacks** (coal, raw ores, ingots, gems, ...: `stash.fungible`, all 64-stackers with no components) are kept
  as one count per id, so a seam does not become sixty entries; they come back in stacks of 64. Everything else is kept
  as the exact stack it was (all its components), minus the `cobblers_dg_gain` key, so a delivered coal stacks with any
  other coal.
- **Delivery** is an item entity at the player's feet with their `Owner`, `PickupDelay:0` and `Age:-32768` (never
  despawns): the blackout recovery's delivery form (`tools/blackout_pack.py:717`).
- **Sell** prices every stack the bank buys at its unit price times its count, adds `exit.bonus_pct_by_band[band]`
  (0..10%) and `exit.boss_bonus_pct` (5%) if the boss fell, pays once with `cobbledollars give`, and checks the balance
  rose by exactly that. Only then is what was sold removed; a failed pay delivers everything instead. What the bank does
  not buy is delivered either way. The bonus numbers are DESIGN values for `trainer-balance-designer`.

## 4. The catch ledger

- `pokemon_captured` (`data/cobblemon/callbacks/pokemon_captured/cobblers_dungeon_risk.molang`) calls `risk/catch` as
  the catcher with the Pokemon's UUID, species and shiny flag. Logged only when the catcher's clock runs (`dg.st` 3..4)
  and they hold the run tag. A shiny, or a species any of that dungeon's prizes can be at any band (rare, legendary, and
  the roster's spine boss: `tools/dungeon_prize.pool_at`), is **never logged**, so no removal can name it.
- Entry: `{pid, sp, sh, who: dg.id, run: dg.run, at: #up}` in `cobblers:dg_risk ledger`.
- Clean exit: the run's entries are dropped; the catches are the player's.
- Any other end: the run's entries (`who` and `run` both match) move to a work list and are looked up **by UUID** one at
  a time. Each result comes back through a queued command (`runmolang`'s nested commands are queued, EXP-022), is
  appended to `cobblers:dg_risk log` (the newest `catches.log_max`), told to the player, and starts the next.
  - `dry_run` (default): found in the party (1) or PC (2) is logged "would remove"; not found (0) is logged. Nothing is
    removed. The dry script reads only UUIDs.
  - `remove`: found, out of battle, holding no item, and (in the party) not the party's last Pokemon: `remove_by_id` from
    the store it is in (3, 4); otherwise kept and logged (5 holds an item, 6 in battle, 7 last in party, 8 the remove
    returned 0).
- **ASSUMED, the probe's first question (EXP-098 S14):** that `runmolang`'s runtime has `for_each` (the repo's proven
  uses are in callbacks: `tools/dungeon.py` `callback`), that a struct's `.id` compares with `==` against a string
  (`tools/entei_boss.py:684` compares species that way), and that `is_empty` returns 1 for an empty stack. If the first
  two fail, the reaper reports nothing and removes nothing.
- Every failure of the chain keeps: a callback that does not fire logs nothing; a script that dies stops the chain with
  the Pokemon untouched; an entry from an older run is dropped, not acted on; a traded, released or missing Pokemon is
  "not found".

## 5. State model and multiplayer

| State | Where | Key |
|---|---|---|
| the stash | storage `cobblers:dg_risk s.p<dg.id>` | the player's dungeon number, `dg.id` |
| waiting for the choice | `dg.rkw` 1 (2: a clean exit with nothing to choose, cleared by forfeit), `dg.rkt` ticks left | player |
| the bonus | `dg.rkb` percent, fixed at the exit | player |
| the choice | `dg.rkc` trigger | player |
| the satchel's use | `dg.rku` (`minecraft.used:minecraft.carrot_on_a_stick`) | player |
| a view | the merchant's `dg.rkv` (owner `dg.id`) and `dg.rkl` (ticks left) | entity |
| catch ledger, its log, the reaper's work | storage `ledger`, `log`, `lw.p<who>` | `who` + `run` |

- **Logout mid-run:** the stash and ledger persist in storage. The run's own rule decides the end (DUNGEONS.md 2.6);
  `m/end` runs as the player when they are back, so the reaper reaches their party and PC online.
- **Logout during the exit choice:** the 60 s count only runs online; it resumes on return and then delivers.
- **Death outside the pocket while choosing:** nothing changes; delivery is wherever they are when they choose.
- **A crash:** storage and the world save on the same schedule; an unresolved stash is deleted at the next threshold
  (the stake), an unresolved ledger entry is dropped (kept).
- **Co-op** (members_max is 1 today): each player's stash and ledger are their own. A loose item near two members goes
  to whichever member's sweep runs first; a viewer opened by one player could be clicked by another.

## 6. Holes left (not covered, each on the safe side unless marked)

- **H1** Eggs from the egg vendor (`givepokemonegg`) land in the inventory unmarked: kept. Owner call.
- **H2** An item on the cursor at the moment of a clean exit keeps its gain key (it no longer stacks with plain ones;
  harmless). On a death it is cleared with the rest.
- **H3** A wild Pokemon's drop is stashed only if Cobblemon gives it no `Owner`/`Thrower` (EXP-098 S3); otherwise kept.
- **H4** An item picked up from further than `stash.absorb_radius` (8) away is kept.
- **H5** A pay that succeeds but whose balance check fails pays AND delivers (generous, not lossy).
- **H6** Removal deletes nothing a player can get back; it stays off until EXP-098's removal steps pass.
- **H7** A catch made with party and PC both full is stored nowhere (Cobblemon ignores the failed add,
  `docs/research/notes/dungeon-catches-on-the-clock.md` section 2); it is logged and then "not found": nothing removed.
