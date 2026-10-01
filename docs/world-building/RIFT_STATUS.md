# The Rift: completion inventory

A read-and-classify pass over the fifteen Rift subsystems, against the repository at
`36eb267`. Nothing here was checked in a running game or against a world save: this
document classifies **data, generators, re-apply steps and what `docs/STATE.md` records**.
Where STATE claims something was probed in game, the claim is quoted and marked
"claimed by STATE, not re-checked here".

## The four states, and one thing they cannot express

- **applied** — data exists, a generator emits it, a step in `tools/reapply.py` applies it,
  and `docs/STATE.md` records that step as having been run against the staging world.
- **generated** — data + generator exist and the generator runs clean, but no re-apply step,
  or no record of it being run.
- **designed** — data or a design doc exists; no generator, or a generator that does not run.
- **not started** — nothing beyond a mention.

**The Rift's *shape* has no re-apply step, by design.** The perimeter, the crags, the peaks
and the scarps are sculpted into the canonical heightmap by `tools/rift_heightmap.py`, so they
arrive with the world export and, in `data/rift_sculpt.json`'s words, "needs no re-applying".
Under the definitions above that makes them **generated**, not applied — but they are not
waiting on a step that somebody forgot to write. STATE line 10 pins the canonical heightmap
(`land_8k_16_rescaled_b145_pads_rift_water.png`, sha256 `d1bc68d3…`) and STATE line 49 records
the staging world `cobblers-dryrun12` as exported from it, so the shape reaches a world by the
export path instead. Both rows are marked `generated (export path)` and should be read that way.

## The table

| # | Subsystem | State | Step / evidence |
|---|---|---|---|
| 1 | The perimeter and crags | **generated** (export path) | no step; `tools/rift_heightmap.py`, `data/rift_sculpt.json` `rim`/`peaks`, `derived/rift_sculpt/plan.json` |
| 2 | The scarps | **generated** (export path) | no step; same tool, `data/rift_sculpt.json` `cut` |
| 3 | The guards and their trailheads | **designed** | the 5 trailhead markers are applied by **R1**; the four zone guards have no data and no generator |
| 4 | The zones and gates | **designed** | no data file, no generator, no step; `docs/mechanics/RIFT_ZONES.md` |
| 5 | The biome | **applied** | **R1B** (`cobblers_rift_biome`), plus `cobblers_rift_storm` self-driving |
| 6 | Victory Road's caves and its ten fights | **applied** (the caves) | **R9C**, **R9E**, **R9F**; the ten fights are marked stands only — **designed** |
| 7 | The Windward Deep's city | **applied** | **R9DC** (after **R9B**, which sinks the pit) |
| 8 | The Compact HQ | **applied** (the shell) | **R9DC**; the rooms are labelled and empty — **designed** |
| 9 | Hoopa's cradle | **designed** | sited and reserved; sealed rock, nothing written |
| 10 | The relic area and its cavern | **applied** (the surface) | **R9DC**; the cavern behind the seal is uncarved — **designed** |
| 11 | The gulch mine and its Megas | **applied** | **R9S** (`cobblers_gulch_mine`, world-local) |
| 12 | The mega town (the Cutters' Gulch) | **applied** | **R9S**, the cove town's 69 buildings |
| 13 | The dig camp | **generated** | **R9M** exists, but the 2026-09-29 reshape is not in the run STATE records |
| 14 | The rim post | **applied** | **R8**, **R9**, **R16**, **R16B**, **R16C** |
| 15 | The League | **applied** (the building and its lot) | **R8B** (the lot), **R9** (`league_building`), **R16**; its five fights are **designed** |

**Counts: applied 9, generated 3, designed 3, not started 0.**

---

### 1. The perimeter and crags — generated (export path)

`data/rift_sculpt.json` holds the whole rim model: `rim.mix` (crags 0.55, sheer 0.15, plates
0.30), `rim.parapet`, `rim.crags` and `rim.plates` with their height, width, length and spacing
ranges, and `peaks` (22 peaks, 110–190 over the plateau, capped at `ceiling.peak_max_y` 305).
`tools/rift_heightmap.py` sculpts it; `tools/rift_perimeter.py` densifies `the_rift` in
`data/regions.json` to one station per block of arc and reports the profile at each (it is a
measurement and report tool, not a pack job, and is absent from `prepare`'s job list).
`derived/rift_sculpt/plan.json`, `basin.npy` and `changed.npy` are present in this checkout, and
`tools/reapply.py` runs `rift_heightmap.py --plan` as `prepare`'s first hydrate job (line 295),
refusing unless it reproduces the named heightmap pixel for pixel. STATE line 230 records
"512,952 columns, 12,811,417 blocks of shape … 78 character stretches, 22 peaks 111-186 over the
plateau (tops y228-305)" and "No settlement footprint moves (drift 0.0 across 27 towns)" — that
is a measurement of the plan, claimed by STATE, not re-checked here. No `tools/reapply.py` step
touches it.

### 2. The scarps — generated (export path)

The scarp is `data/rift_sculpt.json` `cut`: a band 22–46 wide just inside the lip dropped to the
12th percentile of ground within 150 blocks inward, so the lip reads as a sheer riser rather than
a slope. `docs/mechanics/RIFT_FRACTURE.md` line 78 makes them the barrier —
"**The scarps are the barrier.**" — superseding the rim wall and spires of `RIFT_ZONES.md`
section 5. `data/rift_skin.json` records that this is why the old block-cutting prototype was
retired: with the scarp in the heightmap "that cut has nothing left to remove: its slope()
divides by a run of zero". Same tool, same absence of a step. The export paints the rim
`BLACKSTONE` and the scarp `BASALT` (`rift_sculpt.terrain_paint`) so the block pass only has to
convert the visible skin.

### 3. The guards and their trailheads — designed

Two different things share this row, and only one of them exists.

**The trailheads are applied by R1.** `data/rift_sculpt.json` `entrances` names five —
`rim_post_descent` (switchback, 5 legs), `victory_road_descent` (switchback, 4 legs, snapped to
the `victory_road` route), `excavation_haul_road` (landslide), `gulch_mouth` (canyon) and
`wilds_slip` (landslide) — each with a named guard. `entrance_policy` is explicit:
"Guards' trailheads are marked with an armour stand placeholder and not staffed; Codex writes
them (docs/HANDOVER_CODEX.md item 23)." The markers ride in on R1's `fx` pass (`tools/reapply.py`
line 846-848: the block functions, then `cobblers:rift/fx`, a `wait` of 8 and a `check` of
`rift_fx`). STATE line 230: "9 portal sheets and 5 guard trailheads … Audited clean: … paths 5/5,
entities 14/14" — claimed by STATE, not re-checked here. The comment at `tools/reapply.py` line
842 records why the step exists at all: "No step ran it until the 2026-09-24 rehearsal found 0 of
14 on a fresh export: they had been placed by hand on staging."

**The guards do not exist.** `docs/mechanics/RIFT_ZONES.md` section 6 designs them fully — a
one-wide obsidian walkway, a roof at y+2, a two-high barrier column behind a Cobblemon NPC, the
`isPushable`/`isInvulnerableTo`/`allowProjectileHits` reasoning read out of the 1.8.0 source, and
an experiment to run before building. There is no `data/rift_guards.json`, no generator, and no
step. STATE says flatly: "the gate guards are not built, and their characters are for Codex."
Note also that the five trailhead guards (Rim post guard, Victory Road warden, Dig company
foreman, Gulch lookout, Wilds ranger) are **not** the four zone guards G1–G4 of `RIFT_ZONES.md`
section 2; nothing reconciles the two lists.

### 4. The zones and gates — designed

`docs/mechanics/RIFT_ZONES.md` (261 lines) designs four zones with one guard each — Z1 the dig
camp (2 badges, G1 at 3022, 3254), Z2 Victory Road and the League (8 badges, G2 at 3738, 5082),
Z3 the south-east branch (60 species, G3 at 4390, 4894), Z4 the apex (120 species, G4 behind the
League) — plus three cross-walls (the throat at 3384, 3502→3406, 3182; the branch mouth at
4373, 4691→4196, 4927; behind the League at z2560) and the enforcement mechanism: a per-player
pass score `cob_pass_z1`..`cob_pass_z4` set by the guard's dialogue, read by a hidden
`in_zone_<z>` advancement whose reward function turns an unqualified player back.

**None of it is in the repository.** `grep -rn "cob_pass\|in_zone_z\|rift_zone" data/ tools/`
returns nothing. There is no zone data file, no rasterised boxes, no generator, no step. Section 8
lists a six-item build order that has not been started, and its own status line says the rim wall
and spires are superseded. STATE confirms the consequences are live faults: "`crater_operation_stopped`
and `rift_crisis_resolved` are absent from the progression ledger, and the defined Rift-to-League
handoff has no setter while the League opens too early on `gym8_cleared`."

**One exception, and it is the pattern to copy.** The gulch has a working zone of its own, built
inside `tools/gulch_mine.py`: `data/gulch_mine.json` `zone` (a traced polygon inside the sculpt's
lip ring, full height y-64..575, explicitly citing "RIFT_ZONES.md section 4") and `gate` (band,
plug, grille, road, `knock`, `exit`, `arrive`, `turn_back`, `ward`, `ward_margin`,
`messages_are_placeholders`), gated on `cobblers:flag/gym6_cleared`. That proves the enforcement
shape without dialogue.

### 5. The biome — applied (R1B)

`data/rift_skin.json` `biome` drives `cobblers_rift_biome`, applied by **R1B** ("the Rift biome,
painted over the skin", `tools/reapply.py` line 849-850), which runs the pack's indexed functions
after R1's block pass. `RIFT_ZONES.md` section 7 is the design; STATE line 230 records "479 biome
functions" and "biome 25 inside the lip and 0 outside", and "The biome shipped with its spawn-tag
change (40 entries to `cobblers:the_rift`, 2,120 compiled spawns, none left on gravelly hills)" —
claimed by STATE, not re-checked here.

The Rift's weather is a second, self-driving pack: `data/rift_storm.json`
(`period_ticks` 20, `per_check_percent`, `strike`, thunder permanent inside `cobblers:the_rift`)
built by `tools/rift_storm.py`, generated by `prepare` (line 402), listed in `WORLD_LOCAL`, and in
`EXCLUDED` with the reason "self-driving: its own minecraft load tag starts the storm loop". Its
own status field reads "built on staging 2026-09-25". A pack in `EXCLUDED` has no step by design,
so by the strict definition the storm alone is `generated`; the biome row is applied on R1B.

### 6. Victory Road's caves and its ten fights — applied (caves); the fights designed

**The caves are applied.** `data/vr_caves.json` (schema `cobblers.vr-caves/1`, seed 90210) models
one network: 40 caverns merged into halls, 66 galleries with loops, six colliding zones (the Dark,
the Drowned Gallery, the Slagworks, the Bloom, the Raw Tear, the Abandoned Cut), a floor climbing
from the Deep's mouth at y1 to a ravine onto the League's apron at y89. `tools/vr_caves.py build`
is `prepare` job `vr_caves:build` (line 350). Three steps apply it: **R9C** (the caves themselves,
after R9B and R8B), **R9E** (its Habitat Block tiles, ranges 28/16/10/6) and **R9F** (the
Abandoned Cut's Digger NPC). STATE line 240: "On staging: all 1,936,430 model cells match the
saved world" and "Re-applied by `reapply.py` R9C, R9E and R9F" — claimed by STATE, not re-checked
here. The schema 2 spine is retired: `data/victory_road.json` status begins "RETIRED 2026-09-23",
and `cobblers_victory_road`, `cobblers_vr_regions`, `cobblers_vr_clear` and `cobblers_vr_backfill`
all sit in `EXCLUDED` with retirement or staging-only reasons.

**The ten fights are not.** `data/vr_caves.json` `trainers` is a placement rule only — count 10,
`min_apart` 40, a `rechiseled:blackstone_polished_connecting` stand, and the closing words
"Marked and unstaffed." Nine authored teams exist in `data/trainers.json` under
`route_id: "victory_road"` (`route_09_trainer_01` … `_09`), each with a `team`; there is no tenth
and no position. `data/route_trainers.json` holds 13 placements, all Routes 1–3, and **R17** places
exactly `route_trainers.placements()`, so nothing puts a trainer in the cave. STATE agrees twice:
"Victory Road's trainers are marked but unwritten (HANDOVER items 22 and 25)" and "Full `--check`
fails on Victory Road's pins … whose ten fights stand where `tools/vr_caves.py` places them along
its walked route, not at those pins." STATE also records "**EXP-033 is unrun.**"

### 7. The Windward Deep's city — applied (R9DC)

The pit is **R9B** (`data/rift_deep.json`, schema 2: floor y0, five rings at y66/49/32/15/0, 8
lift pairs, 468 tread lights; `tools/rift_deep.py`, `prepare` job `rift_deep`). The city stands on
it: `data/deep_city.json` (schema `cobblers.deep_city/1`, seed 20260927, design
`docs/world-building/DEEP_CITY.md`) with `streets`, `buildings`, `districts`, `plaza`, `towers`,
`sink_gate`, `services`, `spire`, `lights` L1–L7, 15 `rooms` and 4 `reserved` volumes. Its
`ground` field states the rule: "Every position comes from the pit's ring model
(tools/rift_deep.py model())" — never a world, as CLAUDE.md requires. `prepare` runs
`deep_city:build` then `deep_city_audit` (lines 362-363) and refuses a failing audit. **R9DC** is
the step, deliberately not R9D: `tools/reapply.py` line 906 notes "R9D was the retired Victory Road
regions step, and tests/test_reapply_vr_steps.py keeps that id retired." STATE line 155 records
196 buildings, 9 stair towers (8 lift banks + the Sink Gate; corrected 2026-10-01 from a run's own counts), 193 ladders, the Core spire, 99 functions and about 85,000 commands,
and "On staging (`cobblers-dryrun11`, world-local, 2026-09-27): all 99 functions run, 300 of 300
sampled final blocks present" — claimed by STATE, not re-checked here. Not built, per the same
entry: the Slip barrier, holo-signs, NPCs.

**Disagreement (finding).** `data/deep_city.json` `status` says "Built into build/ only; not yet
run on staging, not seen in game", which contradicts STATE line 155's staging record. The commit
that wrote the data (`344eb36`, 2026-09-27) is an ancestor of the commit that declared
`cobblers-dryrun12` the staging world (`c40c37a`), and STATE line 49 records that run as
"completed 35 steps with 0 problems", so the status string looks stale rather than STATE being
wrong. Either way the two must be reconciled; it is not resolved here.

### 8. The Compact HQ — applied (the shell, R9DC); the rooms designed

The HQ is part of `data/deep_city.json`, not a build of its own: `hq` gives it the west sector's
riser lots on every ring (`bearing` 244–266, widened to 205–262 on the floor so "the hall the
confrontation may use is a hall"), a tower at (3427, 3308), 11 across, top y132, carrying "an open
ring crossed by a short bridge (docs/story/FACTION.md)" in sea lanterns, and an iron-bars cordon
round its lower door on the Core. STATE line 155 counts "the HQ 5 sections and a tower to y132".

What is inside is not built and is Codex's: STATE line 155, "Left empty and labelled for Codex:
the HQ's shaft head, director's office, briefing hall, archive, anchor control, lower hall and
tower". Two volumes under it are `reserved` in the data and sealed — `hq_basement`
(3419,-4,3296 → 3445,16,3320, "under ring 0's rock") and `hq_secure_shaft` — with the reason
"Sealed: nothing is written here."

### 9. Hoopa's cradle — designed

Sited, reserved, and empty. `data/rift_regions.json` `sited` holds exactly three entries —
`haven_compact_hq`, `hoopa_cradle`, `cradle_passage` — traced from the owner's annotated heightmap
(`land_8k_16_annotated_rift.png`, sha256 `407f58f4…`, outside the repo).
`data/deep_city.json` `reserved` turns the siting into volumes: `hoopa_cradle`
(3317,-12,3266 → 3397,72,3346, "the relic cavern: Hoopa's cradle, sited at (3357, 3306) floor y12
under the relic area … Sealed: nothing is written here") and `cradle_passage`
(3357,-4,3298 → 3433,24,3318, "the 70-block passage from the HQ basement to the cradle,
climbing 12"). `scope.not_built` names it first: "Hoopa's cradle, the cradle passage, the HQ's
basement and its secure shaft: reserved volumes below, sealed rock, carved by nobody until Codex's
story data exists." STATE: "Hoopa's cradle is reserved and sited only" and "Hoopa's cradle must
stand in the Victory Road zone" — which is Z2, and Z2 does not exist (row 4).

**Disagreement (finding), already recorded by STATE:** "`docs/story/FACTION.md` still puts the
cradle under the League plateau at (3297, 2603); the build follows `data/rift_regions.json` (under
the relic area) and builds nothing at either."

### 10. The relic area and its cavern — applied (the surface, R9DC); the cavern designed

`data/deep_city.json` `relic_area` carries the whole surface: the `shrine` (centre 3386, 3300,
radius 16, 3 steps), the broken `ring` (radius 8 on a 3-block plinth, a 50-degree gap "where a
fragment is missing"), six `arches` on a 13-block orbit, eight `stones` (2 fallen) on a 24-block
orbit, the `lookout` at (3417, 3300) over all five rings, and the Compact's dig with its cordon.
It is applied with the city by **R9DC**; STATE line 155 lists it and its audit against the ring
model, Victory Road's mouth and the sealed volumes as clean.

The cavern below is only a door. `relic_area.sealed_entrance` is at (3360, 3304), facing east,
four deep, "a sunken forecourt four down to a doorway sealed with reinforced deepslate behind iron
bars, on the cradle's side of the shrine. **Nothing is carved behind the seal.**" That volume is
row 9's `hoopa_cradle` reservation.

### 11. The gulch mine and its Megas — applied (R9S)

`data/gulch_mine.json` (schema `cobblers.gulch_mine/1`, seed 20260928, audit
`tools/gulch_mine_audit.py`, recipes `tools/mega_recipes.py`) holds `zone`, `gate`, `town`, `cove`,
`cutters`, `mine`, `faces`, `megas`, `drops` and `farm_tiers`. `prepare` runs `gulch_mine:build`
then `gulch_mine_audit` (lines 356-357). **R9S** applies it — "the southern Rift's mega site: the
gulch gate, the Cutters' square, the Tally Hall and the Cutting Floor, then the Cutters" — the
indexed block functions, then `cobblers:gulch_mine/cutters` and a `wait` of 8; the pack is
`WORLD_LOCAL`. The commit that wrote the current data (`04f507a`, 2026-09-28) **is** an ancestor of
`c40c37a`, the STATE commit declaring `cobblers-dryrun12` staging, whose run "completed 35 steps
with 0 problems" (STATE line 49).

STATE line 153, claimed by STATE and not re-checked here: "On staging (`cobblers-dryrun11`,
world-local, 2026-09-27): R9S run (50 block functions, then the Cutters step), 300 of 300 sampled
final blocks match; the three Cutters stand with their offers (4 raw + 1 diamond per stone,
unlimited, read back over RCON); the mega recipes pack loads." Line 154 adds the section 13
redesign "on staging 2026-09-28, not seen in game": the macro Mega spawn (after EXP-046 found a
plain restart did nothing), the rockslide wall to y186-194, the ward widened, the respawn clock,
the 2-raw-plus-diamond price, the faces as warded scenery. In game, only EXP-045's proof M-1
passed; STATE: "M-2 to M-7 (a Mega from a function, the enrage, a ball refused, the faces, the
Cutters' trades, the Megas' models) are unrun by a player."

Two things inside this row are **not** applied. The **Mega farms** are held for the owner —
STATE line 154: "**Held for the owner:** the Mega farms (both sites fall inside Victory Road's Z2,
8 badges, in RIFT_ZONES.md, while the design puts them after gym 6: a gym-6 zone of their own, or
8 badges?); the drop roll's functions are generated only once a farm den exists." And STATE records
an open fault: "**the gulch Megas' keeper (`tools/gulch_mine.py` `megas/spawn_*`) does not**
[respawn after a plain restart], so after a plain restart its Megas are not replaced until someone
reloads".

**Disagreement (finding).** `data/gulch_mine.json` `status` reads "Built offline only: not
installed, not in any world, not seen in game", against STATE lines 153-154's staging records.
As with the Deep's city, the ancestry says the status string is stale; it is not resolved here.

### 12. The mega town — applied (R9S)

The cove town is not a settlement in `data/placements.json`; it is built by `tools/gulch_mine.py`
and so travels with **R9S**. `data/gulch_mine.json` `town` gives the 61-block square at
(4308, 4848) paved at y88 with a deepslate-brick border, tuff bands every 10 and a meteorid plinth
with a dormant crystal behind glass. `cove` grows the town round it by accretion: `sections`
(`heart`, 4 lapidaries; `workers`, a canteen, 2 washhouses and 24 dwellings; miners; extractors),
`buildings` (each with an id, section, kind, rect, door, wall block and wall height), `paths`,
`walls` and `lamp_posts`. STATE line 154: "the cove town, 69 buildings grown by accretion with a
level cutting into its sunken east, every doorway walkable from the gate. Audits clean;
independent tests merged" — claimed by STATE, not re-checked here.

Its name is not ours: `town.name` says "the Cutters' Gulch (working name; names are the owner's
and Codex's, HANDOVER_CODEX.md item 26)".

### 13. The dig camp — generated

This is the one Rift subsystem whose current data has demonstrably not been applied.

The camp's **surface** is a settlement: `data/placements.json` has `rift_dig_camp` with a finds
shed, eight donor tents, two dig sites and its lights, applied by **R8** (prep + town), **R9**
(donors), **R16** (lights after the donors), **R16B** (dressing) and **R16C** (ambient). It was
approved in batch 2 (STATE: "Erika's town and batch 2, approved as drawn (… the Rift rim post, the
Rift dig camp)").

The camp's **mining works** are `data/rift_mines.json` (53 KB: `grid`, `keep_clear`, `flag`,
`palette`, `town`, `mine`, `geometry`, `pocket`, `retired_gated_section`), built by
`tools/rift_mines.py build` with `tools/rift_mines_audit.py` after it (`prepare` lines 353, 393),
applied by **R9M** — "the Rift dig camp's mines, quarries and the mega stone seam, then its
carts". `cobblers_rift_mines` is `WORLD_LOCAL`; `cobblers_rift_mines_refill` is in `EXCLUDED` as
"staging only: rock back into the Rift spur's retired gated section … a fresh export never had it".

**Why generated and not applied.** The camp was reshaped on 2026-09-29 (commit `2ee3299`, "The dig
camp reshaped: fitted to its pocket, one large quarry, strip mines above"), and the file's own
status says: "reshaped 2026-09-29 (SOUTHERN_RIFT_MEGA.md section 13 and DEEP_CITY.md section 6) …
one large stepped quarry traced from the pocket's own outline with a second older cut beside it,
strip mines on the shoulders above, and an unplanned town of rock houses along two streets …
**Built offline; not installed, not in any world**." `git merge-base --is-ancestor 2ee3299 c40c37a`
is false, and false for `75594e7` as well: the reshape is **not** in the history of either STATE
commit that records the `cobblers-dryrun12` run, so the 35-step run applied the *previous* shape.
What STATE records on staging (line 152) is the 2026-09-27 cut-back: "On staging the cut-back R9M
(49 functions) and the refill ran, and the refill pack was removed: 300 of 300 sampled final blocks
match for each. The ward and the daily face are not yet run by a player." A step exists and has
been exercised; the current data has not been through it.

**Two disagreements (findings).**
1. STATE line 154 says "**Not started:** the West Spur Dig reshape (about 300k tokens more)" and
   line 152 ends "The owner wants the camp reshaped … not built". Commit `2ee3299` did it. STATE
   is stale on this point.
2. `data/placements.json` still carries eight donor tents and the finds shed for `rift_dig_camp`,
   while the reshape's status describes "an unplanned town of rock houses along two streets". Which
   of the two the camp is supposed to be is not stated anywhere I found; `data/rift_mines.json`
   `which_town` and `disagreements` (6 entries) are the place to look before applying R9M again.

Also open, per STATE line 154: "**Question:** the spur's daily crystal after gym 6
(`data/rift_mines.json`) may hand out a free raw stone, against section 13's 'not free'; its loot
is unverified."

### 14. The rim post — applied (R8, R9, R16, R16B, R16C)

`data/placements.json` gives `rift_rim_stop` a Centre (`rift_rim_stop_pokecenter`), two cabins
(`rimpost_cabin_north`, `rimpost_cabin_south`) and the `rimpost_overlook_railing` earthwork, so it
is carried by the ordinary town pipeline: **R8** prep and town, **R9** donors, **R16** lights,
**R16B** dressing, **R16C** the ambient Growlithe ("the rim post's Growlithe", STATE). Its descent
into the Rift is `data/rift_sculpt.json` `entrances.rim_post_descent` — a five-leg switchback near
(3877, 3824), landings 5, guard "Rim post guard" — which is row 1's heightmap sculpt, and its
placeholder marker is row 3's R1.

STATE records the position and why it moved: "**Rift rim post:** moved 178 blocks to
`(3814, 3791)`, ground about y148, still on the rim (the owner, 2026-09-23), because the sculpt put
the rim across its old sightline". A defect found in the fourth rehearsal, "the rim overlook's
paving uncleared", is recorded as fixed. Claimed by STATE, not re-checked here. The rehearsal
record for all places is EXP-026 run 5 on `cobblers-dryrun11`: "26 of 26 places, 0 gaps".

One consequence worth naming: STATE notes the rim post moved *after* the sculpt, so
"today's towns no longer reproduce it" — `rift_heightmap.py --plan` uses the footprints `--apply`
recorded, not today's.

### 15. The League — applied (R8B, R9, R16); its five fights designed

Three layers, two of them applied.

**The lot** is `data/rift_league_tunnel.json` (`lot`, 13 keys; `tunnel`), built by
`tools/rift_league_tunnel.py` (`prepare` line 346) and applied by **R8B** — "the League's lot on
the apex oval, levelled before its donor". `tools/reapply.py` line 866-868 explains the ordering:
"After the towns and BEFORE the donors: the town pass would re-level ground under it, and
place_donor stamps the League building onto the lot this levels." The data is explicit that it
stops there: `not_here` reads "The League building itself is stamped by tools/place_donor.py from
data/placements.json".

**The building** is `league_building`, kind `league`, with a `pack_template`, so `donors()` picks
it up and **R9** places it; **R16** relights afterwards. STATE: "The League stands on the Rift's
apex oval (lot x3635-3754 z2375-2485 levelled to y88; moved there 2026-09-23 from the trunk head
…), Victory Road climbs to its apron, and its spawn-free precinct moved with it on 2026-09-23
(x3616-3776 z2352-2504); on `cobblers-dryrun4` it audited plan-clean and spawn-clean at the trunk
head, 159,470 of 159,471 template blocks." Its Centre and Mart are inside the template, and
`deep_city` builds a second, unused pair by the Sink Gate. All claimed by STATE, not re-checked
here.

**The fights are not placed.** `data/trainers.json` holds five authored records with
`status: "authored"` — `elite_01_lorelei`, `elite_02_bruno`, `elite_03_agatha`, `elite_04_lance`,
`champion_blue` — plus five records marked `post_victory_road`. Nothing places them: **R17** places
`route_trainers.placements()`, which is 13 Route 1–3 entries, and `cobblers_trainers` is in
`EXCLUDED` as self-driving ("the trainers themselves are placed by R17 over RCON"). STATE also
records the gating fault: "the defined Rift-to-League handoff has no setter while the League opens
too early on `gym8_cleared`", and `gym_08_giovanni` is still `status: "held"`.

---

## BUILDABLE NOW

Every item below is `designed` (a whole row, or a designed part of an applied row) and needs no
story, dialogue, quest or scene data from Codex. Ordered by what unblocks the most.

Two designed items are deliberately **excluded**, with the reason:

- **Hoopa's cradle and the cradle passage** — `data/deep_city.json` `scope.not_built` says the
  volumes are "carved by nobody until Codex's story data exists", and Hoopa appears in no
  `data/legendaries.json` encounter. Codex-gated by decision, not by tooling.
- **The four zone guards as NPCs** — `RIFT_ZONES.md` section 6 hands their greeting, pass, refusal,
  turn-back and farewell lines to Codex (HANDOVER item 23). The *walls, gatehouses and enforcement*
  around them are item 1 below and need no lines; the gulch's `gate.messages_are_placeholders`
  is the precedent.

### 1. The zone system: Z1–Z4 boxes, passes, the zone check, the three cross-walls and the gatehouse shells — **large**

Unblocks the most by a wide margin: Hoopa's cradle ("must stand in the Victory Road zone", i.e. Z2),
the held Mega-farm badge question (both farm sites fall inside Z2 at 8 badges while the design puts
them after gym 6), Registeel's region choice, the "League opens too early on `gym8_cleared`" fault,
and the guards themselves once Codex writes them.

- Files that would change: new `data/rift_zones.json` (the four zone polygons, thresholds,
  turn-back points, exit boxes; the three wall lines are already surveyed in `RIFT_ZONES.md`
  section 2), `data/progression.json` (the pass scores and the missing `rift_crisis_resolved` /
  `crater_operation_stopped` flags), `tools/reapply.py` (a new step, plus `prepare` jobs),
  `docs/mechanics/RIFT_ZONES.md` (status), `tests/`.
- Generator to write: `tools/rift_zones.py` — rasterise each polygon with the existing
  `tools/subregion_boxes.py`, emit the `in_zone_<z>` advancements and their reward functions, the
  walls and one-wide obsidian gatehouses, and a fail-closed audit ("every zone has boxes, a
  turn-back point and an exit box", section 8 item 4). `tools/gulch_mine.py`'s `zone`/`gate` is a
  working model of the whole shape, placeholder messages included.
- Note: `RIFT_ZONES.md` section 6 asks for one disposable-world experiment first (barrier behind
  the NPC, sprint-jump, piston, ender pearl, ridden flying Pokemon, exact teleport landing), and
  section 4 flags one unproven mechanic — whether Cobblemon's riding accepts `/ride`.

### 2. Victory Road's ten fights — **medium**

Nine authored teams and ten marked stands already exist; only the wiring is missing. Unblocks
EXP-033 (unrun) and the whole finale, and is the largest single piece of authored content in the
repo that reaches no player.

- Files: `data/trainers.json` (a tenth `route_09` record, or drop `min_apart` to nine),
  new `data/vr_trainers.json` (positions, read from `vr_caves.py`'s own model — never a world),
  `tools/reapply.py` (extend **R17** or add a step).
- Generator: extend `tools/route_trainers.py` to a second source of placements, or a
  `tools/vr_trainers.py` beside it emitting the same rctmod records; `tools/vr_caves.py records`
  already writes Habitat records from the model, so the "ask the model where the stands are" path
  exists.
- Caveat: STATE notes "rctmod forgets wins on a restart", and the level cap in Victory Road moved
  from 65 to 60; the nine teams should be re-read against that before placement.

### 3. The Elite Four and the Champion at the League — **medium**

Five authored teams (`elite_01`..`elite_04`, `champion_blue`) with nowhere to stand. Unblocks the
end of the campaign and, with item 2, makes Victory Road a gauntlet rather than a corridor.

- Files: new `data/league_trainers.json` (seats inside the League template), `tools/reapply.py`
  (extend **R17**), possibly `data/placements.json` if the seats need cleared cells.
- Generator: the same extension as item 2. The seats must be measured out of the League's
  Cobbleverse template (`place_donor` stamps it whole), not read from a world;
  `tools/gym_buildings.py` already seats a leader's spawner at the end of a hall and is the
  nearest precedent.
- Blocked part, kept out of scope: `gym_08_giovanni` is `status: "held"` and the badge-to-League
  handoff has no setter (item 1).

### 4. Apply the reshaped dig camp — **small** (integration, not a build)

The data and the generator are done (`2ee3299`); nothing is written. Cheapest item on the list and
it closes a live inconsistency between `data/rift_mines.json`, STATE and `data/placements.json`.

- Files: `data/placements.json` (reconcile the eight donor tents and the finds shed against "an
  unplanned town of rock houses along two streets"; see `rift_mines.json` `which_town` and its six
  `disagreements`), `docs/STATE.md` (line 152's "not built" and line 154's "Not started: the West
  Spur Dig reshape" are both stale), possibly `tools/rift_mines_audit.py` for the new shape.
- No new generator: `tools/rift_mines.py build` and **R9M** exist. This is a `prepare` + audit +
  staging install, which CLAUDE.md reserves for the main session, not an agent.

### 5. The HQ basement, the secure shaft and the cradle passage as rock — **medium**, and partly Codex-gated

The four `reserved` boxes in `data/deep_city.json` are sealed and empty. The *shells* — a basement
under ring 0's rock, a shaft, a 70-block passage climbing 12 — are geometry, and
`tools/deep_city.py` already builds against the pit's ring model with an offline audit. The rooms
inside them are Codex's, and `scope.not_built` currently forbids carving anything until that data
exists, so this needs the owner to split "the rock" from "the rooms" before it can start.

- Files: `data/deep_city.json` (`reserved` → a built section, `scope`), `tests/`.
- Generator: extend `tools/deep_city.py` and `tools/deep_city_audit.py`; no new step (**R9DC**
  covers it).
- Do first: settle the `docs/story/FACTION.md` (3297, 2603) versus `data/rift_regions.json`
  (under the relic area) conflict for the cradle, which STATE already records as open.

### Also designed, but owner-blocked rather than buildable

- **The Mega farms and their drop roll** — held on one owner question (a gym-6 zone of their own,
  or 8 badges?), and "the drop roll's functions are generated only once a farm den exists".
  Item 1 supplies the zone machinery that makes either answer cheap.
- **Registeel's chamber** — `data/legendaries.json` `registeel.status` is `blocked`, `blocked_by`
  "owner_decision: which part of the Rift"; the record also warns the final clearance proof
  "CANNOT be done in an isolated worktree".
