# EXP-008: Reusable structure placement

## Objective

Determine whether representative Cobblemon/Cobbleverse NBT and jigsaw structures
can be placed, transformed, saved, and reloaded in the Cobblemon 1.8 server
baseline without touching a campaign world.

Success requires at least one Pokémon Center, settlement piece, Gym fixture,
legendary structure, and jigsaw settlement family to resolve through server
commands, followed by a clean save and restart. Visual and gameplay behavior are
reported separately rather than inferred from command success.

## Implementation

The existing EXP-000 101-jar runtime was pointed temporarily at a gitignored flat
Creative world named `structure-proof`. No jar, base-pack file, or future campaign
world was modified. Placement used vanilla commands; Huge Structure Blocks was
present but its extended UI was not exercised.

## Test instructions

With Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0, and the EXP-000
101-jar server plan:

```mcfunction
/place template cobblemon:village_plains/village_plains_pokecenter 0 80 0
/place template cobblemon:village_plains/village_plains_pokecenter 64 80 0 clockwise_90 front_back 1.0 12345
/place template bca:default/one_off/small_battlepad 0 80 128 clockwise_90 left_right 1.0 12345
/place template bca:default/one_off/structure_pokemart 160 80 160 clockwise_90 none 1.0 12345
/place template cobbleverse:brock 0 80 256 180 none 1.0 12345
/execute in minecraft:the_nether run place template legendarymonuments:firescourge_shrine 256 80 0 clockwise_90 front_back 1.0 12345
```

For jigsaw villages, force-load a 15×15-chunk square around the target before:

```mcfunction
/place structure bca:village/default_small 0 80 0
/place structure bca:village/fighting_small 320 80 0
/save-all flush
```

Stop, restart the same disposable world, wait for `Done`, then stop cleanly.

## Results

Functional/headless run on 2026-09-09:

- The Center, Mart, battle pad, Gym and shrine raw-template commands resolved and
  reported `Loaded template`; 90°,
  180°, `front_back`, and `left_right` transform arguments were accepted.
- Both BCA small village IDs reported `Generated structure` once a 15×15 chunk
  area was loaded. Smaller loaded areas failed with `That position is not loaded`.
- BCA generation emitted missing-pool warnings for `bca:paths`,
  `bca:store_workers`, and `bca:feature/decor`; village completeness is PARTIAL.
- Registered `legendarymonuments:firescourge_shrine` resolved but its terrain
  validator rejected the flat site. Raw template placement succeeded.
- `save-all flush` completed, the server stopped cleanly, and the same world
  restarted to `Done (1.315s)` before another clean stop.
- A save warning reported one Cobblemon PC block/entity mismatch at an unrelated
  generated coordinate. Exact cause and relation to the test placements are UNKNOWN.

The concise command/outcome record is `results.json`. It contains no runtime log
or world data.

## Limitations

No client joined. Visual block completeness, entity preservation/orientation,
PC/healer use, trainers, loot, jigsaw seams, terrain fit, mirroring appearance,
and multiplayer synchronization remain unverified. Runtime logs and the disposable
world are not committed.

## Decision

**PARTIAL / ADOPT FOR PROTOTYPES.** Vanilla template placement is a viable base
workflow and supports transforms. Jigsaw placement is viable for surveying but
BCA's missing pools prevent treating generated villages as finished assets.
Proceed to visually inspect and regionalize small component templates; do not begin
large campaign construction until the world-critical dependency freeze is complete.
