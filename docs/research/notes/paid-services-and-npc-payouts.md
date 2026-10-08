# Paid training services and NPC battle payouts (research unit LEVELSET, 2026-10-10)

This note answers two questions from the jars in the offline snapshot
`C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods`, read with Python `zipfile` and `javap -c -p`.
No jar was executed and nothing was booted. The configs come from the repo (`modpack/config/`).

- **VERIFIED** means read from bytecode, a config line or a repo file, which is cited.
- **ASSUMED** means inferred and not yet read.
- **RELAYED** means taken from another document, which is named.

Jars used:

| Jar | Classes read |
|---|---|
| `Cobblemon-fabric-1.8.0+1.21.1.jar` | `command/PokemonEditCommand`, `command/LevelUp`, `command/TestPartySlotCommand`, `command/RunMolangCommand`, `command/argument/PartySlotArgumentType`, `api/pokemon/PokemonProperties(+$Companion)`, `api/pokemon/stats/Stats`, `pokemon/Pokemon`, `pokemon/IVs`, `pokemon/EVs`, `pokemon/PokemonStats`, `entity/npc/NPCBattleActor`, `battles/actor/*`, `api/permission/CobblemonPermissions` |
| `rctmod-fabric-1.21.1-0.19.0-beta.jar` | `server/ModServer`, `commands/PlayerCommands` |
| `rctapi-fabric-1.21.1-0.16.1-beta.jar` | `api/battle/BattleManager$TrainerEntityBattleActor` |
| `CobbleDollars-fabric-2.0.0+Beta-5.1+1.21.1.jar` | `common/CobbleDollars`, `common/event/CobbleDollarsEventsKt`, `common/config/CommonConfig`, `mixins.cobbledollars-common.json` |

## A. The paid training services

### A1. The commands that exist

**Set level, EVs and IVs: `pokemoneditother <player> <slot> <properties>`.** Its alias is `pokeeditother`.
VERIFIED from `PokemonEditCommand`:

- It registers the literal `pokemoneditother`, then an entity argument `player` (`class_2186.method_9305`, a single
  player), then `slot` (`PartySlotArgumentType`), then `properties` (`PokemonPropertiesArgumentType`).
- It is guarded by `CobblemonPermissions.POKEMON_EDIT_OTHER`, whose level is `CHEAT_COMMANDS_AND_COMMAND_BLOCKS`
  (op level 2). A function or RCON can therefore run it.
- The self form is `pokemonedit <slot> <properties>`, alias `pokeedit`.
- Execution: `PartySlotArgumentType.getPokemonOf(ctx, "slot", player)`, then
  `PokemonProperties.apply(pokemon)`, then a feedback line.
- `PartySlotArgumentType.parse` reads an int in the range 1 to 6, so slots are **1-based**.

The property keys are VERIFIED from `PokemonProperties$Companion.parse`:

- **Level:** `level=N`, with aliases `lvl=` and `l=`. `apply` calls `Pokemon.setLevel(int)`.
- **IVs:** `<stat>_iv=N`, clamped to 0..31 (`coerceIn(0,31)`).
- **EVs:** `<stat>_ev=N`, clamped to 0..252 (`coerceIn(0,252)`).
- The key is built as `"\u0001_iv"` or `"\u0001_ev"` around `Stat.toString().lowercase()` over `Stats.PERMANENT`.
  `Stats` is an enum with no `toString` override, so the stat names are `hp`, `attack`, `defence`, `special_attack`,
  `special_defence` and `speed` (British spelling), giving for example `hp_iv=31` and `special_defence_ev=252`.
- Only the stats you name change. `IVs` and `EVs` start from an empty `PokemonStats.stats` `LinkedHashMap`, and
  `commonApply` iterates that map's entries, calling `Pokemon.setIV` and `Pokemon.setEV` per entry.
- Also present: `min_perfect_ivs=N` (it rolls perfect IVs; not a set).

**EV total.** `EVs.canSet` compares against 510 (`MAX_TOTAL_VALUE`), so a set that would push the total over 510 is
refused. VERIFIED that the 510 check is in `canSet`. ASSUMED that the refusal is silent and per stat. The consequence
is that the service should zero all six EVs in one command and then set the spread in a second command, otherwise a
Pokemon that already has EVs keeps some of the old spread.

**Level-up command: `levelup [<player>] <slot>`.** VERIFIED from `LevelUp`:

- `slot` is `IntegerArgumentType.integer(1,99)`.
- The permissions are `LEVEL_UP_SELF` and `LEVEL_UP_OTHER`, both op level 2.
- It adds exactly `getExperienceToNextLevel()` through `Pokemon.addExperienceWithPlayer(..., CommandExperienceSource)`.
- That path fires `EXPERIENCE_GAINED_EVENT_PRE`, `LEVEL_UP_EVENT` and `EXPERIENCE_GAINED_EVENT_POST` (VERIFIED in
  `Pokemon.addExperience`).
- It adds one level per call, and **rctmod's cap applies to it** (see A2).

**Read a party slot: `testpartyslot <player> <slot 1-6> <properties>`.** VERIFIED from `TestPartySlotCommand`:

- It requires permission level 2 (`TEST_PARTY_SLOT`).
- It returns 1 if `properties` matches the slot and 0 otherwise, so `execute if` and `execute store result` can use it.
- `level=N` matches by equality: `commonMatches` uses `if_icmpeq` against `Pokemon.getLevel()`. There is no range
  syntax, so to read a level into a score you test levels one at a time.
- Species are tested the same way: `species=pikachu`.

**There is no command that prints a slot's level or species as a storable number.** `runmolang "<expr>" [player]`
always returns 1 and shows the value only as feedback (VERIFIED in `RunMolangCommand.execute`, which ends
`iconst_1; ireturn`). MoLang has the functions `level`, `set_iv`, `set_ev`, `highest_level` and `party` (VERIFIED
names in `PokemonMoLangFunctions`, `PokemonStoreMoLangFunctions` and `PartyMoLangFunctions`), so a dialogue can
branch through `q.run_command` the way `tools/levelcap_pack.py:111` does. Comparing one slot's struct is called
unproven at `tools/levelcap_pack.py:67`. ASSUMED usable; it needs a test.

### A2. The cap: what `setLevel` does and what rctmod enforces

**`Pokemon.setLevel`** (VERIFIED, bytecode):

- It clamps the level to 1..`CobblemonConfig.maxPokemonLevel`.
- It sets experience straight to `ExperienceGroup.getExperience(level)` and rescales HP.
- `setExperience$common` only sends an `ExperienceUpdatePacket`.
- **No event is fired.** There is no `EXPERIENCE_GAINED_EVENT_PRE` and no `LEVEL_UP_EVENT`.
  - ASSUMED consequence: level-up moves are not learned and level evolutions are not offered by the edit itself.
    This needs a test.

**rctmod's cap** (VERIFIED, `ModServer.registerEventHandlers`):

- `ModServer` subscribes `onExperienceGained` to `CobblemonEvents.EXPERIENCE_GAINED_EVENT_PRE`.
- When `IServerConfig.allowOverLeveling()` is false, it reads `TrainerPlayerData.getLevelCap()` and rewrites the
  event's experience (`ExperienceGainedEvent$Pre.setExperience`).
- Our config has `allowOverLeveling = false` (`modpack/config/rctmod-server.toml:167`).
- The exact trim arithmetic was not decompiled.

So:

- **`pokemoneditother ... level=N` bypasses the cap entirely and can overshoot it.** rctmod never sees a level set,
  because it only hooks experience. The service must pass exactly the cap.
- `levelup` goes through experience, so the cap does trim it.
- A party strictly over the cap is refused battle by rctmod and by our own `battle_check`
  (`tools/levelcap_pack.py:61` and `:111`, `highest_level > cap`). Setting a Pokemon **to** the cap is therefore
  safe, and setting it over the cap locks the player out of trainers.

**Reading the cap.** VERIFIED from `PlayerCommands.player_get_level_cap`: it calls `TrainerPlayerData.getLevelCap()`
and the command returns an int. Our pack reads it on a macro line, because a plain mod-command line can be inert
until a `/reload` (EXP-046):

```
$execute store result score @s <obj> run rctmod player get level_cap @s$(x)
```

That is `tools/levelcap_pack.py:93`, `:134` and `:163`. The guard on a cap that failed to read (0) is at `:94`–`:96`.

### A3. What a dialogue-driven service would run (proposal; not built, not tested)

The player has picked a slot (1–6) in dialogue, and the price is $500.

1. **Read the cap:** `$execute store result score @s svc.cap run rctmod player get level_cap @s$(x)`. If the score
   is not `1..`, stop: the cap did not read.
2. **Already at the cap:** `$execute if score ... run testpartyslot @s $(slot) level=$(cap)`. Refuse without taking
   money. A slot above the cap cannot be detected with one test. Either loop `testpartyslot` over `level=cap+1..100`,
   or use a MoLang comparison, which is unproven.
3. **Empty slot:** if the slot has no Pokemon, `getPokemonOf` throws. ASSUMED: the command then fails and returns 0.
   Test this before taking money.
4. **Payment:** `cobbledollars remove @s 500`. This is the form proven in game, per the comment at
   `tools/arena_runtime.py:752`. Check the balance first. The balance-read command was not checked in this unit.
5. **Apply:** `$pokemoneditother @s $(slot) level=$(cap)`, written as a macro line for the same reason as step 1.
6. **EV service:** first `$pokemoneditother @s $(slot) hp_ev=0 attack_ev=0 defence_ev=0 special_attack_ev=0
   special_defence_ev=0 speed_ev=0`, then `$pokemoneditother @s $(slot) <stat>_ev=252 <stat2>_ev=252 hp_ev=4`.
   The total must stay at or under 510.
7. **IV service:** `$pokemoneditother @s $(slot) hp_iv=31 attack_iv=31 ...`, naming only the stats that were bought.

## B. The arena payout hole

### B1. Our functions pay a purse (VERIFIED, `tools/arena_runtime.py`)

- `fn["pay"]` (lines 751–754) emits `$cobbledollars give @s $(amount)` and a tellraw.
- `fn["won"]` (line 618) calls `purse` on every arena win.
- `purse` (lines 720–734) pays:
  - kind 1, a pool bout: the rank's purse, or the exhibition quarter;
  - kind 2, an exam: the exam leg's purse;
  - kind 3, the streak: `streak/purse`, scoreboard arithmetic, lines 735–750.
- The gauntlet clear bonus is paid at lines 632–634. The streak's every-5th-win bonus is paid at line 710.
- The formula is 13 × the opponent's level sum, rounded to the nearest 50 (`purse`, line 133;
  `data/arena_fights.json` `prizes.purse_formula`). Its coefficient 13 is labelled ASSUMED in that file.

Amounts, computed by running `arena_runtime.ladder()` on the current data:

| Rank | Pool purse (exhibition) | Exam purse | Clear bonus |
|---|---|---|---|
| 1 The Floor | 2200 (550) | 2150 | – |
| 2 The Shaft | 3000 (750) | 2250 | – |
| 3 The Relay | 2300 (550) per leg | 2150, 2250 | 2000 |
| 4 Champion's Door | 3150 (800) | 3150 | – |
| 5 The Sluice | 1700 (400) per leg | 3300 | 2500 |
| 6 The Terrace | 2600 (650) per leg | 4300 | 3000 |
| 7 The Tear | 1850 (450) per leg | 4550 | 5000 |
| 8 The Crown | 2900 (700) per leg | 5800 | 7500 |
| 9 streak | 3000 (3×L78) to 7600 (6×L100) | – | +3000 every 5th win |

### B2. CobbleDollars also pays automatically on a Cobblemon NPC win: the jar says yes

The evidence, all VERIFIED:

- `CobbleDollars` subscribes `CobbleDollarsEventsKt.battleVictory` to `CobblemonEvents.BATTLE_VICTORY`. It is the
  only battle event it uses. Its mixins are Player, ServerPlayer, Villager, Zombie and ZombieVillager; none touches
  battles.
- `battleVictory` does the following:
  - It returns if `battle.isPvP()`.
  - For each winning actor's `getPlayerUUIDs()`, it pays for each loser whose `BattleActor.getType()` is
    `ActorType.WILD` when `earnCobbleDollarsFromWildPokemon` is set, or `ActorType.NPC` when
    `earnCobbleDollarsFromNPC` is set.
  - It does **not** test for rctmod or any particular entity. It tests the actor type only.
- **Cobblemon NPCs are `ActorType.NPC`.** `com/cobblemon/mod/common/entity/npc/NPCBattleActor.<init>` does
  `putfield type = ActorType.NPC`. `BattleBuilder` references `NPCBattleActor`.
  - ASSUMED: `q.npc.start_battle` builds through `BattleBuilder.pvn`. The refusal reasons at
    `tools/arena_runtime.py:604` say it does.
- rctmod trainers are `ActorType.NPC` too (rctapi `BattleManager$TrainerEntityBattleActor`), which is why Brock paid.
- Config: `earnCobbleDollarsFromNPC: true`, `earnCobbleDollarsFromWildPokemon: true` and
  `cobbleDollarsIncomeMultiplier: 1.25` (`modpack/config/cobbledollars/common.json:2-4`).

**The automatic amount** (VERIFIED arithmetic, `battleVictory` bytecode 370–567). Over the losing actor's
`getPokemonList()`:

```
B      = max(1, int(5 * sumLevels * sum(level / 50.0)))
amount = B + random.nextBetween(B / 2, 2 * B)
credit = floor(amount * 1.25)
```

- The mapping of `class_5819.method_43051` to `nextBetween`, inclusive at both ends, is ASSUMED.
- The amount is recomputed for each loser and not summed. Only the last qualifying loser counts; a singles bout has
  one.
- **The formula is quadratic in the team, not linear.**
  - Brock as `gym_01_brock` (levels 18, 18, 20) gives 586–1,173.
  - The two measured payouts, $732 and $600 (RELAYED, `docs/STATE.md:243`, `docs/research/INCOME_MEASUREMENT.md:68`),
    both fall in that range, which corroborates the formula.
  - **Model B in INCOME_MEASUREMENT (a linear $13 per level) is contradicted by the jar.**

What CobbleDollars would add on top of our purse, at the drawn levels:

| Bout | Ours | CobbleDollars auto (min–max) |
|---|---|---|
| Rank 1 pool (55, 56, 57) | 2200 | 5,291 – 10,582 |
| Rank 4 pool (59–62) | 3150 | 10,980 – 21,960 |
| Rank 8 exam (6 Pokemon, 73–76) | 5800 | 37,462 – 74,925 |
| Streak, 6 × L95–100 | 7600 | 64,166 – 128,332 |

**Verdict: the jar settles that CobbleDollars pays every arena win** whenever BATTLE_VICTORY fires with the player as
the winner and the opponent's actor is `NPCBattleActor`. The arena then pays twice, and the automatic share is roughly 1.8
times our purse (the rank 5 minimum) to 17 times (the streak maximum).

The ways out are left to the caller:

- Set `earnCobbleDollarsFromNPC` to false. That also stops every rctmod trainer's pay, which the economy relies on.
- Drop our purse and keep only the bonuses.
- Claw the payment back after the win. That needs the random credit, which a function cannot know without reading
  the balance before and after.

### What only an in-game win proves

1. That an arena win actually credits the automatic amount. Read the balance before and after one rank-1 win, and
   compare the difference minus our purse against 5,291–10,582.
2. That `pokemoneditother @s <slot> level=<cap>` from a function or RCON sets the level and does not push the party
   over the cap. Read it back with `testpartyslot`.
3. Whether moves are learned and evolutions offered after a level set.
4. What happens on an empty slot, and with an EV set that would exceed 510.
5. Whether a MoLang slot comparison can drive a "which Pokemon" dialogue choice.
