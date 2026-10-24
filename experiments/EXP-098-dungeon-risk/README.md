# EXP-098: does the dungeon risk hold a run's finds, give them back or sell them on a clean exit, and only log catches?

**Status: DESIGNED 2026-10-23, NOT_EXECUTED.** Built in `tools/dungeon_risk.py` from `data/dungeon_risk.json`
(spec `docs/mechanics/DUNGEON_RISK.md`), generated into the `cobblers_dungeons` pack (world-local). Run by the main
session on **staging only**, never live. The implementer wrote this plan; `qa-reviewer` grades it.

## Objective

1. Everything a run finds goes to the Run Stash, not the inventory; the Run Satchel shows it; relics stay with the player.
2. A clean exit gives it back (Take it all) or sells it at the bank's price plus the bonus (Sell it all).
3. A death deletes the stash and leaves everything the player carried in.
4. Every catch in a run is logged by its Pokemon UUID; a failed run logs, in `dry_run`, exactly what it would remove and
   removes nothing; a shiny and a prize species are never logged.
5. Only then, with the owner, removal on: exactly the logged UUIDs go, every guard keeps.

## Versions

Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.2+1.21.1, CobbleDollars 2.0.0 Beta-6.1, rctmod 0.19.2-beta (the
server's 102 jars, `docs/STATE.md` "Runtime"). Record the build's commit and `install_check` output with the results.

## Set-up (main session)

1. Live-server safety gate (CLAUDE.md), the lock, then a staging snapshot (D:\cobblers-snapshots, sha256).
2. `python tools/dungeon.py`, install the world-local `cobblers_dungeons` pack into STAGING, `/reload`.
   `/data get storage cobblers:dg_risk cfg` must read `{remove:0b}`; `prices` must hold the bank's list (93 entries
   on 2026-10-23); `/scoreboard objectives list` must show `dg.rku dg.rkc dg.rkw dg.rkt dg.rkb dg.rkv dg.rkl`.
3. One test account, tagged `cobblers.dg_playtest`, `dg.ptband 1`, `dg.ptdun 1` (the Night Shift), a party of two
   (one starter, one throwaway), a held Oran Berry on neither, an emerald and a stone pickaxe of their own in slot 8.

## Steps, each with what to read

| Step | Do | PASS when |
|---|---|---|
| S1 arrival | Enter by a rip. | The Rift Pick AND the Run Satchel are in the inventory; `dg.st` 2 |
| S2 stash | Cross the threshold; mine 5 coal ore in the seam. | The ore drops vanish as they fall; the action bar says "Into your Run Satchel."; inventory has no coal; `/data get storage cobblers:dg_risk s.p<dg.id>` shows `counts:[{id:"minecraft:coal",n:5}]` (Fortune off) |
| S3 mob drop | Defeat a wild Pokemon that drops an item (on-entity). | The drop is stashed. **If it is not** (Cobblemon gave it an Owner/Thrower): record it; hole H3 holds, nothing lost |
| S4 chest | Open a pay-office vault chest; shift-click everything. | Within a tick the chest's stacks leave the inventory and appear in `s.p<id>`, the gain key gone (`components` absent for coal, iron) |
| S5 own item | Drop (Q) the player's own emerald; pick it back up. | The emerald is back in the inventory, never stashed (it has a Thrower) |
| S6 relic | Take a relic at a secret. | The relic stays in the inventory |
| S7 satchel | Right-click the satchel. | A merchant named "Run Satchel" stands in front; right-clicking it opens the trade screen; every stash item is an offer with its tooltip; every offer shows the out-of-stock cross; nothing can be taken; it is gone after 20 s; no "Named entity died" line in the server log |
| S8 clean exit + take | Leave by the far rip; click [Take it all]. | "Your Run Satchel holds N stacks", the worth line, three buttons; Take delivers every stack at the feet (coal back as one stack of 5); `s.p<id>` gone; `dg.rkw` 0 |
| S9 sell | Run again (playtest bypasses the lockout or wait it out), stash coal and an emerald, exit, click [Sell it all]. | Balance rises by exactly (count x bank price) x (100 + bonus) / 100, rounded down (band 1: +0%; +5% with the boss down); anything the bank does not buy is delivered |
| S10 timeout | Exit with a stash and do not click for 60 s. | "No answer, so the Run Satchel is emptied into your hands." and everything delivered |
| S11 death | Run again, stash coal, die (`/kill` in the pocket). | Death titles and lines; "Lost with the run: your Run Satchel and everything in it."; `s.p<id>` gone; the player's own pickaxe and emerald still held (keepInventory) |
| S12 catch log | Run again; catch a wild Pokemon (any ball). | Chat "At stake until you leave by the exit: cobblemon:<species>"; `/data get storage cobblers:dg_risk ledger` has `{pid:"<uuid>",who,run,...}`; compare `pid` with `/pokemon` summary or `q.pokemon.id` read by `runmolang` on that party slot |
| S13 exemptions | Catch a shiny (spawn one: `pokespawn <species> shiny` near the player) and, at band 4+, the prize. | "A shiny! Yours whatever happens." / "The rift's prize..."; NOT in the ledger |
| S14 dry run | Die with logged catches (one in the party, one moved to the PC, one released before the death). | Lines "Not enforced yet: the rift would take back ..." for the two found; `ledger` empty; `log` holds three entries with `o` 1 (party), 2 (PC), 0 (not found); **the party and PC are unchanged** |
| S15 clean exit keeps | Catch, exit cleanly. | "Your catches from the run are yours."; ledger empty; no log entry |
| S16 removal (owner present, throwaway Pokemon only) | Set `data/dungeon_risk.json` `catches.mode` to `remove`, rebuild, install, `/reload`. Catch three throwaways; give one an item; die. | The two without items are gone from party/PC (`o` 3/4); the holder is kept (`o` 5); every other Pokemon untouched; the client's party and PC screens refresh. Then repeat with only a catch in the party: kept (`o` 7). Then set the mode back to `dry_run` unless the owner says otherwise |

## Not covered by this plan (record if seen)

Co-op (members_max 1); a server crash mid-reaper; a trade of a logged catch; an egg from the egg vendor (hole H1:
kept).

## Results

NOT_EXECUTED.

## Decision

Pending the run. Removal stays `dry_run` until S16 passes with the owner.
