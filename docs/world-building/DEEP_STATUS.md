# The Deep: what is there, what was missing, what was finished (2026-10-03)

The owner, overnight 2026-10-03: *"Heaven's Arena is at (3609, 130, 3249) and Hoopa's hall was built, so start by
telling me what is actually there and what is missing - I have flown it and seen neither."*

Sources: `data/deep_city.json`, `tools/deep_city.py` (re-run here), `derived/deep_city/plan.json`,
`data/relic_underground.json`, `tools/relic_underground.py`, `data/arena_trainers.json`, and the main session's
saved-world reads of the **staging** world that night (relayed; marked *relayed* below). No world was read for this
document.

## 1. Why you saw neither

**The hall is underground by design.** Its floor is y5, its dome tops out at y34, and the heightmap's ground over its
centre (3390, 3262) is **y93** (`tools/ground.py`, rounded): 59 blocks of rock. The surface above it is the capped
relic area: the sealed entrance, the lookout and the dig. There is no shrine on the surface since 2026-10-02 (the
owner: "THE RELIC SITE UNDERGROUND, reachable only through the Compact HQ"). The only way in is the Compact guard at
the HQ door, for a player at the finale's stage.

**The arena is in the staging world exactly as planned.** The staging reading looked thin, but the sampling caused it:

- *Relayed:* a 60x60 box round (3609, 3249), sampled every 4 blocks at y90-140, read 2,836 air, 49 cyan stained glass,
  20 polished deepslate, 10 tinted glass and 10 waxed oxidized copper.
- *Measured here:* the city build, sampled on the grid x, z = 3580 + 4k and y = 90 + 4k, gives **exactly** those five
  numbers.
- That grid never lands on a floor. The tiers in that range are at y100 and y117 and the crown at y128, while the
  samples are at 90, 94, ... 138. A complete drum therefore reads "mostly air". On the grid one block over (3579 + 4k)
  the same complete build reads 100% air.
- The centre column (*relayed*: froglight y0, sea lantern y1-127, gold y128, beacon y129, cyan glass y130) is the
  plan's light core and beacon, block for block.

If you flew to (3609, 130, 3249) and did not see a 33-wide glass drum rising 45 blocks over the lip with a beacon on
top, check which world was loaded. `server.properties` `level-name` is the live world's name. The Deep has only ever
been applied to staging (`docs/STATE.md`: "the live world cobblers-10240 has never been opened by this work"), so a
boot without the `--universe/--world` flags shows none of it.

## 2. Feature by feature

| Feature | Plan | In staging (relayed reads, STATE) | Status after tonight |
|---|---|---|---|
| Arena drum and 7 tiers | centre (3609, 3249), r16, tiers y15/32/49/66/83/100/117, 11-wide annulus | Matches. The 60x60 sample reproduces the build exactly; 7 of 7 tier probes pass | Built. **Walking up was broken: fixed in the generator** (below) |
| Arena crown and beacon | deck y128, gold 3x3 y128, beacon y129, cyan glass y130 | Centre column matches. The crown probe failed (see the defect) | Built. The crown was **unreachable on foot** until tonight's fix |
| Champions | `data/arena_trainers.json`: 7 seated champions, aces Lv56 to Lv76, 3 to 6 members, repeatable, no gate (owner decision 2026-10-01) | Seated by R17 2026-10-02 (`trainer_world_audit` 63/63); presence audit finds 1 trainer at each of 7 stands | Done. Nothing owed except the open questions in HEAVENS_ARENA.md section 9 |
| City (196 buildings, 9 stair towers, lights, Centre and Mart) | `tools/deep_city.py` | In staging (R9DC, 2026-10-02 18:15) | **The stair towers could not be climbed** (below). Fixed in 7 of 8 towers and the Sink Gate |
| HQ approach | ring-0 street -> door (3443, 67, 3282) -> guard (3444, 67, 3283) -> storey-0 room -> stair -> records room y0 -> passage -> gallery -> hall | Door area: polished blackstone at y66, air at y67 (*relayed*). A block read cannot see the guard: it is an entity (R18RU, applied 18:15) | Added a sign at the door and lights in the passage and gallery |
| HQ door gate | the guard admits at `rift_crisis_pending` or later; the iron door never opens | No plate (c7594696; the audit refuses any opener) | Verified (section 3). The zone now also needs the guard |
| Hoopa's hall | centre (3390, 3262), r21, floor y5, dome y26-34, relic ring, 6 arches, 8 stones | Carved: at (3380, 3262) polished_tuff at y7 with air from y8 to y32 (*relayed*). At r=10 that is exactly the platform's top step and the dome's height | Built |
| The binder (the finale beat) | `geometry.release`: NPC at (3390, 8, 3268) that grants `rift_crisis_resolved` (commit 01c3416f, 03:29 on 2026-10-03) | **Not in staging.** It was committed after the 18:15 apply | Needs dialogue install and R18RU |
| The relic cavern (Hoopa's cradle) | reserved box [3317,-12,3266,3397,72,3346]; "carved by nobody" | Not carved. The passage dead-ends in rock at x3358 | **Generated and walked offline. Held behind `geometry.cradle.carve`** until its independent audit is extended |
| Capped surface | sealed entrance (3360, 3304), lookout (3417, 3300), dig | R9RU removed the old surface | As planned |

*Relayed, and it disagrees:* the staging note called the surface over the hall "~y60". The heightmap gives y93 at
(3380, 3262). The relayed number is probably where that scan stopped, not the ground. Re-measure it before relying
on it.

## 3. The HQ door: is its stage the finale's?

Yes. `rift_crisis_pending` is the stage at which the finale is live. Dialogue line `rift_007` sets it after
`giovanni_reveal_complete`. The finale's own beat, the binder in the hall, offers "Release Hoopa." only at
`rift_crisis_pending`, and that runs the setter of `rift_crisis_resolved`. If the door were gated on
`rift_crisis_resolved`, the game would deadlock: that flag is earned behind the door.

Verified offline tonight:
- `relic_underground_audit` reports `guard clean`. The guard's option is shown, and its transition passes, at exactly
  the stages from `rift_crisis_pending` on.
- `hq clean`: nothing opens the door.
- `route clean`: the doorstep walk reaches the storey-0 room only through the guard.

Not verified: that the guard NPC stands in staging (no block read can show it), and anything in game.

## 4. What was missing and is now finished (branch `worktree-agent-a2d56e067168bf7a0`)

1. **The city's stairs could not be climbed** (d027200, 9862a78, e761b06). A player stepping up off a stair needs three
   blocks of air over the step he leaves. Every tower kept its roof over step R-3, and the arena's crown deck closed
   over step crown-3. Under the relic audit's own walk rules over the city pack and the pit, a walk from the HQ
   doorstep reached ring 0 and nothing else: no other ring, not the lip at the Sink Gate, not the crown. Now
   `climb_cells()` opens the roof over that step too, and air is written there, so an R9DC re-run clears the old
   block. The same walk now reaches every ring (y1-y67), the lip, all seven tier floors and the crown. Tower siting is
   unchanged, because `stair_plan`'s `opened` is untouched.
   - One tower stays roofed: ring 2 / Relay Row, door (3544, 3241). Its upper lift (3540, 32, 3243) *is* that roof
     cell. Its twin at (3664, 3226) is walkable, so every pair of rings still has a stair that can be climbed. The
     plan records `headroom_blocked_by_lift`.
   - Ladders and hatches inside family buildings were always a second way. The walk model cannot see them.
2. **The HQ door is findable** (1af83a6). A wall sign at (3444, 68, 3281), one block north of the door, reads "THE
   COMPACT / Headquarters / Entry through / the guard only" (`data/deep_city.json` rooms `hq_secure_shaft_head.sign`).
3. **The way down is lit** (1af83a6). 15 sea lanterns are set flush in the floors of the passage and the gallery,
   every 6 blocks on alternating sides (`composition.way_lights`). Both were dark.
4. **The zone pass needs the guard** (1af83a6). `hq_admit` sets `cob_admit_relic`, and the knock box's `qualify` tests
   it, failing closed. Before this, a player with eight badges who dug into the records room got the pass. A call
   taken overnight and recorded in `needs.owner_decisions`. To reverse it, delete `zone.pass.admit`.
5. **Hoopa's cradle** (94435c4). `geometry.cradle` is the sited chamber: centre (3357, 3306), floor y12, radius 16,
   dome y24-28. That is the reserved box exactly. It follows Codex's unmerged contract: a tuff dais with the seep at
   the centre (a clear actor marker), four copper pylons and a grate restraint ring with chains, five Compact
   consoles, eight tuff pillars, floor lights and four clear stands. The passage arrives as a sunken cut. Zone box 4
   and the `relic_cradle` spawn-free zone are added.
   - Run with `carve: true`: report 0 problems; 58 blocks of rock over it and 18 to the hall; a walk from the records
     room reached the marker, all four stands and 780 of 797 floor columns.
   - The independent audit then correctly fails. Its own `expected_air` knows the hall, gallery, passage and HQ only.
   - **Shipped `carve: false`.** Flip it after the audit is extended.

## 5. What the apply runs

`reapply.py prepare` (rebuilds `cobblers_deep_city`, `cobblers_relic_underground`, `cobblers_dialogue` and the spawn
tables for the new spawn-free zone), then `install`, then `run --only R9DC,R9RU,R18RU` and a restart.
- **R9DC** writes the opened roof cells, the crown cells and the sign.
- **R9RU** writes the lights, the admit score functions and, once flipped, the cradle.
- **R18RU** places the binder, which is not yet in staging.
- Then run `presence_audit` with its crown probe fixed, and the in-game checks in section 7.

## 6. Defects found elsewhere (recorded, not chased)

- `tools/presence_audit.py` line 114 probes the crown at `crown - 1` = y127, one block *under* the crown deck at y128.
  All four probe points are air in a complete build, so the probe fails on a complete crown. It uses `all()`, which
  stops at the first air, so STATE's "one of four ring points is air" is more than the probe can say.
- `tests/test_deep_city.py::test_the_city_runs_after_...` errors in a worktree without a built `cobblers_rift_zones`
  ("index names stub"). The cause is the environment.
- `data/deep_city.json` `status` still says "not yet run on staging". STATE says R9DC has run there.
- `deep_city_audit` checks each street level on its own and never the stair between levels. That is how the
  unclimbable towers stayed invisible.

## 7. Independent-audit checklist (for an agent that did not write this)

1. Extend `tools/relic_underground_audit.py` `expected_air`, and the `spawns` derivation, with the cradle, using
   `geometry.cradle`'s declared numbers (formula `rim + round((apex - rim)(1 - (r/R)^2))`). Do not import the
   generator. Then flip `carve` to true and rebuild. `test_the_built_pack_is_clean` must pass. Then mutate the
   generator (for example the radius inside `Geo.in_cradle`) and confirm the audit bites.
2. Add a stair walk to `deep_city_audit`, or a new test, that is independent of `climb_cells`: from a ring-0 street
   cell, every street level, the lip and the arena's crown must be reachable through the built pack over
   `rift_deep.model()`. Mutate `climb_cells` to return `opened` and confirm the walk fails.
3. Confirm the R9DC re-run clears the old roofs. Every `roof_open_over` cell in the plan, and every crown cell over
   step 125, must be written as air in the pack text.
4. Confirm that `qualify` in the built pack refuses a player with no `cob_admit_relic` score (`if score ... matches 1..`
   fails closed), that `hq_admit` still moves `@s` only, by one tp, after its reach test, and that nothing else sets
   `cob_admit_relic`.
5. Confirm the HQ sign's cell (3444, 68, 3281) is clear of the guard (3444, 67-68, 3283), the doorstep (3444, 67-68,
   3282) and the door's end rod.
6. Fix the presence-audit crown probe (y128), then re-read staging after the apply.
7. In game, at coordinates:
   - climb the Sink Gate (3694, 67, 3386) to the lip;
   - climb any tower (3664, 3226) between rings;
   - climb the arena's stair to the crown (3609, 129, 3249);
   - read the sign at the HQ door;
   - talk to the guard at `rift_crisis_pending`, walk the lit passage, and find the binder at (3390, 8, 3268);
   - once flipped, visit the cradle (3357, 13, 3306).

## 8. Owner calls

- **Recorded tonight:** the zone pass needs the guard (reversible by one key).
- **Recorded tonight:** the cradle is dressed from Codex's contract minus the six arches, which already stand in the
  hall.
- **Open:** should the release beat (the binder) move from the hall to the cradle's centre once the cradle is carved?
  Codex's Scene 5 stands it there.
- **Open:** the arena's per-tier signs and its tier-5 terrace (HEAVENS_ARENA.md section 9).
