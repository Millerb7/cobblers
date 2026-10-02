# The relic site underground: the hall off the HQ's cradle passage, and the zone that keeps it

**Status: design plus a generator that runs, 2026-10-01. Nothing is installed, nothing is in any world,
nothing has been seen in game.** `data/relic_underground.json` is the data, `tools/relic_underground.py`
the generator (`report` and `build` both run; `verify` cannot, because there is no staging world to read —
`docs/STATE.md`). It answers the owner, 2026-10-01: *"THE RELIC SITE UNDERGROUND, reachable only through
the Compact HQ, turned back by the zone check rather than barriers."*

It **supersedes `docs/world-building/DEEP_CITY.md` section 5's surface half** and keeps its underground
half unchanged. `DEEP_CITY.md`, `data/deep_city.json` and `tools/deep_city.py` are **not edited here**:
another agent is extending them this wave, so section 3 below is a removal proposal that names the exact
keys and lines.

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
| The gallery | x3389-3391, z3284-3303, 20 long | y5 | y11 | 75 |
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

## 3. What comes off the surface (a proposal; `deep_city` is another agent's this wave)

`tools/deep_city.py build_relic` builds the relic area's surface today. The principle for splitting it:
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
          ring 0, y66   [HQ tower x3422-3432]        turn-back: (3436, 67, 3308), facing east
                              |  shaft down 66
   y0  ................  [HQ basement]  <-- knock box (3422-3424, 1-3, 3305-3307), OUTSIDE the zone
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
- **The hall has no spawn decision**, and a dark 1,849-column room without one is a mob farm. It belongs in
  the Deep's spawn-free precinct or needs its own Habitat band; neither is authored here.
- **The spawn-block check** in `palette.spawn_block_check` is carried from `DEEP_CITY.md`'s check of the
  same list and has not been re-run against `data/spawn_blocks.json`.
- **The cradle's size is unknown.** "Codex may give the cradle up to a 22-block radius before the two rooms
  share rock" is a bound this file measured, not an agreement.

**Owed before this can be installed:** a `tools/reapply.py` step for the carve, after R9DC and before R9E,
on the CAVERN pattern (`02_shell`, `10_void`, `20_surfaces`, `25_reshell`, `30_composition`); the surface
removal of section 3; the hall's spawn decision. The zone pack itself needs no step. And the **sequencing
rule**: the carve must run *after* the pit and the HQ, and *before* Codex's cradle, or the cradle's own
24-block shell will seal this passage's west end — x3358 is one block from the cradle's centre column.

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

## 8. Open decisions for the owner

1. Is the hall the right place, or should the shrine be a chamber the passage *ends* in, past the cradle?
   (That puts the shrine behind the finale, which is a different game.)
2. What the hall holds after the finale — section 5's options (a) presence, (b) a battle or catch, (c) the
   ring becomes a waystone. Unchanged by moving underground, except that (c) is now a waystone in a sealed
   room reached through the HQ.
3. Whether the lookout keeps its railing and lantern on a surface that is otherwise bare spoil.
4. The hall's spawn decision: inside the Deep's spawn-free precinct, or its own Habitat band.
