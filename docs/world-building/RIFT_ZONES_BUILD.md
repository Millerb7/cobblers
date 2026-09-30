# The Rift's zones: the build note

**The design is `docs/mechanics/RIFT_ZONES.md` and is not restated here.** This note records how that design
was implemented, every place the implementation and the design disagree, and what is still owed. The data is
`data/rift_zones.json`, the generator `tools/rift_zones.py`, the step `R9Z` in `tools/reapply.py`.

**Status: nothing is built.** No function has been run, no wall stands in any world, no player has seen a
guard. `python tools/rift_zones.py build` writes a datapack offline; that is all that has happened.

## The rung

Rung 5 and 6 of `CLAUDE.md` principle 6: a datapack with functions, and nothing above it. Cobblemon 1.8.0
has no player-zone concept; no installed addon gates an area; Cobbleverse ships none; no config key expresses
"a player without X may not stand here". A vanilla `minecraft:location` advancement does, and its reward
function acts. The rung is not argued from documentation: `tools/gulch_mine.py` already runs this exact shape
for the gulch, so it is proven inside this repository.

## The zone check, and the one change to the design

`RIFT_ZONES.md` section 4 puts two conditions in the `in_zone_<z>` advancement: the location boxes **and**
`minecraft:entity_scores` with `cob_pass_<z>` below 1.

**That fails open.** `minecraft:entity_scores` does not match when the objective holds no value for that
player, and no player holds one until a guard sets it. Every player who has never met a guard would therefore
fail the advancement's condition, never trigger it, and walk in.

So the advancement tests **location only**, and the reward function tests the pass:

```
execute if entity @s[gamemode=!creative,gamemode=!spectator] unless score @s cob_pass_z1 matches 1.. run function cobblers:rift_zones/z1/turn_back
```

`unless score ... matches 1..` is true for an unset score, so an unknown player is turned back. Fail-closed by
construction. This is the only mechanism change; everything else in section 4 is implemented as written.

## Where the shapes come from, and what was not traced

The four zones are unions of the owner's own traced regions in `data/rift_regions.json`, flood-filled from
that file's seeds out of `land_8k_16_annotated_rift.png`. `trace` refuses to go on unless every fill
reproduces the recorded bbox **exactly**; two of the eleven seeds (`gate`, `relic_area_shrine`) sit on the
annotation's own black lettering, so the fill is retried from each nearby free pixel and only a fill matching
the recorded bbox is accepted.

**The eleven regions do not tile the Rift.** Measured 2026-09-30: the four zones' seed regions hold 616,887
columns and the gulch 61,330, against a Rift interior of 1,964,884. The owner drew named *places* with
unclaimed ground between them; where two meet, the outlines do not touch (the excavation site and the relic
area shared a frontier **3 columns** wide). Zones built as plain unions would leave most of the Rift unzoned,
and an unzoned column is a way round every gate. So each zone claims the interior ground nearest its own
regions (`claim_interior`, a multi-source breadth-first growth). Boundaries stay where the owner's outlines
put them; nothing is left unclaimed, and `trace` fails if anything is.

**Not traced from the sculpted lip.** `data/gulch_mine.json` traces its zone from `derived/rift_sculpt/plan.json`.
That is a derived input and is refused to an isolated agent (`CLAUDE.md`, "Launching a writing agent" step 3),
so it was not used and must not be assumed. One consequence is recorded under "Open for the owner" below.

**Ground is never read from a world.** Every y comes from `tools/ground.py`. The canonical heightmap is the
terrain *before* `data/rift_sculpt.json` raises the rim into crags, so a "rim to rim" ground threshold runs
away on it: a `floor + 32` rule measured the throat at **710 blocks** against the 322 the design surveyed. The
wall line is therefore the traced frontier, not a ground threshold; the heightmap is used only for each
column's own height.

## The walls

A wall is the frontier the two zones share, filtered to the columns standing on walkable floor (within 15 of
the floor at the cut's surveyed point). The rest of each frontier runs up the Rift's own walls and carries no
wall, because `docs/mechanics/RIFT_FRACTURE.md` supersedes the rim wall: **the scarps are the barrier**.

| Wall | Closes | Columns on floor | On scarp (no wall) | Across |
|---|---|---|---|---|
| throat | Z1 | 445 | 979 | 197 |
| league_gate | Z5 | 491 | 246 | 369 |
| behind_league | Z4 | 523 | 169 | 346 |

About 51,000 blocks, against the roughly 789,000 of `RIFT_ZONES.md` section 5, whose rim wall and 257 spires
are not built. Blocks are section 5's own palette; no `nether_portal` block anywhere.

## What the data settles

- **Hoopa's cradle: (3357, 3306)**, `data/rift_regions.json`. `docs/story/FACTION.md`'s (3297, 2603) is
  outside the Rift's extent, 626 blocks north of the relic area it claims to be under, and stands at ground
  y118, rim height. Three records agree against it. **FACTION.md is not edited here** — it is story.
  The cradle is in Z2, as section 2a requires, *only because* the throat cut moved (below).
- **"The League opens too early on `gym8_cleared`": settled by Z5**, the League's precinct, gated on
  `rift_crisis_resolved`. Z2 cannot carry the fix — section 2a puts the finale *inside* Z2, so gating Z2 on it
  would be circular. The geography was already traced: the `gate` region exists for
  `owner_intent[2]`, "the entrance to the Elite Four is sealed off unless you go through the town first".
- **Registeel: the zone system does not choose the region, and says so.** All three candidate columns in
  `data/legendaries.json` lie in Z2, so it is region-neutral. What it does settle is that Registeel's
  **effective gate is 8 badges, not the proposed 7**, wherever in the Rift it goes. `data/legendaries.json` is
  not edited here: a legendary's gate is encounter balance.

## Open for the owner

1. **Z2 has three ways in and one guard.** `data/rift_sculpt.json` cuts `victory_road_descent`,
   `rim_post_descent` and `wilds_slip`. Only G2 grants the pass, so a player with eight badges who walks in at
   the rim post is turned back with no guard there to earn it from. Either the other two trailheads get a
   guard who can grant, or their turn-back line must say where G2 stands.
2. **Gatehouse siting against the sculpted lip.** G1's and G2's gatehouses are placed at the sites
   `data/rift_sculpt.json` names, but the sculpted gap's exact columns live in the derived plan. Re-check both
   from the main session before building.
3. **`data/spawns.json` `rift_west_spur` spawns at levels 56-58** while Z1 opens at two badges
   (`data/rift_mines.json` `disagreements`, `DEEP_CITY.md` section 6). Not changed here; the zone data makes
   the mismatch sharper, because Z1's two-badge pass is now authored rather than proposed.

## Still owed (`report` exits 1 until they exist)

- `rift_crisis_resolved` in `data/progression.json`, and `league.unlocked_by` becoming
  `[gym8_cleared, rift_crisis_resolved]`.
- Its **setter**, which is the finale's quest stage: story data this tool must not invent. Until it exists Z5
  is shut to everyone, which is closed, not open.
- The guards' dialogue (Codex, `docs/HANDOVER_CODEX.md` item 23). The pack emits
  `cobblers:rift_zones/<z>/grant` and `/qualify` so dialogue calls a named function and never has to know the
  objective's name.

## What a test author should assert

Implementation does not write its own tests (`CLAUDE.md` principle 16). What matters:

1. **Fail-closed enforcement.** No emitted `*_zone` advancement may carry a `minecraft:entity_scores`
   condition; every `<z>/zone.mcfunction` must contain `unless score @s cob_pass_<z> matches 1..`.
2. **The zones tile the interior and do not overlap.** Every column of `data/landmarks.json` `rift.extent`
   less the gulch polygon is in exactly one zone's boxes; no two zones' boxes intersect.
3. **The places.** Each zone's arrival and exit box are inside its own boxes and its turn-back point outside,
   tested with **half-open** upper bounds (`b[0] <= x < b[2] + 1`) — a teleport target is a block centre, and
   an inclusive integer test wrongly calls the box's last block outside. This was a real bug in `report`.
4. **Z3 emits nothing**: no advancement, function or wall names `z3`, and no live zone's box centre falls
   inside `data/gulch_mine.json`'s zone polygon.
5. **Section 2a.** No caught-count zone contains Hoopa's cradle or any story-required site; the cradle is in
   Z2.
6. **The ground rule.** `tools/rift_zones.py` reads no world; `tests/test_ground_rule.py` should cover it.
7. **Every wall column stands on walkable floor** (ground within `floor_band` of the cut's floor), and no
   emitted `fill` targets a column the data marks as scarp.
8. **`report` is fail-closed**: it exits non-zero when a box is off the grid, a place is missing, a zone
   overlaps another, the cradle leaves Z2, or an owed dependency is absent. Assert the non-zero exit, not just
   the message.
