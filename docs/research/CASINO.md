# The casino: what is actually possible

Research only; nothing is built. The owner's request (2026-09-27): a Game Corner in Sabrina's town near the
department store, with coins, machines that pay out and a prize counter, and an honest answer if that cannot be done.

Versions: Minecraft 1.21.1 Fabric, Cobblemon 1.8.0 (`Cobblemon-fabric-1.8.0+1.21.1.jar`), CobbleDollars 2.0.0 Beta 5.1,
rctmod 0.19.0-beta, as installed in the server's `mods/` folder (102 jars, read 2026-09-27). Labels follow
`.claude/rules/research.md`: **VERIFIED** means seen in a jar, a repo experiment, or an official page for this version;
**ASSUMED** means inferred and not yet run.

## The answer in brief

- **A real Game Corner is possible without a new mod.** Every part except the combination is already proven here
  or is plain vanilla. The combination is not proven, so it needs one experiment first (EXP-043, below).
- **CobbleDollars read-and-charge is enough on the money side.** It is a complete per-player debit:
  - query the balance, check it, remove the price, re-query to confirm;
  - one function, one tick, nothing interleaved.

  The coins themselves are best kept as a scoreboard score, which is per-player and persistent.
- **The wall the owner describes is per-player *stock*, not per-player *payment*.** A villager or CobbleMerchant
  shows every player the same offers. A counter run by dialogue plus functions can show and sell different things to
  different players, gated by their badge flags.
- **A machine can take a bet, roll and pay per player.** The pieces:
  - a button, detected with vanilla `any_block_use` (the healing-machine checkpoint proves this trigger in game);
  - a reward function running as that player;
  - `random value` for each reel;
  - the payout, decided at the click and revealed about 2 s later.

  Concurrency is safe with one machine lock and per-player state. Details are in section 2.
- **Nothing installed offers gambling.** Four Cobblemon casino mods exist on Modrinth. One, Cobblemon MiniGames,
  has a Cobblemon 1.8.0 build published 2026-09-26: slots, Voltorb Flip, a Coin Case and a prize shop. It is the
  richest option, and it is a new client-and-server dependency with an All Rights Reserved licence.
- **Recommendation:** build the Game Corner as a datapack: coins bought at a counter, 6 slot machines, a
  badge-gated prize counter. Prove it first with EXP-043: one machine, one counter, on staging. Keep the addon as the
  upgrade path if the owner wants arcade games the datapack cannot do.

## 1. Currency: is CobbleDollars read-and-charge enough?

### What is already proven

| Fact | Label | Source |
|---|---|---|
| A function reads a player's balance: `execute store result ... run cobbledollars query <player>` stored 712 | VERIFIED | `experiments/EXP-040-cobbledollars-transaction/README.md:13-15` |
| A function removes an amount by macro, `$cobbledollars remove @s $(amount)`; in game it charged $73 of $725, then $59 of $586, once each | VERIFIED | `tools/blackout_pack.py:220-229`; `experiments/EXP-042-blackout-and-water-ladder/README.md:67,91` |
| The command tree: `query`, `give`/`add`, `remove`/`subtract`, `set`, `pay`, `leaderboard` | VERIFIED | `EXP-040 README:11`, from `CobbleDollarsCommand` |
| Only `pay` has a failure text ("Not enough CobbleDollars"); `remove` has none. So `remove` probably does not refuse a short balance: it clamps, goes negative, or silently removes less | VERIFIED text, ASSUMED behaviour | `assets/cobbledollars/lang/en_us.json` in the jar |
| One function runs to completion inside a tick on the server thread; no other player's function interleaves; there is no rollback | VERIFIED (reasoned from the runtime, and held in EXP-042) | `EXP-040 README:20-27` |
| CobbleDollars saves player data on its own timer (`playerDataSaveFrequency: 15`, unit not read) | VERIFIED value, ASSUMED meaning | `base-pack/cobbleverse/config/cobbledollars/common.json:5` |

So a coin purchase is: query into a score; if the balance is at least the price, `cobbledollars remove @s <price>`
(a literal, no macro needed); query again; only if the new balance is exactly `old - price`, add the coins. That is
the EXP-040 ordered-transaction pattern with the check the charge path already uses. **Yes, it is enough.**

### Where the coins live

| Store | Per-player | Survives restart | Survives re-export | Can be duplicated or forged | Visible to the player | Verdict |
|---|---|---|---|---|---|---|
| **Scoreboard score** (`gc.coins`) | yes, keyed by player name | yes, `data/scoreboard.dat` | only if carried: `carry_players.py` carries `scoreboard.dat` as **optional** (`tools/carry_players.py:81`) | no: no item exists to dupe, drop or trade | on demand (below) | **recommended** |
| A custom coin item (e.g. a gold nugget with `custom_data`) | yes | yes, in `playerdata` | yes, required category (`carry_players.py:66`) | exposed to any item dupe in 138 mods; tradeable between players | always, in the inventory | workable second choice |
| `cobblemon:relic_coin` | yes | yes | yes | the CobbleDollars bank **buys it at $50** (`bank.json:16`), and it feeds Gimmighoul's 999-coin evolution to Gholdengo (jar `species_features/gimmighoul_coins.json`) | always | **reject**: a coin price under $50 is a money printer, and the casino would become the Gholdengo shop |
| A `trigger` objective | yes | yes | as a score | **a player can `/trigger <obj> set 99999`** at permission 0 | yes | never as the store |
| Command storage | no natural per-player key | yes | **not carried at all** | n/a | n/a | no |

- **Scores are per-player and persistent.** VERIFIED: https://minecraft.wiki/w/Scoreboard (32-bit ints, `scoreboard.dat`); the
  blackout pack keeps its own per-player state this way.
- **Scores are keyed by player name, not UUID.** A renamed account loses its coins. ASSUMED from the wiki's "identified by
  username"; on a friends' server this is an admin fix, not a design problem.
- **Finding:** before coins exist, `scoreboard.dat` should become a **required** carry category. The blackout pack's
  checkpoints and counters are already scores (`tools/blackout_pack.py` `OBJECTIVES`).
- **A second finding outside this topic:** `storage cobblers:recovery claims` (the blackout claim ledger) lives in
  command storage. `carry_players.py` does not carry command storage, so a re-export drops open claims. STATE.md:109
  already lists "re-export carry of the claim ledger" as open; this is the file-level reason.

### Showing the coins

- **Action bar or chat on every coin event.** VERIFIED pattern: the blackout pack's `tellraw` with a
  `{"score":{"name":"@s","objective":...}}` component printed "Lost $73" in game (`tools/blackout_pack.py:245`,
  `EXP-042 README:67`); its action-bar checkpoint message was seen (`EXP-042 README:85`).
- **A "check coins" command for non-operators:** a `trigger` objective `gc.show`, enabled for every player, whose only
  effect is to print the score. VERIFIED vanilla: https://minecraft.wiki/w/Commands/trigger (permission 0, disabled after
  use, so re-enable it each time). The trigger value is read and discarded, never trusted.
- **A Coin Case item whose lore shows the balance** (`item modify` with `set_lore` resolving a score component):
  possible, ASSUMED, and it goes stale the moment another function changes the score. Skip it; the action bar is
  enough.
- **Not the sidebar:** the sidebar shows every player's score to everyone (team sidebars per colour are a hack).

### Exploits and their guards

| Exploit | Guard |
|---|---|
| Buy coins with a balance too small (`remove` may not refuse) | query first; refuse below the price; re-query after and add coins only if the drop is exact |
| Cash coins back out, looping odds or prices into money | **no cash-out**, as in the Kanto games; coins only buy prizes |
| Coin as item gets duped or dropped | coins are a score |
| Relic-coin arbitrage | do not use relic coins |
| Trigger objective abuse | the trigger only prints; it never writes coins |
| A crash between the CobbleDollars save and the world save: dollars roll back, coins stay, or the reverse | small window on a friends' server; CobbleDollars saves on its own timer, the scoreboard on world save. Accept, or save with `save-all` after each purchase (ASSUMED to flush both; not checked) |
| Holding coins across a re-export | make `scoreboard.dat` a required carry |
| Score overflow | cap at 99,999 coins; refuse a purchase above the cap |

## 2. A machine that takes a bet, rolls and pays out

### The mechanism, step by step

1. **The control.** Each machine has one button (a reserved type, say `minecraft:polished_blackstone_button`, used
   nowhere else in the town) and a vanilla `marker` entity tagged `gc.machine` carrying the machine number.
2. **Detection.** There is one advancement per machine, `cobblers:casino/machine_<n>`:
   - `minecraft:any_block_use`, with a `location_check` on that block type at that button's position;
   - the reward function is `casino/spin_<n>`.

   The trigger and a block-type filter are VERIFIED in game: the healing-machine checkpoint fired on use
   (`tools/blackout_pack.py:139-142`, `EXP-042 README:85`). A button press is a "default use action" that fires the
   trigger (https://minecraft.wiki/w/Advancement_definition).

   The position filter is ASSUMED. The wiki says the location is the block's centre, so the predicate uses a range
   `{"min": X, "max": X + 0.99}` on each axis, which matches whether the game reports the corner or the centre.
3. **The reward function runs as the clicking player.** VERIFIED: the healer's reward function acts on `@s` and
   saves where that player stood (`tools/blackout_pack.py:255-257`). First line: `advancement revoke @s only
   cobblers:casino/machine_<n>`, the healer's pattern.
4. **Refusals, each with a message to that player only:**
   - the player is mid-spin (tag `gc.spinning`) or inside their cooldown (`gc.next` > game time);
   - the machine is locked (its marker's `gc.until` > game time): "This machine is in use.";
   - coins are below the bet.
5. **The bet.** Bet size is 1, 2 or 3 coins. The player sets it on a second button or lever beside the machine, the
   same detection, stored as `gc.bet` on the player. Subtract it from `gc.coins`.
6. **The roll.** `execute store result score @s gc.r1 run random value 0..19`, then the same for `gc.r2` and `gc.r3`.
   VERIFIED vanilla since 1.20.2, permission 0 without a sequence (https://minecraft.wiki/w/Commands/random); the blackout
   pack uses it in functions (`tools/blackout_pack.py:334,352`).
   - The payout is computed **now**, from the pay table below, into `gc.win` on the player.
   - Nothing about the result depends on anything that happens later, so there is no re-roll.
7. **Lock and schedule the reveal:**
   - the player: `gc.spinning`, `gc.done = now + 40`, `gc.next = now + 50`;
   - the machine marker: `gc.until = now + 50`, and the spinner's reel values copied to it for the display.
8. **The show.** Each machine has three `item_display` entities, one per reel.
   - While spinning, a per-tick loop cycles their item, or rotates them with `transformation` and
     `interpolation_duration` (VERIFIED feature since 1.19.4, https://minecraft.wiki/w/Display).
   - Reels stop left to right at +20, +30 and +40 ticks, each showing its symbol.
   - Sounds for the spinner: `playsound ... @s` for the clicks. The jackpot plays to `@a[distance=..12]`.
   - Display entities are **visible to everyone** (the wiki names no per-player visibility). That is a feature: the
     room sees the jackpot.
9. **The payout.** The tick loop runs `execute as @a[tag=gc.spinning] if score @s gc.done <= #now run function
   casino/reveal`. The reveal:
   - adds `gc.win × gc.bet` to `gc.coins`;
   - shows the result as a title or action bar to `@s`;
   - clears `gc.spinning`.

   It is **not** `schedule function`, which runs as the server with no player (ASSUMED from the command's
   definition; the blackout pack avoids it the same way with its `cobblers.bo_pending` tag,
   `tools/blackout_pack.py:164-166`).
10. **Unlock.** The tick loop frees any machine whose `gc.until` has passed, whoever spun it. A player who logs out
    mid-spin cannot hold a machine.

### The pay table (computed, not tuned in game)

One reel strip of 20 stops, the same on all three reels, each reel an independent `random value 0..19`:

| Symbol | Stops | Three in a row pays (per coin bet) |
|---|---:|---:|
| 7 | 1 | 300 |
| Porygon | 2 | 100 |
| Abra | 3 | 30 |
| Pikachu | 4 | 12 |
| Oran Berry | 4 | 1, 2 or 3 berries from the left: 2, 5, 10 |
| blank | 6 | 0 |

Exact return, enumerated over all 8,000 outcomes: **89.5% RTP** (a 10.5% house edge), a win on 21% of spins. The
jackpot is 1 in 8,000, the Porygon line 1 in 1,000.

### Is anything concurrency-unsafe?

| Situation | What happens | Label |
|---|---|---|
| Two players press two machines in the same tick | two advancements, two reward functions, run one after the other; each writes only its own scores and its own machine | VERIFIED model (EXP-040's one-function-per-tick rule); ASSUMED for this pack until run |
| Two players press the same machine in the same tick | the first run locks it; the second is refused with "in use" and loses nothing, because the check comes before the deduction | ASSUMED (follows from ordering) |
| Shared temporary values (`#tmp` fake players) | safe **within** a function; never carried across ticks. Everything that spans the 2-second spin lives on the player or the marker | design rule |
| One player spams the button (held right-click repeats about every 4 ticks) | `gc.spinning` and `gc.next` refuse everything until the reveal | ASSUMED |
| The player disconnects mid-spin | coins were already taken and the win decided. Tags and scores persist in their player data and the scoreboard. `@a` finds them again on login, so the payout lands then; the machine unlocks on its own timer | ASSUMED; test it |
| Server restart mid-spin | game time persists, so `gc.done` still compares correctly | ASSUMED |
| Re-export | markers, displays and buttons are world state: a record in `data/` and a `tools/reapply.py` step, as for the traders (R14). Coins survive only if `scoreboard.dat` is carried | VERIFIED constraint (ADR-002:51-58) |
| The reel display while two machines spin | each machine owns its three displays, and a lock means one spinner per machine | design rule |

**Verified versus assumed, in one line:** every individual command and trigger above is verified in this repo or is
documented vanilla. The per-machine position filter, the delayed reveal, the lock and the multiplayer behaviour are
not run; EXP-043 runs them.

## 3. What the pack and the ecosystem already offer

### In the installed pack: no gambling mechanism

- **Jar scan (2026-09-27).** All 102 jars in the server's `mods/` folder were scanned for entry names matching
  casino, slot machine, lottery, gamble, jackpot, roulette, arcade, game corner, scratch, coin case, prize, Voltorb
  Flip and minigame.
- **What matched:** only unrelated names (the move Scratch, Charcadet, TMCraft's scratch TMs, a Showdown chat plugin)
  and rctmod's **Gambler** trainer class.
- **The Cobbleverse inventory** (`base-pack/inventory/mod_inventory.json`, 138 entries) lists no minigame or casino
  mod.
- **No structure template.** `docs/world-building/STRUCTURE_INVENTORY.md:600` already records "Game Corner" among
  the civic buildings missing entirely.

Useful pieces that are installed (all VERIFIED from the jars or configs):

| Piece | What it gives | Source |
|---|---|---|
| **CobbleMerchant shops** (CobbleDollars) | a per-entity item shop priced in CobbleDollars. Each player pays from their own balance, but every player sees the same offers. Editable by `/cobbledollars cobblemerchant add item`. Our Mart clerks already use it (`traders.py verify` reads `CobbleMerchantShop`) | `fr/harmex/cobbledollars/.../CobbleMerchant.class`, lang `command.cobbledollars.cobblemerchant.*`; `tools/traders.py:359` |
| **The CobbleDollars Bank** | sells items back for dollars, including relic coins at $50 and pouches at $475 | `base-pack/cobbleverse/config/cobbledollars/bank.json:15-24` |
| **Relic coins** (Cobblemon) | a coin item from ruin loot; 999 of them evolve Gimmighoul. Our world has no ruins, so it has no source today | Cobblemon jar `species_features/gimmighoul_coins.json`; `docs/world-building/STRUCTURE_DECISIONS.md:80` |
| **rctmod Gambler trainers** | 10 trainer definitions with textures (`gambler_*`), an optional group. Casino regulars to battle | `rctmod-fabric-1.21.1-0.19.0-beta.jar` `data/rctmod/trainers/gambler_*.json` |
| **`pokegive` / `givepokemon`** | a Pokemon prize, given by command | `GivePokemon.class` literals `pokegive`, `givepokemon`, `pokegiveother`. Used by hand in `EXP-013/SESSION-DE.md:172`; from a function it is ASSUMED |
| **Cobblemon dialogue running server commands** | a per-player counter: options run `execute as <uuid> at @s run function ...` | `tools/compile_dialogue.py:72-73,165-167`; single-player proof EXP-022 |

**One EXP-022 finding shapes the counter.** A command from dialogue is queued (EXP-022 README:35), so the
conversation cannot branch on whether the purchase worked. The function tells the player ("Not enough coins")
itself.

### Vanilla 1.21.1 mechanisms that fit

| Mechanism | Per-player? | Use | Label |
|---|---|---|---|
| **Vault block** | yes: each player unlocks a given vault **once**; it remembers 128 UUIDs; the key is consumed and random loot is ejected with particles | a scratch card: a paid key opens a vault that shows cycling prizes and spits one out. Once per player per vault, unless a function clears `server_data.rewarded_players` (daily, for everyone) | VERIFIED behaviour (https://minecraft.wiki/w/Vault); clearing by `data modify block` and key matching by components are ASSUMED |
| **Villager or wandering-trader trades** | the purchase is per player | a prize counter paid in a coin *item*: `buy` accepts `components` such as `custom_data`. Set `priceMultiplier: 0` and huge `maxUses`. Hero of the Village still discounts (it ignores the multiplier) | https://minecraftcommands.github.io/wiki/questions/shop.html, https://minecraft.wiki/w/Trading; not run here |
| **Advancement triggers** | yes | `any_block_use` for buttons (VERIFIED in game); `player_interacted_with_entity` for `interaction` entities (built in `tools/scenes_pack.py:312`, never clicked in game: STATE.md:39) | as stated |
| **`trigger` objectives** | yes | the "coins?" command | VERIFIED vanilla |
| **Display entities** | no, visible to all | reels | VERIFIED vanilla |

### Cobblemon casino mods on Modrinth (none installed)

| Mod | Latest for 1.21.1 | Cobblemon 1.8? | Currency | Licence | Fit |
|---|---|---|---|---|---|
| **Cobblemon MiniGames** (`cobblemon-minigames`) | 4.1.0+cobblemon1.8.0, 2026-09-26; 42 versions | **a 1.8.0 build exists** (deps: Cobblemon, Architectury) | its own Arcade Coins, stored in a Coin Case item; no economy integration; `/cobblemonminigames givecoins` at permission 2 | All Rights Reserved | the full Game Corner: slots, roulette, Voltorb Flip, blackjack, derby, pinball, a YAML prize shop that can sell Pokemon, gacha. Every game is a GUI screen |
| **Casino Rocket** (`casino-rocket`) | 1.0.0, 2025-12-31; one version | built against **Cobblemon 1.6.1**; NEEDS BOOT TEST, and likely stale | CobbleDollars (Beta 5.1, our version) buys chips | MIT | slots, blackjack, gacha, casino villagers |
| **Cobble Casino** (`cobble-casino`) | 1.0.16, 2026-08-23 | not stated | wagers **CobbleDollars** directly; slots at 98.5% RTP, blackjack | MIT | a Casino Rocket fork: slots only, no prize counter |
| **Cobblemon Gamble** (`cobblegamble`) | 3.2.0, 2026-09-01 | not stated | wagers **CobbleDollars** (chips 1k-1M) | MIT | poker, roulette, crash, plinko, keno, coin flip, races, player-versus-player tables |
| **CobbleCasino** (`cobblecasino`) | 2026-09-07 | not stated | CrzCoin (another economy mod) | MIT | slots, blackjack, gacha |

Sources: `https://api.modrinth.com/v2/project/<slug>` and `/version` for each, read 2026-09-27. None is in the pack,
so each is `UNKNOWN` against our mod set until a boot test.

What Cobblemon MiniGames would mean, from its own description (ASSUMED until run):
- **It fits:** coins, machines and a counter that sells Pokemon, all built in.
- **It needs taming by config:**
  - the skill games (Flappy Bird, Snake, Block Stacker) pay "score × multiplier" coins, so coins can be farmed with
    no buy-in;
  - `arcadeCoinCrafting` is a recipe switch;
  - the gacha "personalises" Pokemon pools per player, bypassing the campaign's encounter design;
  - all three would be switched off, and coins sold only through our CobbleDollars counter calling `givecoins`.
- **It is a client-required dependency** that every player installs (principles 9 and 12).
- **The licence is All Rights Reserved.** It is fine to run locally; it cannot be committed.
- **Its churn is fast:** 4.0.0 to 4.1.0 in two weeks, with a multiplayer shop crash fixed in 4.0.1.
- **Prizes and badge gating** would be the mod's shop, not ours.

## 4. The honest options, compared

| Option | What the player gets | Cost | Proven | Not proven | Risks |
|---|---|---|---|---|---|
| **A. Full Game Corner, datapack** (coins, 6 slot machines, prize counter) | buy coins with dollars; slots that pay; a counter with Pokemon, TMs and held items, gated by badge | Medium. One generated pack like `blackout_pack.py`, a building, a counter NPC, a `reapply.py` step for markers and displays | charge (EXP-042), balance read (EXP-040), `any_block_use` (EXP-042), per-player dialogue with commands (EXP-022), badge flags (EXP-027), score messages (EXP-042) | per-machine position filter, delayed reveal, lock, reel display, `pokegive` from a function, two players at once | two-player tests are blocked on a second account (STATE.md:248); the display is text and item displays, not a GUI |
| **A+. Full Game Corner, Cobblemon MiniGames** | real GUI slots, Voltorb Flip, a Coin Case, a mod shop | Medium-high: a new client+server dependency, config lockdown, the dollar bridge | nothing in our set | the boot on our 1.8.0 mod set, config lockdown, `givecoins` from a function, multiplayer | ARR, fast churn, farmable skill games, its gacha against the encounter design |
| **B. Prize counter only** | a shop of prizes priced in dollars or in coins bought at the same counter | Low. A dialogue counter, or a CobbleMerchant (items only, same offers for everyone) | the CobbleMerchant shop (13 Mart clerks on staging); the dialogue counter's parts | dialogue gating per badge for this counter | it is a shop with a sign; no chance, so no casino |
| **C. Scratch cards** (vaults, or a card resolved at the counter) | buy a card, watch a vault cycle and eject a random prize | Low-medium: a loot table per tier, vault blocks re-applied | the vault's per-player memory (vanilla) | key matching with `custom_data`; resetting `rewarded_players`; Pokemon prizes need a voucher item | once per vault per player; ejected items can be picked up by anyone nearby |
| **D. Battle arcade** (Battle Tower style) | win streaks against trainers for points | High: random teams per round, level normalisation, streak state | rctmod trainers stand and battle (STATE.md:29) | per-round team rotation. Cobblemon 1.8 NPC `party_pools` are named in CLAUDE.md but unexplored | rctmod forgets wins and never refuses a placed trainer's rematch (STATE.md:15); the dojo already fills the "battle building" role (`gym6_dojo`) |
| **E. Decorative only** | slot-machine props | Low | n/a | n/a | the owner's words: "not a casino" |

## 5. Proposal

### What to build

**A Game Corner, option A**, with three rooms:

- **The coin counter.** A dialogue NPC. The options:
  - "50 coins for $500" and "500 coins for $5,000", each running the checked purchase;
  - "How many coins do I have?"
- **The floor.** Six slot machines, so a group of four never waits. Each has a spin button, a bet lever and three
  reel displays. Two Gambler trainers (rctmod) stand at the machines as battlers.
- **The prize counter.** A second dialogue NPC. Its options appear by badge flag, `q.player` data or
  `advancements={cobblers:flag/gym6_cleared=true}`. Each option runs one function:
  - check the coins;
  - deduct them;
  - `pokegive @s <species> level=<n>` or `give @s <item>`;
  - confirm.

Later, not in the prototype:
- Voltorb Flip as a single in-world 5x5 board with a per-player lock;
- a free **daily Lottery** at the counter: once per in-game day per player, keyed on `time query day`.

### Where

**Recommended: its own building, west of the grand axis at the lake end, facing east across the axis to the
department store's fountain garden.**

- **The lots.** It takes lots `lake_street_lot_31` and `lake_street_lot_32`, which today hold two village farms:
  - `gym6_house_26` `small_farm_1` at (6168, 3476);
  - `gym6_house_22` `large_farm_2` at (6181, 3475).

  Both are in `data/placements.json`, and a farm at the city's front door is the weakest use of the spot.
- **The view.** The garden is the store lot's west end, x 6203-6237, with the fountain at (6222, 3497)
  (`data/placements.json` `gym6_department_store`, rotated 2026-09-26).
- **Result:** the mall and the Game Corner flank the axis where Route 7 leaves, as the Celadon Department Store and
  the Game Corner share a street.
- **Cost:** a building must be authored. No Game Corner template exists (`STRUCTURE_INVENTORY.md:600`). This is
  `world-content-dev` work, and moving two farms is a town-plan change for the owner.

**Fallback: one floor of the department store.**
- It is placed by resource id from BCA (`bca:default/centers/center_department_store`, 40 × 41 × 72).
- The machines would be a second placement inside it.
- Its interior has not been read, so this is ASSUMED to have room.

### Prizes (Sabrina is gym 6; her ace is level 45)

**Levels.**
- The level cap on arrival is Sabrina's ace, 45: `relativeLevelCap = 0` (`modpack/config/rctmod-server.toml:153`),
  `ace_level` 45 (`data/trainers.json:951`).
- Every prize Pokemon comes **below** that cap: 25 before the badge, 35 after. So no prize can trigger the level-cap
  lockout (STATE.md:116).

**Candidates:** species with no home in `data/spawns.json` (checked 2026-09-27), so the counter is their source, not
a shortcut past one.

| Tier | Gate | Prize | Coins | Dollar equivalent | Why |
|---|---|---|---:|---:|---|
| 1 | in town | Abra L25 | 180 | $1,800 | the Kanto Game Corner's first prize; a psychic town; no spawn entry |
| 1 | in town | Clefairy L25 | 500 | $5,000 | classic; no spawn entry; needs a Moon Stone, whose supply is ADR-003's question |
| 1 | in town | Eevee L25 | 1,200 | $12,000 | **no spawn entry anywhere**. `SPAWN_PHILOSOPHY.md:372` notes the eeveelution stones then have no consumer; the Game Corner is a natural home |
| 1 | in town | two or three TMs | 300-800 | | pending EXP-030 (which TM system ships) |
| 2 | `gym6_cleared` | Pinsir L35 | 2,500 | $25,000 | classic; no spawn entry |
| 2 | `gym6_cleared` | Ditto L35 | 4,000 | $40,000 | no spawn entry; enables Cobbreeding. **A judgement call: it changes breeding for the whole group** |
| 2 | `gym6_cleared` | held items (Leftovers, Choice Scarf, Life Orb) | 1,500-3,000 | | only if EXP-031 finds no other source; `trainer-balance-designer` decides |

- **Left out:** Porygon, the Kanto top prize, because it is a common spawn in the Displaced City cavern
  (`data/spawns.json`, `habitat.displaced_city_cavern.porygon`, 32-45). Dratini is a rare spawn at Shrew Lake. Rare
  Candy, Master Ball and anything that lifts a level past the cap are also left out.
- **No prize should be Sabrina's answer.** The gym must stand without the casino. The audit's Steel, Dark and Ghost
  answers stay where they are (`docs/story/GYM_SUFFICIENCY_AUDIT.md:220-245`).

### Economy rates

| Rate | Value | Basis |
|---|---|---|
| Coin price | $10 a coin, sold in 50s and 500s | the Kanto ratio of 50 coins for 1,000 is ASSUMED from memory of the games; halved because our income runs at `cobbleDollarsIncomeMultiplier: 0.5` (`common.json:4`) |
| Cash-out | none | exploit guard |
| Coin cap | 99,999 | overflow guard |
| Bet | 1, 2 or 3 coins; the payout is the multiplier × bet | the Kanto slot bet |
| Return | 89.5% | enumerated above |
| Spin | 40 ticks to reveal, 50 between spins | about 24 spins a minute at most |
| Expected loss at bet 3 | 0.315 coins a spin, about 450 coins ($4,500) an hour of non-stop play | a sink, not a farm |

- **The dollar prices are placeholders.** The one measured income is Brock paying **$732** for a first win and
  **$600** for a rematch (STATE.md:115). Rematches still pay money, so dollars are farmable at the gyms, and the
  casino cannot make that worse: it only converts dollars to prizes at a loss.
- **Calibrate** the coin price against the balance a player actually holds at Sabrina's town. The first playtest to
  reach gym 6 should record it.

### Prototype first: EXP-043, one machine and one counter

- **Where:** staging, beside the Hometown Center.
- **What:** a generated `cobblers_casino` pack with:
  - one machine: a button, a bet lever, a marker, three item displays;
  - a counter: two buttons for the prototype ("buy 50 coins", "check coins"), or a compiled dialogue NPC if cheap;
  - one prize: Eevee L25 for 1,200 coins.

**Pass criteria:**
1. Buying 50 coins with $1,000 leaves $500 and 50 coins. With $499 it is refused, and neither balance changes.
2. A spin at bet 3 with 2 coins is refused. A spin at bet 1 takes 1 coin; the reels stop left to right; the payout
   matches the reels shown.
3. 500 scripted spins over RCON (as the player, by function) land within the binomial range of an 89.5% return.
4. Holding right-click on the button produces exactly one spin per 50 ticks.
5. Logging out mid-spin, then back in: the payout arrives and the machine unlocked on its own.
6. A restart mid-spin: the same.
7. The Eevee prize with 1,199 coins is refused. With 1,200 it gives a level-25 Eevee through `pokegive` from a
   function (the first proof of that call), and the coins drop to 0.
8. **Two players, if a second account is available:**
   - both press the one machine in the same tick: one spins, one is told it is in use, and neither loses coins;
   - they use two machines at once: both are paid correctly.
9. Coins survive a restart. The carry of `scoreboard.dat` is checked in the next re-export rehearsal.

**If the owner prefers the addon route,** the first experiment is instead a boot test of Cobblemon MiniGames
4.1.0+cobblemon1.8.0 against the staging mod set, followed by a config lockdown review.

## Open questions and judgement calls

- **Datapack over addon.** This goes against the preference ladder (a compatible addon ranks above a datapack). The
  reasons:
  - the casino is optional content, and a client-required ARR mod is a heavy price for it;
  - the addon's economy is built for free coin earning, which we would have to fight by config;
  - the prizes and badge gates should be campaign data we own.
- **Score over item coins.** Scores cannot be duped, dropped or given away. The cost is that players cannot hand
  coins to a friend; a "give coins" counter option could add that later.
- **The Ditto, Eevee and Clefairy prizes** each touch another system: breeding, ADR-003 stones, and EXP-030 and
  EXP-031 for TMs and held items. They are candidates for `trainer-balance-designer`, not decisions.
- **The location** moves two planned farms. The owner decides; `world-content-dev` authors the building.
- **EXP-043** is the next free number on this branch. Another branch could claim it first.
- **Disagreement found:** `docs/story/ENCOUNTER_GAPS.md:7` lists Dratini and Porygon as having no authored home,
  but `data/spawns.json` now places both (Shrew Lake and the Displaced City cavern). The gap report is stale for at
  least those two.
