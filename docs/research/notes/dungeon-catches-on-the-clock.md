# Catches on the dungeon clock: mark, ledger and remove-on-failure (Cobblemon 1.8.0)

**Question (the owner, 2026-10-09).** In a timed dungeon run, catching speeds the clock the way mining does
(`docs/mechanics/DUNGEONS.md` 3.3, D13). Catches are lost if the run is not cleanly exited, like escrowed rewards. Removing
a Pokemon is the most destructive thing the pack could do, so the system must **fail safe**: if it is not certain a
Pokemon was caught in this run, it keeps it. A Beast Ball catch of a dungeon legendary is anchored (kept on failure).

**Version and how it was read.** Cobblemon 1.8.0+1.21.1, Fabric. This session had **no shell**, so the jar
(`C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar`) was NOT
opened. Every source claim below is from the GitLab tag `1.8.0`
(`https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/<path>`), read through a
summarising fetch, so a function NAME is as reliable as a file listing and a behaviour is one reading away from
bytecode. Where an earlier note read the jar's bytecode, it is cited. **Nothing was run in game.** Paths below are
relative to `.../mod/common/`.

## Answers in brief

| # | Question | Answer | Label |
|---|---|---|---|
| 1 | Can a run catch be marked, durably? | **Yes, two ways**: a datapack-defined **mark** (`q.pokemon.add_marks`) and a **forced aspect** (`q.pokemon.add_aspects`). Both are saved with the Pokemon. `Pokemon.persistentData` exists but **no datapack, command or MoLang function reaches it** | VERIFIED names and persistence; NOT RUN |
| 2 | Can a marked Pokemon be removed by uuid, party or PC, touching nothing else? | **Yes**: `q.player.party.remove_by_id(uuid)` and `q.player.pc.remove_by_id(uuid)`, reachable from a function with `runmolang "..." <player>`. The commands `takepokemon` and `pctake` are slot-based and cannot do this safely | VERIFIED names; NOT RUN |
| 3 | Can catches be held and delivered on a clean exit? | **No, not intact, and not without a mod.** A catch is in the party before any callback sees it; there is no hold store and no give-from-NBT. A properties-string re-creation is lossy | VERIFIED (absence) |
| 4 | Nuzlocke, full party, PC, logout, crash, evolution, trade | Per-approach table in section 4. All fail toward **keep** under the recommended design except one residual (an emptied party), which needs a guard | mixed, see section 4 |
| 5 | Count toward the multiplier? | **Yes**: a `pokemon_captured` callback runs a function as the player that calls a twin of `greed/take` | VERIFIED hook; the function is new work |
| 6 | Beast Ball readable at the hook, anchoring certain? | **Yes**: `q.poke_ball.ball_type` is in the `pokemon_captured` context. Anchoring is best done by **never marking** a boss species, not by a second check | VERIFIED context; NOT RUN |

## 1. Identifying and marking the catch

### The hook: `pokemon_captured`

- **When it fires.** `EmptyPokeBallEntity.shakeBall`, success branch (`entity/pokeball/EmptyPokeBallEntity.kt`), in this
  order: discard the wild entity and the ball entity; `captureFuture.complete(true)`; `pokemon.caughtBall = pokeBall`;
  ball effects; **`party.add(pokemon.pokemon)`**; leash cleanup; **then**
  `CobblemonEvents.POKEMON_CAPTURED.post(PokemonCapturedEvent(pokemon.pokemon, player, this))`. So the Pokemon is
  **already in the party or the PC** when the callback runs, the entity is gone, and `caughtBall` is set. VERIFIED.
  https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/entity/pokeball/EmptyPokeBallEntity.kt
- **Context** (`api/events/pokemon/PokemonCapturedEvent.kt`): `pokemon` = `pokemon.struct`, `player` =
  `player.asMoLangValue()`, `poke_ball` = `pokeBallEntity.struct`, `item` = the ball's item. There is no cancel and no
  function list: it is a notification. VERIFIED.
- **Same path in and out of battle**, and for a Master Ball (the guaranteed branch still reaches `shakeBall`). VERIFIED
  by the key-ball note (`docs/research/notes/beast-ball-key-1.8.0.md` section 2, jar bytecode). Catches that do **not**
  pass through it: eggs, trades, gifts, `pokegive`, raid rewards. Those are never marked, so never at risk. That is the
  design's whitelist.
- **The repo already uses it three ways:** `tools/entei_boss.py:681-687` (species identifier plus `q.player.uuid`, then
  `execute as <uuid> at @s run function ...`), `tools/hoopa_cradle.py:280-286`, and `tools/blackout_pack.py:1112-1118`
  (`t.pk.id` as text, passed to a macro function). Its own comment: the entity is gone by then, so match the Pokemon by
  uuid (`blackout_pack.py:554-556`). None of them has been run on a catch in a real run of a dungeon.

### What a Pokemon carries, and what can be written from a datapack

`pokemon/Pokemon.kt` fields, VERIFIED from source: `uuid`, `persistentData: CompoundTag` ("Arbitrary data compound";
internal setter), `originalTrainer: String?` ("The Minecraft UniqueID of a Player" or a fake-OT display name),
`originalTrainerType`, `caughtBall`, `tradeable`, `nickname`, `forcedAspects: Set<String>`, `marks: MutableSet<Mark>`.
**There is no met-location, met-date or received-time field.** `PlayerPartyStore.add` sets the original trainer to the
catching player if none is set (`api/storage/party/PlayerPartyStore.kt`), so OT is the player and carries no run.

| Channel | Writable from a datapack? | Survives | Verdict |
|---|---|---|---|
| **Mark** (`Pokemon.marks`) | **Yes**: `q.pokemon.add_marks('<id>')`, `has_mark`, `remove_marks` (`api/molang/function/PokemonMoLangFunctions.kt`). A mark is a datapack JSON in the `marks` registry (`api/mark/Marks.kt`: `JsonDataRegistry`, `resourcePath "marks"`, server data, synced to clients). Fields (`api/mark/Mark.kt`): `name`, `description`, `title`, `titleColor`, `texture`, `replace`, `group`, `chance` (default 0, so never randomly rolled), `indexNumber`, `aspects`, `sortOrder` | PC, party, restart (the codec saves it), `clone()` (round-trips the codec), trade (the same object moves, `TradeManager.performTrade`, per `sketch-cap-1.8.0.md` section 4). **Nothing clears marks on evolution or form change** (`Pokemon.kt`: the species and form setters do not touch marks) | **Recommended, as the second key.** Visible in the summary screen (an advantage: the player can see their catch is at stake). `exchangeMark` posts no event and syncs to the client |
| **Forced aspect** (`forcedAspects`) | **Yes**: `add_aspects` / `remove_aspects` (same file) | Saved (`ForcedAspects`, `PokemonP3`, jar, `sketch-cap-1.8.0.md`) | Invisible, server-side, can carry a string such as a run number. Whether the client ignores an unknown aspect is ASSUMED. A usable alternative; harder to test than `has_mark` because the struct offers only `aspects` (an array), not a containment test |
| `persistentData` | **No.** Not in the Pokemon MoLang function list, not a `PokemonProperties` key, not in any command. Only `Pokemon` and the codecs read it (jar grep, `sketch-cap-1.8.0.md` section 1, which this session's function list agrees with) | n/a | Ruled out |
| `originalTrainer` / `ot` | `apply('ot=...')` (a `PokemonProperties` key, `api/pokemon/PokemonProperties.kt`) | saved | **Rejected**: it overwrites the real OT, which the player sees and which cannot be restored from the Pokemon alone |
| `dmax_level`, `nickname`, `friendship`, `tradeable` | properties keys, applied and matched | saved | Rejected as marks: each is a value the player or another system owns (`dmax_level` is already the Sketch counter, `sketch-cap-1.8.0.md`) |
| `uuid` | read only (`q.pokemon.id`, a string) | permanent | **The identity.** A uuid is never reused |
| Species features | A feature needs a species assignment; a global flag would need one per species | | Rejected as heavy |

`PokemonProperties` has **no `uuid`, `marks`, `aspects`, `persistent` or `uncatchable` key** of its own
(`PokemonProperties.parse`), so `find_by_properties` cannot select by mark or by uuid. Selection by uuid is
`find_by_id`.

### Certainty: what "caught in this run" means

A catch is certain only when **three independent facts agree**:

1. the callback fired for it (so it was a thrown-ball capture, not an egg, trade or gift);
2. the thrower was in a live run at that moment: the dungeon tag on the player and `dg.st == 3`
   (`tools/dungeon.py:75`, "3 clock running"), exactly the gate `greed/take` uses (`tools/dungeon.py:899`);
3. the ledger entry and the mark both exist and name the same run, `dg.run` (`tools/dungeon.py:77`, "the run's number;
   #runs dg.run the last given", so a run number is not reused. ASSUMED monotonic across a re-export; check `#runs` is
   carried).

If any one is missing the Pokemon is unmarked and **kept**. Every failure of the marking path (the callback does not fire,
a MoLang error, a macro that does not parse) leaves a Pokemon unmarked. The marking path can therefore only err toward
keeping. That is the whole fail-safe argument for this half.

## 2. Removing a marked Pokemon

**Mechanism.** `PokemonStoreMoLangFunctions` (`api/molang/function/PokemonStoreMoLangFunctions.kt`) is attached to
**both** `PartyStore.asMoLangValue()` and `PCStore.asMoLangValue()` (`api/molang/MoLangFunctions.kt`). It provides
`find_by_id(uuid)` (a struct, or `0`), **`remove_by_id(uuid)`** (the store's remove result, or `0`), `find_by_properties`,
`pokemon` (an array), `count`, `add(pokemon)`. `Player` MoLang has `party` and `pc` (`PlayerPartyFunctions` list in
`PlayerMoLangFunctions.kt`: "Returns the player's party/PC as a struct"). VERIFIED.

- `remove(pokemon)` (`api/storage/PokemonStore.kt`): returns false if the Pokemon is not at the store coordinates it claims;
  otherwise `recall()`, clears the slot, drops it from the uuid index, returns true. **It does not destroy the object, post a
  release event or return a held item.** `PartyStore.remove` adds a client packet. No battle check anywhere. VERIFIED.
- **From a function:** `runmolang "<script>" <player>` binds `q.player` (`command/RunMolangCommand.kt`; permission
  `RUN_MOLANG`; a fresh runtime; errors are printed to the log and swallowed, the command still returns success). The repo
  already uses this shape in game-proven form (`tools/arena_runtime.py:725,1115`). Passing a uuid goes through a macro, as
  `blackout_pack.py:548-562` does for `pid`. `q.run_command` runs as the server, without an entity
  (`api/molang/function/GeneralMoLangFunctions.kt`).
- **Why not the commands.** `takepokemon <player> <slot>` is party-only, 1-based by slot, and "the Pokemon is removed ...
  before the runner's party is checked" (`command/TakePokemon.kt`). `pctake <player> <box> <slot>` removes by position
  (`command/PcTakeCommand.kt`). A slot is a guess: it shifts when the player rearranges. Neither takes a uuid. Not used.

**Safe order for one removal (all NOT RUN; MoLang syntax ASSUMED):**

```
t.p = q.player.party.find_by_id('<pid>'); (t.p == 0) ? { t.p = q.player.pc.find_by_id('<pid>'); };
(t.p != 0 && t.p.has_mark('cobblers:rift_held') && q.player.in_battle == 0) ? { ... };
```

then return the held item to the player (`t.p.held_item`, `q.player.give_item(item, 1)`, `t.p.remove_held_item()`), verify
the held item is now empty, and **only then** `remove_by_id` from the store that held it. If any step cannot be confirmed
the Pokemon is left alone.

**What can go wrong, each with its safe side:**

| Hazard | What happens | Safe? |
|---|---|---|
| Wrong slot | Not possible: removal is by uuid | yes |
| Pokemon moved between party and PC | `find_by_id` is tried on both stores | yes |
| Pokemon given away (trade) | not found in either store: nothing happens, the partner keeps it | yes (laundering, see section 4) |
| Pokemon released by the player | not found: nothing happens | yes |
| Malformed or unknown uuid | `find_by_id` parses a `UUID`; a bad string throws, the script dies, the command swallows it | yes |
| Held item | `remove` does **not** return it (above). It would be deleted with the Pokemon. Return it first and refuse if it is not empty afterwards | only with the guard |
| **The party would be empty** | A player who put only catches in the party and the originals in the PC has no usable party after removal | **No.** Needs a guard: before removing, if no unmarked Pokemon is in the party, move one from the PC (`party.add` removes it from its old store first, `PokemonStore.add`), or skip. Skipping lets a player dodge the stake by filling the party with catches, so move |
| Party and PC both full at capture | `party.add` returns false and the capture code ignores the result (`EmptyPokeBallEntity.kt`), so the Pokemon is stored nowhere (a Cobblemon behaviour, not ours) | n/a: not found, nothing to remove |
| In a battle | `remove` has no battle check | the engine already kills a player only after the battle (`DUNGEONS.md` 2.5); also test `q.player.in_battle == 0` |

## 3. Holding catches instead

**Verdict: not possible intact in 1.8.0 without a mod.**

- **A catch cannot be stopped from entering the party.** `party.add` runs inside `shakeBall` before the event posts, and
  `pokemon_captured` has no cancel. The only veto is `poke_ball_capture_calculated` with `q.set_shakes(0)`, which makes the
  throw fail, so there is no catch at all (`beast-ball-key-1.8.0.md` section 3). VERIFIED.
- **No holding store.** `Player` MoLang reaches only that player's own party and PC. There is no function to open another
  store, to build a Pokemon from NBT, or to serialise one. `givepokemon` and `givepokemonother` take a **properties
  string** (`command/GivePokemon.kt`, `PokemonPropertiesArgumentType`), and `PokemonProperties` has no NBT or uuid key.
  The `GetNBT` command only reads. VERIFIED (absence in the listed files; the 58 command files were listed, no
  restore-from-NBT command is among them).
- **A properties-string copy is lossy.** It can carry species, form, level, gender, shiny, nature, ability, nickname,
  pokeball, friendship, held item, moves, IVs, EVs, tera type, dmax, gmax, scale, OT and tradeable
  (`PokemonProperties.parse` key table). It cannot carry the uuid, marks, current HP and status, experience inside a level,
  PP, benched moves, features and aspects, the cosmetic item, hyper-trained IVs, or `persistentData`. "Given back intact"
  fails. It also puts the only copy in a string in our storage while the real Pokemon is deleted, so a crash, a lost
  macro or a player who never returns is a **permanent loss**: the default is delete.
- `PokemonStore.remove` does not destroy the object (section 2), and a MoLang struct could hold it in a variable, but
  nothing persists a variable across a restart. Rejected.

## 4. Edge cases, per approach

A = **mark + ledger + remove-on-failure** (recommended). B = **hold and re-give** (section 3). C = **diff the party before
and after** (rejected: it would also delete gifts, hatches and trades). D = **slot commands** (rejected).

| Case | A (mark + ledger) | B (hold) |
|---|---|---|
| **Nuzlocke** (`docs/mechanics/NUZLOCKE_ZONES.md`, `data/nuzlocke_zones.json`) | No code enforces Nuzlocke (`docs/STATE.md` lists "Nuzlocke handling" as open; the zones only drive titles). A dungeon is not one of the 72 zones, so a catch there is outside the "first encounter in a zone" rule, and losing it on failure fits the style. **Owner decision**: whether dungeon catches count as a Nuzlocke catch at all. Nothing collides mechanically | same |
| **Full party** | `party.add` overflows to the PC (`PlayerPartyStore.add`: `overflow_to_pc`, event still posted). `find_by_id` searches both stores, so a PC catch is found. Both full: not stored, nothing to lose | the held copy returns by `party.add`, which overflows the same way, but returning at an inconvenient time fails silently |
| **PC** | Found by uuid in any box | n/a |
| **Logout mid-run** | The run goes on (DUNGEONS.md 2.6). The ledger and marks persist. If the run died while the player was away, the removal must wait for them: **MoLang cannot reach an offline player's stores**, so a "failed, not yet resolved" ledger entry is resolved on their first keeper pass back, in the same place as the dead-run check (`DUNGEONS.md:324-326`). Until then the Pokemon is kept | the held copy is stuck until return |
| **Server crash** | Ledger (command storage, world save) and the Pokemon (player data) save on different schedules. Mark without ledger: kept. Ledger without Pokemon: `find_by_id` returns 0, nothing happens. An old entry only matches its own run number. Every skew resolves to keep | a crash between "removed from the party" and "stored" loses the Pokemon |
| **Evolution in the run** | The same object is evolved in place (`Evolution.forceEvolve` -> `result.apply(pokemon)`, `api/pokemon/evolution/Evolution.kt`), marks are untouched, so the evolved Pokemon is still removed on failure along with its experience. The uuid is not reassigned in the code read (not proven, see experiments). The Shedinja `shed()` copy is a `clone()` that copies marks but has no ledger entry, so it is kept. **Optional guard**: store species and level in the ledger and keep a Pokemon whose species has changed. Owner's call; it is destructive either way | the copy is stale |
| **Trade with a co-op partner** | `TradeManager.performTrade` moves the same object between **parties** only and re-checks membership. The partner now holds a marked Pokemon with no ledger entry for them: **kept**, and the original owner's removal finds nothing. That launders a catch to a friend. Whether `tradeable=false` blocks a trade is **not established**: `TradeManager.kt` has no `tradeable` check in the code read, and `tradeable` is only copied in `Pokemon.kt` (the check, if any, is elsewhere). `trade_event_pre/post` are callbacks (`events/CallbackHandler.kt`), but callbacks cannot cancel. Accept laundering (a trade is friends sharing) or add a `trade_event_post` handler that moves the ledger entry | ignores it |

## 5. Counting toward the multiplier

`greed/take` (`tools/dungeon.py:896-902`) is "as a member whose clock runs": it returns 0 unless `dg.st == 3`, adds 1 to
`dg.greed`, and calls `greed/rate`, which maps the count to the ladder (D13) and never lowers the rate. The catch needs a
**twin**, `greed/catch`: same gate, add a weight, call the same `greed/rate`. The `pokemon_captured` callback calls it:

```
'Generated; NOT RUN. A catch in a live run (a Pokemon the engine can mark), counted once.'
t.id = q.pokemon.species.identifier;      -- as entei_boss.py:684
q.run_command('execute as ' + q.player.uuid + ' at @s run function cobblers:dungeon/catch {pid:"' + q.pokemon.id + '"}');
```

The function (mcfunction) does the gate, the ledger append, and the call to `greed/catch`; the mark is added in MoLang
only if the function reported the gate passed (read back as a player tag, the pattern in `level-cap-catch-block.md`
section 2, ASSUMED synchronous).

- **Keep a separate score** (`dg.catch`) and give `greed/rate` an effective count, so the bar's "taken N" (`dungeon.py:1227`)
  stays the seam's. The weight (one catch = k blocks) is the balance designer's. Ten Larvitar at k = 1 reaches the x1.5 step.
- **A catch can only speed the clock.** The multiplier holds once reached (D13), so releasing a catch does not refund it.
- **Gate it on `dg.st == 3`**: a catch in the entry room, the tail or after the clean exit is unmarked and kept.
- Both the greed count and the ledger entry are written by the same function, so they cannot disagree.

## 6. Beast Ball anchoring

- **The ball is readable at the hook.** `poke_ball` in the `pokemon_captured` context is `pokeBallEntity.struct`; that struct
  carries `ball_type` (`cobblemon:beast_ball`) and is the same struct the key-ball callbacks compare
  (`tools/key_ball.py:160,171`; `beast-ball-key-1.8.0.md` section 3, jar bytecode). `q.pokemon.pokeball` also returns the
  caught ball as a string (`StringValue(pokemon.caughtBall.toString())`), but its format was not read; prefer `ball_type`.
- **The tag is not readable at the hook.** The Pokemon struct has no `has_tag`; the entity (and its `cobblers.key_boss`
  tag) is discarded before the event (`shakeBall` order, section 1). So an anchor cannot test the tag.
- **Recommended anchor: do not mark a boss species.** The callback has the species identifier (`entei_boss.py:684`). A
  species in the dungeon's boss list (`data/key_ball.json` `bosses`, `DUNGEONS.md:515`) is never marked and never
  ledgered, so no removal path can name it. Anchoring becomes an **absence**, which is the strongest kind. The ball adds
  nothing: the key-ball refuses every non-Beast ball at a tagged boss, so a boss catch is a Beast catch by construction.
  If the key ball ever failed and a Master Ball caught a boss, it would still be unmarked, and so kept. Wrong in the
  keep direction.
- **Anchoring by ball alone** (any Beast Ball catch anchors) would let a $5,000 ball bank a Larvitar at a x1 rate: a
  deliberate insurance price. That is a design choice, not a leak, but it dilutes the stake; the owner's wording says
  "dungeon legendary", which the species list expresses exactly.

## Recommendation

**Approach A: a datapack mark, a per-run ledger keyed by Pokemon uuid, removal by uuid on failure only, with the held-item
and empty-party guards.** Concretely:

1. `pokemon_captured` calls a function as the player. The function gates on the live run (`dg.st == 3`, the run tag),
   skips boss species (the anchor), appends `{player, run: dg.run, pid}` to a storage ledger, adds weight to the greed
   count, and reports success. Only then does MoLang call `q.pokemon.add_marks('cobblers:rift_held')`.
2. Clean exit: `remove_marks` for the run's ledger entries (found by uuid, not found = skip) and clear them.
3. Failure (death, timeout kill, dead-run on return): for each entry whose run number is **the failed run's own**, and only
   if the Pokemon is found, still marked, out of battle, and its held item has been returned, `remove_by_id`. Entries of
   other runs are cleared as kept.

Why the other approaches lack the fail-safe property:

| Approach | The property it lacks |
|---|---|
| **B** hold and re-give | Its default is **removed**; keeping depends on a later step succeeding. A crash, a logout or a bug is a permanent loss, and the copy is lossy (section 3). |
| **C** diff the party before and after | It cannot tell a run catch from a gift, a hatched egg or a trade; it deletes on a guess. |
| **D** `takepokemon` / `pctake` by slot | It addresses a position, not a Pokemon: a rearranged party removes the wrong one. |
| Mark by `ot` or nickname | It destroys information it cannot restore. |
| Mark alone, no ledger | A single key. A bug in marking (a mark left from an earlier run) becomes a deletion. Two keys, run number and uuid, are both required. |
| Ledger alone, no mark | Same, from the other side. Cheap to keep both, and the mark is visible to the player. |

The one residual that is not fail-safe by construction is the **emptied party**, which needs the guard in section 2, and
the **held item**, which needs the return-and-verify step. Both are scripts to build and prove, not unknowns in the API.

## Repository disagreements found

- `docs/mechanics/DUNGEONS.md:266-269` lists "a caught Pokemon" among what escrow does **not** hold, `:283` says a death
  line "Kept: everything you mined and picked up, and any catch", and `:335` says a dead-run return keeps "any catch".
  The owner's idea reverses all three for catches made **during a run's clock**; the document needs the new rule.
- `docs/mechanics/DUNGEONS.md:481` says the den's Pokemon are `uncatchable`; the idea needs a catchable nest, which
  `data/spawns.json` and the level-cap pack (`level-cap-catch-block.md`: over-cap targets are refused) must both allow. A
  Larvitar nest above the thrower's cap cannot be caught at all. Check against the cap before designing the nest.

## Unknown / experiment candidates (also added to `EXPERIMENT_BACKLOG.md`)

All on staging, never live, one player, a probe pack; each needs the jar's MoLang dialect, which the repo's callbacks have
only partly exercised.

1. `pokemon_captured` fires for a catch in and out of battle; `q.pokemon.add_marks('<ns>:<id>')` returns 1 for a mark
   defined in a datapack under our namespace (the registry key is the file id; whether a non-`cobblemon` namespace
   resolves through `asIdentifierDefaultingNamespace` is ASSUMED); the mark survives a relog, a PC move, a restart and an
   evolution; the summary screen shows it without a client pack (the `texture` can point at an existing
   `cobblemon:textures/gui/mark/...` file, ASSUMED to render; the `name`/`description` strings are lang keys).
2. `runmolang "..." <player>` evaluates `q.player.party.find_by_id`, `q.player.pc.find_by_id` and `remove_by_id`, with the
   `0` test on a struct and `!=` (the beast-ball note found `!=` untested in Cobblemon's dialect; `==` and nesting are the
   proven forms), and the client's box and party refresh after a removal.
3. The held-item chain: `held_item` -> `give_item` -> `remove_held_item` -> emptiness check.
4. The empty-party rescue: `party.add(pc pokemon)`.
5. Evolution keeps the uuid; the Shedinja clone is marked but not ledgered.
6. Whether `tradeable=false` blocks a trade (`apply('tradeable=false')`), and the `trade_event_post` context.
7. Crash skew: kill the server between the catch and a world save; resolve both orders to keep.
8. `dg.run` is monotonic across a re-export (`#runs`).
9. Reconcile the idea with the level cap and the Nuzlocke owner decision before building.

**Cost to build** (the repo's terms, estimate not measured): one narrow builder with a shell for the callback, the function
pack, the ledger and the probes, about 2.6M, plus an independent audit on `opus` (it can destroy a player's Pokemon, so
escalation rule 1 applies), about 3M, plus the staging proof.
