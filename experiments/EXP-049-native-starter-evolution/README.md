# EXP-049: Native-evolving starters: forms, a same-species stage, the cap gate and the evolution veto

**Status: DESIGNED, NOT RUN (2026-10-02).** Nothing has been built, loaded or observed. It decides which option in
`docs/mechanics/NATIVE_STARTERS_COST.md` is buildable. The evidence behind each step is in
`docs/research/NATIVE_STARTERS_1_8_0.md`.

## Objective

Settle, in one staging session, the six links that the five-starter design (Cosmog, Kubfu, Type: Null, Poipole,
Meltan) rests on and that no source can settle:

1. what the server actually has for the five lines (pack order, `implemented`, models);
2. a `species_additions` form with its own `baseStats`, `moves` and `evolutions` loads, is chosen by a forced aspect,
   and keeps that aspect across a species change;
3. a **same-species** "evolution" can move a Pokémon from one form to the next;
4. the RCT level cap holds against Rare Candy, so that a `level` requirement is a badge gate;
5. an `evolution_tested` callback can veto a native evolution for one Pokémon;
6. `"optional": false` forces an evolution.

## Success criteria

Each step passes or fails on its own; the design takes whatever passes. The options, from
`docs/mechanics/NATIVE_STARTERS_COST.md`:
- **a-lite** needs steps 1, 2, 3 and 4.
- **b / c** needs steps 1, 4 and 5.
- **6** decides only "forced or offered".

## Dependencies

- Staging server and world (never `cobblers-10240`).
- The coordination lock through `python tools/server_lock.py take`, after the process and port check (CLAUDE.md).
- `max-tick-time` is not involved.
- Mod set: the overlay's. Cobblemon 1.8.0+1.21.1, Mega Showdown 1.0.2+1.8, TMCraft 1.4.19+1.8.0, rctmod 0.19.0-beta,
  COBBLEVERSE-DP-v31 in the staging world's datapacks.
- One operator client with the client pack.

## Implementation

A throwaway datapack `exp049` in the staging world's `datapacks/`. It is never committed to `data/` and is removed
afterwards. The text below is a spec, not a schema: the field names are those of the jar's own species files, and of
Cobbleverse's shipped form additions (Primal Dialga, Shadow Mewtwo), which carry `baseStats`, `moves` and
`evolutions` inside a form.

**`data/cobblers/species_additions/cosmog.json`:**
- `target` `cobblemon:cosmog`.
- `forms`: one form, `name` `Exp`, `aspects` `["cobblers_exp"]`.
  - `baseStats` totalling 330, in Solgaleo's shape.
  - `moves` drawn from Solgaleo's level-up list, at levels up to 30.
  - `evolutions`: `level_up` → result `cosmoem`, requirement `level` `minLevel` 12, `"optional": false`.

**`data/cobblers/species_additions/cosmoem.json`:**
- One form, `Exp`, `["cobblers_exp"]`, 430 BST.
- No evolutions.

**`data/cobblers/species_additions/kubfu.json`:**
- Two forms:
  - `ExpA` (`["cobblers_exp_a"]`, 330 BST), with one `level_up` evolution: result
    `kubfu unaspect=cobblers_exp_a aspect=cobblers_exp_b`, requirement `level` 12.
  - `ExpB` (`["cobblers_exp_b"]`, 430 BST), with no evolutions.

**`data/cobblemon/callbacks/evolution_tested/cobblers_exp049.molang`:**
- When the Pokémon carries the aspect `cobblers_exp_veto`, call `q.set_result(false)`.
- How to read the Pokémon's aspects and the evolution's id from MoLang is **ASSUMED**: `q.pokemon` and `q.evolution`
  are the context names in `EvolutionTestedEvent.kt`, but their fields were not read.
- Write the first version to log `q.evolution` and an aspect test with a tracer, as EXP-042 did, before relying on
  either.

Commands used below (the names are VERIFIED):
- `/pokegive` (EXP-045);
- `/pokemonedit`, alias `pokeedit` (`docs/research/notes/starter-stat-mechanics.md` §3b);
- the properties `level=`, `friendship=` and `aspect=` (src:`api/pokemon/PokemonProperties.kt:133,138`;
  `AspectProperties.kt`);
- the item `cobblemon:rare_candy` (jar lang).

## Test instructions

**1. Inventory.** Boot staging with `exp049` absent.
- Grep `logs/latest.log` for `Caught exception applying addition` and `Cannot find species`. Record any that name the
  five lines or the Cobbleverse forms.
- `/pokegive <op> meltan level=69 held_item=minecraft:anvil`, then one Rare Candy.
  - If it offers Melmetal, Cobbleverse's addition won over Mega Showdown's: record it.
  - Run this with the cap lifted, or on an operator outside the RCT series. Record which.
- `/pokegive` one each of cosmog, kubfu, typenull, poipole and meltan at level 5. Send each out.
  - Pass: a real model on each, not the green doll.
  - Record each Poipole's four starting moves, and whether Dragon Pulse can be slotted in from the summary.

**2. Forms load and carry across a species change.** Add `exp049`, then `/reload` (and also a restart; record both).
- `/pokegive <op> cosmog level=5 aspect=cobblers_exp`, and a plain `cosmog level=5`.
- Pass: the summary shows the Exp stats and moves on the first only, and the stats match the formula
  (`CobblemonStatProvider`, notes §4).
- Level it to 12 with Rare Candy, with the cap lifted.
- Pass: it becomes Cosmoem, still carries `cobblers_exp`, and shows the 430 Exp stats.
- Fight a fixed NPC. Pass: damage matches the Exp bases, so Showdown used the form.

**3. The same-species stage.**
- `/pokegive <op> kubfu level=11 aspect=cobblers_exp_a`, then one Rare Candy.
- Record:
  - whether an evolution is offered or happens;
  - the message text;
  - the Pokédex entry;
  - the moves and the ability;
  - whether `cobblers_exp_a` is gone and `cobblers_exp_b` is present;
  - the stats.
- Pass: exactly one transition, to ExpB stats.
- Fail: nothing happens, a crash, a loop, or both aspects held at once.

**4. The cap gate.** As a normal player in the RCT series, before gym 1 (cap 20):
- Bring a Pokémon to 20 and use a Rare Candy, then an Exp. Candy.
- Pass: the level stays 20, so a `level` requirement above a cap cannot be reached before its badge.
- Fail: it goes to 21. The design must then add an `advancement` requirement on `cobblers:flag/gymN_cleared`.

**5. The veto.**
- `/pokegive <op> typenull level=20 friendship=160 aspect=cobblers_exp_veto`, and the same without the aspect.
- Wait 2 s with both in the party.
- Pass: only the one without the aspect is offered Silvally, and the tracer shows the callback ran for both.

**6. Forced.** In step 2's Cosmog, `"optional": false` is set.
- Record whether Cosmoem arrived without a prompt.
- Repeat with the key removed: an offer is expected.

## Results

Not run.

## Limitations

- A staging server with operator commands is not a player's path.
- Steps 2–3 use level 12 for speed, where the design uses 30/31 and 45/46. That changes no code path.
- The step 1 inventory is only as good as the staging world's datapack set. Record `/datapack list`.

## Decision

Pending. Steps 1–4 passing → a-lite. Step 3 failing → c with the veto (step 5).

## Follow-up

- Add a row to `docs/research/EXPERIMENT_BACKLOG.md` when this is scheduled.
- Re-measure the stress test only after `battle_sim` reads the authored starter record
  (`docs/mechanics/NATIVE_STARTERS_COST.md` §5).
