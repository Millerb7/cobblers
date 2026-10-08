# EXP-056: Does Lootr give each player their own copy of the containers we place, and what does a re-apply do to it?

**Status: NOT_EXECUTED.** Blocked on step 0 (the owner's permission to download the jar). Nothing here has been run.

## Objective

The owner chose Lootr for per-player chests on 2026-10-07 (`docs/STATE.md:137` answer 8;
`docs/decisions/ADR-007-per-player-chests-lootr.md`). Every behaviour ADR-007 relies on is ASSUMED in the research
(`docs/research/PER_PLAYER_CHESTS.md:161-171`). This experiment proves or disproves the four that decide how content
is authored: section 7 items 1-3 (cases A, B, C) and the re-apply/re-export behaviour (case D, section 7 item 4 and
`PER_PLAYER_CHESTS.md:237-239`). "Yes" to A-D unlocks ADR-007's conversion plan steps 5-10.

## Success criteria

Each case records PASS, FAIL or the observed alternative; a FAIL is a result, not a stop.

- **0 (boot).** Staging boots with Lootr and Cloth Config; `logs/latest.log` has no Lootr or mixin error; a client
  with Lootr joins; a client without it is refused (record the message).
- **A (command-placed chest with a loot table; item 1).** Within 2 s of the `setblock`, the block at the pad reads
  as a Lootr block (record the exact id). Player 1 opens it and sees the deterministic table's items; takes them;
  Player 2 then opens it and sees the full list; Player 1 reopens and sees an empty inventory. The same in
  `cobblers:pocket` (the portal cache's dimension).
- **B (template paste; item 2).** B1: `minecraft:pillager_outpost/watchtower` pasted with no strip: its chest
  converts. B2: the same paste with `data remove block ... LootTable` in the same function (our `clear_loot`
  order, `tools/place_donor.py:170-183`): the chest stays `minecraft:chest`, opens empty for both players. B3: a
  vanilla barrel with explicit `Items` (the `tools/sea_town.py:852` shape): stays `minecraft:barrel`, shared. B4: one
  Sophisticated Storage barrel from a bird-tower paste after `remove_items`: not converted, the feather absent.
- **C (`custom-chest`; item 3).** C1: `/lootr custom-chest` on a filled vanilla barrel converts it; record the
  resulting block (barrel-shaped or chest-shaped `lootr:lootr_inventory`); two players each get the original items.
  C2: the same command run from a function (`/function`), i.e. at function permission level: works or is refused.
- **D (re-apply and re-export; item 4).** D1: after a server restart a looted container stays looted for Player 1
  and full for Player 2. D2: the same `setblock` re-run over a looted Lootr chest: record whether Player 1 can loot
  it again. D3: the portal cache re-placed by re-running its R16P function (`tools/reapply.py:1919-1921`): same
  question. D4: Lootr's state is where the research says, `<world>/data/lootr/` (`PER_PLAYER_CHESTS.md:158-159`),
  and it is a category `tools/carry_players.py:66-88` does not carry (measured: it does not). Record the verdict for
  a re-export as "resets" or "persists" with which of D2-D4 it rests on.

## Dependencies

- Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0+1.21.1 (the server's set, `docs/STATE.md` "Runtime").
- **Lootr Fabric `1.21.1-1.11.38.127`**, Modrinth project `EltpO5cN`, version `nar56EsW`, file
  `lootr-fabric-1.21.1-1.11.38.127.jar`, 1,111,591 bytes, MIT (`PER_PLAYER_CHESTS.md:62-65`, VERIFIED there through a
  summariser). Hashes in the note are **relayed**: compute sha512 and sha1 from the downloaded file and record them
  here.
- Cloth Config: `cloth-config-15.0.140-fabric.jar` is in the base pack (`base-pack/inventory/pack_hashes.csv:53`,
  measured); whether it is in the server's `mods/` and whether Lootr's declared range accepts it: read at step 1.
- The portals pack built (`tools/portals.py build`, R16P) for the `cobblers:pocket` part of A and for D3.
- Two players for A, B2, C1 and D. Lootr's `/lootr open_as_uuid` and `/lootr openers` (`PER_PLAYER_CHESTS.md:140-142`,
  syntax unverified) may stand in for a second player in a console-only pass; that pass is a proxy and is labelled so.

## Implementation

Nothing is built for this. A deterministic test table is written into a staging-only copy of a pack, in the shape
`tools/portals.py:311-313` emits (one pool per item, `rolls: 1`, `set_count`); its items are vanilla (for example
3 `minecraft:apple`, 1 `minecraft:compass`) so no mod item is involved. It is not committed and not added to `data/`.

## Test instructions

0. **BLOCKING: the owner's explicit permission to download the Lootr jar from Modrinth**, for the server and the
   owner's client. Without it nothing below runs. No other route to the jar is planned.
1. Session start per `CLAUDE.md`: process and port check, then the coordination lock
   `C:\Users\wnd\Documents\github\.cobblers-server-agent.lock`; `python tools/install_check.py --server-dir <server>
   --world-dir <staging world>` (staging: `C:\Users\wnd\Documents\cobblers-staging\staging-2026-10-01`,
   `docs/STATE.md:7`) and report every problem first. **STAGING only**: `server.properties` `level-name` is the live
   world's name, so boot only with the universe flags (`docs/STATE.md:9-11`). Record the jar's sha512/sha1 and read
   its `fabric.mod.json` dependency ranges.
2. **Hazard, before anything is copied:** Lootr in the server's `mods/` converts every loot-table container in
   whatever world boots next. If the staging server shares its `mods/` with the live world, the jar is **removed
   before any live boot**, and the lock note and `docs/HANDOVER_SESSION.md` say it is in `mods/` while it is. Whether
   `install_check.py` flags a jar not in the manifest is not known; do not rely on it.
3. Put Lootr into the server's `mods/` and the owner's client. Boot staging detached, check the process (not only
   RCON), read the log (case 0). Record the config file Lootr generates and its key names against
   `PER_PLAYER_CHESTS.md:143-153`. Leave refresh and decay off.
4. Choose a test pad on staging away from every authored site; measure its ground with
   `round(ground(x, z))` (`tools/ground.py`) and record the coordinates here.
5. **Case A.** `setblock <pad> minecraft:chest[facing=north]{LootTable:"<test ns>:<test table>"}`; after 2 s,
   `execute if block <pad> minecraft:chest` and `data get block <pad>` (record the id). Players 1 and 2 open it in
   turn as in the criteria. Repeat at a free cell inside `cobblers:pocket`.
6. **Case B.** B1: `place template minecraft:pillager_outpost/watchtower <pad+20> none` (the template
   `data/placements.json:8353` names), find its chest (the template's `LootTable` block, as `place_donor.py` finds
   it), read its id after 2 s. B2: a function that runs the same paste at another pad and the `data remove block
   ... LootTable` that `place_donor.py loot_commands` would emit, then read and open. B3: `setblock <pad+40>
   minecraft:barrel[facing=up,open=false]{Items:[{Slot:0b,id:"minecraft:oak_boat",count:1}]}` (the `sea_town.py:851`
   form), read after 2 s, two players. B4: paste one bird tower as its reapply step does (`articuno_tower.py`
   `placement_steps`) at a staging pad, read the Sophisticated Storage barrel's id and contents.
7. **Case C.** C1: a fresh B3 barrel; `/lootr custom-chest <pos>`; read the block; two players open. C2: the same in
   a one-line staging function, run with `/function`; record success or the refusal text.
8. **Case D.** D1: Player 1 loots A's chest; stop the server cleanly, start it, check both players. D2: re-run case
   A's `setblock` exactly; Player 1 opens. D3: Player 1 loots a portal cache in `cobblers:pocket`; run
   `function cobblers:portals/place`; Player 1 opens. D4: with the **staging** server stopped, list
   `<staging world>/data/lootr/` (names and count only). Never the live world.
9. Remove Lootr from the server's `mods/` (step 2) unless the owner says otherwise, boot nothing else with it, release
   the lock. Note: a world that converted containers and then boots without Lootr loses those containers (FAQ,
   `PER_PLAYER_CHESTS.md:75-76`); the staging world is disposable, and this is why.

Optional, not needed for ADR-007's plan: breaking a Lootr container with the defaults (section 7 item 5); a hopper
and a comparator against one; server-side Distant Horizons over a chunk holding one (item 7); whether a
`lootr:lootr_chest` still counts as `minecraft:chest` for Gimmighoul's spawn condition (`data/portals.json:113`).

## Results

**Console proxy pass, 2026-10-08 (overnight; the owner's download permission 2026-10-08).** No player: every
per-player claim below is a proxy and is labelled so. Run on a DISPOSABLE copy of the staging snapshot,
`cobblers-staging/lootr-exp-2026-10-08` (never staging-2026-10-01), Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon
1.8.0+1.21.1, the server's full mod set plus Lootr. The jar: `lootr-fabric-1.21.1-1.11.38.127.jar` from
`cdn.modrinth.com/data/EltpO5cN/versions/nar56EsW/`, 1,111,591 bytes, **sha512 equal to Modrinth's API record
(measured)**, sha1 `6671786d4c36a33dcefff85d757022c2a8ed535f` (matches the note's relayed value). Its
`fabric.mod.json`: fabricloader >=0.17.0, fabric >=0.100.3, minecraft 1.21.1, java >=21, cloth-config >=15.0.127
(the server has 15.0.140). Removed from `mods/` and its generated `config/lootr.json` moved out straight after
(both kept in `C:/Users/wnd/Documents/cobblers-local/mods-pending/`).

| Case | Result |
|---|---|
| 0 boot | PASS: booted (Done), no Lootr or mixin error in the log; `/lootr` registers (custom-chest, openers, open_as_uuid, refresh, decay, ...). Client join NOT run |
| A command-placed chest + LootTable | PASS (block): `lootr:lootr_chest`, LootTable kept, a `LootrId` assigned. Two players NOT run |
| B1 template paste (watchtower) | PASS: its chest at (3029, 113, 4610) became `lootr:lootr_chest` |
| B2 paste then `data remove ... LootTable` | **FAIL as a strip (proxy)**: the chest converted anyway and kept `LootTable` (+ `LootTableSeed`). Run as two RCON commands, not one function: whether `clear_loot`'s in-function order prevents conversion is UNPROVEN, and this result says it may not |
| B3 barrel with literal Items | PASS: stays `minecraft:barrel`, shared |
| B4 bird-tower barrel | NOT run |
| C1 `lootr custom-chest` on a filled barrel | PASS: `lootr:lootr_barrel` with `customInventory` holding the items, `customSize` 27 |
| C2 custom-chest from a function | NOT run |
| D1 restart with a looted chest | NOT run (needs a player) |
| D2 the same setblock re-run over a Lootr chest | **Resets (proxy)**: a NEW `LootrId` (openers are keyed per id), so every player could loot again after a re-apply |
| D3 portal cache via R16P | NOT run (same mechanism as D2: expected to reset) |
| D4 where the state lives | `<world>/data/lootr/` exists (empty: nobody opened anything); `tools/carry_players.py` does not carry it, so a re-export **resets** opened state |

Verdict so far: Lootr loads and converts as documented; a re-apply or re-export resets every player's opened state
(D2, D4); our `clear_loot` order may not keep a stripped container vanilla (B2) — both are findings for ADR-007.
ADR-007 stays Proposed (the owner: until it is seen working). Remaining: two players (A, D1), B2 in one function,
C2, B4.

## Limitations

- A re-export is not run end to end (EXP-024/026's full procedure is too expensive for this question); D's verdict
  for a re-export is inferred from D2-D4 and says so.
- A console pass with `open_as_uuid` uses Lootr to test Lootr; only two real players prove independence.
- Gilded chests are out of scope (Lootr does not convert them without Lootrmon, `PER_PLAYER_CHESTS.md:200`).

## Decision

None yet. Graded by `qa-reviewer`, not by whoever runs it. The verdict goes into ADR-007 (`Revisit when`) and
`docs/research/COBBLEVERSE_COMPATIBILITY.md`.

## Follow-up

ADR-007's conversion plan steps 5-10. If A fails but `/lootr chest <table>` works, the generators emit that command
instead of `setblock`. If D2/D3 reset, step 9's re-apply guard is designed around the id A records.
