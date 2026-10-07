# Ambient Pokemon density, measured (2026-10-08, unit AMB)

The owner's ask (2026-10-08): *"Raise to 350-400 across the settlements. 237 is nine per town and they read thin.
Keep the composition: roughly 30% working, 15% pets, 20% placed in the world, 35% unique situations. Mining towns
higher on working. Each town gets several things nobody else has, written rather than generated."*

## Verdict on the premise

**"237 across 26 settlements" has no source in the repository and is wrong by a factor of three.** It first appears
in commit 12c730e as a question back to the owner. Counted from the data at 45fdc7e:

- **726 ambient Pokemon are authored**: 697 in the 20 town files (`data/ambient_towns/*.json`), plus the snow house's
  6 Buneary (`data/ambient.json` `idle.buneary.spots`) and Arrow Creeks Farm's 23 animals (`data/pokemon_farm.json`
  `animals`).
- **That matches staging**: `ambient_idle verify` read back 530 of 532 idle Pokemon in 22 groups and `ambient.py
  verify` 194 working (2026-10-07, `docs/MORNING_REPORT_2026-10-07.md`). 532 = 503 idle in the town files + 6 + 23,
  exactly; 194 = the town files' workers, exactly.
- The world total is already **well above the 350-400 asked for**, so nothing was added to reach a total. If the
  towns read thin in game, the cause is not the count in the data: either the look predates the 2026-10-07 apply, or
  something between the data and the client (the keeper, chunk loading, the 16-block wake) needs an in-game check.

## How the owner's categories map onto the data

| Owner's category | Data | Counted as |
|---|---|---|
| working | `workers` (tools/ambient.py's keeper) | one per record, `count` if present |
| pets | `pets` (an NPC owner, follow or wait) | one per record |
| placed in the world | `placed` (a `spot` on a `building`: roof, gutter, window, step) | one per record |
| unique situations | `situations` (title + story, members) | the sum of member `count`s |

"Unique" in the owner's sense is a property of a situation, not a category: the data marks it `unique: true`. Below,
**credited** = marked unique *and* its idea (not just its title) appears in no other town; see "Uniqueness" for the check.

## Per settlement (after this unit; counts unchanged by it)

| Settlement | Size | Total | Working | Pets | Placed | Situation Pokemon | Situations | Credited unique |
|---|---|---|---|---|---|---|---|---|
| displaced_city | town | 42 | 11 (26%) | 3 (7%) | 10 (24%) | 18 (43%) | 8 | 4 |
| gorge_hamlet | hamlet | 15 | 4 (27%) | 2 (13%) | 3 (20%) | 6 (40%) | 4 | 3 |
| gym1_town (Stoneford) | town | 48 | 12 (25%) | 7 (15%) | 9 (19%) | 20 (42%) | 8 | 3 |
| gym2_town | town | 47 | 11 (23%) | 6 (13%) | 10 (21%) | 20 (43%) | 8 | 4 |
| gym3_town | town | 43 | 11 (26%) | 5 (12%) | 9 (21%) | 18 (42%) | 7 | 3 |
| gym4_town | town | 48 | 13 (27%) | 7 (15%) | 8 (17%) | 20 (42%) | 7 | 4 (was 1) |
| gym5_town | town | 48 | 13 (27%) | 7 (15%) | 8 (17%) | 20 (42%) | 7 | 4 (was 1) |
| gym6_town | town | 48 | 13 (27%) | 7 (15%) | 8 (17%) | 20 (42%) | 8 | 3 (was 1) |
| gym7_town | town | 48 | 13 (27%) | 7 (15%) | 8 (17%) | 20 (42%) | 8 | 3 (was 1) |
| gym8_town | town | 48 | 13 (27%) | 7 (15%) | 8 (17%) | 20 (42%) | 7 | 3 (was 1) |
| merian_hut | outpost | 6 | 2 | 0 | 1 | 3 | 2 | 2 |
| mining_town (Fossick) | town | 44 | 22 (50%) | 4 (9%) | 4 (9%) | 14 (32%) | 7 | 4 (was 1) |
| northlight | town | 47 | 11 (23%) | 5 (11%) | 11 (23%) | 20 (43%) | 9 | 4 (was 5) |
| rift_dig_camp | outpost | 6 | 3 (50%) | 0 | 1 | 2 | 1 | 1 |
| rift_rim_stop | outpost | 6 | 2 | 0 | 1 | 3 | 1 | 1 |
| sea_town (Pacifidlog) | town | 47 | 13 (28%) | 5 (11%) | 9 (19%) | 20 (43%) | 9 | 4 (was 1) |
| sunset_west | town | 47 | 12 (26%) | 6 (13%) | 9 (19%) | 20 (43%) | 7 | 3 (was 4) |
| tableland_stop | outpost | 6 | 2 | 0 | 1 | 3 | 2 | 2 (was 1) |
| tea_town | town | 47 | 11 (23%) | 5 (11%) | 11 (23%) | 20 (43%) | 7 | 4 (was 4) |
| viltri_light | outpost | 6 | 2 | 0 | 1 | 3 | 2 | 2 |
| **20 town files** | | **697** | **194 (28%)** | **83 (12%)** | **130 (19%)** | **290 (42%)** | **133** | **61** |
| snow house (Buneary) | | 6 | | | | | | |
| Arrow Creeks Farm | | 23 | | | | | | |
| **All** | | **726** | | | | | | |

The composition is already close to the owner's: situations run high (42% against 35%, inside the audit's tolerance
of 0.08 or one Pokemon), pets low (12% against 15%). Every town is inside its size band (`data/ambient.json`
`composition.scale`: town 40-48, hamlet 10-16, outpost 3-6) and the cap of 48. **Stoneford's town file holds 48, not
51**; the 51 of N89 (`docs/OVERNIGHT_REVIEW_2026-10-06.md`) counts three Pokemon from some other source, not traced
here. Both mining settlements are at 50% working (`composition.mining_towns.working_min`).

## Settlements with no ambient Pokemon

`data/placements.json` has 27 settlements; the jungle ruins are retired (B15), which leaves the owner's **26**. Of
those, **20 have a town file** and **6 have none**, each for a recorded reason (`data/ambient.json`
`idle.not_populated`): the hometown (Pallet, intact by the owner's call), the League (nobody lives there), the Scar
(a dead city), Relic Island (nobody lives there), the Route 1 mansion (abandoned) and the Route 1 old mine (a mine
mouth). None of these was populated here: each "none" is a decision, the hometown's the owner's own.

**Our list is not the world.** Two towns with buildings are in no settlement list and have no ambient Pokemon:

- **The Cutters' Gulch cove town** (`data/gulch_mine.json` `town` and `cove`: a square, a rock-cut yard and 69
  buildings in sections of workers, miners and extractors, in staging by R9S). The owner named it a mining town to go
  higher on working. **Not built in this unit**: both generators seat Pokemon through a town plan
  (`tools/ambient.py` `Site` and the composed path of `tools/ambient_idle.py` read `derived/towns/<s>_plan.json` via
  `tools/town_dressing.town_plan`), and the gulch has no town plan; its buildings live in `gulch_mine.json` and its
  block model in `tools/gulch_mine.py`. It needs either a town plan for the gulch or a self-contained group like the
  farm's (`tools/pokemon_farm.py idlers`, checked against the place's own block plan), for workers as well as idlers;
  and `R16C`'s build cannot be run in a worktree without `derived/`. At the town scale it would take 40-48, at least
  half working.
- **The Deep's city** (`data/deep_city.json`, 196 buildings on the pit's rings, in staging by R9DC). Same gap; not
  named by the owner.

Other authored places (the far south's five, Drovers Hollow, the Copperway Khan) were not surveyed.

## Uniqueness: what "nobody else has" was checked against

All 133 situations carry a hand-written title and story; none is generated. But the composition audit's
`situations_distinct` compares only exact titles and exact species-plus-prop sets, so the same *idea* written twice in
different words passes it. Read across all twenty towns, the owner's own examples from the 2026-10-05 brief had been
reused:

| Idea | Towns before this unit | Credited to |
|---|---|---|
| something in a chimney pot | Displaced City, Stoneford, Northlight, Sunset West, Tea Town (all five marked unique); Tilpey's placed Misdreavus too | Northlight (the Froslass that will not let the fire catch) |
| the armorer's badly drawing chimney | Stoneford, Sunset West | rewritten in both |
| a line of Pokemon queuing at a door | Stoneford, Highwire, Fenhide, Cinderlee, Holdfast, Northlight, Sunset West | Highwire (waiting to be charged) |
| dogs at the butcher's door for scraps | Displaced City, Holdfast | rewritten in the Displaced City |
| Psyduck in a back garden / a tenant in a water butt | Viltri Quay (both), Greenhollow; Fenhide's placed Tympole in a rain butt | Viltri Quay; Greenhollow's rewritten, Fenhide's line rewritten |
| asleep in a crate of produce | Greenhollow (the owner's example), Tea Town | Greenhollow |
| Clefairy dancing at an observatory | Tilpey, Northlight | Northlight; Tilpey's rewritten |
| an owl on night watch | Rimwatch (worker), Viltri Light; Northlight's placed Hoothoot | Rimwatch; Viltri Light's rewritten |
| a Rhyhorn lying in a cart's way | Stoneford, Holdfast | Stoneford; Holdfast's rewritten |
| a Cacnea posing as a cactus | Bridgekeep (roof, Cacturne), Redbrow | Bridgekeep; Redbrow's rewritten |
| a Sudowoodo posing as a potted tree | Stoneford, Greenhollow (placed) | Stoneford; Greenhollow's line rewritten |
| a Tatsugiri taken for food | Pacifidlog, Sunset West (pet) | Pacifidlog; Sunset West's line rewritten |
| keys taken by a Pokemon | Stoneford, Fossick | Fossick; Stoneford's rewritten |
| a Pokemon in the water vessel others need | Viltri Quay (rain butt), Cinderlee (stone bath), Holdfast (horse trough), Fossick (wash trough) | Viltri Quay; the others kept, not credited |
| a game played round a barrel | Fenhide (cards), Tilpey (chess) | Fenhide; Tilpey's kept, not credited |
| a stone that turns out to have a face | Fossick (the Ditto in the ore), Tilpey (the Spiritomb memory stone) | Fossick; Tilpey's kept, not credited |

Rewrites keep each record's id, anchor, facing, member offsets, poses and props, so no position changed. Where a
species changed, the new one is smaller than the old by the jar's hitbox x baseScale (Smoliv 0.27 x 0.50 for Psyduck
0.64 x 0.80; Nymble 0.25 x 0.25 for Cacnea 0.45 x 0.52; Pidove 0.28 x 0.44 for Noctowl 0.72 x 1.71), so its body
occupies nothing the old one did not, and none is in the ATM client-model subset.

Then every town got at least three credited things (outposts two where they have two situations), by marking unique the
hand-written situations whose idea no other town has (e.g. Fenhide's card game on the eel barrel and the Kecleon at
the fifth target, Holdfast's Sirfetch'd sentry and Marowak at the cairn, Fossick's Ditto in the ore and Garganacl salt
lick, Pacifidlog's Frillish on the washing line and Starmie lamp) and by the rewrites above. The two Rift outposts have
one situation each in a cast of six, at the band's top; a second needs the owner to lift the outpost band.

**A check is missing** (for `test-author`, not written here): `situations_distinct` should catch a repeated idea, not
only a repeated title. The table above is the hand reading it would have to reproduce.

## Not verified

- The placement layer of `tools/ambient_composition_audit.py` and `tools/ambient_idle.py compose` need
  `derived/towns` and `derived/ambient`, absent in the worktree: the three species swaps are checked by size, not by
  the generator's body replay. Run `python tools/ambient_idle.py compose` and the audit in a full checkout before R16C.
- Nothing here has been seen in game.
