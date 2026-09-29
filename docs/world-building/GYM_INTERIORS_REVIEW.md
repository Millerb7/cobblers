# Gym interiors: independent review

Reviewer: `test-author` (2026-09-29). Not the builder: `tools/gym_interiors.py`, `data/gym_interiors.json`,
`tools/gym_interiors_audit.py` and `tests/test_gym_interiors.py` were written by another agent (CLAUDE.md principle 16).
This review and `tools/gym_interiors_independent.py` / `tests/test_gym_interiors_independent.py` were written without
starting from those files; the incumbent's audit and tests were read last, for section 7 only.

Subject: the six emitted functions `cobblers:gym_interiors/gym{1,2,3,4,5,7}` and `healers`, generated from head
`50b4f8a`. Gyms 6 and 8 are not built; gym 8 (Sabrina in the data, Giovanni in the placement) is out of scope.

## 1. Verdict per gym

| Gym | Fits its site | Route can be completed | Water and blocks | Verdict |
|---|---|---|---|---|
| 1 Brock | yes | yes, but the designed one-way return does not work (F1) and the climb can be jumped past (F2) | clean | fits; two design defects |
| 2 Misty | yes | yes | lanterns float (F6) | fits; passes with a low finding |
| 3 Surge | yes (cover exactly 3 at the north-west corner, measured against the lowest surface possible) | yes | lanterns float (F6) | fits; passes with a low finding |
| 4 Erika | yes | **no**: the works stop at the drain (F3) | two open water sources spread (F4), the hedge decays (F7), lanterns float (F6) | **fails**: nothing past the first bed can be reached |
| 5 Koga | yes | yes | lanterns float (F6) | fits; the fen puzzle can be hopped (F5) |
| 7 Blaine | yes | yes | geyser foot spreads over the rack room (F4), lanterns float, three in the pool (F6) | fits; passes with low findings |

The healing-machine removal covers all eight placed shells exactly (checked against boxes derived here from
`data/placements.json`), and no block outside the eight shells.

None of the works gate the leader (`leader.gate: null` in every gym), so a broken works does not block a badge. That is
a design fact, not a defect, but it bounds how bad F3 is: Erika's works are a dead end, not a wall.

## 2. What was checked, and against what

| Check | Independent source |
|---|---|
| Every write inside the gym's own lot | `data/placements.json` settlement plan, `anchors[role=gym]` rect and `level` |
| Shell box | own formula from position/size/rotation (agrees with `place_donor.box` and with hand-worked rotations in the tests) |
| Surface for cover | `tools/ground.py`, rounded; lowest of the heightmap and the lot's levelled height. No world was read |
| Only one column open into the hall, ending at the hall floor, on the healing machine's cell | `docs/mechanics/GYM_INTERIORS.md` Q1 (floor 2 above the shell base, 26 for Misty); the healer cell from `measured`, rotated here |
| No other building, anchor or street on the lot | `data/placements.json` |
| No wild spawns in the works, no spawn-condition block in the palette | `data/spawn_suppression.json`, `data/spawn_blocks.json` |
| Nothing else claims the columns | every `data/*.json`, scanned for points and rects that land in a dig |
| Route, shortcuts, traps, falls, drowning | a movement model in the audit (walk, one-block jump, sprint jump over one or two blocks, falls with damage, ladders, scaffolding, swimming, one-high crawl, bubble columns) run over the voxels the functions produce, tracing the design's own waypoints, doors and trainer seats |
| Sources sealed, ladders backed, scaffolding grounded, lanterns held, leaves persistent | the emitted blocks, against block rules |

Taken from the design and therefore not independent of it: the route waypoints, the room names, the door list and the
trainer seats (they are the claims being traced), and the healing-machine cell (a measurement of Cobbleverse's
template, which cannot be re-measured here without extracting the no-redistribution NBT).

## 3. Defects

Severity is the effect on a player and on the design, not the size of the edit.

**F3 (high) Erika's drain cannot be entered.** `gym4` cellar. The route goes through a one-block-high flooded channel:
water at (4310, 99, 1494..1497) under a mossy-brick cap at (4310, 100, 1494..1497), entered from a dry mouth at
(4310, 99, 1491..1493) (`fill ... minecraft:air`, "kept dry so it can be entered on foot"). In the game a player
starts swimming only sprinting with the head under water, and the pose is not entered from dry land or from the
surface: the roof over the first water cell stops a walking player. To submerge, the cell in front of the channel needs
two blocks of water over the feet. As emitted it has none. Seven design waypoints from (4310, 99, 1494) on, both
gardeners' second stand, the cistern, the ladder, the potting passage and the hatch are therefore unreachable. Checked
by starting the model in the cistern at (4310, 96, 1499): everything after the drain (partition gap, ladder to
(4315, 103, 1503), passage, hatch (4316, 103, 1494), aisle, shaft) is connected, so the drain is the only break. The
design itself lists this as its one unproven behaviour ("assumed"); the emitted blocks make it fail rather than merely
unproven. Control: flooding (4310, 99..100, 1489..1493) makes every waypoint reachable
(`test_flooding_the_drains_mouth_two_deep_makes_it_enterable`). Confidence: high on the rule; unverified in a game.

**F1 (medium) Brock's chute cannot be walked off.** `gym1`. The chute floor is (1825..1827, 134, 3681..3682), standing
level y135. The way "back" is a four-block drop west onto the straw at (1823..1824, 130, 3681..3682). The cutting room's
last column x1824 is air only to y135 (`fill 1814 131 3679 1824 135 3689`), so a player stepping west from the chute
finds (1824, 136, 3681..3682) rock over their head and stops. The design step (1826, 135, 3681) -> (1823, 131, 3681) is
39 moves in the emitted blocks (the whole climb retraced) for seven blocks of distance. Not a trap: the retrace works,
and the high ledge can be jumped off onto straw. Fix: carve (1824, 136, 3681..3682) or lower the chute floor by one.

**F2 (medium) Brock's climb can be jumped past.** `gym1`. The "dead-end walkway" (1820..1827, 129, 3696) is the west arm
of the scaffold deck, and its tip is a two-block gap and one block down from the low ledge (1815..1823, 130,
3692..3693), with the doorway's four blocks as a run-up. A sprint jump from (1823, 131, 3693) lands on (1823, 130, 3696),
and the deck, the walkway to (1830, 129, 3698..3700), the last ladders, the wall top and the jib beam follow. The pit
floor, the yard hand, the rubble ramp, the crest and the east ladders are skipped. The audit reports the yard hand as
walked round. Fix: move the arm's tip out of jump range of every ledge cell, or drop it two.

**F5 (medium) Koga's decoy causeways connect to the true one.** `gym5`. The "false" spans are within one block of each
other and of the true causeway: (4593, 102, 2478..2479) hangs off the true span at (4593, 2480), and (4591..4594, 102,
2476) is one gap (z2477) beyond it and touches the true span (4595..4599, 2476). Hopping (4593, 2480) -> (4593, 2478) ->
(4593, 2476) -> (4595, 2476) reaches the hide's approach without the far staging and the second tracker at
(4599, 103, 2480) (sight 3.0). The fen puzzle ("most of them stop") does not force a wrong turn or a route. Fix: at least
a four-block gap between any decoy and any span, or a fence.

**F4 (low to medium) Open water sources spread.** A source with air beside or under it flows. `gym4`: 12 sources, the
cistern store (4307..4311, 96, 1502..1503) and the drain's outfall (4310, 99, 1497), wet about 104 air cells across the
cistern and cellar. `gym7`: the two lowest geyser cells (6178, 86..87, 5006) wet about 28 cells of the rack room floor,
26 of them on the walked route. Not lethal (flowing water is a current, not a depth), but neither matches "one deep and
waded" and both push players around ladders. Fix: wall the store and the geyser foot, or accept and say so.

**F7 (medium) Erika's hedge decays.** `gym4` (4314, 99..102, 1481..1493): 49 `minecraft:azalea_leaves` with no
`persistent=true`. With no log within six blocks they decay by random tick. The hedge is the wall that makes the first
gardener's gap the only way through the cellar. Fix: `azalea_leaves[persistent=true]`.

**F6 (low) Lanterns are placed in the air.** Hanging lanterns need a block above them, standing ones a block below.
`gym2` 4 (e.g. (1612, 98, 2866): the room ends at y99, the ceiling is y100), `gym3` 6 ((1738, 163, 1426) hangs 7 below the
ceiling), `gym4` 4 ((4308, 97, 1498) stands one above the floor), `gym5` 7 ((4578, 105, 2486)), `gym7` 10, three of them
inside the pool water at (6166, 74, 5000), (6169, 74, 5002), (6166, 77, 5002). `/fill` does not run the survival check,
so they appear and float, and pop when a neighbour changes (water flowing, a player breaking anything nearby).
Cosmetic until it is not.

## 4. Things looked for and not found

- Every carve inside its lot: dig extents x/z against the lot rect, all six inside. Cover to the surface and to the hall
  floor is at least 3 everywhere (gym 3 exactly 3 at (1735, 171, 1402), against the lowest surface possible; the real
  ground there is higher).
- The shaft is one column, ends at the hall floor's standing level (gym 1 y142, 2 y133, 3 y175, 4 y111, 5 y117, 7 y107)
  and stands on the cell where the healing machine stood, worked out here from the placement's rotation.
- No street, anchor or other placement on any lot; no other data file names any dig's columns.
- Spawn-free zones hold every dig; no spawn-condition block is used except water, which the zones cover.
- Blaine's leap: eighteen blocks from the chamber floor into water six deep on a floor at y72, over the whole 2x2
  hole (6167..6168, 5002..5003); modelled damage 0. The three dry vents stop on the basalt plug and have ladders backed
  by rock. The geyser is a bubble column (soul sand under source water, walls on two sides, sealed on the others) that
  cannot be swum down in the model, and the rack room cannot be reached from the hall without entering the pool
  (`test_the_geyser_cannot_be_swum_down_so_the_leap_cannot_be_skipped`).
- Misty: 8-block drop into 2 deep water, false mouths sealed 1-wide shafts in rock; the longest head-under-water trip there and back in the
  model is 14 blocks (gym 2) and 10 (gym 7) against a limit of 28.
- No reachable trap, no lethal fall, no submerged position without a way to air, no suffocation cell (a cell a
  player can occupy needs an open head cell by construction; bubble column tops open into air).

## 5. Mutations

Every mutation is applied to a copy of the emitted text and must be caught; each is also compared with the unmutated
output so a problem that was already there does not count.

| Mutation | Caught by |
|---|---|
| each gym moved 8 blocks east, 6 tests | site codes (shaft off the healing machine's cell, out of lot, cover, spawn zone) |
| each gym moved 8 blocks south, 6 tests | same |
| each gym raised 12 blocks, 6 tests | cover / breach / column no longer ends at the hall floor |
| Blaine's pool water deleted | a 17-block fall onto stone, 14 damage |
| Blaine's pool one deep | landing water too shallow |
| wall opened between Brock's cutting floor and the pit | rooms joined; door room skippable |
| shaft cut from Blaine's rim chamber to the landing | rooms joined; throat room skippable |
| geyser soul sand replaced with basalt (swim down) | rooms skippable |
| Brock's masons' ladder removed | the pit becomes a trap |
| a ladder turned to face open air | ladder unsupported |
| shaft one block short of the hall floor | column does not end at the hall floor |
| two interiors on the same cells | cell collision |
| a scene record on a dig | data scan |
| control: Erika's mouth flooded two deep | the route becomes reachable (audit does not cry wolf) |

The first draft of the site checks did not catch a gym 1 or gym 2 interior moved 8 blocks: their lots are large enough
to hold it. That is why the healing machine's cell is part of the site check.

## 6. Not covered

Validity is not behaviour (`.claude/rules/testing.md`). Every rule below is from the game and unmeasured here. Each is an
experiment, not a pytest.

- **Movement.** Sprint-jump reach (two blocks with a run-up), the one-high crawl entry (F3), swimming speed, the 300
  ticks of air, fall damage into shallow water, and scaffolding as a ladder both ways. F2 and F5 rest on jump reach;
  F3 on the swim pose rule. A player playtest of gyms 1, 4 and 5 settles them.
- **Trainers.** They are not placed. Guards use the design's seats and a sight ball (the same simplification the
  incumbent makes), not RCT's real trigger.
- **Flowing water** is an upper bound (7 blocks along a floor, down any drop), not a tick simulation.
- **Anything generated from masks or grids** (`water_shape`, rivers, sculpt) is not scanned: only coordinates in the
  JSON are. Misty's cistern lies under a lake town's waterfront lot; whether the water shape reaches the lot was not
  checked.
- **Order and coexistence.** Gym 3's pressed pad is parked (the disposable world does not carry it), so its cover is
  measured against the lot's level, not a world. The ordering after the donors (R16E) is asserted in `tools/reapply.py`,
  not tested here.
- **Block states.** Ids and states were not checked against a registry (no server or jar read). The healing machine's
  cell is a measurement of a template that could not be re-measured.

## 7. Where this differs from the incumbent's audit

The incumbent's audit (`tools/gym_interiors_audit.py`) reports CLEAN on the same output. Both agree on the shell boxes,
cover, falls into hay and water, the bubble column and the healer removal. It differs because its movement model lets a
player enter a one-high flooded gap from a dry cell (its own comment says so), does not jump gaps, and checks that
waypoints are standable rather than that one leads to the next: that is F3, F2/F5 and F1. It also takes its
expectations from `data/gym_interiors.json` (dig boxes, block lists) where this audit takes them from the placements,
the heightmap and block rules, and it does not look at lantern support, leaf persistence or water spread (F6, F7, F4).

Run: `python tools/gym_interiors.py build && python tools/gym_interiors_independent.py` (one verdict line, problems
only) and `python -m pytest tests/test_gym_interiors_independent.py -q`. Known defects are xfailed with the finding
named in `KNOWN_DEFECTS`; fixing one makes its test fail until the entry is deleted.
