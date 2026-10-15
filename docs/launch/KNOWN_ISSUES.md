# Known issues for launch night (2026-10-14)

Launch night is the **first multiplayer test ever**. Everything below is unproven with two or more players unless it
says otherwise. Report what you see; nothing here is a reason not to play.

## Launch state
- The server runs the Cobblemon 1.8.2 set (101 jars); the client pack matches it. See the morning report for the
  staging and live results.
- **Whitelist**: on, but friends must be added by name (`whitelist add <name>`); their names are not in the repo.

## Untested with two players
- **Trainers forget wins** (rctmod, standing limitation): a placed trainer will battle a player who already beat it.
  Our hold-off makes a trainer wait when anyone nearby has beaten it, so an unbeaten partner may have to start the
  fight themselves. Per-player trainers are designed but not built (EXP-034).
- **Challenge mode is per player**: one friend on Challenge and one on Normal near the same leader is untested.
- **The Challenge voucher is not granted** to anyone yet: its schedule exists ($23,748 over 9 grants), the grant does not.
- **Dungeon runs** with two players at once, and Lootr chests' two-player cases: untested.
- **The Trading Post**: its bounded "sell everything" take is assumed vanilla behaviour, never run in game (EXP-061).
  No cap: a pasture of strong Pokemon earns about $3,800 an hour unattended (your call: fine).
- **Kyogre's cave**: a player who logs out inside the cage is sent out on rejoin (built, not run in game).

## Known quirks
- **Rips open and close at random** (3-5 at once, about an hour of play each or until entered; your defaults are not
  confirmed, `data/rip_scheduler.json`). Never run in game. Before installing a pack that changes the rip list, run
  `function cobblers:rips/close_all` (a rebuilt list closes the wrong ground otherwise).
- **Cobbreeding 2.4.1**: a bred egg has a 5% chance to hatch an alpha (the mod's new default, accepted).
- **TM Mega Drain** teaches no Pokemon on Cobblemon 1.8.2 (Venonat and Venomoth lost it).
- **About 43 species render as a placeholder doll** without the AllTheMons subset resource pack.
- **rctmod 0.19.2** (in the 1.8.2 set) shows trainer lines as speech bubbles by default.
- **CobbleDollars Beta-6.1** reads `default_bank.json`; `tools/bank.py` now writes it (economy v2's real bank, installed).
- **The double-KO battle freeze fix** (rctapi 0.16.1+) is installed but has never been reproduced in game.
- **Neruina**: if a block or entity throws repeatedly, it freezes it and kicks the player; tell the owner which.
- **Memory**: the server plays at 12G. With the owner's client on the same PC, close other heavy apps.

## Tests that fail today, unrelated to play
- `test_compact_routes::test_the_owner_s_open_questions_are_listed_with_the_default_built` (an owner-question entry).
