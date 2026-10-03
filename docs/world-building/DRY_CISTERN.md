# The Dry Cistern

A place to find on the Scorched Plateau's west brow (cell F5, sub-region `plateau_west`, region `scorched_plateau`,
paint `badlands_top`), on the high ground above Route 8: an acacia well-head with a lantern over a capped draw-shaft,
the keeper's roofless fallen house, and a stair cut down from the west into a rock-cut cistern under the tableland,
its roof on four pillars, a white band round its walls where the water stood. The keeper's sign says it has been dry
"since the ground opened": the Rift drained the plateau.

- Record: `data/dry_cistern.json` (hand-authored; every Y derived from the heightmap)
- Generator: `tools/dry_cistern.py` -> `build/datapacks/cobblers_dry_cistern` (`--report` writes nothing), on
  `tools/wayside_kit.py`
- Re-apply: **R9CI** (a block pass before R9E: hold, build, release)
- Shared record: the cache `dry_cistern_store` (`data/rewards.json`): a Water Stone, 2 Heavy Balls
- Independent audit: **owed** (below). Tests: none of its own yet.

Status: generated 2026-10-03. **Not audited, not applied to any world, not seen in game.**

## Why here

The second emptiest walked stretch of the south, measured 2026-10-03 (the table in `CHALLENGERS_CAIRN.md`): (4496,
5904), 296 blocks from the nearest authored thing, 139 off Route 8. The site, (4530, 5850), is the brow where the
ground climbs from y155 on the road to y161-166, a broad tilted top with nothing on it. A cistern is what dry high
country keeps; the Water Stone is why it matters: it lies on Route 8, before Giovanni, and water answers a ground team
(`docs/vision/GAME_VISION.md` pillar 1). Optional; the critical path needs none of it.

Measured by the report: the well-head lantern (4534, 166, 5852) is in sight of a standing eye from 76 of Route 8's
walked points (every 4th within 250 blocks); the write box is 105 blocks from the nearest.

## What is built

Cistern floor y151, a 9 by 7 room 5 high (y152-156), the water line at y154; least ground over a roofed void 2 (the
stair's last roofed step). A 12-step stair west (7 roofed, 5 open between red sandstone walls). The draw-shaft at
(4534, 5852): a ladder from the floor to y162, a closed trapdoor in the ground's top block y163, a slab ring, two posts
and a crossbar y167. House floor y163. 2,087 blocks written, x4513-4536 z5838-5855 y150-167.

## What an audit must check

Another agent writes it; it must not import `tools/dry_cistern.py` or `tools/wayside_kit.py` geometry.

1. Every written block is in `blocks.ids`; none is a spawn condition (`data/spawn_blocks.json`) unscoped by
   `data/spawn_block_policy.json` for `dry_cistern`. In particular no `minecraft:sand` or `minecraft:red_sand`
   (both conditions) and no chest or bed.
2. The cistern floor = min ground over the 9 by 7 footprint minus 11, from `tools/ground.py`; every room void has at
   least 6 blocks over it and every roofed stair void at least 2; every void is air in the replayed function.
3. The stair is walkable as in the cairn's audit (one block a step, every step a stair facing west, the way up; 3 air
   above, the top step level with the ground).
4. The shaft: a ladder on every block from the floor to the block under the trapdoor, each with a solid block east of
   it; the trapdoor closed in the ground's top block; nothing solid in the shaft.
5. The well-head's posts and slabs stand on their own columns' ground; the house floor is max ground under its walls
   plus 1 with a foundation down to the ground everywhere under it.
6. The four pillars stand floor to roof; the white terracotta band is only in walls that face the room.
7. The barrel at `dry_cistern_store` `container.at`, the trigger box standable air touching it, and not the shaft's foot.
8. Hung blocks written top down after what holds them; every write inside the function's and R9CI's force-load box and
   `bbox.writes`.
9. Re-measure the sightline from Route 8 and the clearance from every other build's box and every Habitat Block.
10. A GENERATOR mutation (cover cut to 1, a ladder missing, the trapdoor open) is caught.
