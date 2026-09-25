# Why did the Brock battle freeze after a double knockout?

**Answered for:** Minecraft 1.21.1 Fabric, Cobblemon 1.8.0+1.21.1, rctmod
0.19.0-beta, rctapi 0.16.0-beta, cobblemon-battle-extras 1.13.45,
cobblemon-battle-positions 1.1.3. These are the staging versions. The overlay
pins rctapi 0.16.0-beta at `modpack/manifest/overlay.json:178-209`.

**Date:** 2026-09-25.

**Incident (as reported, not re-observed):** Cobbleverse's `kanto_brock` fought
an rctmod trainer battle. Brock's Cranidos used a recoil move, probably Head Smash.
It knocked out the player's Wooloo and fainted from its own recoil in the same
turn. After that the battle never ended, and an operator had to run
`/stopbattle`. The log shows no exception. It has only two related warnings:
BattlePositions' "Trainer stand block not found; opponent teleport skipped" at
battle start, and a vanilla "Entity PokemonEntity[...removed=KILLED] wasn't
found in section ... (destroying due to DISCARDED)" for each player Pokemon
that fainted. Whether either side had Pokemon left is **not known**.

**How the evidence was gathered.** Bash was not available to this session, so
the local jars were not opened. The server `mods/` directory is also inside the
server tree, and the CLAUDE.md live-server gate (port check and lock) could not
be satisfied without a shell. All code evidence below comes from the upstream
source at the release tags, fetched as raw files. Code arrived through a
fetch-and-render step: the identifiers and control flow are reliable, but the
whitespace is approximate.

---

## Short answer

- **Most likely cause:** a known rctapi bug. It was fixed in
  **rctapi 0.16.1-beta** (2026-09-14, Fabric, MC 1.21.1), whose changelog reads
  "*#132* Battle softlocks caused by pokemon fainting on both sides". The fix
  removes an rctapi mixin that delays the AI's `mustChoose` flag. The developer
  noted that on Cobblemon 1.8 that mixin became "(new) cause of softlock when
  both sides fainted". Staging runs 0.16.0-beta, which still has the mixin
  enabled.
- **The "tie" theory is unlikely for this incident.** Cobblemon 1.8.0 has no
  handler for Showdown's `|tie` message, so a real tie would hang. But
  Showdown's Gen 5+ rule gives the win to the side whose Pokemon fainted last
  when everything faints at once. It does not emit a tie in that case.
- **Recommended action:** update rctapi 0.16.0-beta to 0.16.1-beta. This is an
  addon update and needs no config change. Then reproduce the double knockout on
  staging (see the experiment candidates).

---

## Verified

1. **rctapi 0.16.1-beta fixes softlocks when Pokemon faint on both sides.**
   Changelog: "*#132* Battle softlocks caused by pokemon fainting on both sides".
   Details:
   - Released 2026-09-14.
   - Game version `1.21.1`, loader `fabric`, file
     `rctapi-fabric-1.21.1-0.16.1-beta.jar`.
   - sha1 `194ffc5f183b3a1c4f21d02edbbcf67524492ee2`.
   - Source: https://api.modrinth.com/v2/version/bgmxNN26
2. **The fix is commit `5fb66791`** on the `rc/v0.16.1-beta` branch, titled
   "Removed postUpdate mixin (outdated multi-battle softlock workaround)".
   - It changes `CHANGELOG.md` (adding the #132 line) and
     `common/src/main/java/com/gitlab/srcmc/rctapi/mixins/BattleActorMixin.java`.
     In that file it comments out `@Inject(method = "postUpdate", at =
     @At("TAIL"))` `inject$postUpdate`.
   - The removed code set `mustChoose = false` on `AIBattleActor`s in
     rct-managed battles (`BattleState.findFirst(battle) != null`) and then
     restored it through `battle.dispatchGo`.
   - The added comment reads: "DEPRECATED since Cobblemon 1.8: Apparently fixed
     (-> (new) cause of softlock when both sides fainted)".
   - Source:
     https://gitlab.com/api/v4/projects/srcmc%2Frct%2Fapi/repository/commits/5fb66791/diff
3. **rctapi 0.16.0-beta still has that mixin enabled.** `BattleActorMixin.java`
   at tag `v0.16.0-beta` contains an active `inject$postUpdate`. Source:
   https://gitlab.com/srcmc/rct/api/-/raw/v0.16.0-beta/common/src/main/java/com/gitlab/srcmc/rctapi/mixins/BattleActorMixin.java
4. **rctmod accepts rctapi 0.16.1.**
   - rctmod's `fabric.mod.json` declares `"rctapi": ">=${rctapi_min_version}"`.
   - On the `1.21.1` branch head (mod_version 0.19.2-beta), `gradle.properties`
     sets `rctapi_min_version=0.16.0-beta`, `cobblemon_min_ver=1.8.0` and
     `cobblemon_max_ver=1.9.0`.
   - Sources: https://gitlab.com/srcmc/rct/mod/-/raw/1.21.1/fabric/src/main/resources/fabric.mod.json
     and https://gitlab.com/srcmc/rct/mod/-/raw/1.21.1/gradle.properties
   - Only the branch head was read. See Assumed item 4 for 0.19.0.
5. **rctapi 0.16.x requires Cobblemon 1.8.** The 0.16.0-beta changelog says
   "Min required Cobblemon version to `1.8`". Source:
   https://api.modrinth.com/v2/project/rctapi/version
6. **This symptom has been reported before.** rctapi issue #11, "Perish Song
   causes battles to freeze" (Cobblemon 1.6.1, rctmod 0.16.3-beta, rctapi
   0.13.6-beta; closed 2026-01-18), describes the same thing:
   - "after both Pokémon faint, the battle freezes after the switch selection
     screen. The trainer NPC never sends a new Pokémon out".
   - "There were no errors printed".
   - It did not happen with Cobblemon's own NPCs.
   - Source: https://gitlab.com/srcmc/rct/api/-/issues/11
   - Earlier rctapi changelogs also list softlock fixes: 0.13.8 "Pokemon
     fainting ... on both sides", 0.14.2 #89, 0.14.3 #90 "when AI switches", and
     0.14.4 #92 "instructions getting executed in the wrong order". Source:
     https://api.modrinth.com/v2/project/rctapi/version
7. **Cobblemon 1.8.0 has no parser for Showdown `|tie`.**
   - `ShowdownInterpreter.kt` at tag `1.8.0` registers
     `updateInstructionParser["win"] = { ... -> WinInstruction(message) }`. No
     key named `tie` exists.
   - Unknown ids fall through to `?: UnknownInstruction(message)`.
     `UnknownInstruction.invoke` only does
     `battle.dispatchGo { battle.broadcastChatMessage(battleMessage.rawMessage.red()) }`.
   - `WinInstruction` is the path that sets `battle.winners` and `losers`, calls
     `battle.end()` and posts `BATTLE_VICTORY`.
   - Sources:
     https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/battles/ShowdownInterpreter.kt,
     `.../battles/interpreter/instructions/WinInstruction.kt` and
     `.../UnknownInstruction.kt` at the same tag.
8. **In Gen 5+, a simultaneous knockout is not scored as a tie.**
   - Upstream Showdown `checkWin` (and Cobblemon's fork on `master`) does this
     when all sides have zero Pokemon left:
     `this.win(faintData && this.gen > 4 ? faintData.target.side : null)`.
     `faintData` is the last entry taken from `faintQueue` in `faintMessages`.
   - `win()` only emits `tie` when `side` is null.
   - Sources: https://raw.githubusercontent.com/smogon/pokemon-showdown/master/sim/battle.ts
     and https://gitlab.com/cable-mc/cobblemon-showdown/-/raw/master/sim/battle.ts
     (fork last activity 2026-09-04).
9. **Cobblemon 1.8.1 (2026-09-12, Fabric 1.21.1) has no battle-flow fix.** Its
   full changelog has no line about softlocks, ties, faint handling or battle
   end. The only battle-adjacent lines are animation fixes, for example
   Mantyke/Mantine/Quaxly "stuck in a recoil 'expression'". Source:
   https://api.modrinth.com/v2/version/gBW3vLC7
10. **Cobblemon 1.8.0 already includes a related fix,** so we already have it:
    "Fixed a rare issue with battles locking up when you are forced to switch,
    with the switch menu appearing instantly." Source:
    https://wiki.cobblemon.com/index.php/1.8.0
11. **Other known freezes that do not match this incident:**
    - Cobblemon #1518: switch-in hazards fainting several Pokemon in one turn
      (1.6.1, open). https://gitlab.com/cable-mc/cobblemon/-/work_items/1518
    - Cobblemon #2092: an invalid `ShiftActionResponse` from the back button
      (1.8.0/1.8.1, open). https://gitlab.com/api/v4/projects/cable-mc%2Fcobblemon/issues/2092
    - rctmod #138: Flip Turn/U-turn KO (closed 2026-09-08) and #139: Dynamax in
      doubles (open). https://gitlab.com/api/v4/projects/srcmc%2Frct%2Fmod/issues?search=battle
12. **cobblemon-battle-extras has no Cobblemon 1.8 release.**
    - Its latest is 1.13.45 (2026-04-22). Modrinth lists no issues URL or source
      URL; the licence is All Rights Reserved.
    - It is client-required and server-optional.
    - No changelog entry from 1.11.38 to 1.13.45 concerns faint or battle-end
      handling.
    - Sources: https://api.modrinth.com/v2/project/2iY8VFqL and
      https://api.modrinth.com/v2/project/2iY8VFqL/version
13. **cobblemon-battle-positions has no public home that we found.** Our
    inventory records its source as `"type": "unresolved"` and its
    dependencies as `rctapi >=0.14.0` (`modpack/manifest/base-cobbleverse-1.7.42.json:1602-1621`).
    A Modrinth search for it returned 0 hits. No issue tracker was found.
14. **None of the checked sources documents a recovery path other than the
    operator's `/stopbattle`.** The RCT 0.13 FAQ has no entry on stuck battles
    (https://srcmc.gitlab.io/rct/docs/0.13/faq/). The rctmod 0.19.1 and 0.19.2
    changelogs list no battle fixes; their changes are speech bubbles, TMs in
    loot tables, and client render fixes (https://api.modrinth.com/v2/project/rctmod/version).

## Assumed

1. **The staging hang is rctapi #132.** This is the only published bug and fix
   that matches the symptoms: both sides faint on the same turn, the log has no
   exception, and the battle hangs until it is stopped. The claim stays ASSUMED
   for three reasons:
   - rctapi's public issue tracker ends at #33, so the text of issue #132 could
     not be read. It is likely on a private or different tracker.
   - We did not reproduce the hang on 0.16.0 or its absence on 0.16.1.
   - We do not know whether both sides still had Pokemon.
2. **The failing branch is "both sides must switch".** If only the player had
   run out, Showdown's second `checkWin` loop emits `|win|` for Brock. If both
   had run out, the Gen 5+ rule gives the win to the side of the last Pokemon
   to faint, not a tie. Either way `WinInstruction` would have ended the battle.
   A hang therefore fits best with both sides still having Pokemon and needing a
   simultaneous switch, which is where the rctapi mixin applies.
   - This is ASSUMED because it relies on the order of Head Smash's damage and
     recoil in `faintQueue`, which was not traced.
   - It also assumes staging's Cobblemon jar uses fork code identical to
     `master`.
3. **A true `|tie` would also hang Cobblemon 1.8.0, with no rctapi
   involvement.** The code implies the battle would print a red raw `|tie` line
   in chat and never call `battle.end()`. This was inferred from the code and
   not observed. The Gen 5+ rule should make a tie rare in singles; `faintData`
   is only null when `checkWin` is reached with an empty faint queue.
4. **Staging's rctmod 0.19.0-beta accepts rctapi 0.16.1-beta.** Only the branch
   head (0.19.2) was read, and it requires `>=0.16.0-beta`. The rctmod changelog
   records no rctapi floor change between 0.19.0 and 0.19.2.
5. **The "wasn't found in section ... DISCARDED" warning is unrelated.**
   - The message is assumed to be vanilla entity-section bookkeeping, logged
     when a discarded entity is no longer in the section it was indexed under.
     No Mojira or Cobblemon issue that names it was found.
   - The incident report says the warning appeared for every fainted player
     Pokemon, including Marshtomp and Finneon earlier in the same battle, and
     the battle continued after those. So the warning does not by itself mark
     the hang.
6. **The BattlePositions warning is unrelated.** "Trainer stand block not
   found; opponent teleport skipped" means no opponent teleport happened, so a
   BattlePositions teleport cannot have disturbed Brock's side. The inference
   comes from the message text; we have no source for the mod.

## Unknown / experiment candidates

These are not added to `docs/research/EXPERIMENT_BACKLOG.md`, because this task
was limited to `docs/research/notes/`. They should be carried there.

- **Reproduce on staging, then swap versions.**
  - Setup: an rct trainer battle in which a recoil move KOs the target and its
    user on the same turn, with both sides still holding Pokemon.
  - Run it on rctapi 0.16.0-beta and expect the hang. Run it on 0.16.1-beta and
    expect both sides to switch in.
  - A cheaper trigger than recoil is Perish Song or Explosion.
  - Pass condition: the battle continues on 0.16.1 with no `/stopbattle`.
- **Last-Pokemon double KO.** Run the same setup with both sides on their last
  Pokemon. Record the chat line, which should be a `win` for the recoil user's
  side, and whether the battle ends.
  - This confirms the Gen 5+ rule in Cobblemon's fork.
  - It also shows whether a `|tie` can reach the `UnknownInstruction` path.
- **Brock's roster.** Read `kanto_brock` in the Cobbleverse RCT datapack
  (`COBBLEVERSE-RCT-DP-v20`) to see whether Cranidos can be his last Pokemon.
  Also check the player's party size at the time.
- **Local jar confirmation, once the server gate allows it.**
  - Check that the staging `rctapi-fabric-1.21.1-0.16.0-beta.jar` lists
    `BattleActorMixin` in its mixin config.
  - Check that the updated jar still lists the class but without the
    `postUpdate` injection.
  - This needs a shell and the live-server gate in CLAUDE.md.

## Mitigation, in the requested order

1. **Cobblemon native:** none found. Cobblemon 1.8.1 has no relevant fix
   (Verified 9), and the related "forced to switch" fix is already in 1.8.0
   (Verified 10). `/stopbattle` remains the operator recovery.
2. **Addon update:** rctapi 0.16.0-beta to **0.16.1-beta** (Verified 1-4).
   - It targets MC 1.21.1 Fabric and needs Cobblemon 1.8.
   - It also adds an optional `battleScript` AI config property, which is
     described only by its changelog.
   - rctmod 0.19.2-beta also exists but has no battle fix.
3. **Configuration:** none found. No documented config key in Cobblemon, rctmod
   or rctapi addresses this.
