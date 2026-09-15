# EXP-020: Can a datapack flag drive waystone unlocks, and can Xaero's show them?

## Objective

Navigation is waystone-only (`docs/world-building/NAVIGATION.md`). A gym town's waystone
must unlock when that gym is beaten, not when a player first touches it. This experiment
answers three questions:
- whether the pack's Waystones mod can be driven from a datapack;
- which hooks exist to stop early activation;
- whether Xaero's can put markers on players' maps from the server.

## Success criteria

| Id | Question | Pass |
| --- | --- | --- |
| A | Do `waystones activate` / `waystones forget` compile inside a datapack function at `function-permission-level=2`? | the function loads; a function with an invalid `waystones` line (control) does not |
| B | Does an advancement on `rctmod:defeat_count` with `trainer_ids` load, with and without `count`? | both load; an advancement with an unknown trigger (control) does not |
| C | Can a scoreboard objective count waystone activations (`waystones:waystone_activated`)? | the objective is created |
| D | Do vanilla `any_block_use` / `default_block_use` advancements accept a waystone block location? | both load |
| E | Does Xaero's Minimap 26.4.2 or World Map 1.44.2 have a server-to-client waypoint packet? | a waypoint packet class registered in either jar |
| F (player) | At runtime: does the flag activate the waystone, does a right-click on a locked waystone get undone within a tick, and does the waystone appear on Xaero's map? | see Test instructions |

## Dependencies

Server `cobblers-server`:
- Minecraft 1.21.1 Fabric;
- Waystones 21.1.37 (Balm);
- rctmod 0.19.0-beta;
- Xaero's Minimap 26.4.2 and World Map 1.44.2 on both sides.

## Implementation

**Headless run, 2026-09-13.**
- **World:** the disposable EXP-019 world, copied as `exp020-waystones` and booted with
  `--world`. `server.properties` was not touched. The world was moved to scratch afterwards.
- **Probe datapack `exp020`:**
  - `function/activate`: `waystones activate @a <pos>`, `waystones forget @a <pos>`,
    `waystones forget @a all`, and an `execute … if entity @s[advancements=…] run waystones
    activate @s <pos>` line;
  - `function/bogus`: `waystones bogus @a` (control);
  - `advancement/flag/gym1` (`trainer_ids` and `count`) and `gym1_plain` (`trainer_ids` only);
  - `use_any` (`any_block_use`, block tag `#waystones:waystones`);
  - `use_default` (`default_block_use`, `waystones:waystone`);
  - `control_bad_trigger` (control).
- **Jar reads:** Python `zipfile` string scans of the Xaero minimap and world map jars and the
  Waystones and rctmod jars.

The generator the results feed is `tools/progression_pack.py`.

## Test instructions

Headless steps A–D are reproduced by booting the server with the probe pack and running over
RCON:
- `function exp020:activate` and `function exp020:bogus`;
- `scoreboard objectives add t minecraft.custom:waystones.waystone_activated`;
- `reload`, then read the log for `Failed to load function` and `Parsing error loading custom
  advancement`.

**F needs one player, about 15 minutes, on a disposable world:**
1. Generate the pack with a test position. Place a waystone there with
   `/setblock <pos> waystones:waystone`.
2. Walk to the waystone, right-click it, and wait one second.
   - **Pass:** it is not in the waystone list afterwards, and a Xaero waypoint does not
     remain.
3. Beat `kanto_brock`. A trainer spawner with a redstone block works, as in EXP-013 E.
   - **Pass:** the flag advancement is granted, the waystone is listed as activated, and a
     Xaero "discovered waystone" waypoint appears.
4. Log out and back in after `/advancement revoke @s only cobblers:flag/gym1_cleared`.
   - **Pass:** the waystone is forgotten on rejoin, and the waypoint is removed.
5. Share any waypoint from Xaero's waypoint menu and copy the chat line. Its exact format is
   what a server `tellraw` would have to reproduce (NAVIGATION.md §6).
6. Note what RCT shows when a party over the level cap talks to Brock (the cue question in
   NAVIGATION.md §5).

## Results

| Id | Result | Evidence |
| --- | --- | --- |
| A | **PASS.** `exp020:activate` loaded and ran; `exp020:bogus` failed with `Failed to load function exp020:bogus`, so compilation checks `waystones` lines at permission level 2 | server log, RCON `Running function exp020:activate` / `Unknown function exp020:bogus` |
| B | **PASS.** both `rctmod:defeat_count` advancements loaded (`DefeatCountTriggerInstance` fields read from the jar: `player`, `count`, `trainer_ids`, `trainer_type`); the unknown-trigger control failed | log: only `control_bad_trigger` and two Cobblemon advancements failed; loaded count rose by the two use advancements |
| C | **FAIL.** `Unknown criterion 'minecraft.custom:waystones.waystone_activated'`. The same form worked for `minecraft.custom:minecraft.jump` and `minecraft.custom:cobblemon.battles_won`. Balm registers the stat, but it is not in the custom-stat registry by name on this server | RCON |
| D | **PASS (loads).** Whether `any_block_use` fires on a waystone right-click is F | log |
| E | **No packet in either jar.** See below | jar read |
| F | **not run** (needs a player) | |

### What E found

**Minimap packet registration** (`MinimapPacketRegister`): handshake, rules, tracked player,
player-tracker reset and level map properties. **World map** (`xaero/map/message/`):
handshake, rules, tracked player and tracker reset. Neither registers a waypoint packet.

**Minimap waypoint routes found in code:**
- **Server origin:** `ServerWaypointManager` (origin `xaerominimap:server`) is `@Deprecated`.
  It is a client-side container, and no packet feeds it.
- **Chat sharing:** `WaypointSharingHandler` and `ClientEvents`. The client scans **system chat**
  (`handleClientSystemChatReceivedEvent`) as well as player chat for `xaero-waypoint:` and the
  older `xaero_waypoint:`.
  - It labels the sender "Server" and appends an **[Add]** link.
  - Clicking the link opens the Add Waypoint screen, prefilled. The player confirms and picks
    the set.
  - So a `tellraw` can offer a waypoint, but it cannot add, update or remove one on its own.
- **Waystones compatibility, built in:** `xaero/hud/compat/mods/SupportWaystones`.
  - It listens to the Waystones client events `WaystonesListReceivedEvent`,
    `WaystoneUpdatedEvent` and `WaystoneRemoveReceivedEvent`.
  - It adds each activated waystone as a third-party waypoint (a "discovered" origin), and
    each GLOBAL one under a separate origin.
  - It removes them on deactivation.
  - The server profile `config/xaero/minimap/profiles/cobbleverse.cfg` sets
    `discovered_waystone_waypoints = true` and `other_waystone_waypoints = true`.

**Consequence:** the unlocked-waystone layer on the map follows the waystone activation
state, and so the progression flag, with no new dependency. **Not verified in game (F).**

## Limitations

- Headless: no player, so nothing here shows a waystone actually activating, a click being
  undone, or a waypoint drawing.
- `forget` on a waystone a player never activated was not observed.
- The execution order of the `any_block_use` reward against the Waystones activation in the
  same click is unknown. The generator defers the resync by one tick for that reason.
- The share payload format was read only in part (field order is in `shareWaypoint`); step F5
  settles it.

## Decision

**Adapt.**
- Waystone unlocks are driven by advancement flags through `waystones activate/forget` in
  generated functions.
- Early activation is undone by a deferred resync on `any_block_use`. The activation stat
  cannot be used.
- Map markers for unlocked waystones come free from Xaero's built-in Waystones support.
- Gym markers regardless of unlock state have no silent server path. The options are in
  NAVIGATION.md §6.

## Follow-up

- F with one player.
- NAVIGATION.md §6: pick the gym-marker route.
