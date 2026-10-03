# EXP-049: Native-evolving starters: forms, a same-species stage, the cap gate and the evolution veto

**Status: NOT RUN. The a-lite design is BUILT, NOT YET OBSERVED IN GAME (2026-10-03).** The owner chose to build
a-lite before this experiment runs (overnight 2026-10-03). It now checks the built pack, not a throwaway one: see
Results. The evidence behind each step is in `docs/research/NATIVE_STARTERS_1_8_0.md`.

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

**Built, not yet observed in game (2026-10-03).** No step below has run. Nothing here was loaded by Minecraft; valid
JSON and a clean `check` are the most that can be claimed.

**What was built** (commit on `worktree-agent-a2cbd849e6c7fc06d`):
- `data/mythical_starters.json`, the authored record: per line the stage-1 and stage-2 forms, their base stats, one
  authored movepool, the evolutions, the native finals, the 27 traditional starters that stay wild, and the Kubfu
  scroll hand-out (recorded, not built).
- `tools/mythical_starters.py`: `check` (against the jar, the starter config and `data/spawns.json`), `build` (to
  `build/datapacks/cobblers_mythical_starters`, six `data/cobblers/species_additions/mythical_starter_<species>.json`
  and a `pack.mcmeta`), `measure` (battle_sim's own duel).
- `modpack/config/cobblemon/starters.json`: one category, `cosmog|kubfu|typenull|poipole|meltan level=5
  aspect=cobblers_starter_1`. The 27 are off the screen.
- `tools/reapply.py`: the pack in `SERVER_PACKS` and `WORLD_LOCAL`, built by job `mythical_starters:build`.

**So this experiment, when it runs, tests the built pack in place of `exp049`:** step 2 with
`/pokegive <op> cosmog level=29 aspect=cobblers_starter_1` and one Rare Candy; step 3 with `kubfu level=29
aspect=cobblers_starter_1`; step 6 is moot (offered is decided: `optional` is omitted). Step 5 (the veto) is no longer
on the path.

**The lines** (stage 1 at 5 → stage 2 at 30 → native final at 45; all `level_up` unless stated):

| Line | Stage 1 (330 BST) | Stage 2 (430 BST) | Final at 45 | Shape |
|---|---|---|---|---|
| Cosmog | Cosmog `Starter` | Cosmoem `Starter` | Solgaleo (day) / Lunala (night), the native choice | Solgaleo |
| Kubfu | Kubfu `Starter` | Kubfu `Starter-Grown` | Urshifu by `item_interact` with either scroll, plus level 45 | Kubfu |
| Type: Null | Type: Null `Starter` | Type: Null `Starter-Grown` | Silvally (friendship dropped) | Type: Null |
| Poipole | Poipole `Starter` | Poipole `Starter-Grown` | Naganadel (Dragon Pulse dropped; Shed Shell kept) | Poipole |
| Meltan | Meltan `Starter` | Meltan `Starter-Grown` | Melmetal, no anvil | Melmetal |

**Where each is potent, MEASURED** (`python tools/mythical_starters.py measure`: wins of the leader's Pokemon, 1v1
from full health at each gym's cap, IVs 15, damaging level-up moves only; a lower bound, not a prediction):

| Starter | g1@20 | g2@25 | g3@30 | g4@35 | g5@40 | g6@45 | g7@50 | g8@55 | Total | Peak (margin over the five's mean) |
|---|---|---|---|---|---|---|---|---|---|---|
| Cosmog | 0/3 | 1/3 | 0/4 | 2/4 | 2/5 | 5/5 | 5/5 | 5/6 | 20/35 | gym 7 (+0.40) |
| Kubfu | 2/3 | 2/3 | 2/4 | 0/4 | 1/5 | 4/5 | 2/5 | 6/6 | 19/35 | gym 1 (+0.47); level-best at 2 and 3 |
| Type: Null | 0/3 | 1/3 | 1/4 | 0/4 | 2/5 | 3/5 | 2/5 | 6/6 | 15/35 | gym 8 (+0.30) |
| Poipole | 0/3 | 2/3 | 1/4 | 4/4 | 1/5 | 4/5 | 4/5 | 2/6 | 18/35 | gym 4 (+0.65) |
| Meltan | 1/3 | 1/3 | 1/4 | 1/4 | 3/5 | 5/5 | 2/5 | 2/6 | 16/35 | gym 5 (+0.24) |

- **Five different peaks: Kubfu early (gyms 1–3), Poipole at Erika, Meltan at Koga, Cosmog at Sabrina and Blaine,
  Type: Null at Giovanni.** The band is 15–20 of 35, inside today's 27 starters' 9–27 (median 17). The reasons are in
  each line's `potent_at.why`.
- How it was reached: each pool was re-levelled until no two lines peaked at the same gym. Native finals carry the
  late game, so the late peaks come from which coverage each line has learnt by 45 (Silvally's Surf and Ice Beam,
  Lunala's Moongeist Beam).
- **Meltan, an owner call:** the approved 12 moves are kept and **re-levelled** (Iron Head 26→36, High Horsepower
  34→37, Ice Punch 22→40, Brick Break 14→28, Rock Slide 30→24). In the drafted order Meltan measures **20/35, peaking
  at gym 4 with Poipole** (4/4, Steel walls Erika's team), which is "all at once". Re-levelled: 16/35, peak gym 5. The
  cost note's "16" for the draft is RELAYED from a different scratch model; this tool measures the draft at 20.
- **A battle_sim defect found:** Explosion and Self-Destruct never make the user faint (no self-KO handling in
  `tools/battle_sim.py`), so `choose_moveset` takes them as free 250/200-power hits. Silvally measured 6/6 at gym 8 with
  Explosion. `measure` leaves self-KO moves out of the finals (`SELF_KO`); battle_sim itself is unfixed (its owners).

**Format evidence** (each is cited in `tools/mythical_starters.py`'s docstring):
- `species_additions` in our own namespace load: `JsonDataRegistry` lists the path over every namespace and skips
  only `pixelmon` (jar `JsonDataRegistry.class`).
- Forms with `baseStats`, `moves` and `evolutions`: COBBLEVERSE-DP-v31 (Primal Dialga, Shadow Mewtwo); forms with
  non-empty `evolutions` and a custom-property result: Mega Showdown's `pikachu.json`.
- `unaspect=` is a registered property that removes a forced aspect (jar `UnaspectPropertyType.class`, registered in
  `Cobblemon.class`); an evolution applies its result through `PokemonProperties.apply`, which applies custom
  properties (`Evolution.applyTo`).
- **Offered, not forced:** `LevelUpEvolution`'s no-argument constructor passes `optional = true` (bytecode); we omit
  the key. No shipped JSON sets it.
- `PokemonProperties.create()` applies the properties (the aspect, so the form) **before** `initialize()` builds the
  moveset, so the level-5 moves are the form's (bytecode).

**Still unproven, in order of risk:** a same-species evolution moving form to form (step 3); the aspect surviving the
Cosmog → Cosmoem species change (step 2); the forms rendering (a custom aspect with no model variation is ASSUMED to
fall back to the base model); the cap against Rare Candy (step 4); the pack applied by a `/reload` as against a restart.

**What an independent audit must check** (another agent writes it; its expectations must not come from
`tools/mythical_starters.py` or from the record it checks):
1. Every stage's base stats total 330 / 430 and follow the declared shape, computed from the jar's own species file.
2. Every pool move is in the 1.8.0 jar's learnset of some member of the line, and is a Showdown move.
3. Each stage-1 form's only evolution is `level_up` at exactly 30 to stage 2's species with `unaspect=cobblers_starter_1
   aspect=cobblers_starter_2`; each stage-2 evolution is at exactly 45 to a native final with only
   `unaspect=cobblers_starter_2`; no evolution sets `optional`; Kubfu keeps both scrolls as `requiredContext`;
   Cosmoem keeps day/night.
4. 30 and 45 are still gym 3's and gym 6's ace levels in `data/trainers.json` with `relativeLevelCap` 0.
5. The starter config offers exactly the five stage-1 forms and none of the 27; every one of the 27 families has a
   weighted `data/spawns.json` record, walked from the jar's evolutions.
6. No addition targets a final (Solgaleo, Lunala, Urshifu, Silvally, Naganadel, Melmetal), and no form name or aspect
   collides with a native, Mega Showdown or COBBLEVERSE form on the same species.
7. The pack is world-local and is built by a prepare job; the server-wide starter config is installed only where the
   pack is (see below).
8. A mutation of the GENERATOR (for example a stage-2 level of 31 in `files()`), with the record untouched, fails it.

**Breaks today, by design:** `tests/test_battle_stress.py` (two tests: 5 starters, not 27; NATIVE_STARTERS_COST.md
§5) and `tests/test_encounter_hearts.py::test_section_11_places_all_27_mainline_starters` read the 27 from
`starters.json`. The 27 are now in `data/mythical_starters.json` `wild_traditional_starters`; repointing the tests is
the test author's, and the stress test's starter model is its own unit (§5).

**Integration hazard:** `starters.json` is server-wide, the pack world-local. Installed on a server whose world
lacks the pack, a new player is handed a plain Cosmog with Splash. Install both together, and never the config alone
on the live server.

## Limitations

- A staging server with operator commands is not a player's path.
- Steps 2–3 use level 12 for speed, where the design uses 30/31 and 45/46. That changes no code path.
- The step 1 inventory is only as good as the staging world's datapack set. Record `/datapack list`.

## Decision

a-lite is built (the owner, 2026-10-03). Steps 1–4 passing confirm it. **Step 3 failing means the four same-species
lines do not advance at 30:** the fallback is then c with the veto (step 5), and the built pack has to change.

## Follow-up

- Add a row to `docs/research/EXPERIMENT_BACKLOG.md` when this is scheduled.
- Re-measure the stress test only after `battle_sim` reads the authored starter record
  (`docs/mechanics/NATIVE_STARTERS_COST.md` §5).
