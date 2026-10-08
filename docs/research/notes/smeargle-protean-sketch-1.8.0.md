# Smeargle as a sixth starter: Protean, Sketch and the numbers on Cobblemon 1.8.0

**Status:** research only (2026-10-08). Nothing built, no data changed. The owner decides.
**Read:** the snapshot jar `C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar`
(never the live runtime), and `rctapi-fabric-1.21.1-0.16.1-beta.jar` from the same folder. Showdown paths below are
inside the jar's `data/cobblemon/showdown.zip`; Kotlin "offsets" are `javap -c` bytecode offsets.

## 0. Which Showdown runs (VERIFIED)

The jar carries two Showdown copies. The one battles run is `data/cobblemon/showdown.zip`:
`GraalShowdownUnbundler` unzips `/data/cobblemon/showdown.zip` (gated by `showdown.json`, `"showdownVersion": 18`, and
the config getter `getAutoUpdateShowdown`) into `./showdown`, and `GraalShowdownService` loads `showdown/index.js`,
whose first lines are `require('./sim/battle-stream')` and `require('./sim/cobblemon/cobblemon')`.
`assets/cobblemon/showdown/node_modules/pokemon-showdown/` (package.json `"version": "0.11.7"`) is a second copy that
this loader does not use.

**Finding, not fixed:** `tools/battle_sim.py:107` reads moves and the type chart from the node_modules copy, not the one
that runs. 24 moves differ between them (newer moves missing; e.g. Grassy Glide 60 vs 55, Luster Purge and Mist Ball
70 vs 95). It moves no number here: none of the 24 is in any Smeargle moveset below. Both copies' Protean is the
Gen 9 one.

## 1. Protean and Libero: the Gen 9 version (VERIFIED)

**The format.** `BattleFormat.GEN_9_SINGLES` is built with the default-argument mask 25 (bits 1, 8, 16):
`mod` defaults to `ldc "cobblemon"` and `gen` to `bipush 9` (`BattleFormat(String, BattleType, Set, int, int, int,
DefaultConstructorMarker)`, offsets 7 and 43; static init offset 51 `bipush 25`). All five built-in formats are
`GEN_9_*`. `data/mods/cobblemon/scripts.js:25` is `inherit: "base"`, and `data/scripts.js:25` is `gen: 9`.
`config/custom-formats.js:29-33` names "Cobblemon Singles" with `mod: "cobblemon"`. `data/mods/cobblemon/` has no
Protean, Libero or Sketch override (grep). So the base `data/abilities.js` applies.

**Protean**, `data/abilities.js:3513-3534`:

```js
  protean: {
    onPrepareHit(source, target, move) {
      if (this.effectState.protean)
        return;
      ...
      if (type && type !== "???" && source.getTypes().join() !== type) {
        if (!source.setType(type))
          return;
        this.effectState.protean = true;
    ...
    onSwitchIn(pokemon) {
      delete this.effectState.protean;
```

Once per switch-in, then locked until it switches out and back. The Gen 6-8 version, which changes type on every
move, is in `data/mods/gen8/abilities.js:768-780` (no `effectState` check). Cobblemon's format does not load it.
Cobblemon's own text agrees: `assets/cobblemon/lang/en_us.json`, `cobblemon.ability.protean.desc` says it "works only
once each time the Pokémon enters battle".

Details that matter in play:
- The lock is set only when the type actually changes. A Normal move used while Normal does not spend it.
- Status moves count too. The hook is `onPrepareHit`, so a Spore used first turns Smeargle Grass for the whole stay.
- Battle start counts as a switch-in, so the lock resets every battle. Switching out and back in also resets it, at
  the cost of a free hit.

**Libero**, `data/abilities.js:2349-2370`: the same code with `effectState.libero`. It behaves identically and is
no better a fit. Both are registered abilities (`cobblemon.ability.protean` and `.libero` in `en_us.json`).

## 2. Sketch: implemented, and the copy is permanent (VERIFIED)

**In battle**, `data/moves.js:17465-17512`. `onHit` takes `target.lastMove` and fails on:
- a transformed user;
- a move the user already knows;
- `noSketch`, Z and Max moves.

Otherwise it writes the copy into both `source.moveSlots` and `source.baseMoveSlots` at Sketch's index, with full PP,
and emits `-activate ... move: Sketch`. Sketch has `pp: 1, noPPBoosts`. No Sleep Clause applies: the format rules are
`Obtainable, +Past, +Unobtainable` (`BattleFormat` static init), and `data/mods/cobblemon/rulesets.js` has no sleep
clause.

**Out of battle, on the real Pokemon.** `com/cobblemon/mod/common/battles/interpreter/instructions/ActivateInstruction`,
offsets 104-301: when the effect id is `"sketch"` and the Pokemon's moveset contains Sketch, it strips the move name
to `[^A-Za-z0-9]`, looks up both templates (`Moves.getByName`), and calls
`BattlePokemon.getEffectedPokemon().exchangeMove(sketch, copied)`.

`Pokemon.exchangeMove` (offsets 336-503 and `exchangeMove$lambda$4`):
- puts the copied move in Sketch's slot;
- **adds the old move, Sketch, to `benchedMoves`**;
- removes the copy from the bench.

`Pokemon.getAllAccessibleMoves` is the form's `getLevelUpMovesUpTo(level)` plus `benchedMoves`. So Sketch is always
re-slottable, both because it is benched and because Smeargle's learnset is `1:sketch`
(`data/cobblemon/species/generation2/smeargle.json`). Every copied move stays on the bench for good. **Sketch is
unlimited: one new move per use, renewable after every battle, and the copies accumulate.** A per-Pokemon cap of
10, built from a datapack, is costed in `sketch-cap-1.8.0.md`. That note also finds that Mega Showdown overwrites
13 files of the running Showdown, which section 0 does not account for.

**Which battles write through:**
- Cobblemon's `BattleBuilder.pve` and `pvn` pass their clone flag through from the caller.
- `pvp1v1` clones when its flag is set or `adjustLevel > 0`.
- RCT (`rctapi` `BattleManager.toBattleSide` and `toBattlePokemons`) clones the player's team only when the format's
  `getAdjustLevel() > 0` (offsets 14-76; a clone gets `BattleCloneProperty`). Cobblemon's default `adjustLevel` is
  `iconst_m1`, and nothing in our repo sets `adjustLevel` (grep). So Sketching a gym leader persists.

What I did not read: the RCT format provider's own `adjustLevel` (ASSUMED to be the default), and the wild-battle
caller's clone flag (ASSUMED false).

**In co-op this means every move any friend's Pokemon knows.** A PvP battle without level adjustment writes the copy
through too. So signature moves are reachable: Astral Barrage, Sunsteel Strike, Surging Strikes, and Spore from
Breloom. Not run in game.

**Smeargle in the jar:**
- 55/20/35/20/45/75, BST 250 (MEASURED);
- abilities `owntempo`, `technician`, `h:moody`;
- Normal type;
- no evolutions;
- moves `1:sketch` plus tutor, legacy and special entries only.

## 3. The numbers

**Method (MEASURED, a simulation and not reasoning).** This uses `tools/battle_sim.py`'s own `Mon`, `damage` and
`duel`, from a scratch script that changes nothing in the repo:
`smeargle_sim.py` in the session scratchpad, which monkeypatches `battle_sim`.
- IVs 15, no items.
- The opponents are the 16 Pokemon of gyms 6-8 (caps 45, 50, 55) plus the Elite Four and Champion (30 at 60 and 62),
  from `data/trainers.json`. The cap is the ace's level plus `relativeLevelCap` (0).

**Protean as modelled.** The attack that triggers it gets STAB and sets the type. Gen 9 then locks until reset. Gen
6-8 ("gen8") changes on every attack. One known lag: a foe's hit on the turn Smeargle changes type is computed
against the old type.

**Moves.** Four damaging moves, picked greedily per opponent team to maximise wins, then damage. That is a player who
re-tools before each fight, which Sketch allows. Pools:
- **fought** (used unless noted): every move a trainer below the cap carries, 83 moves at 45 and 108 at 60. This is a
  lower bound: wild Pokemon are left out.
- **any**: all 292 damaging moves the sim models honestly, the co-op ceiling.

Excluded from both, because the sim would give them free: recharge, charge turns, recoil, crash damage, self-KO, self
stat drops, lock-in, conditional failure, computed power, Foul Play.

**Metrics.**
- **duels**: wins of the 46, each 1v1 from full health. A fresh duel resets Gen 9's lock, so this is Smeargle
  switching in fresh to every foe.
- **solo**: Smeargle alone through each whole team, never switching. Gen 9 stays locked on its first type. Reported as
  foes downed, summed over gyms 6-8 and over the League.

The five use the native finals from 45, each with `tools/battle_sim.py`'s own `choose_moveset` over its native
learnset plus the authored pool, as `tools/mythical_starters.py measure` does. I also ran them through the same greedy
picker. That moved each line by 0 to 2 duels, so the picker is not what separates them.

**Base stats checked in the jar.** All five of the owner's figures are right: Urshifu 550, Silvally 570, Solgaleo
680, Melmetal 600, Naganadel 540. Lunala, the Cosmog line's other final, is also 680.

| Pokemon | BST | duels g6-8 /16 | duels League /30 | duels all /46 | solo g6-8 | solo League |
|---|---|---|---|---|---|---|
| Lunala | 680 | 14 | 24 | **38** | 7.4 | 11.7 |
| Solgaleo | 680 | 8 | 26 | 34 | 5.4 | 15.9 |
| Urshifu | 550 | 12 | 20 | 32 | 2.9 | 10.6 |
| Melmetal | 600 | 9 | 20 | 29 | 4.5 | 8.9 |
| Silvally | 570 | 11 | 16 | 27 | 3.6 | 7.8 |
| Naganadel | 540 | 10 | 12 | **22** | 4.7 | 9.1 |
| *band of the five* | | *8-14* | *12-26* | *22-38* | *2.9-7.4* | *7.8-15.9* |
| Smeargle native, Own Tempo | 250 | 0 | 0 | 0 | 0.9 | 1.5 |
| Smeargle shape, Gen 9 Protean | 400 | 7 | 8 | 15 | 2.7 | 5.2 |
| Smeargle shape, Gen 9 Protean | 450 | 8 | 13 | 21 | 2.9 | 6.4 |
| fast-mixed, no Protean | 400 | 5 | 8 | 13 | 3.1 | 5.7 |
| fast-mixed, no Protean | 450 | 6 | 11 | 17 | 3.3 | 7.2 |
| fast-mixed, Gen 9 | 360 | 9 | 8 | 17 | 2.7 | 5.2 |
| **fast-mixed, Gen 9** | **400** | 12 | 16 | **28** | 3.5 | **7.0** |
| fast-mixed, Gen 9 | 430 | 12 | 16 | 28 | 3.6 | 7.2 |
| **fast-mixed, Gen 9** | **450** | 12 | 17 | **29** | 3.6 | **8.4** |
| fast-mixed, Gen 9 | 480 | **15** | 20 | 35 | 3.8 | 9.3 |
| fast-mixed, Gen 9 | 520 | 16 | 25 | 41 | 5.9 | 10.3 |
| even, Gen 9 | 450 | 13 | 18 | 31 | 4.3 | 6.1 |
| fast-mixed, Gen 9, pool *any* | 400 / 450 | 12 / 12 | 17 / 20 | 29 / 32 | 4.0 / 4.5 | 7.7 / 9.6 |
| fast-mixed, Gen 6-8 (not what runs) | 400 | 12 | 16 | 28 | 3.5 | 8.9 |
| fast-mixed, Gen 6-8, pool *any* | 400 | 12 | 17 | 29 | 4.7 | 9.4 |

"fast-mixed" is the shape 80/85/65/85/65/105, scaled with `tools/mythical_starters.py`'s own `scale()`:
- 400 gives 66/70/54/70/54/86;
- 450 gives 74/79/60/79/60/98.

"Smeargle shape" scales the native 55/20/35/20/45/75.

What the table says:
1. **400 with Gen 9 Protean lands inside the band in duels:** 28 of 46, against 22-38, with a median of 30.5. It is
   12 of 16 at gyms 6-8, level with Urshifu. Protean is worth about +15 duels at the same stats (13 against 28 at
   400).
2. **It falls just below the band when it has to stay in.** Solo through the League, it downs 7.0 against the floor of
   7.8 (Silvally). That is the Gen 9 lock: one type for the whole team.
3. **450 is inside on every column:** 29 duels, 12 of 16 at gyms 6-8, 8.4 solo in the League (third-lowest of seven).
   **480 is too much**: 15 of 16 at gyms 6-8 beats every final, Lunala's 14 included. 520 beats them all everywhere.
4. **The spread matters more than ±50 BST.** In Smeargle's own shape (Attack and Special Attack 20 each), 450 is 21
   duels, below the band. Any form must move the points into the attacking stats.
5. **Gen 6-8 Protean would not change the duel count** (28 against 28): a fresh duel already gives Gen 9 its free
   type. It would show only when Smeargle stays in (8.9 against 7.0 solo in the League). The owner's fear, "400 with
   infinite type changes may be the strongest", does not arise: that version is not what runs.

**What the sim cannot see, and it all cuts Smeargle's way** (`tools/battle_sim.py:43-63`: no Protect, Substitute,
priority or secondary effects, and support moves only when no attack does damage):
- **Sketch's real edge is utility, not coverage.** Spore (100% sleep, Grass and powder immunities aside), then Shell
  Smash on the sleeping foe, is the classic line, and no Sleep Clause applies (section 2). The sim never plays it.
- Every final is handicapped the same way, but only Smeargle has the whole movepool to exploit.
- **So read 450 as the ceiling, not the target, until an in-game fight says otherwise.**

**Recommendation: about 450, fast-mixed (74/79/60/79/60/98).** Do not use Smeargle's native shape. Treat 400-450 as
the range and 480 as the line not to cross. The other two stages are not measured: the five's 330 and 430 stages were
not modelled here. Run them with the same script when building.

## 4. What a stat form and Protean would take (a-lite mechanism)

The mechanism is `tools/mythical_starters.py:292-302`, a `species_additions` form keyed by a forced aspect.
`addition()` today emits each form's `name`, `aspects`, `baseStats`, `moves` and `evolutions`.

**A form can carry its own abilities and types (VERIFIED).** `FormData` has `_abilities`, `_baseStats`, `_moves` and
`_primaryType`. The jar's own `data/cobblemon/species/generation1/raichu.json` form "Alola" (aspect `alolan`) sets
`abilities: ["surgesurfer", "h:surgesurfer"]`, its own types and a 485 total.

**The ability follows a form change (VERIFIED by reading).** `Pokemon.attemptAbilityUpdate` returns early for a
forced ability. Otherwise it re-maps the current ability by priority and index into the new form's `AbilityPool`, or
re-rolls it. So a form whose `abilities` are `["protean", "protean", "h:protean"]`, the pattern the mythicals use
natively (`beastboost`, `h:beastboost`), keeps Protean through every stage. Starting with Protean at level 5 is
ASSUMED: it needs the EXP-049 step 1 observation, that a starter with the aspect is created in the form.

**The work, by item:**
1. **Three forms, not two.** Smeargle has no evolution and its native "final" is 250. a-lite's "native final at 45"
   does not exist, so the 45 stage is a third form, and both 30 and 45 are **same-species** evolutions:
   - `smeargle unaspect=cobblers_starter_1 aspect=cobblers_starter_2`;
   - then `smeargle unaspect=cobblers_starter_2 aspect=cobblers_starter_3`.

   That is EXP-049 step 3, the link `NATIVE_STARTERS_COST.md:83` calls the riskiest, needed twice, and still not run.
   It also needs a new aspect, `cobblers_starter_3`.
2. **Data**, a seventh object in `data/mythical_starters.json` `lines`. Each stage needs `abilities`, `baseStats` (via
   `scale()` from the chosen shape) and `moves`.
   - The learnset must keep `1:sketch` in every form. `getAllAccessibleMoves` reads the form's learnset, and benched
     Sketch covers it after the first use.
   - There is no other movepool to author: Sketch is the movepool.
   - **Nothing in the form can stop Sketch copying a given move.** That is Showdown's `noSketch` move flag.
3. **The generator.**
   - `addition()` must emit `abilities`.
   - `check_evolution` (`:250-252`) requires the 45 result to be a native final species, and `measure()`
     (`:343-389`) assumes one. Both need a stage-3-form branch.
   - The audit hard-codes five lines, ten forms and `BST = {1: 330, 2: 430}`
     (`tools/mythical_starters_audit.py:62, 375, 434-438, 462`).
   - The starter screen check (`:276`) expects exactly five.
   - `battle_stress.py`'s starter-count arithmetic (`NATIVE_STARTERS_COST.md` section 5) changes again. 108 divides
     by six (18 each), but the 15-sized archetypes do not, so 24/18/18/18/15/15 needs re-totalling.
4. **Wild Smeargle are untouched.** The aspect gates the form.
5. **The only lever over specific moves is Showdown data.** The bundled data is unzipped from the jar and refreshed
   unless the config's `autoUpdateShowdown` is off (`GraalShowdownUnbundler`). Editing the server's `showdown/` folder
   (`noSketch` on Spore or Shell Smash) is possible in principle. That is ASSUMED and untested, and it is outside the
   datapack layer.

**Cost (ASSUMED, scaled from `NATIVE_STARTERS_COST.md` section 4):**
- the data and generator changes, about one session;
- the tests and the stress arithmetic, half a session;
- the shared experiment.

## 5. Is it worth doing

Yes, on the mechanics. Gen 9 Protean is what runs (`data/abilities.js:3513-3534`). Sketch plus Protean is therefore
one type per switch-in, chosen by the first move, not every type at once. A gym's answer-check still lands on it
once it has committed. At 450 in a fast mixed spread it sits inside the five finals' band on every measure here,
and below Lunala and Solgaleo. What argues for caution is not the stats but Sketch's utility:
- it is permanent and accumulating;
- in co-op it reaches any move a friend can show it;
- the sim cannot see it (Spore and setup, no Sleep Clause).

It also needs the unrun same-species evolution twice. **Do it after EXP-049 step 3 passes**, at about 450 with
74/79/60/79/60/98. Then play one in-game fight against Sabrina and one against Lorelei with a Spore + Shell Smash
set, before trusting any number in section 3.

## Repository disagreements found

- `docs/STATE.md:342` says a-lite is "decided ... and NOT built" and EXP-049 "DESIGNED, NOT RUN". But
  `tools/mythical_starters.py`, `tools/mythical_starters_audit.py` and `experiments/EXP-049-native-starter-evolution/README.md:3`
  say a-lite is "BUILT, NOT YET OBSERVED IN GAME (2026-10-03)". STATE never names the tool.
- `tools/battle_sim.py:107` reads the unused Showdown copy (section 0).
