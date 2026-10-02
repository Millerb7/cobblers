# The relic site underground: the hall off the HQ's cradle passage, and the zone that keeps it

**Status: WIRED 2026-10-02, not yet applied to any world, nothing seen in game.** `data/relic_underground.json`
is the data, `tools/relic_underground.py` the generator (`report`, `build`; `verify` is a stub), and
`tools/relic_underground_audit.py` the independent offline audit. `prepare` builds the pack
`cobblers_relic_underground` (world-local) and audits it; **`tools/reapply.py` step R9RU**, after R9DC and before
R9E, holds the box, takes the old surface build off (section 8a) and carves the hall. It answers the owner,
2026-10-01: *"THE RELIC SITE UNDERGROUND, reachable only through the Compact HQ, turned back by the zone check
rather than barriers."*

It **supersedes `docs/world-building/DEEP_CITY.md` section 5's surface half** and keeps its underground
half unchanged. Section 3's removal is **applied** (2026-10-02): `tools/deep_city.py` no longer builds the
surface shrine, `data/deep_city.json` carries `relic_area.capped`, and the old generator is kept verbatim in
`tools/relic_surface_superseded.py`.

**The way in is built (section 8b, 2026-10-02):** the HQ's ring-0 front door at (3443, 67, 3282), which stays
shut: a Compact guard beside it moves a player whose main quest stage is `rift_crisis_pending` or later inside
(section 8c), then a lit stair from the storey-0 room's south-west corner down the reserved secure shaft
to a records room at y0, whose open west doorway is the passage's east end. Until then (section 8, item 3) the hall
was carved, complete and sealed. **Nothing spawns in the hall, the gallery, the passage or the way down**
(section 8d, the owner, 2026-10-02).

Sources: `DEEP_CITY.md` sections 2, 3 and 5 (the HQ's siting, the passage's arithmetic, the composition's
numbers); `docs/mechanics/RIFT_ZONES.md` section 4 (the zone check); `data/rift_zones.json` and
`data/gulch_mine.json` (the two working instances of that check); `tools/cavern_plan.py` (the shell);
`data/rift_regions.json` (`relic_area_shrine`); `tools/rift_deep.py` (the pit's rings); `tools/ground.py`
(every measurement). Every y below is from the canonical heightmap or from arithmetic on those files.
**No world was read to decide anything.**

## 1. What changes, in one paragraph

Section 5 put the shrine on the Deep's west lip — a stepped platform, six ring arches, a plinth with a
broken gold ring 20 blocks tall that "shows against the sky from the dig camp 250 blocks west", a terrace
over the five rings — and then ringed the whole thing in a Compact fence of tinted glass under iron bars
so it was "seen, not entered". The owner has rejected the fence and asked for the site itself to be
underground. So the shrine moves, whole and at its own numbers, into a hall on the HQ-to-cradle passage;
the fence is deleted and nothing physical replaces it; and the enforcement becomes one `minecraft:location`
advancement whose reward function turns a passless player back to the Compact's own front step.

**The way in does not change at all.** Section 5 already had it right: HQ ring-0 front at x3427 → a shaft
down to the basement at y0 → the 70-block passage west, climbing 12 → the cradle. The hall hangs off that
passage. The only thing the design *drops* from it is the shaft's `lumymon:elevator` with
`requiredAdvancement`: that field is **assumed, not sourced** anywhere in this repository, and the gate is
not the shaft.

## 2. Where the chamber goes, and what is above it

| Part | Where | Floor | Ceiling | Measured rock above |
| --- | --- | --- | --- | --- |
| **The relic hall** | centre (3390, 3262), radius 21; bbox x3369-3411, z3241-3283 | y5 | dome, rim y26, apex y34 | **58 blocks at its thinnest**, over all 1,625 carved columns |
| The gallery | x3389-3391, z3284-3304, 21 long (was z3303: see section 8) | y5 | y11 | 75 |
| The passage (section 5's own) | z3305-3307, x3358 (the cradle's doorstep) to x3421 (the HQ doorway) | y1 at the door to y12 at the cradle | floor + 5 | 68 |
| The choked shaft | a 5x5 ring in the dome's apex, (3390, 3262), y35-y40, **solid** | — | — | 53 (a different number: the choke is not void) |
| Hoopa's cradle | (3357, 3306), y12 — **Codex's, unbuilt, untouched here** | | | |

**The depth is forced by the arithmetic, and the branch is the finding.** The HQ-to-cradle axis is 70
blocks long (x3357 to x3427). A hall 43 across, with rock either side of it, does not fit between the
cradle and the HQ's shaft — there is no arrangement of the two rooms plus two passages plus two walls that
closes. So the hall leaves the axis: the gallery turns north out of the passage at (3390, 3306), where
section 5's own ramp is at y6, and runs 20 blocks to the hall's south rim. North of the passage there is as
much room as the hall needs.

**What is above it:** the relic area's own surface, the exact ground the superseded platform stood on. Open
lip between the Slip's ridge (x3290-3310, `DEEP_CITY.md` section 6) and the Deep's west rim, ground y89-97
over the hall and y93 over its centre. The Deep's pit does not reach it: read from `tools/rift_deep.py`'s
model, at z3308 the pit's first column is **x3427** and ring 0's tread is y66 there, while the hall's east
wall is x3411. All **1,849** bbox columns of the hall lie inside the owner's traced `relic_area_shrine`
region, so the site has not moved out of the place the owner drew for it — it has moved 85 blocks down.

**The shell** is `tools/cavern_plan.py`'s: every natural void (air, fluid, falling block, cave decoration)
within 24 blocks of the carve made rock, over the roof and in a 24-block ring round the walls, never above
the ground; two passes, `02_shell` before the carve and `25_reshell` after it, because one pass cannot see
what the excavation opens. The generator emits 12,386 fill commands over 573,439 tested cells. This is the
Displaced City precedent section 5 named, run here.

**The choked shaft** is the one piece of new invention and it is deliberately not a route: a ring of native
masonry in the dome's apex with rubble above it, so a player standing under the apex reads *there was a way
down from here and it fell in* without there being one. No column of it is ever air. Gravel is named in the
data and **not used**: a gravel column falls. It stops at y40, which is also the zone's ceiling.

## 3. What comes off the surface (APPLIED 2026-10-02; the line numbers below are the 2026-10-01 ones)

Done as proposed: `build_relic` builds only the sealed entrance, the lookout and the dig. It still computes the
shrine's disc, the processional way and the standing stones' footprints, **writing nothing**, because the dig's
placement is keyed to them and the dig a world already holds must not move (measured: the new city build writes
exactly the old one's cells minus 8,358 relic/cordon cells, nothing new and nothing changed). `data/deep_city.json`:
`relic_area.capped` added; `arches`, `ring` and `cordon` moved under `relic_area.superseded_surface`; `shrine` and
`stones` marked `built: false`; the decision became `superseded_relic_cordon`. `tools/deep_city.py verify` no
longer needs `relic ring`. `tools/deep_city_audit.py`'s cordon check is **inverted**: it fails on a fenced edge
column, and on any block in the relic area standing more than 3 over the highest ground within 9 (the cap's
tallest kept piece; the ring stood 22 over the shrine). Heaven's Arena is untouched (`arena_plan` is not in the
relic code path; a canvas diff of the whole city before and after the change shows 0 new and 0 changed cells).

`tools/deep_city.py build_relic` built the relic area's surface until 2026-10-02. The principle for splitting it:
**everything that says WHAT was found goes underground; everything that says A DIG HAPPENED stays.** A
player on the lip sees that the Compact dug here, found something and closed it up, and learns nothing
about where it went.

**Stops being built** (data key → the code that builds it):

| Element | `data/deep_city.json` key | `tools/deep_city.py` |
| --- | --- | --- |
| the stepped platform | `relic_area.shrine` | `build_relic`, about lines 1704-1728 |
| the six ring arches | `relic_area.arches` | about lines 1729-1751 |
| the plinth and the broken relic ring | `relic_area.ring` | about lines 1752-1773, **including the `relic ring` entry appended to `checks` at line 1773** |
| the eight standing stones | `relic_area.stones` | about lines 1835-1865 |
| the processional way | (derived from `shrine` and `lookout`) | about lines 1825-1834 |
| **the Compact cordon** | `relic_area.cordon`, and the `relic_cordon` decision at `data/deep_city.json` line 32 | about lines 1934-1954 |

**Stays, as the sealed Compact cap:**

- **the sealed entrance** (`relic_area.sealed_entrance`, about lines 1699-1812) — *it is already the cap.* A
  forecourt four blocks down to a doorway of reinforced deepslate behind iron bars, whose own record
  already says "Nothing is carved behind the seal." It cannot be opened, reinforced deepslate drops
  nothing, and it says only that the Compact shut something. Keep it exactly where it is, at (3360, 3304):
  that is three blocks from the cradle's centre, so it caps the cradle's side of the site, and there is
  nothing behind it either way.
- **the lookout** (`relic_area.lookout`, about lines 1813-1824) — the one element of section 5's surface
  that genuinely cannot go underground. It becomes a Compact survey post with a view, not a shrine terrace.
- **the dig** (`relic_area.debris`, about lines 1866-1933) — seven survey trenches, nine spoil heaps, crates
  and the **five broken gold fragments**, left in the spoil. This is what makes the capped surface legible:
  a dig that found something and was called off. The fragments are what the Compact pulled *out*; the
  intact ring underground is what makes the walk worth it.

**Two dependencies, named here rather than discovered.** (1) `data/deep_city.json` should gain
`relic_area.capped` naming this document, and the `relic_cordon` decision at line 32 should become
`superseded_relic_cordon` with a note rather than being deleted — it records a call the owner has reversed
(CLAUDE.md on displaced work). (2) **the `relic ring` fixture at line 1773 is in `tools/deep_city.py`'s
`need` set at line 2095 and in `tools/deep_city_audit.py`.** Removing the ring without removing that
fixture fails the audit closed on a thing that is no longer built.

## 4. The zone check, not barriers

The rung is **datapack plus functions and commands** (CLAUDE.md principle 6, rungs 5 and 6), and the rungs
below do not reach: Cobblemon native has no player-zone concept, no installed addon gates an area,
Cobbleverse ships none, and no config key expresses a box a player may not stand in. A
`minecraft:location` advancement does, and its reward function acts. The rung is **proven in this
repository, not assumed**: `tools/gulch_mine.py`'s gate and `tools/rift_zones.py`'s five zones are this
exact shape. And the rung above configuration that the superseded design used was *no mechanism at all* —
a fence is a barrier, not a rung.

```
          ring 0, y66   HQ front door (3443, 67, 3282) -> storey-0 room   turn-back: (3444, 67, 3308), facing east
                              |  the stair, 66 down from (3429, 66, 3299) in the reserved shaft (section 8b)
   y0  ................  [records room x3422-3428]  <-- knock box (3422-3424, 1-3, 3305-3307), OUTSIDE the zone
                              |
   y1          x3421 OPEN DOORWAY  ---- threshold x3420-3421: carved, NOT in the zone
                              |          a passless player stands here and sees the passage
   y1..y12   <-------- the passage, 64 blocks west, zone box 3 (x3357-3419) -------->  cradle (Codex's)
                              |
                   x3390 junction, y6
                              |  the gallery, 20 north
   y5                  THE RELIC HALL, r21, dome to y34        zone boxes 1 and 2
```

**What the zone needs.** Six things, and five of them already exist:

1. **One dummy scoreboard objective, `cob_pass_relic`.** `data/rift_zones.json`'s prefix is `cob_pass_` and
   its zones are `cob_pass_z1..z5`, so this collides with none of them. Created by the pack's load function;
   one value per player; set once, never unset.
2. **Two advancements and six functions**, all emitted: `relic_zone`, `relic_knock`; `load`, `zone`,
   `turn_back`, `knock`, `qualify`, `grant`. No tick driver, deliberately — the check is
   advancement-driven, exactly as the gulch's is, and `tools/reapply.py`'s step table already says of the
   gulch that "the gate, the zone check ... act on their own and need no step".
3. **A y-bounded zone: y-64 to y40.** *This is the one place this zone differs from every zone before it,
   and the difference is forced.* `data/rift_zones.json` and `data/gulch_mine.json` are both the full column
   (y-64 to y575) because flying over a surface zone is still inside it. A full-height relic zone cannot
   work: its columns lie under the relic area's walkable surface, which **Z2 already admits at eight
   badges**, so every eight-badge player standing on the lip would be turned back. The top is y40 (the
   dome's apex is y34, the choke stops at y40); the lowest ground anywhere over the zone's three boxes is
   **y86**, measured, so there are 46 blocks of rock between the zone's ceiling and the surface over it.
   The trade is stated in the data: a player who tunnels down to y41 directly over the hall is not in the
   zone. They are in 46 blocks of rock whose last six blocks are the choke.
4. **The pass, which is "you came through the HQ".** It is granted only in the knock box inside the HQ
   basement at the open doorway, and only to a player holding all eight badge flags
   (`cobblers:flag/gym1_cleared` … `gym8_cleared`). The route is the gate; the zone check is what stops
   every other route. The knock box is **outside** the zone's boxes, so nothing has to be excluded and the
   knock and zone advancements can never fire on the same tick and race — a fault
   `tools/rift_zones.py` had to engineer around.
5. **No setter is invented.** `DEEP_CITY.md` section 5 opens the cradle on `rift_crisis_pending` and stands
   the cordon down on `rift_crisis_resolved`. **Neither is available to an advancement today.**
   `rift_crisis_pending` is a *value of the quest field* `quest.main_worldshift_reveal.stage`
   (`data/progression.json`), set by the dialogue transition `record_rift_crisis_pending`
   (`data/quests.json`, from node `rift_007`) — not an advancement, and a different mechanism from
   `tools/progression_pack.py`'s flags. `rift_crisis_resolved` **has no setter on any branch**;
   `data/quests.json` says so itself and `data/rift_zones.json` `zones.z5.needs_progression` records the
   same, which is why the whole Z1–Z5 system is built and deliberately not installed. The eight badge flags
   are the only flags in this design whose setter exists (`set_by.kind: trainer_defeat`, EXP-027). **The
   upgrade, when a setter exists, is one field** — `zone.pass.threshold_advancements` — and no code, no
   geometry and no re-carve. Adding `rift_crisis_resolved` *before* it has a setter would make the zone
   shut forever rather than open at eight badges, so `tools/relic_underground.py report` fails closed if it
   finds that flag in the pass.
6. **The fail-closed shape, copied deliberately.** The score is **not** tested inside the advancement.
   `minecraft:entity_scores` does not match when the objective has no value for that player, which is every
   player who has never stood at the door, so a score condition in the advancement fails **open**. The
   advancement tests location only; the function tests the score with
   `execute unless score @s cob_pass_relic matches 1..`, which is true for an unset score.

**No exit box and no arrival teleport.** `RIFT_ZONES.md` section 4 needs both because its zones sit behind
walls with gatehouses. There is no wall here: the doorway is open, the player walks in, and leaving is
walking east out of box 3. Two advancements and two functions fewer, and two fewer things that can misfire.

## 5. State, and the multiplayer cases

| Case | What happens |
| --- | --- |
| **where state lives** | one dummy objective, `cob_pass_relic`, one value per player. Nothing server-wide, no global counter, no first-player-wins |
| a player joins late | no score, so no pass; they walk the HQ themselves. The hall's blocks are not per-player, so they walk into the room the others left |
| dies inside | the turn-back resets the spawnpoint *before* teleporting, so a bed or anchor placed inside cannot loop a passless player. A passed player respawns wherever they would and walks back in |
| disconnects inside | the location advancement re-fires within a second of login; passed stays, passless is turned back to ring 0 |
| plays in a different order | the pass depends on eight badges and one doorway. No ordering with the cradle, the finale or any other zone |
| a passed player leads a passless one in | the grant is `@s` in the knock box, so only the one standing there is granted. The one behind is turned back at x3420 |
| flies, pearls, digs, rides, teleports in | every route ends with the player inside the boxes and the test fires within a second. The mount is moved first (`execute on vehicle`); that Cobblemon riding survives it is **unproven**, as `RIFT_ZONES.md` section 4 already records |
| an operator inspecting | `@s[gamemode=!creative,gamemode=!spectator]`: creative and spectator are never turned back, as the gulch's gate does it |
| cost | one location test per player per second against **three** boxes — an order of magnitude cheaper than Z1–Z5, which test a few hundred each |

## 6. What ran, and what did not

**Ran, offline, in this worktree:**

- `python tools/ground.py` at the columns in section 2, and the swath measurements the data records.
- `python tools/relic_underground.py report` → **0 problems, 3 owed.** It measured 1,625 carved columns,
  58 blocks of rock over the void at its thinnest, 53 over the choke, a 46-block margin between the zone's
  ceiling and the lowest ground over it, 2,495 composition blocks with the highest non-choke block at y26
  against a dome apex of y34, and **0** hall columns outside the traced region.
- `python tools/relic_underground.py build` → the pack and the carve into
  `build/cobblers_relic_underground`: 2 advancements, 6 zone functions, 5 carve functions, 35,554 air
  blocks, 3,250 floor and ceiling blocks, 12,386 shell fills over 573,439 tested cells, 2,495 composition
  blocks. The emitted `zone`, `qualify` and `relic_zone.json` were read back and are the intended commands.

**The report found three real faults before this document was written**, which is the only evidence here
that the checks bite:

1. six carved columns outside the zone's boxes, at (3420-3421, 3305-3307) — the doorway threshold, now a
   declared `zone.threshold_x` with a reason, not a silent hole;
2. a composition block at (3410, 6, 3270) outside the hall — the two **fallen** standing stones were laid
   outward, and a stone of height 8 at orbit 19 reaches 26 in a hall of radius 21. They now fall inward,
   toward the ring;
3. the cover check conflated the void's ceiling with the choked shaft's solid top and reported the smaller
   number (53) as a cavern's cover. They are two measurements and are now reported as two.

**Not verified, explicitly:**

- **Nothing has been seen in a running Minecraft.** No server was touched; `prepare` and the full suite
  were not run (out of scope for this unit).
- **`verify` could not run.** There is no staging world to read (`docs/STATE.md`: the staging worlds are
  gone), so "in the world" currently means nothing. The checks it must make when one exists are listed in
  `tools/relic_underground.py cmd_verify`.
- **The mutation test was not run.** CLAUDE.md's standard for an independent check is to mutate the
  *generator* and confirm the check bites. The attempt to do that was refused by the harness (section 7),
  and per the refusal rule that line stopped there. The three faults above are the checks biting on real
  input, which is weaker evidence than a mutation and is what there is.
- **No block id was read from a jar here.** `legendarymonuments:distortion_stone` is carried from
  `data/deep_city.json` and `data/rift_skin.json`, which record it as placed on staging; the fallback
  `minecraft:tuff` is kept.
- **`lumymon:elevator`'s `requiredAdvancement` is assumed, not sourced.** This design does not depend on it.
- **Hoopa.** `pokespawn hoopa` spawned `cobblemon:hoopa` in a running game on 2026-10-01, so the species
  exists in Cobblemon 1.8.0. **Whether it renders is a client fact and is not verified.** Nothing here
  breaks on a placeholder model: the hall's content is architecture and relics, and no block, light or
  route depends on Hoopa being drawn.
- **The hall's light level is not measured** (`tools/light_plan.py`'s emitter table is known incomplete).
- **The hall's spawn decision is made** (2026-10-02, section 8d): nothing spawns there. That nothing does in game
  is not verified.
- **The spawn-block check** in `palette.spawn_block_check` is carried from `DEEP_CITY.md`'s check of the
  same list and has not been re-run against `data/spawn_blocks.json`.
- **The cradle's size is unknown.** "Codex may give the cradle up to a 22-block radius before the two rooms
  share rock" is a bound this file measured, not an agreement.

**Owed before this can be installed (2026-10-01):** the step, the surface removal and the spawn decision. All
three are done (sections 8 and 8d). The **sequencing rule** stands:
the carve runs *after* the pit and the HQ, and *before* Codex's cradle, or the cradle's own 24-block shell will
seal this passage's west end — x3358 is one block from the cradle's centre column.

## 7. Refusals during this work

Two commands were refused by the harness's worktree guard, and both are recorded verbatim because a
refusal ends the attempt (CLAUDE.md) rather than being routed around.

> This agent is isolated in the worktree
> C:\Users\wnd\Documents\github\cobblers\.claude\worktrees\agent-a60bfd9fd27e95945, but this command is too
> complex to verify that it stays inside the worktree. Refusing to run it — a worktree-isolated agent's git
> operations must target its own worktree. Split it into plain, separate commands and run them from
> C:\Users\wnd\Documents\github\cobblers\.claude\worktrees\agent-a60bfd9fd27e95945.

That one refused a batch measurement of the zone boxes' ground minima. Only the remedy the refusal itself
names was used: plain, separate `python tools/ground.py` calls at the box corners. The generator then
measured the same quantity itself, which is where the 46-block margin comes from.

> This agent is isolated in the worktree
> C:\Users\wnd\Documents\github\cobblers\.claude\worktrees\agent-a60bfd9fd27e95945, but this command feeds
> python a program assembled at runtime in a plain command, so what it runs cannot be shown not to be git.
> Refusing to run it — a worktree-isolated agent's git operations must target its own worktree. Run the
> plain command from C:\Users\wnd\Documents\github\cobblers\.claude\worktrees\agent-a60bfd9fd27e95945.

That one refused the mutation test (a `sed` of the dome's ceiling formula inside the generator, then
`report`). **That line of work stopped and was not attempted another way.** The working tree was checked
afterwards and is unmodified. The mutation test is the one thing this unit owes an independent reviewer.

## 8. 2026-10-02: wired, and what wiring it found

**The wiring.** `tools/reapply.py`: `cobblers_relic_underground` in the server packs and in `WORLD_LOCAL` (its zone
advancement acts on its own); prepare jobs `relic_underground:build` (after `deep_city_audit`; the build runs its
fail-closed `report` first) and `relic_underground_audit` (late, after every other block pack, because it sweeps
them); and **step R9RU** right after R9DC: `forceload add 3285 3217 3445 3384` (121 chunks), `undo`, the five shell
parts, `10_void`, `20_surfaces`, the five reshell parts, `30_composition`, `forceload remove`. Every block function
is split at 3,000 commands and passes `tools/function_limits.py` (the step holds the chunks: `# chunks-loaded-by`).
The pack's output path moved from `build/cobblers_relic_underground` to `build/datapacks/` where `install` finds it.

**Four faults, found by measuring rather than by the report, which read the same numbers as the generator:**

1. **The gallery did not reach the passage.** The gallery was z3284-3303 and the passage's interior z3305-3307:
   the passage's one-block north wall at z3304 stood between them, so the hall was sealed off from the route.
   The new audit's route check (a walk from the HQ doorway to the plinth's foot through what was actually
   written) found it; the gallery is now z3284-3304 and the walk reaches the plinth's foot.
2. **The turn-back point was inside the HQ tower.** (3436.5, 67, 3308.5) is in the tower's ground floor, whose
   walls are closed at y67-68 in the city's build: a turned-back player would have been shut in. The data's
   "HQ tower (x3422-3432)" was wrong; the built tower is x3427-3439. Moved to **(3444.5, 67, 3308.5)**, the
   city's sidewalk on ring 0 just east of the HQ's ring-0 building, two clear blocks over it; `report` re-checks
   the tread, the floor and the head room every run.
3. **The HQ's basement and secure shaft are built by no tool.** `data/deep_city.json` reserves them
   (`hq_basement`, `hq_secure_shaft`) and nothing writes there; the city lays a reinforced-deepslate hatch at the
   shaft's head, (3427, 66, 3308) and (3427, 66, 3309). So the passage ends in rock at x3422, the knock box
   (3422-3424, 1-3, 3305-3307) is solid, **nobody can walk in and nobody can be granted the pass.** The hall is
   reachable only by digging, and the zone turns a passless digger back. Carving the basement and shaft is
   DEEP_CITY.md section 9 step 5 ("HQ, shaft, passage and cradle, once Codex sends the chamber's needs") and an
   owner/Codex decision; it is not done here (`zone.hq_access`). **Superseded the same day by section 8b**, which
   builds them.
4. **The shell would have filled the city.** The shell's `replace` converts air; under the Deep's ring 0 the
   city cuts rooms into the risers. The build now caps a pit column's shell at its tread and drops any cell the
   city writes. Measured: **0 cells clipped** either way at today's geometry, so this is a guard, not a repair.

## 8a. The undo (in R9RU, before the carve)

The world already holds the old surface build, and a data edit changes nothing there. **Which cells:**
`tools/relic_surface_superseded.py` -- `build_relic()` from `tools/deep_city.py` at c63b67a, verbatim -- run on a
fresh canvas (9,575 cells; the dumped pre-change city build had exactly 9,575 relic- and cordon-owned cells), minus
every cell the CURRENT city build writes (1,217: the sealed entrance, the lookout and the dig stay). Never derived
from a world. **What goes back:**

- over the ground (heightmap, rounded), where the old block was solid: **air** (2,858 cells: the cordon's 463
  tinted glass and 926 bars, the 102 raw-gold ring cells, the 146 distortion-stone arch cells, the stones, the
  platform's raised courses);
- over the ground, where the old build CUT AIR (4,831 cells): **nothing** -- that world has air there already, and
  a fresh world may hold an earlier pack's block in it;
- at and under the ground (669 cells, depth 0-2, where the platform and the way cut or paved the ground): the
  ground **`tools/paint_maps.py` painted for the export**, by its own rule (the `rift_west_spur` sub-region's
  `rift_floor` preset, its gravel patches, `terrain_below 96` on height plus jitter, the rock slope), from the same
  value noise and seed 20260914. All 669 come out **GRAVEL** and are laid as gravel, bottom-up so none falls.
  None of these columns is touched by the Rift sculpt (0 of 1,469), so the Rift skin never painted them.

**Swept, not assumed:** `cobblers_rift_zones` (the throat wall runs along the relic area's west side) writes 0
cells the old build wrote; the audit sweeps every built pack for a cell the undo or the shell touches.

## 8b. The HQ's way down (2026-10-02, `carve/40_hq` in R9RU)

The owner's sentence needs a way in through the HQ, and no tool built one. `data/relic_underground.json`
`geometry.hq` is the data and `tools/relic_underground.py` builds it as `carve/40_hq`, the last block function of
R9RU: after the reshell, so no shell pass seals it, and the shell never lays a cell of it.

**What the HQ actually is, measured off `tools/deep_city.py`'s build (not a world):**

- The HQ **tower** is `tower_box` [3428, 3303, 3438, 3313]: walls x3428 and x3438, interior x3429-3437. It has **no
  door** ("the tower's storeys, empty; no way in is built"). The ring-0 section's own walls flank it at x3427 or x3428
  and x3439, which is where the earlier "x3427-3439" came from.
- The HQ's **ring-0 section** is lot `hq_66` (939 columns, x3427-3448, z3251-3320). Its storey 0 is the room
  `hq_secure_shaft_head`: air y67-70 over the Deep's tread y66. Its one door is **(3443, 67, 3282), an iron door
  facing east, closed, with nothing to open it** (the lot is sealed because that room is).
- The city's **hatch** at (3427, 66, 3308) and (3427, 66, 3309) lay **under the section's west wall** (waxed oxidized
  copper from y67 up): the sited column lost its 3x3 to the tower box and the pit's edge. No shaft could open there.
- The reserved **secure shaft** [3423, 0, 3304, 3431, 65, 3312] was drawn for a tower at x3422-3432. Today x3423-3426
  is the lip's rock outside the pit, x3427-3428 walls, x3429-3431 under the tower's sealed ground storey; no column
  of the room's floor is over it.

**What is built:**

| Part | Where | What |
| --- | --- | --- |
| Front door | (3443, 67, 3282), the city's iron door | **shut, with nothing beside it that opens it** (section 8c). The door is untouched. The first build's two plates, (3444, 67, 3282) and (3442, 67, 3282), are gone (`front_door.superseded_plates`) |
| Stair head | (3429, 66, 3299), the room's south-west corner | the first three treads open in the room's floor (z3299-3301); the next two pass under the room's and the tower's walls at z3302-3303 with the tread y66 as their ceiling |
| The stair | x3429-3431, z3299-3312, y0-66 | a switchback in the shaft's 3 x 9: lane a (x3429) descends south, lane b (x3431) north, the spine x3430 is R9B's rock, landings at z3304 and z3312 cross it. 59 `polished_blackstone_brick_stairs` treads facing uphill, 23 `polished_blackstone_bricks` landing cells, three clear over every one. Floors: head y65-53, landings y52/44/36/28/20/12/4, the foot y0 |
| Stair foot | (3429-3430, 0, 3308) | west through the spine into the records room |
| Records room | interior x3422-3428, y1-4, z3301-3310 | floor `polished_blackstone_bricks` y0, walls `deepslate_bricks`, ceiling `deepslate_tiles` y5; bookshelves along the north wall, barrels (empty) along the south, a lectern |
| Doorway | x3421, z3305-3307 | the passage's own cells, open: its floor is y1, so a step up west from the room's y0 |
| Knock box | (3422-3424, 1-3, 3305-3307) | the room's west end at the doorway: carved air on the room's floor |
| Lanterns | 19 standing, 2 hanging | in spine niches at every landing and each flight's middle, three along the head flight, five in the room. Never light blocks. Light NOT MEASURED |
| Old hatch | (3427, 66, 3308), (3427, 66, 3309) | laid back to `deepslate` (the tread's bare-rock margin there was native rock). `tools/deep_city.py` no longer lays it |

**Reserved, and sealed.** Every cell is inside `data/deep_city.json`'s `hq_basement`, `hq_secure_shaft` or the new
`hq_shaft_head` [3428, 58, 3298, 3430, 66, 3303], except the two hatch cells. The city build fails
closed if it ever writes into any of them; with the hatch gone its build diff is **exactly those two cells removed,
0 added, 0 changed** (452,337 cells before, 452,335 after). Every face of the way down's air is written, in the shell
or a hull (`replace` void with rock, inside the reserved boxes, never over a pit tread), under a pit tread where R9B
refills every void from y-4, or the HQ room's open air over the stair's head; `report` and the audit both check it.

**The walk, checked.** `tools/relic_underground_audit.py` now walks from **outside the front door** (3444, 67, 3282)
to the plinth's foot through the blocks actually there: the relic pack's writes, else the city pack's (read as text),
else the pit's tread and the heightmap; since 2026-10-02 the door is crossed only by the guard's edge (section 8c);
the walk must pass the guard, the stair's head and the knock box. CLEAN (2026-10-02, after the guard): 980 places
without the guards and the room not among them, 3,406 with them, hall reached. Mutating the **generator** (data
untouched) bites: the stair's head re-sealed (the hatch, in effect) fails `route` and `hq`; a plate put back at the
door fails `hq` and `route` (section 8c); the room one column short of the doorway is refused by the generator's own report
and, with that report silenced, fails `route`, `zone` and `hq` (`tests/test_relic_underground.py`).

**Found while doing it, fixed here:** the audit failed in any checkout that had built `cobblers_deep` (the pit,
R9B): 46,909 shell cells overlapped R9B's own `replace #rift_void` fills, and the old rule counted any overlap as a
conflict. Two void-to-rock fills never fight and R9B runs first, so the audit now exempts the `replace` fills of
packs applied before R9RU (`EARLIER`, today only `cobblers_deep`; a test pins R9B < R9DC < R9RU in
`tools/reapply.py`) and still fails on any definite write (the plates were the one exception until 2026-10-02).

**Sequencing.** A re-run of R9B after R9RU would refill the stair and the room (its refill is `replace`). R9B runs
before R9DC before R9RU in `tools/reapply.py`.

**For the owner (2026-10-01):** the plates opened the door for anyone. **Answered 2026-10-02:** the plates came off
and the door is the guard's (section 8c).

## 8c. The door and its guard (2026-10-02)

The owner: *"The pressure plates are wrong: the HQ door should need the finale's quest stage, not a plate anyone can
stand on."* Chosen stage: **`rift_crisis_pending`**, so the door is passed by a player whose
`quest.main_worldshift_reveal.stage` is `rift_crisis_pending`, `rift_released` or `league_recognized`.

That stage is a per-player enum in Cobblemon player data. Dialogue reads it (`tools/compile_dialogue.py`, the same
per-player gating `docs/mechanics/MARKET_GATING.md` describes); no command, advancement or function can. So the gate
is a dialogue option, and the door is never opened at all:

| Part | Where | What |
| --- | --- | --- |
| The door | (3443, 67, 3282) | the city's iron door, **shut**, nothing beside it (`front_door.opened_by`) |
| The guard | (3444, 67, 3283), yaw -90 (facing the street) | `npc_main_relic_hq_guard`, conversation `dlg_main_relic_hq_guard`, on the sidewalk one south of the doorstep |
| The doorstep | (3444, 67, 3282) | where a player stands to talk to him; the audit's walk starts here |
| The inside landing | (3440, 67, 3282), facing west | two blocks inside the door on the storey-0 room's floor (the tread y66) |
| The inside guard | (3441, 67, 3280), yaw 0 (facing the landing) | `npc_main_relic_hq_guard_inside`, conversation `dlg_main_relic_hq_guard_inside`: "Let me out." moves you to the doorstep. **Not asked for**: added because with the door shut nothing else lets an admitted player out |

**How it runs.** The guard's entry rules pick `admit` at those three stages and `turned_away` otherwise. Turned away
is two lines and closes ("Compact HQ. This door opens on orders, and I've none with your name on them." / "When the
operation needs you, they'll tell me. Move along."). `admit` offers **Go through.**, `visible_when` the stage is one
of the three, whose action is the main quest's transition `relic_hq_admit` (conditions: the same three stages; effect:
`function cobblers:relic_underground/hq_admit`). The compiler runs that as `execute as <that player's uuid> at @s`,
and the function refuses a player more than 6 blocks from the guard, dismounts them and teleports **@s** to
(3440.5, 67, 3282.5). Nobody else moves and the door never opens, so nobody follows. `hq_release` is the same shape,
ungated, to (3444.5, 67, 3282.5). Both conversations are the main quest's (`tools/validate_data.py` lets a quest read
only its own fields), with two cursor fields declared in `data/progression.json`.

**What sets the stage.** `record_rift_crisis_pending` (`data/quests.json`), run when a player at
`giovanni_reveal_complete` acknowledges the Rift surveyor's line `rift_007` (`dlg_main_rift_surveyor`, seated by R17N
at (3552, 112, 5334)). **A setter exists in data and compiles**; nobody has walked that chain in game. Nothing yet
moves the stage past `rift_crisis_pending` (`unlock_league_after_rift_resolution` waits on a `rift_crisis_resolved`
setter), which does not matter here: the door opens from `rift_crisis_pending` on.

**Placed by** `tools/reapply.py` step **R18RU** (after R17N and R18U): the two NPCs over RCON, each turned to its yaw,
from `relic_underground.npc_placements()`. Their classes come from `cobblers_dialogue`, so the server must have
restarted with it.

**Audited** (`tools/relic_underground_audit.py`, kind `guard` and `route`): from `data/dialogue.json`,
`data/quests.json` and `data/progression.json`, which the generator does not write, the audit finds every transition
that runs `hq_admit` and every conversation that calls one; only the guard's option may, its `visible_when` and its
transition's conditions must each admit **exactly** the enum's values from `rift_crisis_pending` on (that stage is
written in the audit, the owner's word, not read from the relic data), and the built function must move `@s` only,
only near the guard, by one tp. That tp is the guard's edge. The walk is run twice: without the guards, the storey-0
room must be out of reach from the doorstep (any pressure plate, button or lever beside the door makes the door
passable, and is also an `hq` fault on its own); with the guards' edges, the hall must be reached through the guard.
Mutating the **generator**: a plate put back at (3444, 67, 3282) is refused by the generator's own report, and with
the report silenced the audit fails `hq` ("an opener beside it") and `route` ("reached WITHOUT the guard"); a guard
function that teleports back onto the doorstep fails `route`; a guard function written with `@a` fails `guard`
(`tests/test_relic_underground.py`).

**Not covered:** a player can still break the HQ's walls in survival, as anywhere; the hall itself is still the zone's
(section 4). And the zone pass (eight badges at the knock box) does not know about the guard: a player who digs into
the records room past him with eight badges is let into the hall. Section 11 item 6.

## 8d. Nothing spawns in the hall (2026-10-02)

The owner: *"Hoopa's hall: nothing spawns there. It is the end of the story, not a cave."* Made real the way the gyms
are: three spawn-free zones in `data/spawn_suppression.json`, which `tools/compile_spawns.py` cuts out of every
route, sub-region and waterway pool and `tools/suppress_inherited_spawns.py` adds to the inherited pools'
anticondition boxes. **No Habitat Block.** Vanilla hostiles need nothing: MobsBeGone cancels them all
(`docs/STATE.md`, "No vanilla hostiles").

| Zone | Box [x0, z0, x1, z1] | Holds |
| --- | --- | --- |
| `relic_hall` | [3360, 3232, 3415, 3287] | the hall (zone box 1 [3366, 3238, 3414, 3286]) |
| `relic_gallery` | [3384, 3280, 3399, 3311] | the gallery (zone box 2 [3386, 3284, 3394, 3304]) |
| `relic_way_down` | [3352, 3296, 3431, 3319] | the passage (zone box 3 [3357, 3302, 3419, 3310]), the records room and the stair (x3421-3431, z3299-3312) |

Each is snapped **out** to the 8-block grid `merge_boxes` enforces. A spawn-free box is x/z only, every y, so it also
clears Cobblemon spawns on what stands over these columns: the capped relic area's surface over the hall and passage,
and the Deep's HQ section over the stair (x3424-3431, including about 60 columns of ring 0's street). Snapping out
also takes in x3352-3356 at the cradle's doorstep (Codex's); a scripted Hoopa there is not a wild spawn and is not
affected. The audit (kind `spawns`) checks that every one of the 1,724 columns it derives for the hall, gallery,
passage and way down is inside a zone and that no Habitat Block stands in one; the generator's report checks the
zones are in `data/spawn_suppression.json` as `composition.spawn_decision.zones` records them.

## 9. World probes

For the session that holds the server, after R9RU, over RCON. Each `execute if block` prints "Test passed" when
true. Expected results in brackets. None was run by the author.

The hall, gallery and passage:

```
execute if block 3390 20 3262 minecraft:air            [passed]  hall air at its centre, over the plinth
execute if block 3390 34 3262 minecraft:air            [passed]  the dome's apex
execute if block 3390 35 3262 minecraft:tuff           [passed]  the choked shaft (cobbled_deepslate/tuff), no air
execute if block 3390 5 3282 minecraft:deepslate       [passed]  the hall's floor at its south rim
execute if block 3390 5 3262 minecraft:tuff_bricks     [passed]  the platform's lowest step, laid in the floor
execute if block 3390 8 3262 minecraft:chiseled_tuff_bricks [passed]  the plinth
execute if block 3390 6 3295 minecraft:air             [passed]  the gallery
execute if block 3390 6 3304 minecraft:air             [passed]  the gallery's mouth through the passage wall
execute if block 3390 5 3304 minecraft:deepslate       [passed]  its floor
execute if block 3390 7 3306 minecraft:air             [passed]  the passage at the junction (floor y6)
execute if block 3421 2 3306 minecraft:air             [passed]  the passage at the HQ doorway (floor y1)
execute if block 3421 1 3306 minecraft:deepslate       [passed]  the doorway's floor
execute if block 3358 13 3306 minecraft:air            [passed]  the passage's west end at the cradle's doorstep
```

The HQ's way down (section 8b):

```
execute if block 3443 67 3282 minecraft:iron_door      [passed]  the HQ's front door (the city's)
execute if block 3443 67 3282 minecraft:iron_door[open=false] [passed]  ... and shut
execute if block 3444 67 3282 minecraft:air            [passed]  the doorstep: NO plate (the first build's is gone)
execute if block 3442 67 3282 minecraft:air            [passed]  inside the door: NO plate
execute if block 3444 66 3283 minecraft:polished_blackstone_bricks [passed]  the guard's floor
execute if block 3440 67 3282 minecraft:air            [passed]  the inside landing, clear
execute if block 3440 68 3282 minecraft:air            [passed]  ... and its head room
execute if block 3441 67 3280 minecraft:air            [passed]  the inside guard's cell (air; he is an entity)
execute if block 3429 66 3299 minecraft:air            [passed]  the shaft head OPEN in the room's floor
execute if block 3429 65 3299 minecraft:polished_blackstone_brick_stairs [passed]  its first tread
execute if block 3429 63 3302 minecraft:air            [passed]  the head flight under the room's wall
execute if block 3429 66 3302 minecraft:air            [failed]  ... whose ceiling is the tread, intact
execute if block 3430 52 3312 minecraft:polished_blackstone_bricks [passed]  a landing (landing_1, floor y52)
execute if block 3430 53 3312 minecraft:air            [passed]  its head room
execute if block 3430 53 3311 minecraft:lantern        [passed]  its lantern, in the spine
execute if block 3430 30 3308 minecraft:air            [failed]  the spine between the lanes is rock
execute if block 3429 0 3308 minecraft:polished_blackstone_bricks [passed]  the stair's foot
execute if block 3430 1 3308 minecraft:air             [passed]  through the spine into the room
execute if block 3425 0 3306 minecraft:polished_blackstone_bricks [passed]  the records room's floor
execute if block 3425 1 3306 minecraft:air             [passed]  its air
execute if block 3425 5 3306 minecraft:deepslate_tiles [passed]  its ceiling
execute if block 3425 2 3301 minecraft:bookshelf       [passed]  the records
execute if block 3423 1 3306 minecraft:air             [passed]  the knock box, carved
execute if block 3423 0 3306 minecraft:polished_blackstone_bricks [passed]  ... on the room's floor
execute if block 3422 2 3306 minecraft:air             [passed]  the doorway, room side
execute if block 3421 2 3306 minecraft:air             [passed]  the doorway, passage side (floor y1, one step up)
execute if block 3427 66 3308 minecraft:deepslate      [passed]  the old hatch, laid back to rock
execute if block 3427 66 3309 minecraft:deepslate      [passed]
```

The guards (after R18RU; each selector counts the NPCs within 2 blocks, as R18RU's own check does):

```
execute if entity @e[type=cobblemon:npc,x=3444,y=67,z=3283,distance=..2]   [passed, count: 1]  the guard
execute if entity @e[type=cobblemon:npc,x=3441,y=67,z=3280,distance=..2]   [passed, count: 1]  the inside guard
execute if entity @e[type=cobblemon:npc,x=3443,y=67,z=3282,distance=..1]   [failed]  nothing stands IN the doorway
```

A walk, for the session holding the server: `/tp @p 3444 67 3282 90 0` (facing the door). Talk to the guard at a stage before
`rift_crisis_pending`: two lines and he closes, and the door stays shut. Set the stage (or walk the Rift surveyor's
conversation from `giovanni_reveal_complete`), talk again: **Go through.** must be offered, and choosing it must put
you at (3440.5, 67, 3282.5) inside, facing west, with the door still shut and a second player standing beside you
outside still outside. From inside, the inside guard's **Let me out.** must put you on the doorstep. Then, admitted,
walk along the room to its south-west corner, down the stair to the room at y0, west to the doorway. With fewer than eight badges,
stepping west past x3419 must turn you back to (3444.5, 67, 3308.5); with all eight, standing in the knock box must
print "The Compact's passage is open to you." and `scoreboard players get @p cob_pass_relic` must read 1.

The zone (installed and loaded):

```
datapack list enabled                                  [lists file/cobblers_relic_underground]
scoreboard objectives list                             [includes cob_pass_relic]
advancement revoke @p only cobblers:relic_underground/relic_zone   [revokes, or "couldn't revoke"; NOT "unknown"]
advancement revoke @p only cobblers:relic_underground/relic_knock  [same]
```

The old surface, now natural ground (the cordon's glass, the gold ring, an arch, the platform's cut):

```
execute if block 3285 94 3352 minecraft:air            [passed]  was the cordon's tinted glass (ground y93)
execute if block 3386 101 3292 minecraft:air           [passed]  was the gold relic ring
execute if block 3385 94 3298 minecraft:air            [passed]  was the ring (raw gold), ground y88
execute if block 3373 89 3298 minecraft:air            [passed]  was a distortion-stone arch
execute if block 3370 88 3296 minecraft:gravel         [passed]  was the platform, ground y88, painted GRAVEL
execute if block 3360 85 3304 minecraft:reinforced_deepslate [passed]  the sealed entrance KEPT
execute if block 3353 88 3330 minecraft:raw_gold_block [passed]  a ring fragment in the dig KEPT
execute if block 3444 66 3308 minecraft:polished_blackstone_bricks [passed]  the turn-back's floor
execute if block 3444 67 3308 minecraft:air            [passed]  the turn-back's head room
execute if block 3444 68 3308 minecraft:air            [passed]
```

Entities: R9RU summons none. Nothing spawns there (section 8d), so after the spawn packs are rebuilt and
installed: `execute if entity @e[type=cobblemon:pokemon,x=3369,y=5,z=3241,dx=42,dy=30,dz=42]` [failed, count 0],
and the same over the passage, `@e[type=cobblemon:pokemon,x=3357,y=0,z=3302,dx=72,dy=20,dz=8]` [failed]. Only
meaningful once `cobblers_spawns` and `cobblers_suppress` have been rebuilt with the three zones (they are built at
`prepare` and `install`, not by R9RU).

## 10. Where to fly

| What | Coordinates | Note |
| --- | --- | --- |
| The HQ front step (turn-back) | (3444, 67, 3308), facing east | ring 0's sidewalk; the turned-back land here |
| The HQ's front door | (3444, 67, 3282), facing west | the doorstep; the iron door is (3443, 67, 3282), shut |
| The Compact guard | (3444, 67, 3283) | beside the doorstep, facing the street; talk to him to go in |
| The inside landing | (3440, 67, 3282), facing west | where "Go through." puts you |
| The inside guard | (3441, 67, 3280) | "Let me out." puts you back on the doorstep |
| The shaft head | (3429, 66, 3299); stand at (3429, 67, 3297) to look down it | the stair opens in the storey-0 room's south-west corner |
| A landing | (3430, 53, 3312) | landing_1, lantern in the spine beside it |
| The records room (basement) | (3425, 1, 3306) | floor y0; the stair's foot is (3429, 1, 3308) |
| The doorway into the passage | (3421, 2, 3306) | the passage's end; the knock box is the room's west end, (3422-3424, 1, 3305-3307) |
| The old hatch | (3427, 66, 3308) | deepslate under the HQ section's wall; nothing to see |
| The gallery mouth | (3390, 7, 3305) | step down north into the gallery at y6 |
| The hall centre | (3390, 8, 3262) | on the platform by the plinth; the ring stands over it to y26 |
| The surface over it | (3390, 94, 3262) | the capped relic area: no shrine, no fence |

## 11. Open decisions for the owner

1. Is the hall the right place, or should the shrine be a chamber the passage *ends* in, past the cradle?
   (That puts the shrine behind the finale, which is a different game.)
2. What the hall holds after the finale — section 5's options (a) presence, (b) a battle or catch, (c) the
   ring becomes a waystone. Unchanged by moving underground, except that (c) is now a waystone in a sealed
   room reached through the HQ.
3. Whether the lookout keeps its railing and lantern on a surface that is otherwise bare spoil.
4. **The hall's spawn decision: DECIDED 2026-10-02** (section 8d): nothing spawns there. No Hoopa encounter is
   invented: Hoopa's cradle (3357, 3306) is Codex's.
5. **The HQ's ring-0 door: DECIDED 2026-10-02** (section 8c): it stays shut and the guard admits a player at
   `rift_crisis_pending` or later. Still open: whether the records room should hold anything (a reward, readable
   records) -- it holds shelves, barrels and a lectern, and no loot.
6. **New, 2026-10-02: the way out, and whether the pass needs the guard.** (a) The inside guard who lets anyone out
   was added by the unit that took the plates off, because nothing else opens the door; keep him, or choose another
   way out. (b) The zone pass is still "eight badges at the knock box", so a player who digs into the records room
   past the guard is let into the hall. `hq_admit` could set a per-player score that `qualify` also tests; not done,
   because the brief kept the zone and the knock box as they are.
7. **The guard's lines** are short Compact placeholders written by the unit; the owner or Codex may rewrite them in
   `data/dialogue.json` (the audit reads the gate, not the words).

## 12. Not verified (2026-10-02)

- Nothing seen in game; R9RU has not run on any world. `prepare`, `reapply plan` and the full suite were not run
  by this unit (`plan` needs every pack built, and `cobblers_rift` needs `derived/rift_sculpt`, absent here).
- The undo's ground is paint_maps' **terrain code**, mapped to a block: GRAVEL as gravel is a code name, not a read
  of WorldPainter's material or its layer depth (depth 0-2 laid as gravel).
- **The Rift skin's crack grooves, veins and lip debris are not swept**: they need `derived/rift_sculpt/basin.npy`,
  absent in this worktree. The skin's surface bands are not involved (0 of the columns is sculpt-touched); if a
  crack groove sat at a ground cell the old platform overwrote, the undo lays gravel there instead.
- Victory Road's caves and any pack not built in the worktree were not swept: the audit swept
  `cobblers_deep_city` and `cobblers_rift_zones` only here. In `prepare` it sweeps every pack built before it.
  The 2026-10-02 HQ unit swept `cobblers_deep` and `cobblers_deep_city` (built in its worktree), nothing else.
- The door and its guards (section 8c): nothing seen in game. That the compiled option shows only at the three
  stages, that `hq_admit` runs for the speaker only and lands them inside, that `ride @s dismount` and `return fail`
  behave as written, and that the guards stand where R18RU puts them, are all unverified. The audit's guard edge
  does not model line of sight or the door's hitbox between a player and a guard.
- The spawn-free zones (section 8d): offline only; nothing has been seen not to spawn.
- The HQ's way down (section 8b): nothing seen in game. That the stair walks (the audit models a tread as a full block and a step of one), the light on the stair and in the room,
  and the zone's turn-back and grant at the new knock box are all unverified.
- `tools/lakebed_repair.py` seeds its bed noise from `data/world.json` `seed` (null, so 0) + 17, but
  `tools/paint_maps.py` paints with `--seed` 20260914 + 17: the two disagree. Found here, not fixed (not this
  unit's file).
