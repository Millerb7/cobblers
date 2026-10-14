# Known issues for launch night (2026-10-14)

Launch night is the **first multiplayer test ever**. Everything below is unproven with two or more players unless it
says otherwise. Report what you see; nothing here is a reason not to play.

## Not yet done (blocked on the owner)
- **The server still runs Cobblemon 1.8.0.** The swap to the 1.8.2 mod set was refused by the session's permission
  check twice (it counts as a production deploy). Until you swap it, clients built from tonight's pack will not match.
- **No staging install of tonight's build, and no live export.** Both were blocked the same way. The live world is
  untouched.
- **Whitelist not on, friends not added** (their names are not in the repo).

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
- **Rips stand still**: the dungeon rips that open and close at random sites (job D) are being built tonight; until
  they are installed, rips are the old fixed ones (or none, if not yet applied).
- **TM Mega Drain** teaches no Pokemon on Cobblemon 1.8.2 (Venonat and Venomoth lost it).
- **About 43 species render as a placeholder doll** without the AllTheMons subset resource pack.
- **rctmod 0.19.2** (in the 1.8.2 set) shows trainer lines as speech bubbles by default.
- **CobbleDollars Beta-6.1** (in the 1.8.2 set) migrates the bank file on first start (`bank.json` to
  `default_bank.json`); our tools still write `bank.json`. Read the migrated file before trusting shop prices.
- **The double-KO battle freeze fix** (rctapi 0.16.1+) is installed but has never been reproduced in game.
- **Neruina**: if a block or entity throws repeatedly, it freezes it and kicks the player; tell the owner which.
- **Memory**: the server plays at 12G. With the owner's client on the same PC, close other heavy apps.

## Tests that fail today, unrelated to play
- `test_compact_routes::test_the_owner_s_open_questions_are_listed_with_the_default_built` (an owner-question entry).
