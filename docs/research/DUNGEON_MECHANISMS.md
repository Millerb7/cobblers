# Timed rift dungeons: what the mechanisms can and cannot do

**Question (the owner, relayed by the brief, 2026-10-08).** An instanced run against a timer. Finish it or leave
before the clock runs out, or die. The entrances are visible rips torn from the Rift, which a player chooses to
enter. A run is 1,000-2,000 blocks long. The clock budgets about 2 minutes for a small fight and 5-10 for a boss.
A player can always turn back, but backtracking spends the same clock. The legs are:
- trainer fights;
- a staged boss that heals and comes back a level higher with a different moveset;
- resource areas that speed the clock (5 taken: 1.25x; 20 taken: 3x);
- parkour with no Pokemon deployable;
- legendary encounters, such as a lake with something obvious at the bottom for a player with Dive.

**Scope.** Research only; nothing is built. This answers *mechanisms*. The run's design is for the design agent,
which reads this file. `docs/mechanics/DUNGEONS.md` is the earlier hub-and-wings design (about 30 minutes, no
timer). Where the owner's new shape differs, that is a design change, not a finding here.

**Read for this note (2026-10-08, read only):**
- jars in `C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/`: Cobblemon 1.8.0, LegendaryMonuments,
  Mega Showdown 1.0.2, cobblemon-additions 4.1.6, rctmod 0.19.0. Read with Python `zipfile` and `javap` (JDK 21);
- the snapshot's `datapacks/`, including `COBBLEVERSE-DP-v31.zip`;
- this repository's tools and data.

The live server directory was not touched.

**Labels.**
- **VERIFIED**: read from the jar, class and member named.
- **VERIFIED (repo)**: read from this repository's code or data, file and line named.
- **Relayed**: stated by another note or document and not re-read here; the source is named.
- **Vanilla**: standard Minecraft 1.21.1 command behaviour, not read from a jar here. Treat it as ASSUMED until a staging probe.
- **ASSUMED**: an inference; each one is listed in section 10 as a probe.

**Two premises in the brief are wrong, and both matter:**
1. **"The mining caves' occupancy guard uses `minecraft.mined` stats."** It does not. The guard tests entity
   presence: `execute if entity ... run return 0` over the gallery's body and shell
   (`tools/mining_caves.py:15-18`, citing `tools/mines.py:719-731`). No `minecraft.mined` objective exists anywhere in
   `tools/`, `data/` or `docs/` (grep, 2026-10-08). The break counter in section 2 is therefore new, with no precedent
   in this repo.
2. **"The portals from the ultra beast pack."** No installed mod or datapack ships an Ultra Wormhole, an Ultra Space
   portal or any Ultra-themed portal (section 7). The phrase must mean a mod that is not installed.

---

## Verdicts

| # | Question | Verdict |
|---|---|---|
| 1 | Timer, display, death | **Works.** A per-slot countdown score, a per-slot bossbar, and `kill` into the existing blackout. **Pausing in battle works with a caveat:** the in-battle test is VERIFIED, but a stalled battle freezes the clock unless capped |
| 2 | Resource multiplier | **Works.** The fill rate is scaled per keeper pass. Counting needs a choice between the `minecraft.mined` stat (vanilla, needs the right tool) and marker entities on each ore (counts whatever is taken, whoever takes it) |
| 3 | Boss stages | **Works two ways.** (a) **One battle**: a staged NPC party of the same species at rising levels. Its caveat: the NPC AI picks the switch-in by matchup, so the stage order is not guaranteed. (b) **Chained battles**: a victory callback swaps the party and starts the next fight; this is the arena's proven loop. **No way exists to heal a boss inside one battle from a datapack** |
| 4 | No Pokemon deployable | **Not possible as a refusal at datapack level**: no MoLang callback can cancel anything in 1.8.0 (VERIFIED, all 81). **Nearest, works with caveat:** a zone sweep removes any player-owned Pokemon entity, which returns it to the party with its HP kept (VERIFIED). Riders are dismounted (repo precedent). Never use `kill` on one |
| 5 | Parkour and death | **Works.** A fall death is a blackout: $600 flat, inventory kept, no items lost, out of the instance. A catch band below each section returns the player to the section start for a clock penalty, so a fall costs time instead of the run |
| 6 | Multiplayer | **Works.** A slot owned by a party, with the clock on the slot and not on a player. The space holds hundreds of runs; the real limits are slot count and chunk loading. Two players against one NPC in one battle is still OPEN |
| 7 | Portals | **No Ultra Wormhole is installed.** The nearest is LegendaryMonuments' distortion portal **entity**, whose destination is hard-coded to its own Distortion World (VERIFIED), so it is usable only as a sealed visual with our own trigger. The alternative is a vanilla-built rip: frame, particles and an interaction entity. Static and random both work; random means a scheduler over authored candidate sites |
| 8 | Instancing | **Works, with a choice.** Rebuild the whole run per entry (heavy: about 250 chunks and around a million blocks per run, untimed), or keep a persistent shell placed by re-apply and reset only the mutable parts per entry (recommended). The pocket's contents do not survive a re-export, so the shell must be a re-apply step |

---

## 1. The timer

### 1.1 Tracking: count down a score, never subtract game times

The Entei room measures with `time query gametime` deltas:
- `#now` is stored at `tools/entei_boss.py:387` and `:444`;
- the lockout is `#d = now - eb.last`, at `:460-462`.

A game clock that goes backwards breaks that arithmetic. A re-export carries the scores but not `level.dat`'s `Time`
(`:456-459`; review N142, `docs/OVERNIGHT_REVIEW_2026-10-06.md:151`). The fix had to treat a negative `#d` as "outside"
(`:458`) and restart a spawn delay when the clock went back (`:538-539`).

**For a run clock, decrement a score instead.** Hold one score per slot, `#s<k> dg.clock`. Each keeper pass, while
the run is live, subtracts `period x rate` from it:
- **Units.** Use quarter-ticks, so 1.25x stays an integer. Rates are 4 (1x), 5 (1.25x), 12 (3x) and 0 (paused).
  A 30-minute budget is 36,000 ticks x 4 = 144,000 units, far inside 2^31.
- **Immune to game-time jumps.** Nothing is compared against `gametime`. A re-export, a `/time set` or a
  restart cannot move it. Vanilla `time set` changes the day time, not the game time, but the point stands for
  re-exports.
- **Stops by itself when the server is down.** The keeper only runs while the server ticks, so a crash or restart
  costs no clock. The keeper re-schedules itself from `load`, as Entei's does (`tools/entei_boss.py:381`,
  VERIFIED (repo)).
- **Logout.** Recommend Entei's rule: the run ends when its owner is no longer in the slot, freed on the next keeper
  pass (`tools/entei_boss.py:524-529`, `:545-555`, VERIFIED (repo)). Cobblemon also fires `player_logged_out`
  (callback event name VERIFIED in `events/CallbackHandler`; see 1.4). A design that freezes the clock while the
  player is offline is possible too, but then a logout becomes a free pause.
- **Granularity.** Entei's keeper period is in `data/entei_boss.json` `keeper.period_ticks`. For a clock, 20 ticks
  (one second) is enough: the display is in seconds and a pass costs a few commands per live slot.

### 1.2 Display: one bossbar per slot

| Surface | Per player? | Fits a run clock? |
|---|---|---|
| **Bossbar** (`bossbar add/set`) | **Yes.** `bossbar set <id> players <targets>` sets exactly who sees it (vanilla) | **Yes. Recommend.** Use one bar per slot, `cobblers:dg_s<k>`. Set `max` once and `value` each pass with `execute store result bossbar <id> value run scoreboard players get #s<k> dg.clock` (vanilla). `color` is one of seven (blue, green, pink, purple, red, white, yellow); `style` is `progress` or `notched_6/10/12/20`. The name is a text component: build mm:ss from two score components, with a branch adding the leading zero for seconds 0-9 |
| Actionbar (`title @s actionbar`) | Yes | **For moments, not the clock.** It fades in about 3 s unless re-sent, and other packs write to it already: blackout `tools/blackout_pack.py:350` and `:992`, the gulch `tools/gulch_mine.py:1208` (VERIFIED (repo)). A permanent actionbar clock would fight them. Use it for "the rift tightens" |
| Sidebar (`scoreboard objectives setdisplay sidebar`) | **No.** The display slot is server-wide. Only `sidebar.team.<colour>` narrows it, and only by team colour | **No.** Two runs would show each other's clocks, and teams collide with anything else using them |
| Title (`title @s title`) | Yes | For the last 10 seconds and the death line |

Two bossbar facts the design must respect (vanilla, ASSUMED until a probe, B1):
- **The `players` set is a stored list of UUIDs.** It is saved with the world, and a player in it sees the bar again
  on reconnect. The run's end must run `bossbar set <id> players` with an empty target, or remove the bar.
- **A score inside `bossbar set ... name` is resolved when the command runs**, not live. So the name is re-set every
  pass, with the value.

### 1.3 What "you die" means: four options, one already built

| Option | What happens (sources) | Fit |
|---|---|---|
| **A. `kill @s` into the existing blackout** | The blackout counts a vanilla death through `deathCount` (`tools/blackout_pack.py:12`, `:55`). It charges **$600 flat** (`data/blackout.json` `money`, decision B10), returns the player to their checkpoint, which is also their spawnpoint (`tools/blackout_pack.py:14-17`), and heals the party. **`gamerule keepInventory true`** is set at load (`tools/blackout_pack.py:174`), so the inventory is kept. A command death is environmental, so **no items are lost** (`docs/mechanics/DEATH_AND_WIPE.md:20-26`, rule 5, which lists "commands" by name). All VERIFIED (repo). The respawn is in the overworld, so dying also ends the run | **Recommend as the base.** It is built, and a dungeon death matches every other death |
| B. Lenient Death | `modpack/config/lenientdeath.json5`: `preserveItemsOnDeath.enabled: "yes"`, `alwaysPreserved` holds the Pokedexes, `byItemType.enabled: false` (VERIFIED (repo), lines 207-260 and 386-391) | **Moot while keepInventory is true.** Every item is kept before Lenient Death would choose. Do not build on its keep list |
| C. Harsher: forfeit the run's loot | The run's rewards are held in **escrow**: counted in scores or storage and paid only at a clean exit, never put in the inventory during the run. Death forfeits the escrow | **Recommend adding this to A** if the owner wants a timeout to hurt more than a $600 fall. It does not break rule 5 ("environmental death never loses items"), because escrowed loot was never an item the player held. Taking items from the inventory on a timeout **would** break rule 5 and needs the owner's decision. Ores mined in a seam are real drops, so a seam either pays into escrow (the tool-and-count design in 2.1) or is not forfeitable |
| D. Harsher: a lockout or a party penalty | A lockout is Entei's (`data/entei_boss.json` `lockout`). A party "faint" has no clean command (see 4.2: `kill` on a Pokemon entity is unsafe), and Cobblemon offers no party-wide damage command | A lockout works. A party penalty is not recommended |

**How to kill.** Use `kill @s`. It deals generic-kill damage, which bypasses invulnerability, so a totem of undying does
not save the player (vanilla, ASSUMED until B2). `damage @s <n> minecraft:outside_border` reads better in the death
message ("left the confines of this world"), but a totem can stop it. If it is used, follow it with `kill` as a
backstop.

**A timeout during a battle.** If the clock is not paused in battle (1.4), it can reach 0 mid-fight. Do not kill a
player mid-battle: what Cobblemon does with the battle and the NPC is not read (ASSUMED risk, B3). Two options:
- **sudden death**: the clock holds at 0, and the player is killed the moment `in_battle` goes false (1.4), whatever
  the result;
- `stopbattle` first (`com/cobblemon/mod/common/command/StopBattleCommand.class` exists, VERIFIED as a class; its
  syntax is not read), then `kill`.

Recommend sudden death.

### 1.4 Can the clock pause during a battle? Yes, and here is how reliable it is

**The owner's text implies it does not pause** ("the clock budgets for fights: about 2 minutes for a small one, 5-10
for a boss"). Both are buildable. This is the owner's call, and it changes the budget: with a pause, fights cost no
clock and the budget is pure movement.

**The test (VERIFIED):** `q.player.in_battle`, a function on the player struct
(`com/cobblemon/mod/common/api/molang/function/PlayerMoLangFunctions`, string `in_battle` at constant #358). It calls
`PlayerExtensionsKt.isInBattle(ServerPlayer)` (`javap`, PlayerMoLangFunctions line 1503). It is the battle registry's
own answer, not an inference from events. The same struct also has `battle`, `opponent` and `riding_pokemon`
(VERIFIED as names). A function reads it with
`runmolang "<expr>" <player>`, which binds `q.player`. The arena uses exactly this as its ground truth:
`(q.npc.in_battle == 0 && q.player.in_battle == 0) ? { q.run_command(...) }` (`tools/arena_runtime.py:1112-1117`,
VERIFIED (repo)). The `runmolang` tree is VERIFIED (`RunMolangCommand.register`): `molang`, then an optional
`player` (entity argument), then `npc` and/or `pokemon`, in either order.

**The events (VERIFIED, `events/CallbackHandler`):**
- `battle_started_pre` and `battle_started_post`;
- `battle_victory`, `battle_fainted` and `battle_fled`;
- `player_died`, `player_logged_out` and `player_tick_post`.

They run from `data/cobblemon/callbacks/<event>/*.molang` and must sit under the `cobblemon` namespace (EXP-042,
relayed in `tools/arena_runtime.py:1139`). The `battle_started_post` context is `battle, npcs, players, wild_pokemon`
(relayed, `docs/research/notes/sketch-cap-1.8.0.md:108`).

**Recommended shape:**
- **Pause only in battles that pay for it.** `battle_started_post` tags the player `dg.fight` only when an NPC in the
  battle carries the dungeon's tag. Use the arena's pattern for this: `q.run_command('execute as ' + <npc uuid> +
  ' if entity @s[tag=...] ...')` (`tools/arena_runtime.py:1146-1151`).
- **Clear the tag from the poll, not from the end events.** The keeper polls `q.player.in_battle` each pass and
  clears `dg.fight` when it reads 0. A forfeit or a flee from an NPC battle sends no result
  (`tools/arena_runtime.py:1112`, VERIFIED (repo)), so `battle_victory` alone would leave a stale tag and a
  permanently frozen clock.
- **The rate is 0 while every live member of the slot is tagged and in battle** (co-op, section 6).

**Reliability:**
- `in_battle` is the registry's own state, so it is right at every poll (VERIFIED as a call; not run). The
  error is at most one keeper period: 20 ticks of clock run or paused wrongly at each battle edge.
- The events add immediacy, and the poll makes it correct.
- **The abuse case is not in the data. It is a player sitting in the battle menu.** Cobblemon battles have no turn
  timer by default (ASSUMED, B4), so a paused clock can be frozen indefinitely. Cap it:
  - a per-battle pause allowance (for example 3 minutes, then the clock runs at 1x), or
  - a reduced rate in battle (for example 1 unit in 4) instead of 0.
- **PvP and wild battles must not pause.** Two co-op players can challenge each other, and the pocket's
  `the_void` biome is assumed to spawn no wild Pokemon but was never tested for Cobblemon's own spawner
  (`data/portals.json` `pocket.generator.biome_why`, relayed: "NOT VERIFIED for Cobblemon"). The tag-only-for-
  dungeon-NPCs rule closes both.

---

## 2. The resource multiplier

### 2.1 Counting what a player takes: two mechanisms

| Mechanism | How | Strengths | Weaknesses |
|---|---|---|---|
| **The `minecraft.mined` stat** | `scoreboard objectives add dg.dia minecraft.mined:minecraft.diamond_ore`, plus one for `deepslate_diamond_ore`; set to 0 at entry. Inside the pocket only dungeon blocks exist, so every increment is a dungeon take. For co-op, sum the members | Per player for free; no entities | **Vanilla awards the stat only when the block is harvested with the correct tool** (the drop path). A wrong tool breaks the block with no count (vanilla, ASSUMED until R1). In adventure mode nothing breaks unless the tool carries `can_break` (2.3). One objective per block id |
| **Marker per ore** | At slot build, a `marker` entity sits in each seam block (tag `dg.ore`, slot tag). Each pass: `execute as @e[type=marker,tag=dg.ore,tag=dg.s<k>] at @s unless block ~ ~ ~ #<seam ores> run ...` counts it once and kills the marker | **World-shaped** (CLAUDE.md "Our list is not the world"): it counts what is gone, by any tool, piston or explosion. Exact per slot | Attribution to a player is by the nearest member, which is fine for one player and approximate in co-op. Costs one entity per ore (a 20-block seam is 20 markers) |

**Recommendation.** Use the marker count for the multiplier: it is the world's truth. Add the stat only if the design
needs per-player credit in co-op. Either way, **the thresholds key on the slot's count**, not a player's, so in co-op
one partner's greed tightens the clock for both. That is a design decision to state, not an accident.

### 2.2 Scaling the clock

The keeper's decrement is `period x rate`, with `rate` chosen from the slot's count by threshold. With the owner's two
points, 0-4 is 4 units (1x), 5-19 is 5 (1.25x) and 20+ is 12 (3x). Values between are the design agent's. All
scoreboard arithmetic (`scoreboard players operation`), as Entei's keeper already does
(`tools/entei_boss.py:536-541`).

**Edge:** a multiplier that only ever rises makes the leg a one-way commitment, and that is the point. It interacts
with 1.4: if battles pause the clock, the multiplier does nothing during a fight. If battles do not pause, a greedy
player fights at 3x. The design agent must pick one.

### 2.3 Making it legible, and keeping the take to the seam

- **The bossbar is the state** (1.2): white at 1x, yellow at 1.25x, red at 3x, and the multiplier in its name ("Rift
  collapse 12:34 - x1.25").
- **The crossing is the moment.** On crossing a threshold:
  - `title @a[<slot>] actionbar "The rift tightens."`;
  - a sound, such as `playsound minecraft:block.respawn_anchor.deplete`;
  - optionally particles at the seam.
- **Keep the take to the seam with adventure mode** (precedent: the scene runtime puts a survival player in adventure
  mode inside `no_build` boxes and back on leaving, `tools/scenes_pack.py:390-406`, VERIFIED (repo); the Gastly
  mansion uses it, `docs/STATE.md:332`). The dungeon hands out a **rift pick** whose `minecraft:can_break` component
  lists the seam ores only (vanilla 1.21 item component, ASSUMED until R2). The player's own tools then break nothing
  in the instance, and nothing outside the seam can be mined, bridged or dug past.
  - Cost: every exit path must restore survival. Run a backstop overworld sweep that resets any adventure-mode player
    who carries the dungeon tag. Without it, one missed path leaves a player in adventure mode in the overworld.

---

## 3. Boss stages

### 3.1 What exists

- **A Cobblemon NPC's party**, from the arena work (relayed, `docs/research/notes/arena-per-player-opponents.md:97-104`;
  VERIFIED in source there):
  - `simple` (a list of property strings), `pool`, `composed pool` or `script`;
  - property strings carry `level=`, `moves=` (comma separated), `ability=`, `held_item=` and `nature=`
    (`tools/arena_runtime.py:323-341`, keys read from the 1.8.0 PokemonProperties parser).
- **NPC MoLang has `set_npc_party`, `create_npc_party`, `set_class`, `start_battle`, `stop_battles`, `heal`,
  `in_battle` and `can_battle`** (VERIFIED as names, `api/molang/function/NPCMoLangFunctions` constant pool). Their
  argument shapes are not read (ASSUMED, S1).
- **The NPC battle AI is `StrongBattleAI`.** It chooses the forced switch-in by matchup (`choose`,
  `considerSwitching`, `bestSwitch`, `estimateMatchup`) and also switches voluntarily (`shouldSwitchOut`,
  `switchOutMatchupThreshold`, `hpSwitchOutThreshold`). All VERIFIED as members of
  `battles/ai/StrongBattleAI.class`.
- **In-battle form change:**
  - A Cobblemon-native NPC never Dynamaxes, because its AI never chooses the gimmick (relayed,
    `docs/research/notes/dynamax-1.8.0.md:101`).
  - An **RCT** trainer's AI does Dynamax when the team member's JSON says `"gimmicks": {"dynamax": true}`
    (relayed, same note, lines 25 and 103-106; never run).
  - Mega Evolution for RCT trainers is driven by held items per the RCT docs (relayed,
    `docs/research/notes/wild-mega-pokemon.md:215`; docs not pinned to 0.19.0).
- **rctmod:**
  - one static team per trainer id;
  - trainer state such as `Cooldown` is entity NBT, so it cannot be held per player;
  - no command starts a battle; it starts by a click or a look.

  All relayed from `docs/research/notes/rct-arena-capabilities.md:28-55`. A dungeon NPC that is an rctmod trainer in
  a series can move a player's level cap (`docs/mechanics/DUNGEONS.md:200-204`, relayed).
- **Cobblemon cannot heal a battling Pokemon from outside the battle.** No callback can change battle state: the
  callbacks cannot cancel or alter anything (section 4.1), and the `heal` functions act on party storage. That a heal
  applied to the NPC's stored party does not reach the live battle copy is ASSUMED (S2).

### 3.2 Two ways to build stages

**(a) One battle: a staged party.** The boss NPC's `simple` party is the same species N times, for example
`"<boss> level=60 moves=a,b,c,d"`, `"<boss> level=61 moves=e,f,g,h"`, `"<boss> level=62 moves=i,j,k,l"`. When stage 1
faints, the NPC sends out the next member at full HP. To the player, the boss "heals and comes back a level higher with
a different moveset".
- **The caveat that decides it:** `StrongBattleAI` chooses which member comes in by matchup, and may switch out a
  healthy one. **The stage order is not guaranteed** (VERIFIED as the AI's structure; how it ranks identical species
  at different levels is not read). Stage 3 could come first, and stages could alternate.
  - Mitigations: the AI's `skill` value (the arena uses 0-5, `tools/arena_runtime.py:116`) may change switching. Or
    make the stages different enough that the matchup ranks them in order. Neither is verified (S3).
- **Species clause:** that the battle format allows three of one species is ASSUMED (S4).
- **Gains:** a single battle; the player cannot heal or re-order between stages (bag items are the arena's rule,
  `data/arena_fights.json:30`, relayed); `battle_fainted` can cue each stage with a title and a sound (the event is
  VERIFIED; using its context to tell which member fainted is ASSUMED).
- **A real in-battle transformation as the last stage** (Mega or Dynamax) needs an **RCT** trainer. RCT battles start
  only by a click or a look, and one trainer id serves every player. Per-player slots would need one trainer id per
  slot per boss.

**(b) Chained battles (recommend).** Each stage is a separate battle with the same visible boss:
- `battle_victory` (the arena's callback pattern, `tools/arena_runtime.py:1134-1151`) runs a function as the winner.
- That function cues the stage (title, particles, a 40-60 tick pause), then either swaps the NPC's party
  (`q.npc.set_npc_party`, ASSUMED shape) or replaces the NPC with the next stage's class (`spawnnpcat`, the arena's
  proven spawn).
- It then starts the next battle with `runmolang "q.npc.start_battle(q.player, 'singles');" <player> <npc>`.
- The arena's chain is spawn, start, `battle_victory`, next leg. It **PASSED in game for one player**
  (`docs/mechanics/DUNGEONS.md:200-202`, relaying `arena-per-player-opponents.md:357-368`).
- Between stages the boss is new and full, and the **player's party carries HP, PP and faints** (the arena gauntlet
  rule, `data/arena_fights.json:27`, relayed). The design must decide whether bag items are allowed in the gap; the
  arena's no-bag rule applies inside a battle, not between battles.
- A loss in any stage is a normal NPC loss, and the blackout fires (VERIFIED in game per `DUNGEONS.md:260-262`,
  relayed).
- The order is guaranteed, because the function chooses the next stage.

**Is there any way to keep it one battle?** Only (a), and only with the order caveat. No datapack-level mechanism heals
or replaces a Pokemon inside a running Showdown battle.

---

## 4. No Pokemon deployable

### 4.1 Refusal: not possible from a datapack

**Every MoLang callback in Cobblemon 1.8.0 is run with no Cancelable** (VERIFIED). `events/CallbackHandler` makes 81
`CobblemonCallbacks.run$default` calls. In every one, the Cancelable argument is `aconst_null`, with mask 8 or 12. This
includes `pokemon_sent_pre`, `ride_event_pre`, `battle_started_pre`, `pokemon_recall_pre` and `thrown_pokeball_hit`
(each read at its `setup$lambda`). `CobblemonCallbacks.run` drops `q.cancel` when the Cancelable is null (relayed,
`docs/research/notes/beast-ball-key-1.8.0.md:96`). **No datapack can refuse a send-out, a ride or a battle start.**
Only Kotlin can (Mega Showdown does, for Zygarde cores; same note).

### 4.2 Nearest: remove the Pokemon after it appears

**Removing a player-owned Pokemon entity returns it to the party with its HP kept** (VERIFIED,
`entity/pokemon/PokemonEntity.method_5650`, i.e. `remove(RemovalReason)`): when the Pokemon's `ActivePokemonState`
entity is this entity, it sets the Pokemon's state to `InactivePokemonState`. It does not change health. That is a
recall without the animation.

How to remove one from a function:
- **`runmolang "q.pokemon.discard;" <player> <pokemon entity>`.** The `pokemon` argument is a single entity, and its
  struct is the `PokemonEntity` struct, built with `addEntityFunctions`, `addLivingEntityFunctions` and
  `addPokemonEntityFunctions` (VERIFIED, `RunMolangCommand` bytes 80-113; `PokemonEntity` constant pool #954-#968).
  `discard` is in `EntityMoLangFunctions` (VERIFIED as a name). That the query is named `q.pokemon` and that `discard`
  takes no argument are ASSUMED (P1).
- **Or a `pokemon_sent_post` callback** (context `pokemon`, `pokemon_entity`, `level`, `position`; VERIFIED in
  `PokemonSentEvent$Post`). It tests the position against the zone and calls `discard` on `pokemon_entity`. This acts
  on the same tick as the send-out.
- **Never `kill` a player's Pokemon.** `kill` on a living entity is generic-kill damage, which bypasses invulnerability
  (vanilla). `PokemonEntity.method_5643` (hurt) writes the entity's health back into the party Pokemon with
  `setCurrentHealth` when the Pokemon is owned (VERIFIED, bytes 78-135). So a kill would very likely **faint** it
  (ASSUMED, P2). In a Nuzlocke zone a faint can be permanent (`docs/mechanics/NUZLOCKE_ZONES.md`). Teleporting one
  into the void is the same fault.

**Shape.** A keeper sweep over the parkour box each pass (20 ticks, or every tick in the parkour box if the design
wants no window):
1. `execute in cobblers:pocket as @e[type=cobblemon:pokemon,<box>,tag=!<our boss tags>] run ...` discard. Inside a
   parkour box there are no wild or NPC Pokemon, so "untagged" means "the player's".
2. Players in the box: `ride @s dismount`, then `execute on passengers run ride @s dismount`. This is the Nether
   gate's bounce, VERIFIED (repo) at `tools/nether_gate.py:192-193`. `q.player.riding_pokemon` names the case, if the
   message should differ.
3. A line on the actionbar: "The rift will not hold them here."

**What the player sees:** the ball's send-out animation, then the Pokemon blinks out within one pass, with no recall
beam, and the line.

**Edge cases the geometry must close, because a sweep cannot:**
- **A rider in mid-air over a gap** is dismounted and falls. **Sweep at the section's entry, on solid ground**: a gate
  box before the first jump. The in-section sweep is the backstop. Put a catch band under every gap (section 5) so a
  mid-air dismount costs clock, not the run.
- **Flying over a section from outside its box.** Make the box enclose the whole air volume to the ceiling, and give
  parkour sections a ceiling 3-4 blocks above the route, so there is no room to fly above it.
- **Entering already mounted.** Crossing a dimension recalls sent-out Pokemon (relayed: ADR-004, `docs/STATE.md:240`,
  EXP-047), so a player arrives in the pocket on foot.
- **Not Pokemon, but the same bypass:**
  - ender pearls: kill `ender_pearl` entities in the box;
  - elytra: refuse entry at the door if `execute if items entity @s armor.chest minecraft:elytra` (vanilla 1.20.5+);
    low ceilings make it useless anyway;
  - placing blocks: adventure mode (2.3);
  - Waystones warp items teleport the player *out*, which is leaving, and the sweep ends the run.
- **Shoulder-mounted Pokemon** (`shoulder_mount` event exists) do not help traversal. Leave them alone.

**Verdict:** works with caveat. It is not a refusal: there is a one-pass window, and it needs P1 proven.

---

## 5. Parkour and death

**What a fall costs today.** A fall death is a vanilla death, and so a blackout (1.3 A):
- $600 flat;
- a return to the checkpoint in the overworld, so the run is over;
- the inventory kept, and no items lost (rule 5).

Fall damage is environmental.

**What keeps a fall from wiping the run:**

| Mechanism | How | Verdict |
|---|---|---|
| **Catch band and soft respawn (recommend)** | Under every gap, a box a few blocks below the route. A player in it is teleported to the section's start marker, given `resistance 5` for 2 seconds (level 5 is a 100% reduction, vanilla), and charged a clock penalty (subtract units from `#s<k> dg.clock`) | Works. This is the owner's model: a fall costs clock, and too many falls cost the run. Resistance covers whether a teleport resets fall distance, which is not read (ASSUMED, F1). The pocket's bedrock floor is at y0 (`data/portals.json` `pocket.floor_y_why`), so nothing reaches the void |
| No fall damage in the instance | `gamerule fallDamage false` is **server-wide**: one GameRules for every dimension (vanilla 1.21.1) | **Reject.** It would turn off fall damage in the overworld too. Per-zone `slow_falling` removes the challenge |
| Checkpoints mid-section | The start marker moves forward as the player clears a section; it is stored on the slot | Works with the catch band. A section is the unit of retry |
| Water, powder snow or slime landings | Vanilla blocks that cancel fall damage | Works as dressing, but it reads as a hint and the player keeps going from the bottom |

**Hazards inside the dungeon to check:**
- **The portals' rescue box.** `cobblers:portals/tick` teleports any player found in x -512..1152, z -512..768,
  y 0..94 of the pocket (computed from `tools/portals.py:438-441`: room centres x 0-640, z 0 and 256, from `:204-206`,
  with `rescue_margin` 512; VERIFIED (repo)). A dungeon slot must sit outside it, as Entei's z -768 row does.
- **Forgiving Void.** `forgivingvoid-fabric-1.21.1-21.1.7` is installed. A bedrock floor at y0 means it never fires.
  Its config was not read.
- **Water.** The blackout's water system has **no dimension filter**: `execute as @e[type=player,...] at @s run
  function ...water/tick` (`tools/blackout_pack.py:191`, VERIFIED (repo); `docs/STATE.md:240`). Its depth rules
  therefore hold in the pocket (section 9).

---

## 6. Multiplayer

**Shared runs and private instances.** Entei's rule is one player per slot:
- `#s<k> eb.own` holds the owner's id;
- the keeper ejects anyone in the band not standing in their own slot (`tools/entei_boss.py:383-404`, VERIFIED (repo));
- slots are 4, at x -768/-640/-512/-384, z -768, y 96, 128 apart (`data/entei_boss.json` `pocket`, VERIFIED (repo)).

A co-op run generalises it:
- **The slot owns the run; members are listed on it.** Give each member a run tag and `dg.slot = k`. The ownership
  test becomes "is a member of slot k".
- **The clock is on the slot** (`#s<k> dg.clock`), so it is one clock by construction.
- **The bossbar's `players` is the members.**
- **Pause:** rate 0 only while **every** live member is in a dungeon fight. Otherwise a player idling in a fight
  freezes the clock for a partner who is free to walk.
- **Resources:** the slot's count (2.1).
- **Death:** one member's death ends that member's run and leaves the partner's. The run ends when the last member is
  gone. Timeout kills every member.
- **Boss fights in co-op:** each player fights their own NPC, the arena's per-player pattern. Two players in one
  battle against one NPC is **OPEN** (`docs/mechanics/NETHER_DUNGEON_SCOPE.md` X5, relayed). A co-op test needs the
  second account (`docs/STATE.md:182`).

**How many simultaneous instances.**
- **Space:** the pocket shares the overworld border, x and z -1024..9215 (`data/entei_boss.json` `pocket.border`,
  relaying `docs/world-building/DIMENSIONS_AND_BORDERS.md:31-35`), and y 0..255 (`data/portals.json`
  `pocket.generator`). Take out the rescue box, Entei's row and a 32-block margin. With z rows from 1024 to 9183 at
  128 spacing, that is 63 rows. Each row holds four 2,048-long runs across x, so **about 250 instances of a
  2,000-block run.** Space is not the limit.
- **Load:** a chunk loads only near a player or under `forceload`. An idle slot costs nothing.
  - A live slot costs the same chunks the player would load in the overworld, plus the keeper's commands.
  - A rebuild needs its chunks force-loaded. A 2,000 x 32 strip is 125 x 2 = 250 chunks, under the 256-per-add limit
    (`tools/function_limits.py:45`, VERIFIED (repo)).
- **So the cap is a design number:** slots per dungeon. The group is a few friends, and Entei uses 4.

---

## 7. The portals

### 7.1 "The ultra beast pack": not installed

**VERIFIED:** no jar in the server snapshot and no datapack has an entry matching wormhole, ultra space, `ultra_portal`
or rift. Searched:
- all 98 jars in `mods/`;
- `COBBLEVERSE-DP-v31.zip`, whose only Ultra entry is `data/cobblemonraiddens/tags/raid/boss/ultrabeast.json`;
- the snapshot's other datapacks.

"Ultra Wormhole" appears only in Cobblemon's Pokedex lang text. The Ultra Beasts themselves come from Cobblemon and
COBBLEVERSE-DP, with no portal (`docs/research/notes/ultra-beasts-1.8.0.md`). Mega Showdown's "Ultra" entries are
Ultra Necrozma and Ultra Burst. cobblemon-additions has none.

**Two uninstalled mods match the phrase** (web listings, 2026-10-08, relayed; no jar read):
- **"Cobblemon Ultra Beasts"**: a wormhole appears near a player on a timer. Walking in leads to an "Ultra-Space"
  dimension where one of ten structures is built with its Ultra Beast. It is listed for MC 1.21.1 and Cobblemon 1.8.0
  ([moddex](https://moddex.gg/mod/cobblemon-ultra-beasts),
  [modpackindex](https://www.modpackindex.com/mod/84580/cobblemon-ultra-beasts)).
- **"Cobblemon Ultra Wormholes"**: server-side timed raid events against a shared Ultra Beast
  ([CurseForge](https://www.curseforge.com/minecraft/mc-mods/cobblemon-ultra-wormholes/files/7882626)).

Either is a **new dependency** (CLAUDE.md principle 9). The first brings its own dimension and structure rules, which
would compete with ours (timer, slots, sweeps). **The owner must say which pack was meant before anything is built
on it.** Without it, 7.2 and 7.3 are the options.

### 7.2 Installed nearest: LegendaryMonuments' distortion portal entity (visual only)

VERIFIED, `github/jorgaomc/entities/DistortionPortalEntity.class`, entity id `legendarymonuments:distortion_portal`
(`ModEntities`):
- **It is an entity, not a block.** It extends `Entity`, its dimensions are 3 x 3, and it cannot be damaged
  (`method_5643` returns false). Its box is its position plus or minus 1.5 on every axis (`method_33332`).
- **Its destination is hard-coded.** Every 5 ticks (`age % 5 == 0`), on the server, every `ServerPlayer` whose box
  intersects it is teleported:
  - from the Distortion World, to their respawn point (`teleportToOverworldSpawn`);
  - from anywhere else, **to `legendarymonuments:distortion_world` at their own block position**
    (`teleportToDistortionWorld`; the key is a static final).

  Nothing in a datapack changes the destination.
- The client draws its animated model and particles (`DistortionPortalEntityRenderer`, `distortion_portalAnimation`;
  client particles every 3 ticks). LegendaryMonuments is world-critical and in the client pack (CLAUDE.md).

**Using it as our rip:**
- Summon it inside a sealed **3 x 3 x 3 of barrier blocks**, so no player's box can intersect its own. That AABB
  intersection is strict, so touching a face does not count (ASSUMED, G1).
- Put our trigger in front of it: an interaction entity click (the proven arch click, EXP-034, as Entei's arch uses
  via `tools/portals.py`), or a keeper proximity test.
- **The risk is a trap.** One gap in the seal sends a player to the Distortion World at the same x, y, z, which may be
  open void or the inside of an island. This is a world-critical mod's dimension that we do not otherwise use
  (`docs/research/notes/cobbleverse-legendary-structures.md:219` refuses the island). **Recommend it only if the owner
  wants that look**, with the seal audited.

### 7.3 Vanilla-built rip (recommend)

- **The frame:** crying obsidian, or a Rift palette block.
- **The visual:**
  - the keeper re-emits `particle minecraft:reverse_portal`, `minecraft:portal` or `minecraft:dragon_breath` in the
    opening (vanilla);
  - or Cobblemon's own `bedrockparticle` (`command/BedrockParticleCommand.class`, VERIFIED as a class; its syntax is
    not read);
  - `block_display` entities for a torn edge.
- **The trigger:** an interaction entity click (EXP-034) or proximity.

Nothing teleports by itself, so nothing can misroute. **Never use the vanilla `nether_portal` or `end_portal` blocks
as decoration.** They teleport on their own: to the Nether after 80 ticks of standing in one, and to the End at once.

### 7.4 Static or random

- **Static:** authored sites, each a `data/placements.json` record, with ground from the heightmap (CLAUDE.md, "Ground
  comes from the heightmap"). Enter by click. Built by a re-apply step, as Entei's room is (R16Q,
  `tools/entei_boss.py:35`).
- **Random: a scheduler over authored candidates.** Never truly random: every candidate is a validated site.
  - A keeper chooses one with `random value 1..N`, the vanilla 1.20.2+ command used by the cave restore
    (`tools/mining_caves.py:778`, VERIFIED (repo)).
  - It force-loads the site's chunk, places the rip, and records an expiry score that counts down, as in 1.1.
  - On expiry it removes the rip and un-force-loads. Entities persist in unloaded chunks, so the removal needs the
    chunk loaded.
  - **How a player finds a random one:**
    - a server-wide `tellraw` with the coordinates;
    - optionally a lodestone compass, `give` with a `minecraft:lodestone_tracker` component holding the target and
      `tracked:false` (vanilla 1.21, ASSUMED until G2);
    - a chat waypoint for Xaero's map is ASSUMED (not read in `docs/research/notes/xaero-map-effects.md`).
  - **The cost:** the scheduler, an expiry, chunk loading per site, and a validator proving every candidate is clear
    of towns, legs and water (the shrines tool's refusal-based clearance is the pattern,
    `docs/research/notes/cobbleverse-legendary-structures.md:236`, relayed).

---

## 8. Instancing: building and resetting a 1,000-2,000-block run

**Constraints (VERIFIED (repo), `tools/function_limits.py:9-18` and `:41-45`):**
- `fill` and `clone` are refused above 32,768 blocks;
- `forceload add` is refused above 256 chunks;
- the command chain is 65,536 per function run;
- a write into a chunk not force-loaded does nothing, and says nothing.

**The pocket's contents do not survive a re-export.** They live in the world folder, so they are rebuilt from
functions (`docs/STATE.md:240`, EXP-047). Whatever is built in the pocket must be a re-apply step or a build-on-entry
function. Entei's rooms are re-apply step R16Q.

**The scale:** a corridor 2,000 long with a 9 x 9 cross-section is 162,000 blocks before rooms, seams and dressing. It
crosses 125 chunks in its long direction.

| Approach | What it does | Cost per entry | Verdict |
|---|---|---|---|
| **Persistent shell, reset the mutables (recommend)** | Re-apply builds each slot's shell once: corridors, parkour, rooms. Adventure mode (2.3) means the player cannot change the shell. On entry, rebuild only what a run changes: seam blocks and their markers, doors and gates, the leg flags, the NPC and boss entities, the clock | A few hundred blocks and some entities, in the chunks being reset | Works. It is the cave restore's pattern (variants refilled into a fixed host, `tools/mining_caves.py:19-22`) and Entei's (a fixed room, a per-run spawn) |
| Full rebuild on entry (`docs/mechanics/DUNGEONS.md` 2.4) | Force-load the strip (about 250 chunks, one `forceload add` at most, or several), then `place template` or `clone` from a master copy in the pocket, in 32,768-block pieces (at least 5 `clone`s for the corridor alone), spread over ticks with `schedule`, then teleport | Around a million blocks at full dressing; the time is **not measured** | Works, but heavy, and every entry pays it. Measure it before choosing (XD1, `DUNGEONS.md` 7.4) |

**Notes for either approach:**
- **`place template`** with a datapack structure NBT is not limited to the structure block's 48^3. That limit is the
  block's UI. `huge-structure-blocks-fabric-1.1.6` is installed for authoring larger ones (ASSUMED, I1).
- **A slot is disjoint from the rescue box and from Entei's row,** and inside the border margin (section 6).
- **Every write function carries `# chunks-loaded-by:`** or force-loads, or `function_limits` refuses it.
- **The occupancy guard is mandatory.** A reset never runs on top of a player or a Pokemon: the cave rule,
  `tools/mining_caves.py:15-18`. A slot is reset on entry, when it is free by definition. But the keeper must also
  never reset a slot that some member still stands in.

---

## 9. The legendary at the bottom of the lake

- **Depth is already gated.** The water system gives vanilla air without a qualifying partner, then drown pulses of
  half the player's maximum health. Dive training plus a Dive-capable party member gives unlimited air
  (`docs/mechanics/DEATH_AND_WIPE.md:32-38`, rules 9-10). It runs in the pocket with no dimension filter (5).
  Drowning is an environmental death, a blackout, and the run ends.
- **The encounter is Entei's pattern:**
  - `spawnpokemonat` by macro (`tools/entei_boss.py:615-618`);
  - bind by species, tag and `PersistenceRequired`, with a leash;
  - catchable once, then `uncatchable` (`data/entei_boss.json` `props`).

  A catch-mode legendary is a key boss: only a Beast Ball (`data/key_ball.json`, relayed in `DUNGEONS.md:225-228`).
- **"Make it obvious":**
  - `effect give <the entity> minecraft:glowing infinite 0 true`: the outline draws through water and blocks for every
    player (vanilla);
  - a beacon whose beam rises from the lakebed. The pocket has a skylight (`data/portals.json` `has_skylight`);
    whether the beam shows through water is ASSUMED (L1);
  - sea lanterns or glow lichen on the bed;
  - a bubble column above the spot;
  - keeper particles (`minecraft:glow` or `minecraft:end_rod`) rising from it.
- **ASSUMED:** that a battle starts and runs normally with the player underwater (L2). Battles are positional, and a
  ball or send-out underwater goes through `raycastSafeSendout` (VERIFIED in `SendOutPokemonHandler`; behaviour under
  water not read).

---

## 10. What to prove before building (staging; designed by the builder, run by the main session)

| Id | Probe | Settles |
|---|---|---|
| P1 | `runmolang "q.pokemon.discard;" <player> <own sent-out Pokemon>`: does it vanish, and is the party Pokemon at the same HP and recallable? Repeat from a `pokemon_sent_post` callback | 4.2, the whole no-deploy leg |
| P2 | (disposable world, a throwaway Pokemon) `kill` an owned sent-out Pokemon: does it faint? | that `kill` is banned for a reason |
| B1 | A bossbar with `players` set, name re-set each second with score components; log out and in; clear | 1.2 |
| B2 | `kill @s` with a totem in the off hand; check the blackout fires once | 1.3 |
| B3 | Reaching 0 mid-battle: sudden death (wait for `in_battle` 0) versus `stopbattle` then `kill` | 1.3 |
| B4 | An NPC battle left idle for 10 minutes: does anything time it out? | 1.4, the pause cap |
| R1 | `minecraft.mined:minecraft.diamond_ore` with a wrong tool, the right tool, silk touch and in adventure with `can_break` | 2.1 |
| R2 | An item with `minecraft:can_break` for the seam ores, in adventure mode | 2.3 |
| S1-S4 | `set_npc_party` and `start_battle` argument shapes; whether `heal` reaches a live battle; a staged same-species party: order over 10 fights at two `skill` values; three of one species allowed | 3.2 |
| F1 | Teleport mid-fall and land: fall damage with and without `resistance 5` | 5 |
| G1 | A player pressing into a barrier-sealed distortion portal from all six sides is never moved | 7.2 |
| G2 | A lodestone-tracker compass to a coordinate | 7.4 |
| I1 | `place template` of a structure larger than 48^3 from a datapack | 8 |
| L1, L2 | A beacon beam through 20 blocks of water; a battle started underwater | 9 |
| XD1 | Reset time of one slot by both approaches in section 8 (already listed, `DUNGEONS.md` 7.4) | 8 |
| X5 | Two players and one NPC in one battle, or two NPCs side by side (needs the second account) | 6 |

**Not verified anywhere in this note:** that any of the above runs. Every VERIFIED line is a code or data read. None
of these mechanisms has been run for a dungeon, and only the arena's NPC loop has been run at all.
