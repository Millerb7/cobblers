# EXP-000: Cobbleverse base on Cobblemon 1.8

## Objective
Determine whether the Cobbleverse 1.7.42 mod set, with our overlay
(`modpack/manifest/overlay.json`), boots and plays on Cobblemon 1.8.0 (Fabric,
MC 1.21.1). "Yes" means the campaign can target 1.8 and keep the Cobbleverse
feel; "no" means we either pin to 1.7.3 or shrink the mod set.

## Success criteria
- Dedicated server reaches `Done (` with the overlay mod set and no mod-resolution errors.
- A client built from the same manifest (plus client-only mods) connects.
- Smoke tests below all pass at least once in multiplayer (two clients).

## Dependencies
- Java 21, Fabric loader >= 0.18.4 for MC 1.21.1 (pin the exact version in results).
- `modpack/manifest/base-cobbleverse-1.7.42.json` + `overlay.json` (7 replacements, 2 removals, 34 server-excluded).
- Local copy of the base jars; the 1.8 replacement jars from Modrinth (`tools/pack_manifest.py download`).
- `server/scripts/assemble-server.ps1`, `server/scripts/boot-test.ps1`.

## Implementation
Nothing is built; this is a compatibility probe. The overlay is the artifact
under test. Every boot attempt is captured in `runs/<timestamp>/` by
`boot-test.ps1` (latest.log, crash reports, mods.txt, verdict.txt).

## Test instructions (boot-test procedure)
1. **Known-working baseline.** Assemble a server from the base manifest only
   (`assemble-server.ps1 ... ` with `--no-overlay` behaviour: temporarily run
   `python tools/pack_manifest.py plan --side server --no-overlay --json` or use
   the Cobbleverse install directly). Boot it. It must reach `Done (`. Record the
   loader version. This is row 0 in `results.md`.
2. **Upgrade only Cobblemon.** Swap `Cobblemon-fabric-1.7.3+1.21.1.jar` for
   `Cobblemon-fabric-1.8.0+1.21.1.jar`. Boot. Expected: mod resolution failure
   naming tmcraft, capture_xp, tim_core, better_pokedex_scanner (hard pins) and
   possibly rctmod. Record the exact list - it validates or corrects the overlay.
3. **Apply the overlay.** `assemble-server.ps1 -ExtraDir <1.8 jars> -TargetDir <srv>/mods -Apply -Clean`.
   Boot with `boot-test.ps1`. Record failures; for each: update / remove /
   replace via `overlay.json` (never by hand-editing the server), re-assemble, boot again.
4. **Repeat** until `Done (`. Every attempt is a row in `results.md`.
5. **Client.** Build a client instance from `plan` (all sides), connect.
6. **Smoke tests** (two players where marked):
   - server boots, client connects, no "missing registry" / "mismatched mods" kick
   - `/pokespawn <species>` spawns; wild Pokemon spawn naturally in a few biomes
   - battle a wild Pokemon to a finish; catch one; the capture-XP mod grants XP
   - an RCT trainer spawns near a player and a battle can be started and finished (both players)
   - Mega evolution via Mega Showdown works in a trainer battle
   - TM machine (TMCraft) crafts/teaches a move
   - PC opens, deposits and withdraws; Poke Center PC datapack structure exists
   - Cobblenav opens; raid den (cobblemonraiddens) can be found; breeding (Cobbreeding) starts an egg
   - a second client sees the first player's Pokemon and battle
7. Write the decision in `README.md > Decision` and `docs/decisions/`.

## Results
See `results.md`. No boot attempt has been made yet.

## Limitations
- Boot success is not gameplay success; the 23 `needs_functional_test` mods
  must be exercised (step 6), not just loaded.
- World-gen mods (Terralith, LegendaryMonuments, CobbleFurnies) changing
  between versions could break an existing world; test on a fresh world first.
- Client-only mods are not covered by the server boot at all.

## Decision
Pending.

## Follow-up
- Pin the Fabric loader version in `server/launch/README.md`.
- Turn the smoke-test list into a checklist datapack or a script once the
  campaign tooling exists.
