# Gym interiors

**Status:** design proposal, 2026-09-28. Nothing here is built, and no experiment has run against it.
**Written by:** `content-architect` (no shell: every claim below is read from files, never run).
**The problem (the owner, 2026-09-28):** "The gyms are one room with a leader. That is the weakest part of
the map and I want to fix it."

Every claim is marked **VERIFIED** with `path:line`, or **ASSUMED**. Nothing here asserts a Cobblemon or addon
capability that is not already recorded in the repository.

---

## 0. Why the gyms read the same

**VERIFIED.** Seven of the eight gyms are literally the same building recoloured:
`docs/world-building/STRUCTURE_INVENTORY.md:583-585` — "Seven of the eight gyms are one 27×17×23/24 building
recoloured", the leader read from each template's `rctmod:trainer_spawner`. The footprints in
`data/placements.json` agree: Brock 27·17·24 (`data/placements.json:4603-4607`), Koga 27·17·24
(`:5527-5531`), Sabrina 27·17·24 (`:6009-6013`), Blaine 27·17·23 (`:6989-6993`), Giovanni 27·17·24
(`:7371-7375`), Surge 27·17·23 (`:13396-13400`), Erika 27·17·23 (`:7909-7913`). Only Misty's is its own
building, 36·40·32 (`data/placements.json:5490-5494`, `STRUCTURE_INVENTORY.md:575`).

**VERIFIED.** What is inside each one: "an `rctmod:trainer_spawner` locked to the leader; battle-position
blocks and a healing machine; a display case" (`STRUCTURE_INVENTORY.md:89-93`). Brock's also carries 9 command
blocks that summon a "Kanto Map Guide" villager when its pressure plate is pressed, and erase themselves
(`STRUCTURE_INVENTORY.md:101`). `docs/world-building/NAVIGATION.md:189-192` states the same conclusion
already: "the only identity in their blocks is the spawner id".

So the weakness is real and measured, not an impression. Eight gyms, one room, one shell, seven times.

---

## 1. Templates: extend in place, or rebuild?

### What is already possible

| Route | What it is | Precedent | Cost in authored data | Cost in build steps | Risk to what stands |
| --- | --- | --- | --- | --- | --- |
| **A. Dress the standing shell** | write blocks into the placed building after the donor step | `data/town_dressing.json` + `tools/town_dressing.py`, re-applied at R16B, verified in the world by `tools/build_audit.py --only town_dressing` (`docs/STATE.md:130`) | one data file of pieces | one generator, one offline audit, one `reapply.py` step (after the donor) | **none**: the donor step is untouched, the pack is world-local and re-runnable |
| **B. Override the template at its namespace path** | emit `data/cobbleverse/structure/<leader>.nbt` from a pack that loads after Cobbleverse | CLAUDE.md's layer rule allows it ("overridden … or from a file our generators emit at the same namespace path"); `tools/structure_nbt.py` can write a template (`tools/structure_nbt.py:58`) | a whole building as data | a generator, plus a **clear-and-re-place** of every standing gym | **high**, and **refused on licence**: a derivative of `COBBLEVERSE-DP-v31.zip`'s NBT is no-redistribution (`data/placements.json:4594`) and may never be committed (CLAUDE.md, "Only MIT-style sources may be committed") |
| **C. Carve the interior below the shell** | the shell keeps its hall; a stair descends from it into rooms cut under the lot | ADR-004, Accepted: "Carve in place anything the fiction says is right there" (`docs/decisions/ADR-004-pocket-spaces.md:29-31`); the technique is the one `tools/deep_city.py`, `tools/gulch_mine.py` and `tools/rift_mines.py` already use (`docs/STATE.md:140-143`) | one data file per gym or one for all eight | one generator, one offline audit, one `reapply.py` step | **none to the shell**; it adds an excavation under a levelled lot, and needs the spawn-suppression box widened (below) |
| **D. Pocket dimension** | the gym's door leads to an instanced space | ADR-004 allows it "only for spaces that must be bigger than their entrance, or instanced per player" (`ADR-004:32-34`) | a dimension, its spawn rules, per-player coordinates | a dimension datapack, a restart, a re-application step (`ADR-004:53-56`) | moderate; a loading screen, a coordinate jump, sent-out Pokemon recalled (`ADR-004:57-63`) |

### Recommendation

**A + C.** The shell stays the gym's face and its **last** room — the leader, the healing machine, the display
case, all already there. The puzzle is a **descent**: a stair down from the hall into two or three cut rooms,
built by a generated block pack exactly as the Deep's city and the gulch mine are. Dressing (A) handles the hall
itself; the dig (C) gives the eight gyms the space to stop looking alike, without re-placing a single building.

Why not B: the licence forbids committing a derivative of the Cobbleverse NBT, and an override would still
require clearing and re-placing 7 gyms on the disposable world and 8 on staging
(`docs/STATE.md:23`). Why not D: no gym needs a space bigger than its entrance except Sabrina's, and Sabrina's
illusion is better served by the per-player push barriers we already run (section 2) than by a dimension.

### What this needs that I cannot establish

**The interior floor plan of the eight templates is not on file anywhere in this repository.** The renders in
`build/structure_renders/` cannot show it — "Glass is opaque, so interiors are hidden"
(`docs/world-building/STRUCTURE_INVENTORY.md:773-775`). Without the plan I cannot say where a stairhead fits,
how much free floor the hall has, or where the leader's battle position is.

**The exact follow-up, for a session with a shell** (the NBT is inside the installed, gitignored
`COBBLEVERSE-DP-v31.zip` at `data/cobbleverse/structure/brock.nbt`, `data/placements.json:4592-4593`; read it
locally, never commit it; take the server lock first per CLAUDE.md):

```
# 1. extract the eight templates from the installed pack into the scratchpad (never into the repo)
# 2. what exists today, per file: size, block count, material counts
python tools/structure_nbt.py info <scratchpad>/brock.nbt
# 3. a floor plan: NO TOOL PRINTS ONE. structure_nbt.load() returns {size, palette, blocks} with every
#    block position (tools/structure_nbt.py:138-144), so a y-slice dump is ~20 lines; either add
#    `tools/structure_nbt.py plan <file> --y <k>` or write it as a throwaway in the scratchpad.
```

The plan must come from the **template**, not from a world scan: the template is authored upstream data, a world
holds whatever was built into it last (CLAUDE.md, "Ground comes from the heightmap, never from a world"). A
world read afterwards is a check, not a source.

Three more things the same read must answer, each of which changes the design:

1. **Where the `rctmod:trainer_spawner` sits, and whether our placed leader comes from it.** A puzzle whose last
   door opens onto the leader has to know where the leader stands.
2. **Where Brock's pressure plate and 9 command blocks sit** (`STRUCTURE_INVENTORY.md:101`). If the plate is on
   the puzzle route, the first player to step on it summons a map-guide villager into the gym. Removing it is a
   one-line donor substitution, the shape of which already exists: gym 8 substitutes a redstone torch for a
   plain torch (`data/placements.json:7389-7395`).
3. **How much clear floor the hall has**, which decides whether the stairhead is a hole in the floor or an
   extension cut into the wall behind the leader.

---

## 2. Puzzle mechanisms we actually have

Ordered by CLAUDE.md principle 6. Nothing below is invented; each line cites the file that already does it.

### Free — vanilla blocks, no datapack, shared world state

Buttons, levers, pressure plates (including weighted), tripwire hooks, target blocks, observers, comparators,
repeaters, hoppers, droppers, dispensers, pistons and sticky pistons, doors, trapdoors, fence gates, redstone
lamps, copper bulbs, note blocks, bells, item frames (rotation read by a comparator), lecterns, cauldrons, ice
and blue ice, soul sand and magma bubble columns, water and lava streams, ladders, scaffolding, sculk sensors
and calibrated sculk sensors, the crafter. A redstone circuit is shared, persists across restarts and a
re-export re-runs only what our packs write, so a vanilla circuit must be **written by a generated pack** to be
reproducible (CLAUDE.md layer rule: `build/` is disposable).

Two standing facts constrain this tier:

- **No vanilla hostile mob exists in this pack.** VERIFIED, `docs/STATE.md:99`: MobsBeGone blacklists 81
  entities and cancels them in `ServerLevel.addEntity`; a summoned zombie answers "Summoned" and does not
  exist. **No gym puzzle may use a mob.**
- **Every gym interior is already a spawn-free zone.** VERIFIED, `docs/STATE.md:23` and
  `data/spawn_suppression.json:61-71` (`gym_brock`, box `[1808, 3664, 1847, 3695]`). The boxes are **x/z only,
  four numbers, all y** — so a dig under the lot is covered, but only within that x/z rectangle. Any room that
  leaves the rectangle needs the record widened.

### Cheap — the machinery that exists and runs today

| Capability | Where it is | What it can do | What it cannot do |
| --- | --- | --- | --- |
| **Per-player push barrier** ("a door only you cannot pass") | `tools/scenes_pack.py:369-374`, used as the Gastly ballroom barrier at `data/scenes.json:691-728` and `:781-814` | teleport a player out of a box back to a marker, with a grey italic message, while a condition on **their own** quest fields holds | it is not a block: everyone sees the same open doorway; it fires on the scene cycle, i.e. **up to 1 second late** (`tools/scenes_pack.py:58`, `PERIOD = 20`) |
| **Per-player particle wall** | `tools/scenes_pack.py:358-360, 406-412` (`particle … force @s`) | show one player a shimmer nobody else sees; a `sequence` kind steps through phases each cycle (`:361-368`) | nothing solid |
| **Zone that advances quest state** | `tools/scenes_pack.py:329-350` | run a named quest transition for a player standing in a box | **cannot check an item** (`:344-345`) and **cannot give or take one** (`:346-347`); held-item conditions are refused in any beat (`:124-127`) |
| **Clickable prop → the clicker's own dialogue** | `tools/scenes_pack.py:317-327` (an interaction entity plus a `minecraft:player_interacted_with_entity` advancement, `:311-315`) | one shared object, a per-player conversation | it always opens a dialogue; it is not a lever |
| **Dialogue that checks and moves items, reads flags, runs functions** | `tools/compile_dialogue.py:145-151` (held item / inventory), `:152-158` (progression flag as an advancement), `:171-199` (give, reward-once with delivery verified), `:184-189` (`sync_scene`, `scene_function`, `function`) | everything a zone cannot | only from a click, never from standing somewhere |
| **Per-player actor** (a Pokemon that is yours, placed by your own state) | `tools/scenes_pack.py:208-309` | a guide, a guardian, a checkpoint that survives death, logout and restart | one per player per marker; spawned through `q.run_command`, never a bare function (`:258-265`) |
| **Adventure mode inside a box** | `tools/scenes_pack.py:381-404` | a survival player who steps in cannot break or place, and is returned to survival on leaving; creative and spectator untouched | a player already in adventure or creative is not managed |
| **Zone check on a progression flag** ("you are not allowed past here yet") | `tools/gulch_mine.py:1166-1168` (`minecraft:location` advancement), `:1210-1219` (turn back, mount first, actionbar message) | turn a whole polygon's worth of ground into a gate keyed on `cobblers:flag/<id>` | the location trigger fires about **every 20 ticks** (`tools/gulch_mine.py:1357`) |
| **Per-player ward** (you cannot mine this) | `tools/gulch_mine.py:1195-1199` | Mining Fatigue IV refreshed every second, creative and spectator exempt | it is not a lock; a determined player with milk gets seconds (`:1357`) |
| **A trainer win writing a per-player field** | `tools/route_trainers.py:118-127` (`rctmod:defeat_count` advancement → function → `runmolang`) | "this room's puzzle opens only for a player who beat its guardian" — already the mansion's shape (`data/mansion_guardians.json:4`) | fires on a win only, never a loss or a forfeit (`tools/route_trainers.py:25-27`) |
| **Per-player flags and per-player fields** | `cobblers:flag/<id>` advancements (`docs/STATE.md:125`); quest fields in Cobblemon player data, `quest.<quest_id>.<field>` (`docs/STATE.md:78`, `tools/compile_dialogue.py:12-14`) | the campaign's whole per-player state model | advancements are not readable from Molang directly; they are probed (`tools/compile_dialogue.py:152-158`) |
| **Shared world state as a field** | `data/progression.json:461-465`, `"scope": "world"` (the crushed house) | one fact the whole server shares | one value; not a per-room machine |

**The owner is right that the zone-check machinery exists**, and it exists twice, in two different shapes: the
scene runtime's `push` (keyed on the player's **quest fields**, 1 s cycle) and the gulch's location-trigger zone
(keyed on an **advancement flag**, ~1 s trigger). Neither makes a per-player *block*. Minecraft has no
per-player block state without a client mod, so **a "door only you can walk through" is always a teleport back,
never a closed door** — and both implementations are up to a second late, which is a design constraint, not a
bug: a sprinting player covers roughly 5.6 blocks in that second, so every per-player doorway needs a vestibule
deeper than that before anything the player must not reach. (The 5.6 figure is **ASSUMED** from vanilla sprint
speed; the latency is VERIFIED.)

### Needs new wiring — small, and still datapack tier

1. **A shared door that opens when a vanilla circuit is solved.** One tick function per gym:
   `execute if block <pos> <state> run setblock …`. New generator, new data, new offline audit. No new
   mechanism. (Often unnecessary: vanilla redstone can open the door itself.)
2. **A puzzle that resets when the room empties.** Nothing in the repo does this. A `minecraft:location`
   advancement on the interior box plus a tick check for "no player inside" plus a reset function.
3. **An item-gated step that is not a click.** A zone cannot read an item (`tools/scenes_pack.py:344-345`).
   Either a prop with a dialogue, or a new `minecraft:item_used_on_block` advancement — the precedent is the
   blackout's `any_block_use` on the healing machine (`tools/blackout_pack.py:16-19`).

### Refused

- **Scripting layer:** none exists in this pack (CLAUDE.md, "No KubeJS or scripting layer exists in the base
  pack"). Nothing below needs one.
- **Server companion / custom mod:** nothing in this design needs one. Principle 5 and 6 hold.

---

## 3. Trainers inside

**VERIFIED.** An rctmod trainer with `forceBattleOnSight` battles on eye contact within
`forceBattleMaxDistance` (`tools/route_trainers.py:99-104`), and **the sight check passes through walls** — the
owner saw Paula start a fight from the foyer, in game, 2026-09-24 (`data/mansion_guardians.json:4`). The
mansion's rule follows from it and applies unchanged to a gym: **a trainer's `sight_distance` is the largest
value that reaches no standable cell outside her own room, less 0.75.** In a cut interior with rooms 6-10 blocks
apart that means small numbers (the mansion's are 4.0 and 4.5, `data/mansion_guardians.json:23, 112`), or rooms
placed further apart than the sight radius. A validator check can enforce it once the interior model exists
(section 6).

**VERIFIED standing limitation.** rctmod never refuses a rematch with a placed trainer: `couldBattleAgainst`
returns true for a `summon_persistent` trainer before it looks at who beat it, and for the others the memory is
never saved (`docs/STATE.md:16`, `tools/route_trainers.py:36-45`). `maxTrainerDefeats` does nothing for ours
(`tools/route_trainers.py:45`). **Design against rctmod as if it forgets every win.**

**What holds them off today** (`tools/route_trainers.py:139-152`): every 10 ticks, for each placed trainer,
(a) it is teleported home if knockback moved it; (b) every nearby player gets or loses the tag
`cobblers_beat_<id>` from **their own** defeat field, which is the truth; (c) a 40-tick `Cooldown` is merged
onto the trainer **only while every nearby player has beaten it** (`:151-152`).

Three consequences for gym interiors, and they are the whole multiplayer story for trainers:

1. **A mixed-progress pair removes the cooldown.** The cooldown line requires `if entity @a[…,tag=beat]` and
   `unless entity @a[…,tag=!beat]`. Two players in a gym where one has beaten a trainer and one has not satisfy
   the first and fail the second, so no cooldown is written and **the player who already won can be pulled into
   a rematch while their partner is still fighting**. VERIFIED from the generated line; **not observed in
   game** (EXP-034, two players at once, is unrun: `docs/STATE.md:44, 211`).
2. **So a gym route must not walk a beaten player back past a trainer.** Either the way out is a different way
   (a one-way drop, a ladder from the leader's room to the entrance) or the trainers stand where a returning
   player does not pass them.
3. **Do not use the fight as the gate; use the fight's field as the gate.** A trainer's win writes a per-player
   field (`tools/route_trainers.py:118-127`); the room's door reads that field. That is exactly the mansion's
   design — "each room guarded by a Channeler who battles on sight and must be beaten before the room's puzzle
   opens" (`docs/STATE.md:211`) — and it is robust against rctmod forgetting, because the field never forgets.

`forceBattleOnSight` should stay **on** for gym trainers: it is what makes a trainer standing on the route
unavoidable, and the lesson is already taught on Route 1 (`tools/route_trainers.py:16-18`).

---

## 4. Eight puzzles

Hard rules applied: **none reads like another**; **difficulty rises**; **no wiki knowledge** — every solution is
visible in the room; every gym says how many trainers it holds and **where they stand relative to the route**,
so a player must pass them.

**Two collisions were found and replaced during this design, as required.** (i) Brock's first draft was three
levers raising a piston stair; that is the same idea as Surge's breaker board — flip switches until the way
opens — so **Brock was replaced** with a pure climb that has no mechanism at all, which also suits gym 1.
(ii) Misty's first draft was three sluice levers draining and flooding bays; the same idea again, so **Misty was
replaced** with a current the player rides and cannot switch.

| # | Leader / role (`TOWN_CHARACTER.md:41-48`) | The puzzle, in one line | The verb | Trainers, and where they stand on the route | Mechanism tier | Build cost |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **Brock** — the plateau's builders and the rescue coordinator | **The unfinished wall.** The hall is a wall half built under scaffolding; the only continuous way up to Brock's platform is found by looking: ladders, planks, a jib beam across a gap, one dead-end that is obvious from the floor. | climb / read a route | **2.** An apprentice mason on the first landing, which the only route crosses; a second on the jib beam's far end, the only way onto the top scaffold. | **Free** (vanilla blocks) + `no_build` box | one block pack, one data record, two trainer records. No new wiring. |
| 2 | **Misty** — the lake town that takes in whoever the water brings | **The current.** One flooded hall crossed by soul-sand up-columns and plain water fall-channels. There are no switches: you read the flow, pick which column to enter and when, and the wrong one returns you to the door's landing. | ride / time an entry | **2.** A swimmer on the first island the current delivers you to — its only exit is past her; a lifeguard at the top landing where you climb out of the last column. | **Free** + `no_build` | one block pack (the water shape is blocks, not heightmap: it is inside a building), one data record, two trainers. |
| 3 | **Surge** — the signal town that keeps the power and the relays running | **The breaker board.** Six copper line segments run across the floor and up the wall to the door lamp; four breakers each feed two of them, and the wiring is drawn on the floor in copper. Trace the lines, find the one setting that lights the whole run. | trace and complete a circuit | **2.** A lineman on the catwalk between the board and the generator, the only crossing of the floor trench; a second at the door threshold, passed on the way through once it is lit. | **Free** + `no_build` | one block pack (the wiring is a build), one data record, two trainers. |
| 4 | **Erika** — Peak Pond Hollow's mediator between residents and arrivals | **The trellis dials.** Four item frames on the glasshouse trellis, one per flowerbed; each must be turned to the direction that bed actually drains, which you see by looking at the bed's slope and its standing water. Comparators read the rotations; the hedge gate opens on all four. | observe terrain, then set a dial to match | **2.** A gardener in the single gap in the hedge between the two halves of the garden — the route has no other crossing; a second on the path between the last dial and the gate. | **Free** (item frame + comparator) + `no_build`; **one ASSUMED behaviour**: that adventure mode permits rotating an item frame (section 7) | one block pack, one data record, two trainers. |
| 5 | **Koga** — the fen-edge watch town whose trackers read the marsh | **The quiet crossing.** A dark hall of calibrated sculk sensors; step or sprint in range and the alarm shuts the far gate and walks you back. You cross by reading which route is carpeted (carpet muffles), by crouching where it is not, and by the tracker's board of cast prints, which shows where feet may fall. | move unseen | **3.** A tracker at each end of the sensor field's only crossing — passed going in and coming out; a third on the balcony above the field, on the route to the alarm reset. | **Free** (sensors, carpet, a vanilla self-resetting gate) + `no_build` | one block pack, one data record, three trainers. **Check first:** carpet/wool are spawn conditions and were stripped from the mansion and the Route 1-3 sites (`docs/STATE.md:46`); inside a gym's suppression box they are safe, but the box must cover the room (section 6). |
| 6 | **Sabrina** — the region's place of study, recording what the Rift does to memory and perception | **Four doors, one true.** Three chambers; each has four identical doorways and only one lets *you* through. The other three push you back with a message; which one is true is shown by **particles only you can see**, and it changes each time you are turned back. Two players standing side by side are sent through different doors. | trust your own eyes, not your partner's | **3.** A psychic in the middle of each chamber, at its only choke point between the entry vestibule and the four doors. | **Cheap** — the scene runtime, unchanged: `push` (`tools/scenes_pack.py:369-374`), `particles` with `force @s` (`:406-412`), zones (`:329-350`), all keyed on `quest.gym6_interior.*` fields | no new code. One scene record, three quest fields, three trainers, one block pack for the rooms. **Needs a vestibule deeper than a sprinting player covers in the cycle's 1 s** (`tools/scenes_pack.py:58`). |
| 7 | **Blaine** — the crater-rim research town studying the cone's energy | **The vent's rhythm.** A gallery of retracting basalt bridges driven by a clock the player cannot reach. Each fumarole puffs a fixed count before its bridge withdraws; watch one full cycle from the lip, then cross three bridges in sequence. A miss drops you into a cooled ash pit with a stair back to the lip — never into lava. | time a moving route | **3.** A researcher at the near lip, passed before the first bridge; one on the mid island between bridges 2 and 3, the island's only exit; one at the sample rack past the last bridge. | **Free** (observer/dropper clocks, pistons) + `no_build` | one block pack, one data record, three trainers. |
| 8 | **Giovanni** — the southern garrison holding the last gate before Victory Road | **The drill.** Four sectors, each with a shutter, and a klaxon that starts a countdown. Three sectors are breached — which three is shown by the smoke and rubble in them, and it is drawn fresh each run by a vanilla randomiser — and you must close those three and leave the fourth open as the way out before the count ends. Wrong, and the shutters reopen and the drill restarts. | triage under a clock | **4.** A garrison trainer in the muster hall at the door, before the drill can start; one inside each of two sectors, between the sector mouth and its shutter; one at the command post past the last shutter. | **Free** for the shutters, the clock and the dropper randomiser; **new wiring** only if the reset is done as a function rather than as vanilla redstone | one block pack, one data record, four trainers, and the only reset machine in the eight. |

**Difficulty curve:** 1 look → 2 time one entry → 3 trace a small logic problem → 4 map four observations onto
four settings → 5 cross under a detector with a movement rule → 6 distrust the room and your partner → 7 time
three moving crossings in sequence → 8 read four rooms and act on three of them before a clock runs out.
Trainer counts rise with it: 2, 2, 2, 2, 3, 3, 3, 4 — 21 gym trainers, none of which exists yet
(`docs/STATE.md:30` counts 63 trainer records today, all route, mansion or boss).

**Every one of these needs floor space the 27·17·24 shell does not obviously have.** Under route A+C, the shell
holds the entry hall and the leader's room, and rooms 1-3 of each puzzle are cut below the lot. Misty's own
36·40·32 building is the exception: it is 40 tall, so her current can climb inside it (VERIFIED size, ASSUMED
that the interior is open enough — see section 7).

---

## 5. Multiplayer, answered explicitly

**The question: two players in a gym at once; one solving the puzzle for the other; does a solved puzzle stay
solved?**

**The hard fact first.** Blocks are shared world state. Minecraft has no per-player block without a client mod,
and this repository has no mechanism that makes one. So **every puzzle in the free tier (1, 2, 3, 4, 5, 7, 8) is
shared: one player can and will solve it for the other, and it stays solved until something resets it.** Only
gym 6 is per-player, and only because it is built out of the per-player machinery rather than out of blocks.

**Grounded in how this repository already splits state:**

- shared world state: the crushed house, `data/progression.json:461-465`, `"scope": "world"`;
- per player: dialogue cursors and rewards (`docs/STATE.md:65-66, 82`), the Gastly escort — "each player owns and
  advances an independent Gastly escort; there is no shared-party quest state" (`docs/STATE.md:79`), and the
  ballroom barrier (`data/scenes.json:691-728`);
- per player and already correct for gyms: the badge itself is an advancement on rctmod's `defeat_count`,
  proven on `cobblers-dryrun4` that beating Brock set `gym1_cleared` and nothing else (`docs/STATE.md:125`).

**The three contracts a puzzle can take, and what each costs:**

| Contract | What a player sees | Machinery | Cost |
| --- | --- | --- | --- |
| **shared, permanent** | the second player walks into an open gym; a late joiner never sees the puzzle | none beyond the blocks | free, and it throws the content away for everyone but the first player |
| **shared, resets when the room empties** (recommended default) | everyone solves it; nobody is locked out mid-solve; a returning player finds it shut again | one `minecraft:location` advancement on the interior box + a tick check for "no player inside" + one reset function per gym (**new wiring**, item 2 of section 2.3) | ~40 generated lines per gym, one audit; the reset must require the box empty, so a partner cannot wipe a solve in progress |
| **per player** (gym 6 only) | each player is pushed back at their own doorway; solving it for someone else is impossible | scene `push` + `particles` + zones, all existing (`tools/scenes_pack.py:352-379`) | no new code; one quest field per door, a 1 s latency and a vestibule per doorway. Doing this in all eight would multiply fields and barriers for no gain |

**Recommendation.** Shared-with-reset-on-empty for gyms 1-5, 7 and 8; per-player for gym 6, where it is the
theme. The group's real gate is the leader battle, which is already per-player and already proven.

**And one more rule, because it is a speedrun and nuzlocke goal** (`docs/vision/GAME_VISION.md:158-174`): **a
player who already holds that gym's badge passes every door of that gym.** Otherwise a returning player
re-solves a puzzle to reach a healing machine, and that is backtracking a waystone cannot cover. This is one
extra condition on each door: `flag` = `gym<N>_cleared` (`tools/compile_dialogue.py:152-158` for the
quest-field doors, `tools/gulch_mine.py:1180-1181` for the flag doors).

**What breaks if a player leaves mid-dungeon** (`GAME_VISION.md:149-151` requires the answer): the shared
circuit is untouched and resets when the last player leaves; the per-player state is in Cobblemon player data
and survives logout, death and restart by construction (`tools/compile_dialogue.py:12-14`); a scene actor
vanishes when its owner leaves the area and returns where their state says (`tools/scenes_pack.py:12-16`).

### `data/system_contracts.json` — yes, a new system and five contracts

A new system `gym_interiors` (paths: `data/gym_interiors.json`, its generator, this document), with:

| id | Statement | Owner → consumer |
| --- | --- | --- |
| G1 | Every gym room, including every cut room, lies inside that gym's `data/spawn_suppression.json` box in x/z, so no puzzle block draws a wild Pokemon into a gym | `wild_spawns` → `gym_interiors` |
| G2 | No gym route requires more than a few seconds submerged, so no gym crossing can be affected by the air ladder or swim fatigue | `gym_interiors`, constrained by `water_ladder`, `swim_fatigue` |
| G3 | No gym route can kill a player or cost them a blackout charge: every fall lands in a walk-back, never in lava or a drop that kills | `gym_interiors` → `blackout_checkpoints`, `recovery_claims` |
| G4 | Every gym interior box is a `no_build` box, so no puzzle can be dug through or built over | `gym_interiors`, constrained by `world_block_packs` |
| G5 | A player holding that gym's badge flag passes every door in that gym | `progression` → `gym_interiors` |

The fields and the enforcement pattern are `data/system_contracts.json:5-12` and its `tests/test_system_contracts.py`.

---

## 6. The data model, and what validates it

One new authored file, `data/gym_interiors.json`, schema `cobblers.gym-interiors/1`. Nothing about the building
is re-authored: the shell's position, size and rotation are **derived** from `data/placements.json`'s donor
record, never copied (the measured-record rule, `docs/STATE.md:93`).

```
gyms[]
  id                  "gym1" … "gym8"
  settlement          → data/placements.json
  donor               the donor record id (gym1_brock_gym …); shell geometry is read from it
  entrance            [x, y, z] inside the shell where the route starts
  dig                 boxes cut below the lot, or null (Misty: null, her building is 40 tall)
  rooms[]             {id, box, role: "hall"|"puzzle"|"guard"|"leader", why}
  route[]             ordered waypoints through the rooms: the line a player must walk
  mechanism           {tier: "free"|"cheap"|"new_wiring", kind, what_the_player_sees}
  state_scope         "shared_reset_on_empty" | "per_player" | "shared_permanent"
  reset               {box, trigger, function} when state_scope is shared_reset_on_empty
  doors[]             {id, at, opens_on: {flag|field|block_state}, vestibule_depth}
  trainers[]          {id, seat, yaw, sight_distance, room, passed_at: route index, why_unavoidable}
  leader              {id, room, seat_from: "template spawner" | authored}
  no_build[]          boxes handed to the scene runtime
  blocks[]            every block id the generator may write (the town_dressing pattern)
```

Checks for `tools/validate_data.py` (written by `test-author`, not by whoever builds the gyms — CLAUDE.md,
"Content implementation and its test/review use different agents"):

1. every room box lies inside the gym's `data/spawn_suppression.json` box in x/z (contract G1), and inside the
   shell or the dig;
2. every trainer seat lies in a room, is standable, and its `sight_distance` reaches **no standable cell outside
   its own room** — the mansion rule, `data/mansion_guardians.json:4`; this needs the interior model, so it can
   only run once the floor plan exists;
3. the route passes within a stated distance of every trainer seat, so "a player must pass them" is machine
   checked rather than asserted;
4. no block in `blocks[]` is a spawn condition (`data/spawn_blocks.json`), as `tests/test_town_dressing.py`
   already does for the dressing (`docs/STATE.md:130`);
5. every `no_build` box covers every room (contract G4);
6. every per-player door names a field declared in `data/progression.json` `quest_fields`, under
   `quest.gym<N>_interior.<field>` (the reserved namespace, `docs/STATE.md:78`);
7. every door has `opens_on` including that gym's badge flag (contract G5);
8. every gym has a `state_scope`, and a shared one has a `reset` box;
9. every vestibule is deeper than the stated sprint margin (section 2, the 1 s cycle).

Plus an offline audit in the generator's own tool (`tools/gym_interiors_audit.py`), the pattern every block pack
here already follows: replay the written functions and compare against the plan, refuse at `prepare` on a
failure (`docs/STATE.md:46`, `tools/gulch_mine_audit.py`, `tools/shrines_audit.py`).

---

## 7. Not covered, and what needs an experiment

**Not covered by this document:** the leaders' rosters and levels (paused, `docs/STATE.md:152`); gym rewards and
the TM farming question (`docs/STATE.md:126`); Giovanni's doubles format (`docs/story/GIOVANNI_FORMAT.md`); the
League's interior; the gyms' dialogue and the leaders' characters (Codex); anything about the gym *towns* above
ground.

**Open questions, each a named measurement I could not make (no shell):**

| # | Question | How to settle it |
| --- | --- | --- |
| Q1 | **The interior floor plan of the eight templates.** Everything in section 4 assumes the hall has room for a stairhead and that Misty's 40-tall building is open inside. | Section 1's command block: extract the NBTs locally, `python tools/structure_nbt.py info <file>` for sizes, then a y-slice dump from `structure_nbt.load()` (`tools/structure_nbt.py:138-144`). **Blocks the whole design.** |
| Q2 | **Where the leader stands, and whether the placed leader comes from the template's `rctmod:trainer_spawner`** (`STRUCTURE_INVENTORY.md:89-93`). | Same read, plus one RCON look at a standing gym on staging under the lock. |
| Q3 | **Brock's pressure plate and 9 command blocks** (`STRUCTURE_INVENTORY.md:101`): are they on the route? | Same read. Fix, if needed, is a donor substitution (`data/placements.json:7389-7395` is the precedent). |
| Q4 | **Does adventure mode permit rotating an item frame, and using levers and buttons?** Erika's dials, Surge's breakers and Giovanni's shutters all depend on it. Vanilla says yes; **this pack has not been checked.** | Two minutes on staging inside a `no_build` box: rotate a frame, flip a lever, press a button. |
| Q5 | **How deep must a vestibule be** against the 1 s cycle (`tools/scenes_pack.py:58`) and the ~20-tick location trigger (`tools/gulch_mine.py:1357`), for a sprinting player? | Staging: sprint at a `push` box and measure the overrun. Sabrina's gym is unbuildable without the number. |
| Q6 | **Two players in a scene at once.** The whole scene runtime has never had two players in it (EXP-034, `docs/STATE.md:44, 211`); nothing has been clicked in game. | EXP-034, with the owner and a second player. **This gates gym 6 entirely.** |
| Q7 | **The mixed-progress rematch** (section 3, item 1): does a beaten player get pulled into a rematch while their partner fights? | Staging, two players, one placed trainer. |
| Q8 | **Carpet and wool inside a suppression box** (Koga): safe, or still a spawn condition somewhere the box does not cover? | `data/spawn_blocks.json` and `data/spawn_block_policy.json`, then the validator check 4 above. |
| Q9 | **Does a cut room under a levelled gym lot survive a re-export**, and does its re-application step fit the driver's 80 jobs? | A `reapply.py` step and a staging rehearsal, as every other block pack has had. |

**The experiment to run first** is `EXP-005 Puzzle dungeon` — planned, never run, "three states and sealed reward"
(`docs/research/EXPERIMENT_BACKLOG.md:13`). Its subject should be **gym 1's interior**: the cheapest puzzle, the
free tier, the shared reset, two trainers, one block pack, in a building that already stands. If gym 1 does not
survive a playtest and a two-player run, none of the other seven should be built. Principle 20.

---

## 8. Plan

Each step is one task, small enough to be a single experiment or content unit.

| # | Step | Agent | Writes |
| --- | --- | --- | --- |
| 1 | Read the eight gym templates' NBT: floor plans, the spawner's position, Brock's plate and command blocks (Q1-Q3). Needs a shell and the local pack. | `dependency-auditor` (pack metadata is its beat), or the main session | `docs/research/notes/cobbleverse-gym-interiors.md` |
| 2 | In-game mechanism checks Q4, Q5, Q7 on staging, under the lock, with the owner. Twenty minutes, one session. | main session | `experiments/EXP-005-*/` |
| 3 | EXP-034 with two players: the scene runtime clicked, and two players in one scene (Q6). | main session with the owner | `experiments/EXP-034-*/` |
| 4 | Accept or reject the A+C route and the puzzle list, with the plans in hand. If accepted, an ADR (this constrains every gym and is expensive to reverse). | `content-architect` proposes; **the owner accepts** | `docs/decisions/ADR-00N-gym-interiors.md` (status Proposed) |
| 5 | Author `data/gym_interiors.json` for gym 1 only: rooms, route, doors, no_build, blocks, two trainer seats. | `world-content-dev` | `data/` |
| 6 | The generator and its offline audit; the `reapply.py` step; the shared reset wiring. | `datapack-content-dev` | `tools/`, `data/` |
| 7 | The validator checks and the contract tests (G1-G5). Different agent from step 6. | `test-author` | `tools/validate_data.py`, `tests/`, `data/system_contracts.json` |
| 8 | Gym 1's two trainers: rosters, levels against the cap curve, dialogue lines. | `trainer-balance-designer` | `data/` |
| 9 | Build on staging, playtest gym 1 with two players, grade against EXP-005's criteria. | main session, then `qa-reviewer` | reports only |
| 10 | Only then, gyms 2-8, one at a time, each its own unit. | as steps 5-9 | |

Steps 1-3 are cheap and settle everything. **No gym content should be authored before step 4.**

---

## Q1 ANSWERED (2026-09-29): the real interiors, measured from the templates

Read from `COBBLEVERSE-DP-v31.zip`'s `data/cobbleverse/structure/<leader>.nbt` in memory, never extracted into the
repo and never scanned from a world (CLAUDE.md's ground rule). **The block maps are not committed**: the templates are
no-redistribution, so only measurements live here. The maps were produced locally and handed to the owner.

Method: the interior floor is the y with the most *roofed standable* cells (passable at y and y+1, solid at y-1, and
some solid above). A naive "densest floor" heuristic is wrong for Misty, whose gym is built into a rock mass and whose
densest level is the stone itself.

| leader | envelope (x,y,z) | interior floor y | standable roofed cells |
|---|---|---|---|
| brock | 27x17x24 | 2 | 222 |
| misty | 36x40x32 | 26 | 158 |
| ltsurge | 27x17x23 | 2 | 226 |
| erika | 27x17x23 | 2 | 160 |
| koga | 27x17x24 | 2 | 199 |
| sabrina | 27x17x24 | 2 | 248 |
| blaine | 27x17x23 | 2 | 238 |
| giovanni | 27x17x24 | 2 | 226 |

**Correction to this document's opening claim.** It says seven of the eight gyms are "the same building recoloured",
citing the inventory and the footprints. At the level of geometry that is **not true**: every one of the eight has a
distinct solid shape (eight different sha256 of the solid-cell set; 1,772 to 1,899 solid cells). They share an
envelope and a family resemblance, not a shell.

**What is true, and is the real finding:** every gym, Misty's included, is **one oval chamber** — an entrance at one
end, the healing machine and a chest at the other, the `rctmod:trainer_spawner` in the middle, and 160 to 248
standable cells of undivided floor. Misty's is the same room, only larger and set higher inside a rock body. So the
owner's complaint holds exactly, and each gym has its own outline to design against rather than one generic room.

Consequences for the design above:
- **There is no second storey to reuse.** Every interior is a single level; upper volume is roof.
- **The puzzle rooms must be carved below**, as this document already proposes, because the shells have no spare
  interior to subdivide without touching the template.
- **Per-gym outlines differ**, so a single generic room plan will not drop into all seven. Each needs its own fit.
- Brock's template really does carry the 9 command blocks and a pressure plate (7 chain + 2 command, 1 light weighted
  plate), confirming Q3.
- Notable per gym: Surge 9 dark-oak trapdoors and a yellow gilded chest; Koga 8 crimson trapdoors and a green gilded
  chest; Blaine 2 lava cauldrons; Giovanni 2 iron doors and **no barrel**; Misty 147 water blocks, 3 water-stone ores
  and a blue gilded chest; Brock a deepslate water-stone ore and 6 apricorn trapdoors.

Still open from the original list: Q2 (where the leader stands / whether the spawner places him) is partly answered —
there is exactly one `rctmod:trainer_spawner` per template — but its position relative to the door is not yet
measured against each room's route. Q4 to Q9 are unchanged.
