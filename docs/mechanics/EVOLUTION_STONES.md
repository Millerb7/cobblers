# Evolution stones: where they come from, and the face that resets

**Status: proposed design, 2026-09-23. Nothing is implemented and nothing is placed.** The
mechanism it proposes is an ADR (`docs/decisions/ADR-003-evolution-stone-supply.md`, Proposed);
accepting it is the owner's call. Every claim below is labelled VERIFIED (a file, a line, an
experiment) or ASSUMED (design judgement or mainline knowledge). The runtime questions are
listed at the end as experiment candidates; **none of them has been run.**

This document answers five mechanical questions the owner posed — shared or per-player, ore or
loot, the reset, the strip-mine bound, and the rate — and one design question: which towns are
known for a stone. It does not author content.

---

## 1. The gap, in one paragraph

**VERIFIED** a WorldPainter export writes every chunk as already generated, so none of
Cobblemon 1.8.0's 42 evolution-stone ore features ever runs
(`docs/world-building/WORLDGEN_FEATURES.md:5-9, 25`). **VERIFIED** the Nether still generates
normally, so `cobblemon:nether_fire_stone_ore` is the only stone ore in the game, and Fire Stone
is the one stone with no consumer at all in the placed rosters
(`docs/mechanics/SPAWN_PHILOSOPHY.md:271-286, 347`). **VERIFIED by count on `data/spawns.json`**
20 rostered families are gated on one of the ten stones and 10 more on another item
(`SPAWN_PHILOSOPHY.md:316-353`). **Owner-supplied, from a jar read in another session and not
yet filed in `docs/research/`:** all 66 evolution-stone recipes in the 1.8 jar take ore,
deepslate ore, or the stone's own compressed block as input — not one takes ordinary materials.
That closes the question `SPAWN_PHILOSOPHY.md:387-391` left open ("**UNKNOWN** what those
recipes take as input … this single question decides whether GAP 1 is a blocker or a note"): it
is a blocker. **Without a deliberate source, 20 rostered families cannot be completed at all.**

That jar read should be filed as a research note by `cobblemon-researcher` and cited from
`SPAWN_PHILOSOPHY.md:377-404`; this document treats it as given because the owner states it as
established, not because the repository proves it.

**VERIFIED** the 23 ore blocks exist and are registered, and their ids are readable
(`base-pack/cobbleverse/config/roughlyenoughitems/collapsible.json5:139-161`): ten
`cobblemon:<stone>_stone_ore`, ten `deepslate_<stone>_stone_ore`, plus
`dripstone_moon_stone_ore`, `terracotta_sun_stone_ore` and `nether_fire_stone_ore`.
**VERIFIED (EXP-017 A1)** the features' own replace rules confirm those three host rocks are
deliberate: sun stone alone also replaces `#minecraft:terracotta`, moon stone alone has a
dripstone feature at count 256, fire stone alone has a netherrack feature
(`experiments/EXP-017-ore-pockets-and-object-load/README.md:85-88`). Cobblemon has already
decided that three of the ten stones want particular geology. The design below follows that.

---

## 2. The fiction: worldshift residue

The owner's premise, fixed: evolution stones appeared in this region recently, nobody knows why,
and the explanation the *world* eventually offers is worldshift residue — matter from elsewhere
pushed up through the ground. The region itself knows only that the ground started giving up
strange stones, and some towns grew around working them.

The term is already in the repository: the Displaced City is "a summit town moved by the
Worldshift" and Relic Island is "the F4 worldshift fragment"
(`docs/world-building/SETTLEMENTS.md:108, 188`). Nothing new is being coined.

**Four constraints keep this from colliding with `docs/story/ARC.md`.** They are hard; content
that breaks one is wrong.

1. **No stone site may deliver a required fact.** ARC narrative rule 7: "Optional places deepen
   or challenge the required account but never supply a fact needed to reach the next gym"
   (`ARC.md:69-70`). Every site below is off the critical path, and the reveal ladder
   (`ARC.md:681-693`) is untouched: Brock still delivers "Pallet replaced a native settlement",
   Surge still delivers "exchanges can be triggered and steered", Erika still delivers "every
   rescue exchange displaces something".
2. **Miners have no theory.** A miner may say the ground changed, that the seams are not in the
   rock the way ore is, that nobody's grandfather cut a stone. No NPC at a mine may connect
   stones to exchanges, to the Haven Compact, or to Hoopa before the required beat that earns
   it. This is the same epistemic stance ARC already gives Pallet: "Residents offer incompatible
   interpretations in short, uncertain fragments" (`ARC.md:184-186`).
3. **"Recently" means a generation, not a year.** A town cannot grow around working a stone that
   appeared last spring. ASSUMED and proposed: the first finds are roughly fifteen to twenty
   years old — before Pallet arrived, and contemporary with the earlier city-scale exchange that
   Erika's survey records establish (`ARC.md:381-387`). This is not a coincidence the player is
   told about; it is a coincidence a player can notice. It also explains the trade: long enough
   for a cutting to become a livelihood, not long enough for an industry.
4. **The Haven Compact did not make them and must not be said to.** The Compact's crews may find
   the stones interesting — they are physical evidence of exchange — which is a free hook for
   later optional content. Nothing in this design requires it, and ARC's villain identity
   (`ARC.md:138-142`) is untouched.

The two strongest fiction sites fall out of this by themselves. **The Scar** is the bared summit
where the Displaced City stood (`SETTLEMENTS.md:189`); **the Displaced City** is where that
summit went (`SETTLEMENTS.md:107-133`). If the residue is real anywhere, it is at both ends of a
completed exchange, and a player who visits both without ever being told anything has been shown
the premise.

---

## 3. Where the stones are, and why one town per stone is wrong

### 3.1 The recommendation

**Reject one town per stone.** Ten mining towns would consume every non-gym place on the map,
including four rest stops and three outposts with no services, and overwrite identities
`SETTLEMENTS.md` deliberately gave them: a harbour, a weather observatory, a tea town. It would
also make the map legible in the worst way — a commodity grid where every settlement answers the
same question. And it costs ten build sites, ten re-apply steps and ten reset loops for a system
worth perhaps two hours of play across a campaign (§7).

**Recommended: seven sites, ten stones, five readings.** Assignment is by three criteria in
order: (a) reachability in campaign order, because the families are useless once earned too
late; (b) the host rock Cobblemon itself implies; (c) the identity the place already has.

| Stone | Families gated | Site | Kind | Reachable | Why here |
| --- | ---: | --- | --- | --- | --- |
| **Water** | 4 | **Viltri Light** (550, 4518) | raw exposure | `route_01`, 40% along, 840 off | A sea-cliff cut under the lighthouse over an estuary no river uses any more. Water stones where the water left: the outpost currently gives a player nothing to do |
| **Leaf** | 1 | **Tea town** (2654, 3605) | worked | `route_02`, 13% along, 891 off | The terrace cuttings. The only cherry-grove country on the map |
| **Shiny** | 3 | **Tea town** | worked | as above | The polished stone the tea houses face their walls with. Second seam, same quarry |
| **Sun** | 4 | **The Scar** (2110, 950) | raw exposure | `route_04`, 27% along, 437 off | A summit scraped flat and open to the sky, where the city was taken. Nobody lives there; you chip what is exposed. **Terracotta host** is Cobblemon's own (EXP-017 A1) |
| **Moon** | 2 | **The Displaced City** (2969, 1710) | city working | `route_04`, 57% along, 287 off | A city living under rock with no sun. **Dripstone host** is Cobblemon's own |
| **Ice** | 2 | **Northlight** (7265, 1556) | worked | `route_06`, 80% along, 2,106 off | The only snowy islands; an ice-type field station already |
| **Dusk** | 2 | **Gorge hamlet** (6814, 4367) | worked | `route_07`, 60% along, 283 off | The Tilpey outflow gorge cut the seam open; the bridge-keepers work both walls |
| **Dawn** | 1 | **Gorge hamlet** | worked | as above | The east wall. Dusk and dawn, one gorge, two faces |
| **Thunder** | 1 | **Mining Town** (6633, 5716) | worked, deep | `route_08`, 3% along, 905 off | The deep workings |
| **Fire** | 0 | **Mining Town** | worked, thermal | as above | The thermal adit into the eastern cone. `#cobblemon:is_volcanic` and `is_thermal` are painted only here (`SETTLEMENTS.md:98-104`) |

Distances and legs are **VERIFIED** from `data/towns.json` (`distance_from_critical_path_blocks`
and `nearest_leg`, lines 1234-2175). Note that `SETTLEMENTS.md:63` still records Sunset West at
2,021 blocks off path while `data/towns.json:1234` now records 935 against `victory_road` at
fraction 0.0; the town was re-sited (`docs/STATE.md`, "Towns") and the prose is stale. The data
wins, and that is a finding for `world-content-dev`, not something to paper over.

### 3.2 The Mining Town anchors it, but not by holding the most stones

The owner's instinct that the mining town anchors this is right, and it is right for a reason
that is not "it has the most faces". The Mining Town is **the only place that works stone as an
industry** — mine head, ore rail, smelter, fossil lab (`data/towns.json:1348`) — so it is:

- the only site with more than one working level, and the only one whose faces are *inside* a
  real mine rather than cut into a cliff;
- the clearing house in fiction: every stone passes through here, which is where "the rest are
  traded on" lives, and the natural home for badge-gated trader stock when that lands
  (`docs/STATE.md`, "Encounter data"/traders);
- where the mechanic is explained rather than discovered, for the player who reached gym 7
  without ever finding a seam.

What it is not is the place a player learns this early, because it is 905 blocks off leg 8. That
is why Water and Shiny — seven of the twenty families between them — are at Viltri Light and tea
town, reachable after gym 0 and gym 1. **Twelve of the twenty stone-gated families are served
before gym 5; all twenty before gym 8.** That matters because `docs/STATE.md` already records
early-route availability as the lever for the starter spread, and half of these families are
mid-tier answers a weak starter needs.

### 3.3 The alternatives, and why not

- **Shiny at Relic Island instead of tea town.** Fiction-strongest option on the map: a torn-off
  islet from Pallet's arrival, 440 blocks from the hometown, where the residue glitters along
  the tear. Rejected on space, not on merit — the islet's dry core is 20 blocks square
  (`docs/STATE.md`, "Relic Island footprint") and a 9×5×6 face plus its backing is most of it.
  If the owner prefers the image to the clearance, this is the one swap worth making.
- **Water at Sunset West.** The obvious home for the water stone, and wrong: Sunset West is the
  harbour, and by route it is not reached until Giovanni. Four families would arrive at gym 8.
- **Sun at the Tableland stop.** Terracotta country and a prospector's house already
  (`SETTLEMENTS.md:171-172`) — the best host-rock fit on the map. Rejected only because it sits
  at 53% of leg 8, and Sun gates four families. If the Scar proves unbuildable as an exposure,
  this is the fallback and the fiction still works (a prospector who found the seam).
- **Two stones at one place, three times.** Accepted deliberately at tea town, the gorge hamlet
  and the Mining Town, because ten single-stone towns is the failure mode we are avoiding. A
  place known for two stones still reads as a place known for its stone.

---

## 4. The mechanic: a face that resets

### 4.1 The rung, and what it is not

Under `CLAUDE.md` principle 6 this lands at **functions and commands (rung 7)**, with the ore
blocks and their drops at **Cobblemon native (rung 1)** and nothing above rung 7 used at all.

- **Rung 1, native, does the real work.** The ore blocks exist and are registered
  (`collapsible.json5:139-161`); breaking one uses Cobblemon's own block loot table; crafting a
  stone uses Cobblemon's own recipes. We supply position, not behaviour.
- **Rung 2, a compatible addon:** no mod in the installed set is *recorded* in `docs/research/`
  as providing a resettable resource node. That is an absence of evidence, not a disproof; if
  the owner wants it ruled out properly it is a question for `cobblemon-researcher`, not a
  reason to build.
- **Rung 5, datapack alone:** cannot express "put these blocks back on a timer". A loot table
  can express what a container holds; it cannot express rock.
- **Rungs 8-10 (scripting, companion, custom mod): not needed and not proposed.**

The proven shape is already in this repository: a generated `.mcfunction`, re-applied by a
`tools/reapply.py` step (`tools/rift_deep.py`, `tools/habitat_blocks.py`,
`tools/reapply.py:267-311`), and self-driving packs whose own `load`/`tick` tags run them
(`tools/reapply.py:70-72`).

### 4.2 Shared or per-player — and the answer to the question under it

**The honest form of this question: with the mechanisms this project has, "ore in the rock" and
"per-player" are mutually exclusive.** A block is world state. The only durable per-player state
available is player data — advancements and Cobblemon quest fields — which ADR-002 establishes
as the reward spine precisely because a re-export replaces region files while
`tools/carry_players.py:65-75` carries player state
(`docs/decisions/ADR-002-reward-delivery-mechanism.md:52-59`). There is no server-side
per-player block view without a mod.

So the choice is:

| Option | Cost | Verdict |
| --- | --- | --- |
| **A. Shared face, resets** | First-come within a cycle. Player-placed blocks inside the box are destroyed on reset. Needs the occupancy guard (§4.4) so nobody is filled in | **Recommended** |
| **B. N faces instanced per player** | Player count is not fixed; a late joiner has no instance; N× the build, N× the reset, and a player still sees another player's rock. ADR-002 already rejected the same shape for caches (`ADR-002:132-133`) | Rejected |
| **C. Per-player grant at the face (ADR-002 spine)** | Per-player and once-only by construction, and it cannot be repeated — an advancement has no second grant (`ADR-002:196-198`). It is also not mining: the rock becomes a button | Rejected as the mechanism, **kept as the floor** |
| **D. Ore drops nothing; a trigger grants the stone** | C in costume, with the same objection and a worse lie | Rejected |

**Recommended: A with C as a floor.** The face is shared and resets; *additionally*, each site
grants one stone of its type, once, per player, on first arrival, by exactly the mechanism
ADR-002 proposes — a `minecraft:location` advancement with a reward function that runs as the
earning player. That costs one new record per site and no new mechanism, and it buys the thing a
shared resource cannot give: **a player who arrives second is never empty-handed.** It is also
the teaching moment — the stone appears with a toast, and the seam in the wall explains where it
came from.

Its dependency is stated plainly: **the ADR-002 proof gates the floor, not the face.** If the
two-player advancement proof (`ADR-002:144-174`) fails, the faces still work and the floor is
dropped.

**Why first-come is tolerable here in a way it is not for a cache.** ADR-002's objection is to a
mechanism whose answer to "two players arrive" is "the first one takes it"
(`ADR-002:43-46`) — a one-shot container. A face that refills in ten minutes answers "the second
one waits a few minutes, or mines the next face along". And the demand it serves is small and
bounded (§7): nobody needs a hundred Water Stones.

### 4.3 Ore in the rock, or a loot mechanism

**Ore in the rock.** The owner is right that it is the only version that feels like mining, and
here it is also the cheapest: the ore block already exists, already drops through Cobblemon's
own loot table, and needs no datapack from us at all. A loot mechanism would need a table, a
container, a placement, a restock, and it would be shared and random on first open
(`ADR-002:108-117`) — worse on every axis including fiction.

The cost of ore in the rock is exactly the two things the rest of this section handles: it is
shared (§4.2) and it is finite unless it resets (§4.4).

One consequence worth naming: **a face is also ordinary ore.** Coal, iron, copper and the
occasional diamond in the same rock make it read as a mine rather than a vending machine, and
they do one more job in §4.6.

### 4.4 The reset

**Shape.** One generated pack, `cobblers_mines`, from one tool, `tools/mines.py`, from one
record file, `data/mines.json`.

- `build_<site>` — the gallery or cut, its lighting, its backing and its bedrock skin. Runs once
  per export, from a re-apply step.
- `reset_<face>_v<k>` — for each face, **k authored variants** (recommend 8), each a `fill` of
  the box back to host rock followed by the variant's `setblock`s for ore and filler.
- `mines/tick` — the driver.

**Budget per reset.** A 9 × 5 × 6 face is 270 blocks: one or two `fill`s (well under the 32,768
block limit `tools/function_limits.py` enforces) plus 3-7 `setblock`s. Call it **under 12
commands and 270 block writes per face per reset**. For comparison the Rift skin is 1,647,987
commands in one pass (`docs/STATE.md`, "The Rift overhaul"). This is noise.

**Budget per tick.** The driver runs on a `schedule` at a 5-second cadence, not every tick: it
increments one fake-player score per face and compares it with the face's period. Twenty faces is
roughly 40 commands every 100 ticks. ASSUMED and to be verified: that `schedule function <id>
<t> replace` is idempotent when re-armed by the pack's `minecraft:load` tag, so a restart cannot
double-arm it. The fallback if it is not is a `minecraft:tick` tag function with the same score
logic, which is the pattern `cobblers_progression` and `cobblers_sizes` already use
(`tools/reapply.py:70-71`).

**The occupancy guard is mandatory.** A reset runs only if no player is inside the box:
`execute unless entity @a[x=…,dx=…,y=…,dy=…,z=…,dz=…] run function …`. If a player is inside,
the timer stays at its threshold and the face resets on the next cadence after they leave.
Filling stone into a player is a bug, and a face that resets while its miner is working it is
worse than one that never resets.

**Variants and scatter.** Runtime randomness is nearly pointless here: ore inside rock is
invisible until it is exposed, so a player cannot memorise a layout they never see whole. The
variants exist so that a player who *does* clear the whole box twice does not find the same
sixteen blocks. **Recommend deterministic rotation** — variant index = reset counter modulo k —
because it needs no unverified command, with the generator producing the scatter from a per-face
seed. `random value` (1.20.2+) is an upgrade, not a requirement, and is ASSUMED until someone
runs it.

**Re-export survival.** The whole thing is generated from `data/mines.json`, so it survives by
construction — which is the only way anything survives here. Concretely it needs **a new
`tools/reapply.py` step**, because `prepare` now fails closed on a generated pack that no step
runs (`tools/reapply.py:155-163`), and because five builds were silently missing exactly this
(`docs/STATE.md`, "The re-export was reported as rehearsed end to end…"). Ordering:

- **after R9 (pack donors)**, because the tea town, Northlight, gorge hamlet and Mining Town
  faces sit inside or beside town plans and a donor is stamped whole and would erase them —
  the same reason the lights are R16 (`tools/reapply.py:301-303`);
- **after R2 (the cavern)** for the Displaced City working, which is inside it;
- the Scar and Viltri Light have no ordering constraint beyond the terrain itself.

Recommended id **R17**, run immediately after R16, with the driver re-arming itself from the
pack's `load` tag.

### 4.5 Can a player strip-mine past the face?

Yes, unless it is bounded — and the bound matters more for encounters than for economy.

**The economy answer is that it pays nothing.** VERIFIED: no evolution-stone ore generates
anywhere in the export (`WORLDGEN_FEATURES.md:5-9`). The stone ore exists *only* inside the face
boxes. Digging past a face reaches ordinary rock: the ceiling on a player's yield is the ore in
the boxes whether or not they respect the walls.

**The encounter answer is why it still needs a wall.** VERIFIED and recorded 2026-09-23: the
bounded-suppression pack is not installed and upstream pools are live in unauthored caves;
2,662 spawn files carry 5,850 underground-only spawn details, with Gengar bands at 36-50
(`docs/STATE.md`, "What actually spawns underground in the Rift is the pack's, not ours"). A
gym-2 player who tunnels out of the Viltri Light cut and into a natural cave meets the pack's
underground roster, not ours. So the bound protects the encounter design.

**Four layers, in the order they take effect:**

1. **The face box is closed.** Its far side and both walls are two blocks of host rock, and
   immediately behind that a one-block skin of `minecraft:bedrock`, generated with the gallery.
   Unbreakable in survival, and only ever seen by a player who mines the full depth of a face on
   purpose. This is the same idea as the Displaced City's shell, which turns every void within
   24 blocks of the chamber to rock (`docs/STATE.md`, "Displaced City cavern").
2. **The gallery is shelled, not bedrocked.** Around the walked parts of a worked mine, a rock
   shell in the cavern's style: no bedrock a player can see from a corridor, no open cave mouth,
   no water pocket running in. Bedrock is reserved for the back of a face, where the fiction is
   "the seam ends".
3. **The reset repairs.** Anything a player removes inside the box is back next cycle; anything
   they place inside it is gone next cycle. Say so in the site's reading so it is a rule, not a
   surprise.
4. **The validator refuses overlaps.** No face box may intersect another, a town plan, a street,
   a spawn-suppression zone, a route corridor, or a Habitat Block's range (§6).

A raw exposure (the Scar, Viltri Light) has no gallery: it is a cut in a cliff or a scraped
summit, backed by bedrock two blocks in, with nothing to tunnel into and nowhere to get lost.
That is the cheaper build and the safer one, which is part of why two early sites are exposures.

### 4.6 The Pokémon is flavour, and the pack already supplies it

The owner ruled out a mechanic that depends on a wandering Pokémon, and the design does not need
one: the reset runs on its own schedule and knows nothing about entities except "is a player
standing in the box".

For the association the owner wants — a Rock type seen breaking ground nearby — **the pack
already does this for free**, and it is VERIFIED from measured data rather than assumed.
`data/spawn_blocks.json` records every block a loaded spawn condition names, scanned from the
server's 327 mod jars and 10 datapacks (`data/spawn_blocks.json:1-18`):

| Put this in the face | And Cobblemon/Cobbleverse spawn | Line |
| --- | --- | --- |
| `minecraft:coal_ore` | Rolycoly, Carkol, Coalossal, Torkoal | `:1577-1585` |
| `minecraft:iron_ore` | Aron, Lairon, Aggron, **Geodude (Alolan)**, Golem (Alolan) | `:2027-2035` |
| `minecraft:diamond_ore` | Carbink, Sableye, Glimmet, Glimmora | `:1857-1865` |
| `minecraft:redstone_ore` | Klink, Klang, Klinklang | `:2881-2889` |

All of them are `neededNearbyBlocks` conditions. Filler ore in the face is therefore not
decoration: **it is the spawn rule.** A Geodude beside the iron in the rock, at a face nobody
told it about, is exactly the reading asked for.

Three costs, all real:

- **VERIFIED, and this is a rule not a warning:** a placed template containing a spawn-condition
  block fails `tools/validate_data.py`'s `spawn-blocks` check unless
  `data/spawn_block_policy.json` whitelists it with a `why`
  (`tools/validate_data.py:2583-2637`). Filler ore in a face is a **deliberate encounter** and
  must be whitelisted as one, per site, with its reason. That is the system working.
- The levels will be upstream levels, not ours. Setting a band needs a Habitat Block with
  `replace_spawns`, and **VERIFIED** zero are placed, ranges must not overlap, and a block
  survives a restart but not a re-export (`docs/STATE.md`, "Habitat Blocks"). A mine face is a
  good first customer for that manifest; it is not a prerequisite for the stones.
- **VERIFIED** no `cobblemon:*_stone_ore` block appears anywhere in `data/spawn_blocks.json`
  (searched: zero matches). The stone ores themselves summon nothing. The flavour comes from the
  vanilla filler or from nothing.

---

## 5. Data model

**`data/mines.json`, schema `cobblers.mines/1`.** Owner on the `docs/STATE.md` table:
`datapack-content-dev`, alongside the future `data/events.json`; its validator belongs to
`test-author`. The row is added when the file is created, not after. Nothing below is
implemented.

```jsonc
{
  "schema": "cobblers.mines/1",
  "sites": [{
    "id": "viltri_light_cut",
    "settlement": "viltri_light",          // must exist in data/towns.json
    "kind": "exposure",                    // exposure | worked | city_working
    "stone": "water",                      // one of the ten
    "ore": {"stone": "cobblemon:water_stone_ore",
            "deepslate": "cobblemon:deepslate_water_stone_ore",
            "host": "minecraft:stone"},
    "reading": "prose: what a player sees, and the rule that the face repairs itself",
    "reachable_after": "gym0",             // derived from the leg, recorded for the availability check
    "access": {"entry": [x, y, z], "gallery": null},
    "faces": [{
      "id": "viltri_light_cut_a",
      "box": {"min": [x, y, z], "max": [x, y, z]},
      "backing": {"host_thickness": 2, "skin": "minecraft:bedrock"},
      "reset": {"period_seconds": 600, "offset_seconds": 0, "skip_if_occupied": true},
      "yield": {"ore_min": 2, "ore_max": 4,
                "filler": [{"block": "minecraft:coal_ore", "min": 0, "max": 3}]},
      "variants": 8,
      "seed": 20260923
    }],
    "seed_grant": {                        // ADR-002 spine; optional, and droppable if its proof fails
      "advancement": "cobblers:mine/viltri_light",
      "items": [{"item": "cobblemon:water_stone", "count": 1, "verification": "<jar path of model + lang key>"}]
    },
    "spawn_block_policy": "whitelist entry id that allows this face's filler ore",
    "reapply_step": "R17"
  }]
}
```

**Validation to specify with `test-author`** (contracts, not implementations):

1. Every `settlement` exists in `data/towns.json`; every `stone` is one of the ten; every block
   id is one that exists in the installed set.
2. Every box is inside the world border, and its ground comes from `tools/ground.py` or measured
   plan data — **never from a world save** (`CLAUDE.md`, "Ground comes from the heightmap";
   `tests/test_ground_rule.py`).
3. No two boxes intersect; no box intersects a town plan rect, a street, a spawn-free zone
   (`data/spawn_suppression.json`), a route corridor box, or a Habitat Block's
   `RangeOfInfluence`.
4. Every filler block that appears in `data/spawn_blocks.json` is whitelisted in
   `data/spawn_block_policy.json` with a `why` naming this site.
5. `period_seconds` within a stated range; `ore_max >= ore_min`; `variants >= 2`.
6. Every site is named by a `tools/reapply.py` step — and `prepare`'s own fail-closed check
   (`tools/reapply.py:155-172`) enforces the other direction.
7. **A coverage check, which is the point of the whole file:** every stone in
   `SPAWN_PHILOSOPHY.md`'s stone-gated twenty has at least one site, and the report prints, per
   stone, the earliest leg it is reachable from. A silent regression to "all ten at gym 8" is
   the most likely way this design decays.

---

## 6. The rate, with the arithmetic

### 6.1 Demand is small, and that is the surprising part

- **20 stone-gated families**, VERIFIED (`SPAWN_PHILOSOPHY.md:326`), by stone: Water 4, Sun 4,
  Shiny 3, Ice 2, Dusk 2, Moon 2, Leaf 1, Dawn 1, Thunder 1, Fire 0.
- A player needs **one stone per family they care about**. A completionist needs 20; a normal
  player 5-10.
- A party of four completionists needs **80 stones across the campaign** — but per stone type
  the number is tiny: **16 Water, 16 Sun, 12 Shiny, 8 each of Ice/Dusk/Moon, 4 each of
  Leaf/Dawn/Thunder, 0 Fire.**
- Evolution stones have no other sink in this campaign today. If they ever become currency, or
  if eeveelutions enter the rosters (VERIFIED absent: `eevee` does not appear in
  `data/spawns.json` at all, `SPAWN_PHILOSOPHY.md:372-375`), these numbers change and the rate
  must be re-tuned.

**The consequence, and it drives the whole design: the reset is not a rate limiter. It is an
availability guarantee.** Nothing about this economy needs throttling; what it needs is that a
player who walks to a seam finds something in it. Design for that and the per-hour ceiling stops
mattering.

### 6.2 Supply, per face and per visit

Recommended starting parameters, all of them data and all of them tunable:

| Parameter | Value | Why |
| --- | --- | --- |
| Face box | 9 × 5 × 6 = **270 blocks** | Three to five minutes to work out with an iron pick; a real face, not a wall of ore |
| Ore per face per reset | **2-4** of the site's stone (mean 3) | Enough for one player's need in one or two faces; never a pile |
| Filler per face | 0-3 vanilla ore | Reads as a mine; supplies the flavour spawns (§4.6) |
| Faces per stone | **2**, so 20 faces over seven sites | Two faces at Viltri Light, the Scar, the Displaced City and Northlight; four at the tea town, the gorge hamlet and the Mining Town, which carry two stones each |
| Reset period | **600 s**, the two faces of a stone staggered 300 s apart | Long enough to be a mine, short enough that a second player waits minutes |

- **Per visit (15 minutes):** two fresh faces ≈ 6 stones of that stone, plus a reset during the
  visit ≈ **9**. At a two-stone site, that again for the other stone.
- **Per hour, camping the same stone:** 2 faces × 6 resets × 3 = **36**. Absurd, and harmless:
  the whole party's lifetime need for the biggest stone is 16. Nobody will do it twice.
- **Per stone, per player:** one visit is a surplus. That is intentional — the cost of a stone
  is the trip, not the swing of the pick.

A face belongs to exactly one stone. A site that carries two stones has two pairs of faces, in
two different cuts or on two different levels, so "the east wall is dawn and the west wall is
dusk" is a thing a player can learn rather than a lucky draw.

### 6.3 The campaign cost is travel, and here it is

Round trips from the critical path, sprinting at about 5.6 blocks per second, using the measured
off-path distances in `data/towns.json`:

| Site | Off path | Round trip | At the face |
| --- | ---: | ---: | ---: |
| Viltri Light | 840 | ~5 min | ~10 min |
| Tea town | 891 | ~5 min | ~10 min |
| The Scar | 437 | ~3 min | ~10 min |
| Displaced City | 287 | ~2 min | ~10 min |
| Northlight | 2,106 | ~13 min (over water) | ~10 min |
| Gorge hamlet | 283 | ~2 min | ~10 min |
| Mining Town | 905 | ~5 min | ~10 min |
| **Total** | | **~35 min** | **~70 min** |

**About one hour and forty-five minutes, spread across a whole campaign, for one player to visit
every site and come away with every stone they will ever need.** Against a campaign measured in
tens of hours that is the right price for unlocking twenty families — and almost all of it is
walking somewhere new, which is what the map is for.

Two honest caveats. The Northlight trip is a sea crossing and may be twice that; and none of
these numbers survives contact with a pickaxe-tier surprise (§7, item 2).

---

## 7. What is VERIFIED, what is ASSUMED, and what must be run

**VERIFIED from files and experiments, cited above:** the ore does not generate; the 23 ore
block ids; the three special host rocks and the feature configs behind them (EXP-017 A1); the
20 stone-gated families and their split by stone; the off-path distances and legs of all seven
sites; that vanilla filler ore summons Rolycoly, Aron, Geodude-Alolan, Carbink and Klink lines
through `neededNearbyBlocks`; that no stone ore summons anything; that a spawn-condition block in
placed content fails validation unless whitelisted; that a re-export erases placed blocks and
that `reapply.py prepare` now fails closed on a pack with no step; that upstream spawn pools are
live in unauthored caves.

**ASSUMED (design judgement, or knowledge not read out of this repository):** the 66-recipe
finding, which is the owner's and belongs in `docs/research/`; the family-to-stone mapping, which
`SPAWN_PHILOSOPHY.md:357-362` already flags as mainline knowledge rather than a jar read; that a
fifteen-to-twenty-year-old first find is the right age for the fiction; every number in §6.2.

**Experiment candidates, in the order that collapses the most uncertainty per unit of work.**
None has been run, and **no content should be authored beyond one proof face** until items 1-4
pass — principle 20, and the same discipline ADR-002 imposed on caches.

1. **What a stone ore drops, and at what tool tier.** `/give` the block, place it, break it with
   wood, stone, iron and diamond picks, with and without Fortune and Silk Touch; record the
   drop and the count. This decides §6 outright, and the tier decides whether Viltri Light can be
   an early site at all. Cheap: one disposable world, one player, ten minutes. **Read first:**
   the block's loot table and `#minecraft:needs_*_tool` tags out of the 1.8.0 jar, which may
   answer it with no server at all.
2. **The recipe ratio.** Ore → stone, and compressed block → stone, at what counts. Together
   with (1) this turns every number in §6.2 into arithmetic instead of estimate.
3. **The reset, in a running game.** A 270-block `fill` plus `setblock`s completes without a
   visible hitch; `execute unless entity @a[…]` correctly refuses while a player stands in the
   box and fires the moment they leave; two players mining the same face both get drops.
4. **The driver survives a restart.** `schedule … replace` re-armed from a `load` tag does not
   double-fire and does not stall; or the `tick`-tag fallback does the same.
5. **The bound holds.** A player cannot leave a gallery into unauthored cave, and cannot reach
   the bedrock skin without deliberately mining the full depth of a face.
6. **The flavour spawns happen.** With a player standing at a face for five minutes, something
   from the §4.6 table appears — and at what level. **VERIFIED constraint on planning this:**
   Cobblemon spawns only around players, so this is an appointment with somebody in game, not an
   agent task (`docs/STATE.md`, "Every spawn test needs a player").
7. **The ADR-002 floor.** The per-site first-visit grant is the same two-player advancement proof
   that already blocks badge flags and caches; run it once, for all three.
8. **It survives a re-export.** `reapply.py prepare` covers `cobblers_mines`; R17 rebuilds every
   face on a staging export; the audit counts ore blocks per face against the record.

---

## 8. What this does not decide, and who it goes to

- **Site geometry.** Every box, entry, gallery and backing is world-content work on measured
  ground: `world-content-dev`, with `data/towns.json` and `data/placements.json` unchanged until
  then. The Mining Town's faces must not wait on its Axiom set-piece mine
  (`data/towns.json:1405-1414`); they are self-contained and can be re-sited into it later.
- **`data/mines.json` and `tools/mines.py`:** `datapack-content-dev`, after the ADR is accepted.
- **The validator and its tests:** `test-author`, never the implementer.
- **Whether the base stages are actually catchable early** where their stone now is — Budew,
  Togepi, Minccino near tea town, Poliwag and Staryu near Viltri Light. If they are not, the
  early availability this design buys is imaginary. `trainer-balance-designer` and
  `datapack-content-dev`, against `data/spawns.json`.
- **Trader stock.** "The rest are traded on" needs the badge-gated stock that `docs/STATE.md`
  records as unlanded; until then trade is fiction and the faces are the supply.
- **The scatter pass / Underground Pockets alternative.** EXP-017 A3 measured recommended
  Underground Pockets settings within about ±30% of Cobblemon's own densities
  (`EXP-017/README.md:147-168`), which would restore the ore world-wide at the next export. It
  is a real alternative and is argued in ADR-003; it is not recommended, because it puts the
  supply in unauthored caves where the pack's own spawns live and gives no place its identity.
