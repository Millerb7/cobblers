# The gym interiors as built: gyms 2, 3, 4, 5 and 7

**Status, 2026-09-29:** authored and generated offline. **Nothing here has been seen in a running game.** A clean
`tools/gym_interiors_audit.py` proves the geometry is consistent with the placements and the heightmap; it proves
nothing about how any of it plays.

**Scope.** Gym 1 (Brock) was already built and is unchanged except for one field. Gym 6 (Sabrina) is excluded: it is
the only per-player puzzle and waits on EXP-034. Gym 8 (Giovanni) is its own unit. So `tools/reapply.py` R16E now
reads *"no healer in any of the 8 gyms, and 6 carved interior(s)"*.

The model is the one commit `6976742` established and is not replaced: `data/gym_interiors.json`, one generator, one
offline fail-closed audit, one re-application step. Shell geometry is still never authored - every world coordinate
descends from the donor record in `data/placements.json` through `place_donor.box()` and `place_town.rotate()`.

---

## What each site actually is, measured

Ground is `tools/ground.py`, the canonical heightmap, rounded. No world was read.

| gym | shell box (derived) | hall floor | ground over the lot | what the site gives, and what it refuses |
|---|---|---|---|---|
| 2 Misty | `1594,107,2859 .. 1629,146,2890` | y133 | 104-108, falling to 93 south-east | Her hall stands **26 courses up on the template's own rock**: the only gym whose floor is 25 blocks above grade. Her spawn-free box leaves 2 blocks either side, so the works can only go **straight down**. |
| 3 Surge | `1726,173,1397 .. 1748,189,1423` | y175 | **174 at the west face, 197 at the east; 250 thirty blocks on** | The only gym **cut into a hillside**. East of it the ridge buries everything, so the hall can be 15 blocks tall. The box's east edge at x1751 is what stops it going deeper. |
| 4 Erika | `4297,109,1480 .. 4323,125,1502` | y111 | **110 across the whole lot, 109-111 for 40 blocks around** | Dead flat. Ceilings may not pass y107. The site gives area and no height at all. |
| 5 Koga | `4577,115,2467 .. 4603,131,2490` | y117 | 115-117 | The most **confined** lot: the spawn-free box leaves 4 blocks east and 2 south. One room the size of the lot. |
| 7 Blaine | `6159,105,4982 .. 6181,121,5008` | y107 | 106, flat | Flat like Erika's, but with **35 blocks of rock under it**: nothing horizontal, everything vertical. |

## What was built, and why it follows from that

| gym | title | verb | the shape the site forced |
|---|---|---|---|
| 2 | the cistern under the lake | **ride** | A 42-block scaffolding well down the rock plinth into a basin; a one-way fall of 8 into a race **swum at the surface** (water to y87, air over it, so nothing asks a player to hold their breath); three identical mouths at its head, one lit; the ledger gallery above, and a 4-block sill back down to the cistern. |
| 3 | the adit into Vessu | **trace** | One hall **15 blocks tall**, four cable trenches cut 9 deep in its floor, and a catwalk at y167 behind a **copper grate** - see-through, two high, so the run is read over it and cannot be stepped off. Three lines are plugged; from inside a trench you can see nothing. |
| 4 | the beds below the glasshouse | **crawl** | A cellar 4 tall under a flat garden. Beds on legs with a hand's width of water under them; an azalea hedge with one gap; the way south is a **1-high flooded drain** swum on your front, discharging 3 above the cistern floor so it cannot be swum back. |
| 5 | the sump under the watch | **footing** | A mud fen 6 below a web of **1-wide causeways** that branch four times and mostly stop; the trackers' board of cast prints on the staging wall is the route. A miss is a fall into mud, a wade and a climb. |
| 7 | the throat | **leap** | Four 2x2 vents in a floor. Three stop 5 down on a plug with a ladder out; the fourth is **18 blocks of fall into 6 of water**. Back up is a **soul-sand geyser**, which is the only one-way-upward thing in the six and is what stops the leap being optional. |

Brock climbs, Misty rides, Surge traces, Erika crawls, Koga steps, Blaine jumps: six verbs, no repeats. A test
(`tests/test_gym_interiors.py::test_no_two_built_gyms_are_the_same_puzzle`) fails if two ever share one, and another
fails if two gyms' room dimensions match.

**The one thing all six share, deliberately:** the shaft. The healer's cell is the only interior cell of any shell
whose position was measured, so it is the only place a hole may be cut, and the top of every shaft stands inside a
building whose blocks were never measured. Scaffolding is the only climbable that needs no wall behind it, so every
gym's entrance is a scaffolding column. Everything below the first ten blocks differs.

## Deviations from the accepted design, and why

`docs/mechanics/GYM_INTERIORS.md` section 4 gives Surge a breaker board, Erika item-frame dials, Koga a sculk alarm
and Blaine retracting piston bridges. **None of the four is built.** All four are redstone logic, and nothing in this
repository can check a redstone circuit offline: the audit replays blocks into a voxel model, not signals. Shipping
four unverifiable circuits blind into a world that has to be re-applied is exactly the thing principle 18 exists to
stop. So each gym keeps its designed **verb** and the apparatus is built as scenery - the breaker board is on the
relay chamber's wall, the sculk sensors are the trackers' listening posts, the fumaroles are in Blaine's floor - and
the puzzle itself is geometry, which can be checked in full before anyone stands in it.

Misty's design asked for soul-sand up-columns at the race's head. A bubble column is one-way upward, and three of
them would strand a player who chose a wrong mouth, so the false mouths are plain sumps swum back out of in five
blocks. The one bubble column in the six is Blaine's geyser, where being unable to swim back down **is** the point.

Every gym takes `state_scope: shared_permanent`, for gym 1's reason: nothing is switched, so nothing can be
desynchronised between two players and nothing needs resetting.

## What the audit now checks, and what each check caught

`tools/gym_interiors_audit.py` is offline, fail-closed, and reads only the written functions plus data it derives
itself. It never imports the generator and never reads a world. New in this unit:

- **the interior against the placement**: the authored entrance must equal the measured healer cell mapped through
  that placement's own rotation; the recorded floor course and standing level must equal the shell's base plus the
  measured template offsets; the dig must lie wholly below the shell's lowest course and inside the gym's spawn-free
  box; the penetration must be one column at the entrance.
- **the standing template**: the part of any write that lands inside the placed shell's box must be inside the
  declared penetration. The first version of this check refused all six shafts, because a single `fill` runs from the
  dig up into the shell - so it now checks the intersection, not the whole box.
- **water**: it holds a player, needs no headroom (a flooded 1-high channel is swum), and ends a fall safely.
- **bubble columns**: found by scanning down a water column for soul sand, and refused as a downward move. Without
  this the model let a player swim down Blaine's geyser and skip his whole interior.
- **contract G2**: the longest run of route with the player's *head* under water, capped at 14 blocks. Misty's is 10,
  Erika's 4, Blaine's 8.
- **spawn conditions**: `minecraft:water` is a spawn condition (`data/spawn_blocks.json`). It is written in gyms 2, 4
  and 7 only, declared per gym, and every cell of it must lie inside that gym's spawn-free box, which is contract G1
  and the whole of the reason it is safe (`tools/compile_spawns.py` cuts the zone out of every compiled spawn file,
  all y). This answers Q8 of the design's open list for water; carpets are still not used.

**The audit refused 39 problems across five drafts before this one.** Worth recording, because each was a real fault
and not a formality:

- Misty's gallery and the cistern were 0 blocks apart with no route between them, and her canal route ran *through*
  the swimmer's island.
- Surge's relay sill capped its own ladder, so the way out ended one block short.
- Erika's third planting bed sat on top of the ladder and on the east aisle; the route's first three steps had soil
  at head height.
- Koga's fen ladder's landing block overwrote the ladder; one false causeway spur connected past the second tracker,
  so he could be walked round; the hide's chute had no shaft under it.
- Blaine's stair climbed the wrong way and landed in rock; the galleries' north wall left a lane past the second
  researcher; the rack room was 6x9 with a trainer in the middle of it, which closes nothing; three false throats'
  ladders were faced into their own holes, where nothing would have carried them.

## What is not done, deliberately

- **No rosters.** Twelve new trainer seats exist (2, 2, 2, 3, 3) with yaw and sight distance only.
  `derived/gym_interiors/trainer_seats.json` is the handoff in the shape `data/route_trainers.json` takes. Until
  `data/trainers.json` carries these ids, nothing is placed.
- **No leader gates.** As gym 1: a gate needs the shell's door cell and the Q1 read did not measure it.
- **The `no_build` boxes are authored and not wired.** Contract G4 needs a scene record in `data/scenes.json`.
- **No redstone anywhere**, per the deviation above.

## What a playtest has to answer

1. **Erika's drain.** Can a player swim a 1-block-high flooded channel? The swimming pose is 0.6 blocks tall in
   vanilla and this is the usual way such a tunnel is passed, but it has not been tried in this pack. If it fails,
   the drain becomes two high and one `fill` changes. This is the only behavioural assumption in the five.
2. **Blaine's leap.** 18 blocks into 6 of water should be harmless; it is also the first time this campaign asks a
   player to jump into a dark hole. Does the lit throat read as the safe one *before* they step off?
3. **Blaine's geyser** carries a player 10 blocks. Does it, reliably, from a standing start at its foot?
4. **Misty's well** is 42 cells of scaffolding. Is that tedious enough to matter?
5. **Two spills are expected and cosmetic**: Erika's drain discharging into her cistern, and the geyser's foot
   leaking across the rack room's floor. Both are water finding its own level out of a deliberate opening. If either
   looks wrong, it is a wall, not a redesign.
6. **The trench lines in Surge's run** are read from a catwalk 10 blocks above them. Is the plugged line visible from
   there, at the light level the lanterns give?
