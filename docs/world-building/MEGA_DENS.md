# The Mega dens, made visible

The owner, 2026-10-02: *"Den dressing rather than a taller trigger box. I want to see something from the air and go
down to it, not trigger a spawn by flying near. That is the whole 'seen, not reached' idea."*

Until this pass the seven open-air Mega dens of the southern Rift (`data/gulch_mine.json` `farms[].dens[]`) wrote no
block at all: a den was a keeper line and a leash line. Each now has a lair round its anchor, about 24-30 blocks across,
that reads from the air against the Rift skin's distortion stone and tuff.

| | |
|---|---|
| Data | `data/mega_dens.json` (the dressing only; species, anchor and leash stay in `data/gulch_mine.json`) |
| Builder | `tools/mega_dens.py build` -> `build/datapacks/cobblers_mega_dens` (world-local), one function per den |
| Audit | `tools/mega_dens_audit.py` (independent: replays the functions against the records and the heightmap) |
| Tests | `tests/test_mega_dens.py` (clean pack + ten generator mutations, each caught) |
| Step | **R9MD**, after R9S (the gulch, whose keeper spawns the Megas at these anchors) and before R9E. Per den: `forceload add` its write box, wait 3, run `cobblers:mega_dens/<species>`, `forceload remove` |
| Lighting | **Dark by design.** Wild lairs: no lantern, torch, campfire or any light-emitting block |

## What every den has

- **The scrape**: a ragged disc (radius 12 +/- 2) of churned ground written AT each column's own ground level, in the
  species' mix of coarse dirt, rooted dirt, podzol, gravel, snow, sandstone, ash or char. The audit fails a den if
  more than a fifth of it is the skin's own palette.
- **The ring**: up to nine shoved boulders at 13-15 blocks, 2-3 high, broken by a 40-degree gap where the approach comes in.
- **The approach**: a three-wide trampled track (path blocks and churned dirt) from 10 to 24 blocks out, pointing toward
  the nearest point of the critical path (`data/route_paths.json`), so the track on the ground points the way a player
  came.
- **The carcass**: a bone spine with ribs and a skull 7 blocks out, and loose bones over the scrape.
- **The sign** at `feature_at`, 8-9 blocks from the anchor on the side away from the approach.
- **The pad**: every column within 3 of the anchor levelled to the anchor's ground (one block) and the 6 blocks over
  it written air. The gulch's keeper spawns the Mega AT the anchor; nothing else is written within 3 of it, and nothing
  that stands on the ground comes within 4.

## The seven dens, and where to fly

Fly to the coordinates in the last column and look down from about 30 blocks up: the disc and the ring are what to
look for first, the sign second.

| Den | Species | Anchor (Mega spawns here) | The sign | Its most visible feature (fly to) |
|---|---|---|---|---|
| `gm_east_arm_shoulder` | Aggron | (4528, 123, 4416) | torn ore and iron scrap: a spoil heap 3 high of torn rock studded with raw iron and raw copper, bent iron bars standing out of it, chain and a wrecked anvil thrown aside | spoil heap top, bars on it: **(4536, 126, 4419)** |
| `gm_east_arm_bench` | Pinsir | (4576, 122, 4680) | felled and split trunks: a woodpile of crossed oak logs, trunks lying split lengthwise (bark beside stripped wood), snapped stumps | woodpile: **(4583, 123, 4683)** |
| `gm_east_arm_head` | Manectric | (4608, 133, 4944) | scorched and fused ground: an obsidian strike point, seven forking black streaks of blackstone and basalt across the scrape, glass fulgurites where the bolts ended | the black star round the strike: **(4605, 132, 4936)** |
| `gm_east_arm_tail` | Houndoom | (4488, 145, 5216) | charred ground and ash: the whole scrape grey and black (concrete-powder ash, coal block, blackstone, soul soil), burnt dark-oak trunks with coal ends, a heap of bone and skulls | the ash disc and bone heap: **(4482, 145, 5210)** |
| `gm_west_arm_crest` | Abomasnow | (3944, 147, 3904) | a frost patch: snow block and packed ice over the scrape and past it, drifts of snow layers, packed-ice spires with blue-ice tips | the tallest spire (6): **(3937, 152, 3909)** |
| `gm_west_arm_shelf` | Tyranitar | (4080, 149, 4168) | smashed boulders and a crater: a crater of radius 4 punched 2 into the ground with a rubble rim, the ring's boulders split through with pieces knocked off | the crater floor: **(4071, 146, 4168)** |
| `gm_west_arm_tail` | Garchomp | (4248, 129, 5328) | a sand burrow (in sandstone: sand is a spawn condition): a pale sandstone fan, a dark 3x3 hole 2 deep lined in sandstone, a mound on three sides and a stair out on the fourth | the burrow's floor: **(4243, 125, 5321)** |

Write boxes (`[x0, y0, z0, x1, y1, z1]`, the anchor +/- 27 and its ground -8..+14) are in `data/mega_dens.json`
`dens[].write_box`; each is inside `farms_grid` (x 3828..4692, y 87..197, z 3840..5392), and nothing was widened.

## Substitutions (spawn-condition contract C4)

Sand, magma block, iron block, iron ore and plain ice are spawn conditions (`data/spawn_blocks.json`) or leave water
when broken, and no policy entry allows them here. So Garchomp's sand is sandstone, Houndoom's embers are coal block
and blackstone, Aggron's iron is raw iron and raw copper block, and Abomasnow's ice is packed and blue ice, which never
melt and never leave water. The audit is listed as a C4 checker in `data/system_contracts.json`.

## Measured, and what is not verified

- Every anchor is round(ground) + 1 on the canonical heightmap. Within 3 of the anchors the ground varies by at most
  one block (pinsir: one column a block higher, cut to air by the pad; garchomp: one a block lower, under the pad).
- No den column is under painted water; the nearest critical path is 169 blocks (abomasnow); every den is 32+ blocks
  from every placement and from the Rift zone walls and posts, writes nothing inside the gulch's block box
  (`gulch_mine.json` `grid`) or zone polygon (the closest anchor, manectric, is 68 blocks from the polygon), and is
  590+ blocks from the nearest resident anchor.
- **Two anchors (abomasnow, tyranitar) lie inside Rift zone z2's AREA** (`data/rift_zones.json` `zones.z2.boxes`), and
  aggron's box reaches it. The gulch put the dens there; a zone's area is an access region, not a footprint of blocks.
  What the zones build (cross-walls, gatehouse posts) is 32+ blocks from every den. If "outside every Rift zone" was
  meant as the area itself, two of these dens cannot be dressed where the gulch puts them: that is the owner's call.
- **Not verified in a world**: that the fills land on the ground the heightmap predicts (the skin pass R1 writes over
  the same surface first and this pass writes over it), how the dens read from the air, and that the keeper's Mega
  spawns cleanly on the pad. The probes below are what a session holding the server runs after R9MD.
- The re-application step list cannot be built in a worktree (it needs the other packs' indexes);
  `tests/test_mega_dens.py` checks R9MD sits between R9S and R9E in `tools/reapply.py`'s source.

## World probes

Generated by `python tools/mega_dens.py probes` from the build (re-run it after any change to the dens). Every line is
expected to answer `Test passed` after R9MD has run. Blocks are named by id only, so any state matches.

### Aggron (`gm_east_arm_shoulder`), anchor (4528, 123, 4416)

- `execute if block 4528 122 4416 minecraft:coarse_dirt` -> `Test passed` (the pad under the anchor)
- `execute if block 4528 123 4416 minecraft:air` -> `Test passed` (the anchor itself is open)
- `execute if block 4528 128 4416 minecraft:air` -> `Test passed` (the top of the head room)
- `execute if block 4531 124 4416 minecraft:air` -> `Test passed` (the edge of the spawn cylinder)
- `execute if block 4536 126 4419 minecraft:iron_bars` -> `Test passed` (the sign's own column, at its top (spoil_heap))
- `execute if block 4512 122 4411 minecraft:dirt_path` -> `Test passed` (the trampled approach)
- `execute if block 4540 124 4407 minecraft:tuff` -> `Test passed` (the top of the tallest ring boulder)
- `execute positioned 4528 123 4416 if entity @e[type=cobblemon:pokemon,distance=..32]` -> `Test passed` while the gulch's keeper holds this den's Mega (cobblers_gulch_mine, not this pack)

### Pinsir (`gm_east_arm_bench`), anchor (4576, 122, 4680)

- `execute if block 4576 121 4680 minecraft:rooted_dirt` -> `Test passed` (the pad under the anchor)
- `execute if block 4576 122 4680 minecraft:air` -> `Test passed` (the anchor itself is open)
- `execute if block 4576 127 4680 minecraft:air` -> `Test passed` (the top of the head room)
- `execute if block 4579 123 4680 minecraft:air` -> `Test passed` (the edge of the spawn cylinder)
- `execute if block 4583 123 4683 minecraft:stripped_oak_log` -> `Test passed` (the sign's own column, at its top (woodpile))
- `execute if block 4561 121 4674 minecraft:dirt_path` -> `Test passed` (the trampled approach)
- `execute if block 4586 124 4670 minecraft:mossy_cobblestone` -> `Test passed` (the top of the tallest ring boulder)
- `execute positioned 4576 122 4680 if entity @e[type=cobblemon:pokemon,distance=..32]` -> `Test passed` while the gulch's keeper holds this den's Mega (cobblers_gulch_mine, not this pack)

### Manectric (`gm_east_arm_head`), anchor (4608, 133, 4944)

- `execute if block 4608 132 4944 minecraft:coarse_dirt` -> `Test passed` (the pad under the anchor)
- `execute if block 4608 133 4944 minecraft:air` -> `Test passed` (the anchor itself is open)
- `execute if block 4608 138 4944 minecraft:air` -> `Test passed` (the top of the head room)
- `execute if block 4611 134 4944 minecraft:air` -> `Test passed` (the edge of the spawn cylinder)
- `execute if block 4605 132 4936 minecraft:obsidian` -> `Test passed` (the sign's own column, at its top (strike))
- `execute if block 4614 133 4959 minecraft:dirt_path` -> `Test passed` (the trampled approach)
- `execute if block 4622 136 4944 minecraft:tuff` -> `Test passed` (the top of the tallest ring boulder)
- `execute positioned 4608 133 4944 if entity @e[type=cobblemon:pokemon,distance=..32]` -> `Test passed` while the gulch's keeper holds this den's Mega (cobblers_gulch_mine, not this pack)

### Houndoom (`gm_east_arm_tail`), anchor (4488, 145, 5216)

- `execute if block 4488 144 5216 minecraft:soul_soil` -> `Test passed` (the pad under the anchor)
- `execute if block 4488 145 5216 minecraft:air` -> `Test passed` (the anchor itself is open)
- `execute if block 4488 150 5216 minecraft:air` -> `Test passed` (the top of the head room)
- `execute if block 4491 146 5216 minecraft:air` -> `Test passed` (the edge of the spawn cylinder)
- `execute if block 4482 145 5210 minecraft:bone_block` -> `Test passed` (the sign's own column, at its top (bone_pile))
- `execute if block 4500 145 5228 minecraft:dirt_path` -> `Test passed` (the trampled approach)
- `execute if block 4502 147 5216 minecraft:cobbled_deepslate` -> `Test passed` (the top of the tallest ring boulder)
- `execute if block 4481 145 5211 minecraft:skeleton_skull` -> `Test passed` (a skull)
- `execute positioned 4488 145 5216 if entity @e[type=cobblemon:pokemon,distance=..32]` -> `Test passed` while the gulch's keeper holds this den's Mega (cobblers_gulch_mine, not this pack)

### Abomasnow (`gm_west_arm_crest`), anchor (3944, 147, 3904)

- `execute if block 3944 146 3904 minecraft:snow_block` -> `Test passed` (the pad under the anchor)
- `execute if block 3944 147 3904 minecraft:air` -> `Test passed` (the anchor itself is open)
- `execute if block 3944 152 3904 minecraft:air` -> `Test passed` (the top of the head room)
- `execute if block 3947 148 3904 minecraft:air` -> `Test passed` (the edge of the spawn cylinder)
- `execute if block 3937 152 3909 minecraft:blue_ice` -> `Test passed` (the sign's own column, at its top (frost))
- `execute if block 3961 144 3894 minecraft:dirt_path` -> `Test passed` (the trampled approach)
- `execute if block 3946 149 3918 minecraft:calcite` -> `Test passed` (the top of the tallest ring boulder)
- `execute positioned 3944 147 3904 if entity @e[type=cobblemon:pokemon,distance=..32]` -> `Test passed` while the gulch's keeper holds this den's Mega (cobblers_gulch_mine, not this pack)

### Tyranitar (`gm_west_arm_shelf`), anchor (4080, 149, 4168)

- `execute if block 4080 148 4168 minecraft:coarse_dirt` -> `Test passed` (the pad under the anchor)
- `execute if block 4080 149 4168 minecraft:air` -> `Test passed` (the anchor itself is open)
- `execute if block 4080 154 4168 minecraft:air` -> `Test passed` (the top of the head room)
- `execute if block 4083 150 4168 minecraft:air` -> `Test passed` (the edge of the spawn cylinder)
- `execute if block 4071 146 4168 minecraft:andesite` -> `Test passed` (the sign's own column, at its top (crater))
- `execute if block 4071 148 4168 minecraft:air` -> `Test passed` (the crater is open where the ground was)
- `execute if block 4097 146 4169 minecraft:dirt_path` -> `Test passed` (the trampled approach)
- `execute if block 4091 151 4159 minecraft:cobblestone` -> `Test passed` (the top of the tallest ring boulder)
- `execute positioned 4080 149 4168 if entity @e[type=cobblemon:pokemon,distance=..32]` -> `Test passed` while the gulch's keeper holds this den's Mega (cobblers_gulch_mine, not this pack)

### Garchomp (`gm_west_arm_tail`), anchor (4248, 129, 5328)

- `execute if block 4248 128 5328 minecraft:smooth_sandstone` -> `Test passed` (the pad under the anchor)
- `execute if block 4248 129 5328 minecraft:air` -> `Test passed` (the anchor itself is open)
- `execute if block 4248 134 5328 minecraft:air` -> `Test passed` (the top of the head room)
- `execute if block 4251 130 5328 minecraft:air` -> `Test passed` (the edge of the spawn cylinder)
- `execute if block 4243 125 5321 minecraft:smooth_sandstone` -> `Test passed` (the sign's own column, at its top (burrow))
- `execute if block 4243 127 5321 minecraft:air` -> `Test passed` (the burrow is open where the ground was)
- `execute if block 4258 129 5341 minecraft:dirt_path` -> `Test passed` (the trampled approach)
- `execute if block 4261 130 5322 minecraft:sandstone` -> `Test passed` (the top of the tallest ring boulder)
- `execute positioned 4248 129 5328 if entity @e[type=cobblemon:pokemon,distance=..32]` -> `Test passed` while the gulch's keeper holds this den's Mega (cobblers_gulch_mine, not this pack)
