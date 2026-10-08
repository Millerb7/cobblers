# EXP-062: Do the paid training services set exactly the cap, refuse for free, and leave the Pokemon sound?

**Status: NOT_EXECUTED.** Written 2026-10-10 by the builder of `tools/training_services.py` (unit SERVICES). Run
and graded by someone else (CLAUDE.md principle 16). Every step needs a player in game.

Number: the brief named EXP-062; EXP-059 to EXP-061 are left to concurrent units of the same night.

## Objective

`cobblers_training_services` puts a keeper at each of the eight training grounds (`data/training_services.json`,
placed by `tools/reapply.py` R17TS). For CobbleDollars the keeper raises one party Pokemon to the player's RCT level
cap ($500), trains in an EV spread ($2,000, after gym 2) or sets IVs to 31 ($1,000 a stat, after gym 8). The
commands were read from the jars, not run (`docs/research/notes/paid-services-and-npc-payouts.md` A1-A3), and the
design calls five behaviours untested and blocking (`docs/mechanics/ECONOMY_OVERHAUL.md` section 5, BUILD LIST
U7). This experiment answers them. "Yes" to S1, S3, S4 and S5, and an S2 result the owner accepts, unblocks placing
the keepers in a world players use.

## Where it runs

- A disposable staging world, never `cobblers-10240`. The live-server safety gate (CLAUDE.md) comes first: port 25565,
  a Minecraft Java process and the shared lock. Start the server detached and check the process, not just RCON.
- Install `cobblers_training_services` with the rest of the world-local packs (`tools/reapply.py install`), restart
  (NPC classes load at boot), then run step R17TS only (`--only R17TS`, reported as a partial run).
- One player who is an operator for the setup commands. The keeper's own purchases need no op.
- Read the verdict from the game: the party screen, the summary screen's stats page and `cobbledollars query`.

## Setup

1. `cobbledollars query <player>`: record B0.
2. Give the player a known party: slot 1 a level-5 Pokemon one level below a level-up move and below its level
   evolution (for example a level-5 Charmander: Ember at 4 is learned, Smokescreen at 10 is not, Charmeleon at 16),
   slot 2 empty, slot 3 any Pokemon at exactly the current cap, slot 4 any Pokemon above the cap.
3. `rctmod player get level_cap <player>`: record the cap C (20 for a fresh player).

## S1: does a raise set the slot to exactly the cap read, and read back?

At a keeper: Train a Pokemon to my cap, Slot 1.

- **Must show:** slot 1 is level C in the party screen; `testpartyslot <player> 1 level=C` returns 1; the balance is
  B0 - 500; the chat line says "trained to level C".
- **Then:** raise a cap (clear a gym, or `rctmod` sets it), take the raise again on slot 1: the level follows the NEW
  cap, never a stored one.
- **Must never show:** a level above C. That locks the player out of every trainer (`levelcap_pack.py` battle_check).

## S2: what does a level set skip?

After S1, open slot 1's summary and moves.

- **Record:** whether the moves between level 5 and C were learned or offered; whether the evolution due by C was
  offered (now, on the next level-up, or never); whether the experience bar sits at the start of level C.
- `setLevel` fires no level-up event (note A2), so the expected answer is "not learned, not offered until the next
  real level-up". Whatever the answer, it goes to the owner: the raise page warns the player to check moves.

## S3: an empty slot

Raise Slot 2 (empty). Then, as an op at the console: `pokemoneditother <player> 2 level=C` and
`testpartyslot <player> 2 level=1`.

- **Must show:** the keeper says "no Pokemon in that slot, nothing was charged"; the balance is unchanged.
- **Record:** what each console command prints and returns on an empty slot (the pack assumes testpartyslot
  returns 0 or fails, and the edit fails without effect).
- Also Slot 3 (at the cap) and Slot 4 (above the cap): each refused by name, the balance unchanged, slot 4's level
  NOT lowered.

## S4: an EV set past 510

As an op: `pokemoneditother <player> 1 attack_ev=252 speed_ev=252 hp_ev=6` (a full 510). Then, with gym 2 cleared,
buy "Physical wall" for slot 1 at the keeper.

- **Must show:** HP 252, Defence 252, Sp. Def 4, every other EV 0 on the stats page; the balance down $2,000.
- **Control:** on a second full-510 Pokemon, as an op, `pokemoneditother <player> <slot> hp_ev=252 defence_ev=252
  special_defence_ev=4` with no zeroing first. **Record** what is set and what is refused: the note says
  `EVs.canSet` refuses past 510, and that refusal is why the pack zeroes all six first.
- **Record also:** `testpartyslot <player> 1 hp_ev=252` returns 1 or 0. The pack does not read EVs or IVs back
  because this is unread; a 1 would let a later version verify them.

## S5: the charge-then-refuse paths, through the keeper

1. **Short:** set the balance to $499 (spend it, or `cobbledollars remove`), raise slot 1: refused, the balance
   still $499.
2. **Gates:** without gym 2, the hub shows no Effort training option; without gym 8, no Perfect a stat option.
   Running `function cobblers:training_services/ev/physical_wall/slot1` as the player (an op: `execute as <player>
   run function ...`) is refused with the balance unchanged.
3. **Double click:** click a slot option twice fast: one charge.
4. **Postgame:** with a cap of 100 (the Champion cleared, or set), a raise is refused: "past what I train to",
   nothing charged.
5. **The menu:** every page renders all its options (the IV page has eight: six stats, all six and Back), and Back
   returns to the page before.
6. **Every refusal:** the balance after equals the balance before, to the dollar.

## Pass / fail

- **Pass:** S1, S3, S4 and S5 as written, and S2 recorded.
- **Fail:** any level above the cap, any charge on a refused path, any slot level lowered, or an EV spread that keeps
  part of the old one.

## Results

Not run.
