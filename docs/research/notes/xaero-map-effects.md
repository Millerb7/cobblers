# Xaero's map status effects: do they stop the cache, or only the display?

Asked 2026-09-26: this is open question 1 of Codex's gated-interactions spec, and it gates the pocket approach. The
spec itself is not in this repository or any local checkout; the question is taken from the owner's summary. The
question: do the Xaero status effects the pack enables stop Xaero from **writing** its map cache, or only from
**rendering** it? If writing continues, a player who later opens the world map finds whatever the pockets are, for
example a grid of chambers in the western ocean.

Jars: `xaerominimap-fabric-1.21.1-26.4.2.jar` and `xaeroworldmap-fabric-1.21.1-1.44.2.jar`. The server's copies and
the staging client's copies are byte-identical (`cmp`). They were read with `javap`.

## The effects (VERIFIED, from the jars and the running server)

| Effect id | Mod | Accepted by `effect give` on staging |
|---|---|---|
| `xaerominimap:no_minimap` | minimap | yes |
| `xaerominimap:no_entity_radar` | minimap | yes |
| `xaerominimap:no_waypoints` | minimap | yes |
| `xaerominimap:no_cave_maps` | minimap | yes |
| `xaeroworldmap:no_world_map` | world map | yes |
| `xaeroworldmap:no_cave_maps` | world map | yes |

Each also has a `_harmful` variant (`effect.xaerominimap.no_minimap_harmful`, and so on) that the same code checks.
Two of those were tried on the server and were accepted. A made-up id (`xaerominimap:not_real`) is rejected with
"Can't find element ... of type 'minecraft:mob_effect'", so the check does discriminate. There are six base effects,
not five: the minimap and the world map each register their own `no_cave_maps`.

**Per player.** Effects are applied to the player entity, and every check listed below reads the local client's own
player. So one player's effects cannot hide another player's map. This is a property of mob effects in general and
was read from the code; it was not tested with two players.

## What each effect suppresses (VERIFIED, from the bytecode)

Every method in either jar that reads each effect's field:

| Effect | Read in | What that is |
|---|---|---|
| `no_world_map` | `xaero.map.gui.GuiMap.render` (`method_25394`) only | the world map screen: it draws a "no world map" message in place of the map |
| world map `no_cave_maps` | `WorldMapConfigOptionClientRedirectors` | redirects `CAVE_MODE_ALLOWED` to OFF while the effect lasts |
| `no_minimap` | `MinimapRenderer.render`, `ToggleMapFunction.onPress` | the minimap HUD, and its toggle key |
| `no_entity_radar` | `RadarStateUpdater.update` | the radar dots |
| `no_waypoints` | `WaypointMapRenderer.shouldRender`, `WaypointWorldRenderer.shouldRender`, `ClientEvents.handleGuiOpen`, `TemporaryWaypointFunction.onPress` | drawing waypoints, opening waypoint screens, making temporary waypoints |
| minimap `no_cave_maps` | `MinimapConfigClientUtils.hasNoCaveModeEffect` | the minimap's cave mode |

**The world map's writer never reads an effect.**
- `xaero.map.MapWriter` and `xaero.map.MapProcessor` contain no reference to `xaero.map.effects.Effects`.
- The writer is gated only by config options: `WRITING_DISTANCE`, `UPDATE_CHUNKS`, `LOAD_NEW_CHUNKS`,
  `FORCE_FAST_WRITING`, `LIGHTING`, `FLOWERS`, `ADJUST_HEIGHT_FOR_SHORT_BLOCKS`, the cave-mode depth and timer
  options, `SKIP_WORLD_RENDER` and `MAP_ITEM`.

**Reading from the code:** `no_world_map` and `no_minimap` hide the maps and leave the writer running. A player under
them still records every region the writer reaches, and sees it all once the effect ends.

**One possible partial exception.** World map `no_cave_maps` turns `CAVE_MODE_ALLOWED` off. Whether the writer also
stops writing cave layers when cave mode is not allowed has not been traced (NOT VERIFIED). It would not matter for
surface features, because the writer always records the surface.

## Test in game

The in-game test is set up on staging (`cobblers-dryrun11`).
- A 15 x 15 magenta concrete pad with a lime cross stands on the western ocean at (-640, 62, 4096), inside the
  border's western margin.
- The staging client's current world-map cache (`xaero/world-map/Multiplayer_localhost/null/mw$-644763732`, 111
  regions) holds no region west of x = 0, so any `-N_*.zip` written there is new.
- The pad is in region file `-2_8.zip`.

**Procedure:**
1. Apply all six effects to the player.
2. Teleport them to the pad and wait there for 30 s.
3. Teleport them back and clear the effects.
4. Check two things:
   - on disk, whether `-2_8.zip` or any other negative-x region now exists (this counts after the region is saved or
     the player logs out);
   - in game, whether the world map shows the pad.

Result: _not yet run_.

## What it means for the gated-interactions design

If the test confirms the reading above, these effects cannot hide the pockets from the map; they only blank the map
while a player is inside. Ways out, to be judged in the spec:
- keep the pockets where the map shows nothing distinctive (for example deep under a uniform seabed, the surface only);
- build the pockets so their top-down surface reads as ordinary terrain;
- use a server-enforced Xaero config for the pocket area, if the per-server profile can limit writing. The world map's
  options are "profiled", and whether a server profile can force `LOAD_NEW_CHUNKS` or `WRITING_DISTANCE` for its players
  is NOT VERIFIED;
- accept that the map remembers.
