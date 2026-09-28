# The stone economy

**Status: proposed design, 2026-09-27; built offline 2026-09-28 (the owner: "the evolution stones
incorporated ... build them into the towns that have them"). The faces and the Exchange exist as data and a
generated pack, audited offline; nothing has run in a game, and nothing is installed. §14 records what was built
and where it differs from the design below.** This answers the owner's stone-economy brief in full. It builds on
`docs/mechanics/EVOLUTION_STONES.md` and `docs/decisions/ADR-003-evolution-stone-supply.md` (both
Proposed, 2026-09-23): ore in the rock, at seven places, in faces that a generated function resets.
That decision stands. This document re-checks it against the jar and the rosters, and it changes
five things. §10 lists them, and ADR-003 carries them as an amendment.

Labels: **VERIFIED** means a file, a line, a jar read or an experiment, cited. **ASSUMED** means
design judgement or knowledge not read out of this repository. **Nothing here has run in a game.**

---

## 0. What was checked for this document

**VERIFIED (jar read, 2026-09-27).** The Cobblemon jar that was read is `Cobblemon-fabric-1.8.0+1.21.1.jar`,
SHA-256 `a6228f32…9ec31`. That is the hash `data/spawns.json` records under `compilation.jar_sha256`.
The Mega Showdown jar is `mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar`, SHA-1 `50b2012b…c7a2`.
That is the hash `modpack/manifest/overlay.json:259` records. Both were read from a local client profile
with Python's `zipfile`, outside the server tree. The following questions were open in
`EVOLUTION_STONES.md` §7, and the jar answers them:

| Question (`EVOLUTION_STONES.md` §7) | Answer | Source in the jar |
| --- | --- | --- |
| 1. What a stone ore drops | **One stone of its type.** Fortune applies through the vanilla `ore_drops` formula. Silk Touch drops the ore block itself. Explosions decay the drop | `data/cobblemon/loot_table/blocks/*_stone_ore.json`: all 23 have the same shape |
| 1. At what tool tier | **An iron pickaxe or better** for all 22 overworld ore blocks. `nether_fire_stone_ore` needs only a pickaxe | `data/minecraft/tags/block/needs_iron_tool.json`, `mineable/pickaxe.json` |
| 2. The recipe ratio | **Ore to stone is 1:1** by smelting (200 ticks) or blasting (100 ticks), for all 23 ores. **A block gives 9 stones** by shapeless craft, and 9 stones make a block. That is 56 recipes producing a stone. The owner's "66" is these 56 plus the 10 compress recipes. Every one takes ore or the block, never ordinary materials | `data/cobblemon/recipe/*_stone_from_*.json`, `*_stone_block.json` |
| (new) Other uses of a stone | **Five held-item recipes:** Damp Rock (Water Stone *or* Water Gem), Heat Rock and Flame Orb (Fire Stone *or* Fire Gem), Icy Rock (Ice Stone *or* Ice Gem), and **Metal Alloy (Thunder Stone plus 4 iron). Metal Alloy is what evolves Duraludon into Archaludon** | `recipe/damp_rock.json`, `heat_rock.json`, `icy_rock.json`, `flame_orb.json`, `metal_alloy.json`; `species/…/duraludon.json` |
| (new) Mega Showdown's meteorid ores | `mega_showdown:mega_meteorid_<stone>_ore` exists for all ten stones. Each **drops the Cobblemon stone** (for example `cobblemon:water_stone`), with the same Fortune and Silk Touch rules. They are pickaxe-mineable and **carry no tool-tier tag**. They have **no smelting recipe**, so a Silk-Touched meteorid ore has to be placed and mined again | `mega_showdown/loot_table/blocks/mega_meteorid_*_ore.json`; `minecraft/tags/block/mineable/pickaxe.json`; only 4 meteorid recipes, all building blocks |

**VERIFIED (jar read plus `data/spawns.json`): demand, recounted.** Every species that is catchable at
a weight above zero in `entries`, `subregions`, `habitats` or `marine_zones` was walked forward through
the jar's own `evolutions` blocks, forms included. Each step whose `requiredContext` is an evolution
stone was counted. Earlier counts used mainline knowledge. This one does not. It gives **28 families and 29 stone uses
per completionist**: 28 evolutions, plus Archaludon through Metal Alloy, and 31 with the two biome
variants. The 2026-09-23
count was 20 families. Thunder moved the most, from **1 to 6**. §6.1 has the table.

---

## 1. The recommendation: a handful of stone towns, the rest traded on

**The owner's doubt is right. One town per stone is wrong. Recommend a handful of places known for a
stone, one clearing house, and trade for the rest.** ADR-003 already rejected one-per-stone, and the
reasons hold:

- **There are ten stones and too few places.** Ten stone towns would take every non-gym place on the
  map, including rest stops and outposts with no services. That is ten builds and ten reset loops.
- **It overwrites identities that were given on purpose.** A harbour, an observatory, a tea town and
  an archaeologists' camp each already answer a question (`docs/world-building/SETTLEMENTS.md`). If
  every settlement answers "which stone?", the map becomes a commodity grid.
- **Cobblemon itself says the stones are not uniform.** Three stones have a host rock of their own:
  sun stone replaces terracotta, moon stone has a dripstone feature, and fire stone has a netherrack
  feature (EXP-017 A1, `experiments/EXP-017-ore-pockets-and-object-load/README.md:85-88`).
- **Demand is lopsided.** Thunder is needed by 6 families, and Fire by no evolution at all (§6.1).
  Even distribution gives the same weight to a stone nobody needs and to one six families need.

**The shape:** **seven stone places, ten stones, and one clearing house.** Three places carry two
stones. The Mining Town anchors the system. It anchors it not by holding the most seams but by being
three things at once: the only place that works stone as an industry, the deep second source of the
most-needed stone, and **the Exchange**, where every stone can be bought (§8). "The rest are traded on"
becomes a mechanism there rather than a line of fiction. The Rift dig camp is the other mining
settlement. It stays an **archaeology** camp and carries no evolution stone (§7).

**Assignment criteria, in ADR-003's order:**

1. Reachability, measured against when each stone is *first needed* (§6.1). The needs were not
   measured before.
2. The host rock Cobblemon implies.
3. The identity the place already has.

Criterion 1 is what moves Thunder.

---

## 2. The fiction

This is unchanged from `EVOLUTION_STONES.md` §2, and its four constraints stay hard rules:

- no stone site delivers a required fact;
- miners have no theory;
- "recently" means a generation, not a year;
- the Haven Compact did not make the stones.

The premise is worldshift residue: matter from elsewhere pushed up through the ground. The region
knows only that the ground began giving up strange stones, and some towns grew around working them.

Two readings are strengthened by this revision:

- **The Scar and the Displaced City are the two ends of one exchange.** Sun is exposed where the
  summit lay open to the sky. Moon and Thunder are found where the summit went, under rock, in a city
  that lives on light that is not the sun. The Displaced City's cavern already rosters Magnemite and
  Sableye (`data/spawns.json`, habitat `displaced_city_cavern`), and a Thunder seam gives the Magnemite
  a reason to be there.
- **The Exchange is where the region's ignorance is spoken aloud.** Every stone passes through the
  Mining Town's assay house, and the assayer can say, truthfully, that no two seams behave like ore.
  That is the fiction's "nobody knows why", given to the one person best placed to notice.

---

## 3. Stone by stone

The **stage** column is the leg on which the source opens: leg N is the route walked to gym N, from
`data/towns.json` `nearest_leg`. The **first need** column is the first gym before which a consumer
can be caught, from `docs/story/AVAILABILITY.md`. It says "off rN" where the pool is off the route
corridor near route N, and "habitat" where the pool needs a Habitat Block. The **rate** column is
per face, per reset (§6.2). The **floor** is one stone per player on first arrival (§4).

| Stone | Families needing it | First need | Source | Where | Stage | Rate | Other sources |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| **Water** | 4 | gym 1 (Staryu, Shellder) | native ore, stone host, raw exposure | **Viltri Light** (550, 4518), 840 off | leg 1 | 2 faces × 2-4; floor 1 | VR Drowned Gallery cache (1), Exchange |
| **Leaf** | 2 | gym 6 (Nuzleaf; Gloom off r6) | native ore, worked terrace | **Tea town** (2654, 3605), 891 off | leg 2 | 2 × 2-4; floor 1 | VR Bloom cache (1), Exchange |
| **Shiny** | 3 | off r2 (Budew, Togepi by friendship); gym 4 (Minccino) | native ore, worked terrace | **Tea town** | leg 2 | 2 × 2-4; floor 1 | VR Bloom cache (1), Exchange |
| **Sun** | 4 (+1 biome variant) | off r1 (Cottonee); off r6, r8 | native ore, **terracotta host**, raw exposure | **The Scar** (2110, 950), 437 off | leg 4 | 2 × 2-4; floor 1 | VR Bloom cache (1), Exchange |
| **Moon** | 2 | gym 8 (Nidorina, Nidorino) | native ore, **dripstone host**, city working | **Displaced City** (2969, 1710), 287 off | leg 4 | 2 × 2-4; floor 1 | Exchange |
| **Thunder** | **6** (+1 biome variant) | gym 4 (Nosepass, Pichu); Displaced City cavern (Magnemite) | native ore, deep working | **Displaced City** (primary, new) **and Mining Town** (second seam) | leg 4 / leg 8 | 2 × **3-5** at each; floor 1 at each | Exchange |
| **Ice** | 3 | off r4 (Alolan Vulpix and Sandshrew) | native ore, worked | **Northlight** (7265, 1556), 2,106 off over water | leg 6 | 2 × 2-4; floor 1 | Exchange |
| **Dusk** | 3 | the Route 1 mansion habitat (Murkrow, Misdreavus, Litwick); off r6 | native ore, gorge wall | **Gorge hamlet** (6814, 4367), 283 off | leg 7 | 2 × 2-4; floor 1 | Exchange |
| **Dawn** | 2 | off r2 (Ralts, male); gym 4 (Snorunt, female) | native ore, gorge wall | **Gorge hamlet** | leg 7 | 2 × 2-4; floor 1 | Exchange |
| **Fire** | 0 (Heat Rock and Flame Orb only) | none | native ore, thermal adit | **Mining Town** (6633, 5716), 905 off | leg 8 | 2 × 1-3; floor 1 | Nether (`nether_fire_stone_ore` generates there, ASSUMED reachable), VR Slagworks cache (1), Exchange |

The VR caches are VERIFIED in `data/rewards.json`: `vr_drowned_gallery` holds Water;
`vr_bloom` holds Leaf, Sun and Shiny; `vr_slagworks` holds Fire. They are per player and come after
gym 8.

That is **22 faces over seven places**. ADR-003 had 20. The two new faces are the Displaced City's
Thunder pair.

### The lag between need and source

This lag is what ADR-003 could not see without a count of when each stone is first needed.

| Stone | Need opens | Source opens | Lag | Verdict |
| --- | --- | --- | --- | --- |
| Water | gym 1 | leg 1 | 0 | right |
| Shiny | off r2 | leg 2 | 0 | right |
| Leaf | gym 6 | leg 2 | −4 (early) | harmless: tea identity |
| Sun | off r1 | leg 4 | 3 | acceptable: Cottonee only; most Sun families are gym 6-8 |
| Moon | gym 8 | leg 4 | −4 (early) | harmless: the Scar/City pairing is worth it |
| **Thunder** | **gym 4** | **leg 8 under ADR-003** | **4** | **wrong. Fixed:** the Displaced City opens at leg 4 |
| Ice | off r4 | leg 6 | 2 | acceptable |
| Dusk, Dawn | mansion (habitat) / off r2 / gym 4 | leg 7 | 3-6 | **deliberate** (judgement): Honchkrow, Mismagius, Chandelure, Gallade and Froslass are power spikes, and mainline gives these two stones late. Open decision O-3 |

---

## 4. Per-player or shared, and what each costs

**The constraint under the question (VERIFIED):** a block is world state, and a re-export replaces
region files. Per-player state is durable. `tools/carry_players.py:65-81` carries advancements,
player data and CobbleDollars as required categories and `data/scoreboard.dat` as an optional one.
There is no per-player view of a block without a mod. So "ore in the rock" is shared by construction.

| Option | Fair to a second player? | Build cost | Runtime cost | Survives re-export | Verdict |
| --- | --- | --- | --- | --- | --- |
| **A. Shared face that restores** | Waits minutes, or works the other face | 22 face boxes, one pack | a check every 100 ticks per place with a player near; ≤12 commands per restore (§5.3) | rebuilt by its step; timers optional | **Recommended** |
| **B. Faces instanced per player** | Yes, while the player count is fixed | N × 22 boxes | N × A | yes | Rejected: player count not fixed; a late joiner has none; everyone still sees everyone's rock (`ADR-002:132-133`) |
| **C. One-shot per-player grant on arrival** (ADR-002 advancement) | Yes | one record per site | none after the grant | **yes, advancements carried as required** | **Kept as the floor**, one stone per stone-type per site per player |
| **D. The ore drops nothing; a trigger grants the stone** | Yes | as C | as C | as C | Rejected: C in costume; the rock becomes a button |
| **E. Per-player repeatable allowance** (new) | Yes | one scoreboard objective per site, one function | a per-player cooldown check on approach | scoreboard is optional in the carry, so a re-export refreshes every cooldown, which is harmless | **Fallback only.** This is a vending machine. It becomes worth building if play shows contention, and demand says it will not (§6.3) |

Option E is new since ADR-003. Per-player scoreboard and storage records are VERIFIED to load and run
in this runtime: the blackout claim ledger writes `storage cobblers:recovery`, and its rolls use
`random value` (`tools/blackout_pack.py:154-180, 334, 352`; EXP-042 on staging). That makes E
cheap. It is still not mining.

**Recommendation: A with C as the floor. It is the same as ADR-003, with one sharpening.** At a
two-stone place the floor gives one of *each*. The floor also solves the tool-tier problem: an iron
pickaxe is required (§0), and a player arriving at Viltri Light on leg 1 may not have one yet.
**The floor is how the earliest site gives something to a player who cannot yet mine it.** The face
is there for when they can.

The floor depends on ADR-002's two-player advancement proof, and on nothing else. If that proof
fails, drop the floor and the faces are unaffected.

---

## 5. Ore or loot, and how the face restores

### 5.1 Ore in the rock is itself the right loot mechanism

The owner's worry comes from ADR-002. A container's loot table is rolled once, on first open, into
one shared inventory (`ADR-002:108-117`). **A block's loot table works the other way.** It rolls per
break and drops the item to the player who broke the block. It is deterministic apart from Fortune,
and it is Cobblemon's own (VERIFIED, §0). So ore in the rock is shared *as rock* and personal *as
drops*. It needs no loot table, no container and no restock from us.

The two runners-up and why not:

- **A restocking barrel (`LootTable` set by function).** It is shared and random, and it needs an
  authored table. It is worse on every axis.
- **Suspicious gravel with a stone loot table.** It is brushable and archaeological, a fit for the
  dig camp. It is rolled once, shared and random, and it would need a custom table (rung 5).
  Reserve it for fossils and relics (§7).

**Native Cobblemon ore (rung 1) is the default everywhere.** Mega Showdown's meteorid ores are a
real alternative, VERIFIED to drop the same stones with no tool tier. They are offered as open
decision O-4, not recommended. They are rung 2 rather than rung 1. Silk Touch on them is a trap:
there is no smelting recipe, so the block has to be placed and mined again. And the owner's fiction is
"strange stones in the ground", not a meteor strike.

### 5.2 The template and its variants

The face is not stamped from a stored structure. **The template is data:** `tools/mines.py` generates,
for each face:

- `build_<site>`: the gallery or cut, the lighting, the host backing and the skin (§6.4). It runs once
  per export from a re-apply step.
- `restore_<face>_v<k>` for k = 0..7: **eight authored variants.** Each is a filtered `fill` of the
  box back to host rock, then that variant's `setblock`s for ore and filler. Each `setblock` is guarded
  so that it only writes where a resettable block stands (§5.4).
- `mines/tick`: the driver.

**Choosing a variant:** `random value 0..7`, rolled again once if it equals the last variant used.
`random value` loads and runs in this runtime (`tools/blackout_pack.py:334`,
`tools/rift_storm.py:69`, both on staging). ADR-003 marked it ASSUMED. That is now obsolete. Plain
rotation (counter mod 8) is the fallback and needs nothing. Either way, no two restores in a row
place the same ore.

**One visible tell per variant (judgement).** Each variant puts at least one ore block on the exposed
surface of the face. The rest are hidden in the box. A seam a player can see reads as a seam and
teaches the place in one glance. Hidden ore alone reads as luck.

### 5.3 When it restores, and what it costs per tick

**ADR-003's schedule has a flaw, and this is the second change.** ADR-003 had the faces restore on a
fixed 600-second timer from a `schedule` loop. `fill` and `setblock` fail on a chunk that is not
loaded. The repository already guards against exactly that: `tools/reapply.py:771, 803, 829` use
`execute if loaded`. Most faces, most of the time, have nobody near them, so a timed restore would
mostly fail. The failures would be silent, or they would need a forceload.

**Restore on approach instead.** The driver runs every 100 ticks from the pack's `minecraft:tick` tag.
`cobblers_progression` and `cobblers_blackout` already drive themselves this way
(`tools/reapply.py:89-95`). For each place, the driver does this:

1. `execute if entity @a[<place's approach box, about 64 blocks out>]`. If nobody is near, stop.
   That costs one selector per place.
2. For each face at that place: when `now − last_restore ≥ period` (600 s by default)
   **and** `execute if loaded` holds for both corners of the box
   **and** `unless entity @a[<face box>]`
   **and** `unless entity @e[type=cobblemon:pokemon,<face box>]` — that last check is a sent-out
   partner standing in a dug tunnel — then restore the face and stamp `last_restore`.

The owner's "own schedule" survives: the period is time, not an event. What changes is when the
period is *checked*. A player who comes back after an hour finds the seam fresh the moment they
arrive, and nobody pays anything while no one is there.

**Tick cost:** at most 7 place selectors per 100 ticks when idle. At a busy place, add 4 score
comparisons and 3 guards per face, which is under 1 command per tick averaged. A restore is 1
filtered `fill` of 270 blocks plus at most 7 guarded `setblock`s plus 2 score writes: **≤12 commands
and ≤270 block writes**, well under the 32,768-block limit `tools/function_limits.py` enforces. For
scale, the Rift skin was 1.6 million commands in one pass (`docs/STATE.md`). This is noise. ASSUMED
until measured: no visible hitch. That is proof item P-3.

### 5.4 What the restore must never destroy

`fill … replace` without a filter deletes a chest a player left in the box, and its contents go with
it. `fill` does not drop items. **The restore therefore fills only over the tag
`#cobblers:face_resettable`.** The tag holds air and cave air, water and lava, the site's host rock
and its cobbled form, gravel, torches, the ten stone ores and their variants, and the filler ores.
Anything else a player placed is left standing. Every ore `setblock` is wrapped as
`execute if block <pos> #cobblers:face_resettable run setblock …`. So a player's chest survives, and
it simply blocks one ore slot until it is moved. Say so in the place's reading: "the seam repairs
the rock, not your things." ASSUMED: `fill … replace <tag>` accepts a block tag in 1.21.1. That is
vanilla behaviour, but it is not proven here. Proof item P-3.

### 5.5 Re-export survival

The design survives by construction, because everything is generated from `data/mines.json`.

- **The step is `R9O`, not R17 or R9M.** R17 is taken by "scene props, scene NPCs and the route
  trainers". **R9M is the Rift dig camp's** (`tools/rift_mines.py`, which took the name first), and **R9S the
  southern Rift's mega site** (`tools/gulch_mine.py`): the owner's decision 12 of
  `docs/world-building/SOUTHERN_RIFT_MEGA.md` (2026-09-27) gives the evolution-stone faces a new letter. `R9O`
  ("ore") is proposed here; R9D is retired and R9DC, R9E, R9F and R9G are taken. The step runs after R9C (Victory
  Road's caves), after R9 (the donors) and after R2 (the Displaced City cavern), and before R9E, because a face's
  optional Habitat Block sits on a finished floor. This is the third change to ADR-003 (whose amendment still says
  R9M: to be brought in line).
- `reapply.py prepare` fails closed on a pack that no step runs, so `cobblers_mines` needs its step to exist before it
  can ship.
- The mega stone faces are not this system's: the gulch's two faces (`data/gulch_mine.json`) use the same restore on
  approach, filter and occupancy guard, with their own tick driver in `cobblers_gulch_mine`, a 30-minute period and
  meteorid as the host. The dig camp's one crystal is a third, daily face in `cobblers_rift_mines`. Proofs P-2 to P-4
  cover all three.
- Faces are rebuilt at variant 0. Restore timers live in `data/scoreboard.dat`, which the carry
  treats as optional. If they are lost, every face is simply fresh, and nothing breaks.
- The floor is advancements, **carried as required**. A player who took a floor keeps it and cannot
  take it again.
- The resident Pokemon (§9) are entities, which a re-export erases. They are re-summoned over RCON,
  like `sapling_celebi` (R14C). Functions cannot run Cobblemon's spawn command (`docs/STATE.md`).
- The Exchange clerk is a trader record, re-summoned by R14 (`data/traders.json`).

---

## 6. The rate

### 6.1 Demand, verified from the jar

Each row is one stone evolution a completionist makes once. "First catchable" is from
`docs/story/AVAILABILITY.md`. Levels are the roster's first bands.

| Stone | Evolution (from → to) | First catchable |
| --- | --- | --- |
| Water | Staryu → Starmie; Shellder → Cloyster | gym 1, west shore (7-10) |
| | Lombre → Ludicolo | gym 2, route 2 (18-21) |
| | Poliwhirl → Poliwrath | gym 6, route 6 (37-39) |
| Sun | Cottonee → Whimsicott | off r1, south-west fields (5-15) |
| | Petilil → Lilligant (and Hisuian Lilligant in a `petilil_hisuibiome` biome) | off r6 and r8 |
| | Gloom → Bellossom | off r6, Tilpey west meadows (39-48) |
| | Helioptile → Heliolisk | off r8, south-east dunes |
| Thunder | Nosepass → Probopass | gym 4, route 4 (28-30) |
| | Pikachu → Raichu, from Pichu by friendship (and Alolan Raichu in a `pikachu_alolabiome` biome) | gym 4, Peak Pond (30-32) |
| | Magneton → Magnezone | Displaced City cavern habitat (32-45) |
| | Tadbulb → Bellibolt | gym 7, Tilpey waters (39-48) |
| | Charjabug → Vikavolt | off r8, Long Isle south (44-50) |
| | Duraludon → Archaludon, through Metal Alloy (a Thunder Stone plus 4 iron) | Victory Road, the Raw Tear |
| Shiny | Roselia → Roserade (from Budew) | off r2, Arrow Lake |
| | Togetic → Togekiss (from Togepi) | off r2, Shrew Lake |
| | Minccino → Cinccino | gym 4, north shore downs (30-38) |
| Ice | Alolan Vulpix → Alolan Ninetales; Alolan Sandshrew → Alolan Sandslash | off r4, Frostpeak strand; off r6, the pine isles |
| | Crabrawler → Crabominable | gym 8, south strand (50-52) |
| Dusk | Murkrow → Honchkrow; Misdreavus → Mismagius | Route 1 mansion habitat (6-15); off r6, wedge north |
| | Lampent → Chandelure (Litwick levels at 41) | Route 1 mansion habitat |
| Dawn | Kirlia → Gallade (male only) | off r2, Shrew Lake (Ralts) |
| | Snorunt → Froslass (female only) | gym 4, route 4 (29-31) |
| Leaf | Gloom → Vileplume | off r6 |
| | Nuzleaf → Shiftry | gym 6, Tilpey east shore (41-43) |
| Moon | Nidorina → Nidoqueen; Nidorino → Nidoking | gym 8, route 8 and the Rift foot (49-51) |
| Fire | none (Vulpix, the only Fire Stone line, is rostered only in its Alolan form, which takes Ice) | — |

**Per completionist: Water 4, Sun 4, Thunder 6, Shiny 3, Ice 3, Dusk 3, Dawn 2, Leaf 2, Moon 2,
Fire 0.** That is **29**, or **31** with both biome variants. The held-item sinks are optional:
Damp Rock, Heat Rock, Icy Rock and Flame Orb, and each also accepts a type gem instead. Eevee is
still absent from the rosters (VERIFIED: no `eevee` row), so the eeveelution economy has no consumer.
Its arrival would add 3 stones per player (Water, Thunder, Fire).

A normal player evolves perhaps 8-10 of these. **A party of four completionists needs about 120
stones over a whole campaign**, and at most 24-28 of any one type (Thunder).

The blackout system can take stones. Evolution stones are in `data/blackout.json`'s consumables
list: a wild blackout has a 35% chance of taking one item from that list, and the item is recoverable
by defeating or catching the guardian (EXP-042). It is a small, temporary loss, and it argues only
for "carry what you need".

### 6.2 Supply

| Parameter | Value | Why |
| --- | --- | --- |
| Face | 9 × 5 × 6 = 270 blocks | ADR-003's size. About 3 minutes to clear with an iron pick: stone takes 8 ticks, ore and deepslate about 15. The hardness figures are vanilla, ASSUMED for Cobblemon's ore |
| Ore per face per restore | **2-4** (mean 3). **Thunder 3-5** (mean 4). **Fire 1-3** | tuned per stone to demand, not uniform; one visible (§5.2) |
| Filler | 0-3 vanilla ore, only where the policy allows (§9) | a mine, not a vending machine |
| Faces per stone per place | 2, restored at least 600 s apart, the two offset by 300 s | a second player waits minutes or works the other face |
| Floor | 1 of each stone the place carries, per player, once | the second arrival is never empty-handed; covers the iron-pick gap |
| Fortune | VERIFIED to apply (`ore_drops`). ASSUMED mean multiplier 1.33 / 1.75 / 2.2 at levels I / II / III | a late-game player needs fewer swings, not more stones |

**On arrival at a fresh place:** 2 faces × mean yield + 1 floor per player.

- Water at Viltri for a party of four: 6 + 4 = **10** against an early need of 8 (Starmie and
  Cloyster, four players each).
- Thunder at the Displaced City: 8 + 4 = **12** against an early need of 12 (Probopass, Raichu and
  Magnezone, four players each).
- Sun at the Scar: 10 against 16 over the campaign. The later need is met on a return visit.

**Ceiling while camping:** 2 faces × 6 restores an hour × 3 = 36 of one stone per hour. That is
absurd, and harmless: nobody needs that many, and a stone cannot be sold (§8).

### 6.3 How much hunting for how many stones

- **At the face:** about 1 minute of digging per stone, because a cleared face of 3 minutes holds 3.
  A completionist's 29 stones take **about 30 minutes of digging in a whole campaign**.
- **Travel:** seven places. ADR-003's measured round trips total about 35 minutes. The Scar and the
  Displaced City share leg 4, and the Tea town and Viltri are the two long early detours
  (`EVOLUTION_STONES.md` §6.3).
- **Total, one completionist:** about **65-75 minutes** spread across tens of hours. A normal player
  who evolves 8-10 needs about 45 minutes, most of it walking to places they have not seen.
- **Contention:** per stone type, a party of four never needs more than two faces' worth at once,
  except Thunder and Sun on a first visit. There it waits one restore, 10 minutes, or comes back
  later.

**The reset is an availability guarantee, not a rate limiter.** The price of a stone is the trip.
That was ADR-003's conclusion, and the recount, with half as much demand again, does not change it.

### 6.4 Can a player strip-mine past the face?

**For the economy it pays nothing.** No stone ore generates anywhere in this world
(`docs/world-building/WORLDGEN_FEATURES.md:5-9`), so the only stone ore is in the boxes. Digging
past a face finds host rock. The export's Resources layer does put vanilla ores in the rock
(`docs/world-building/REEXPORT.md:703`, ASSUMED still true of the live world), which is fine.

**For encounters, the concern is narrower than ADR-003 assumed.** The export has no caves or chasms
(`REEXPORT.md:705`). Every underground void is one we authored. So a tunnel past a face reaches solid
rock, not an unauthored cave. It reaches something designed only where a face backs onto an
authored void: the Displaced City cavern, the Mining Town's workings, or the Rift. The pack's own
underground pools are live (`docs/STATE.md`), and those pools can use the space *any* player tunnel
creates. That is a world-wide property of digging, not something a face introduces.

**The recommendation, and it is a judgement:**

1. **Two blocks of host rock** backing every hidden side of the box. This is unchanged.
2. **A bedrock skin only where the box sits within 24 blocks of an authored void.** Behind it, the
   fiction is "the seam ends". The raw exposures and outdoor cuts need none. This relaxes
   `EVOLUTION_STONES.md` §4.5, which put bedrock behind every face.
3. **The restore repairs:** what a player removes returns, and resettable blocks they place are
   reset (§5.4).
4. **The validator refuses overlaps** with town plans, streets, spawn-suppression zones, route
   corridors, Habitat Block ranges and one another. This is unchanged.

---

## 7. Where each stone belongs, and where the rest go

| Place | Stone | The reading | Why here |
| --- | --- | --- | --- |
| **Viltri Light** (outpost, leg 1) | Water | A sea-cliff cut under the lighthouse, over an estuary no river uses any more. Water stones where the water left | The first need is gym 1. The outpost otherwise gives a player nothing to do. The floor covers the player without an iron pick |
| **Tea town** (leg 2) | Leaf, Shiny | Terrace cuttings. The tea houses face their walls with the polished stone | Shiny is needed from route 2 on. Leaf is early but in keeping, and the tea identity is kept, not replaced |
| **The Scar** (leg 4) | Sun | A scraped summit open to the sky, among the ruins (`data/ruins.json`). You chip what is exposed | Terracotta is Cobblemon's own host. It is the near end of the exchange |
| **Displaced City** (leg 4) | Moon, **Thunder** | Two seams in the cavern walls: a pale one on the dripstone benches, and a crackling one where the Magnemite gather | Dripstone is Moon's own host. Thunder is needed from gym 4 and the city is 287 off leg 4. It is the far end of the exchange |
| **Northlight** (leg 6) | Ice | The field station's cutting on the only snowy islands | Ice identity already. It is reached over water on the surface, with no Surf depth |
| **Gorge hamlet** (leg 7) | Dusk, Dawn | The Tilpey outflow cut the seam open. Dusk is on the west wall and dawn on the east | Two faces of one gorge. Late on purpose (O-3) |
| **Mining Town** (leg 8) | Fire, Thunder (deep), **the Exchange** | The thermal adit into the eastern cone; the deep workings; the assay house | The only industrial mine. The volcanic and thermal tags are painted only here. The clearing house for everything else |

**Where the rest go:**

- **The Rift dig camp** stays archaeology. It is an archaeologists' camp over Registeel's steel
  chamber (`data/towns.json`), and `DEEP_CITY.md` §6 already gives it five resource adits of its
  own: coal, iron, the LumyMon relic seam, Galar particle, and a fossil bed. Its story is relics, and
  evolution stones would blur that. The two mining settlements should be different kinds of place:
  the Mining Town works stone, and the dig camp digs up the past. The camp opens after gym 8, and only
  Moon's need is that late.
- **The Route 1 old mine** stays ore-free. The owner deliberately placed nothing there that decides a
  spawn (`docs/world-building/EARLY_ROUTES.md:116-125`). A stone ore decides no spawn (VERIFIED: no
  `*_stone_ore` in `data/spawn_blocks.json`), so a seam *could* go there without breaking that call.
  This is offered as O-5, the purest image of the premise: a worked-out mine whose back wall has
  started giving up something new.
- **Sunset West, the Tableland stop and Relic Island** are left alone. They are the alternatives
  ADR-003 weighed and set aside, and they keep their identities.

---

## 8. The trade half: the Exchange

"The rest are traded on" needs a mechanism. The one this repository already has is the CobbleDollars
merchant. Traders are summoned from shopkeeper templates carrying a `CobbleMerchantShop` compound,
and a stock policy filters it (`tools/traders.py:146-178`; `data/traders.json`, 25 traders). The
standing policy is "a trader sells only what its town produces". The Mining Town produces stone.

- **One clerk, the Assayer, in the Mining Town.** A `data/traders.json` record with a new stock kind,
  `stones`: all ten stones, unlimited, at one price. The proposed price is 2,100-3,000 CobbleDollars
  (ASSUMED; mainline's department-store price is 2,100, and the Mart revive here is 2,000). O-6.
- **No buy-back, ever. This is a rule, not a preference.** The faces are an unlimited supply (§6.2).
  The moment a stone has a sell price, a face becomes a money printer. The Exchange sells and never
  buys.
- **Why it is late, and why that is right.** The Exchange opens at leg 8. It is the catch-up for a
  player who skipped a place, and the answer for the eeveelution demand if that ever arrives. It is
  not the supply. A stone bought early would bypass the trip, which is the whole price.
- **ASSUMED, and the Exchange's own proof (P-7):** that a `CobbleMerchantShop` can be authored with
  our own offers, not only filtered from a template. The filter is proven; authoring from scratch is
  not. The fallback is a vanilla villager with explicit `Offers` and a very high `maxUses`, for
  example two of any stone for one of another. That is vanilla NBT, and equally unproven here.

---

## 9. The Rock-type flavour

The owner ruled that the Pokemon is flavour, not the trigger. The design honours that: the restore
knows nothing about Pokemon except "is one standing in the box". There are two layers.

**1. A resident at the face. It is reliable, which is the owner's reason for having it.** One
Pokemon per place stands at the face, facing the rock. It is uncatchable, unbattleable, not wandering
and persistent. This is the proven pattern of the sapling Celebi (`data/sapling_celebi.json`: EXP-023
proved `Unbattleable`, `NoAI`, `PersistenceRequired` and `HideLabel` hold across a restart), but awake
rather than asleep. It is summoned over RCON by the re-apply, and a keeper function returns it home
and removes duplicates. A player sees a Rock type at the seam every time, so the association forms
without depending on a spawn.

| Place | Resident (proposed) | Rostered nearby? |
| --- | --- | --- |
| Viltri Light | Binacle | yes, north-west coast |
| Tea town | Carbink (the shine) | Mining Town fossil levels only |
| The Scar | **Solrock** | Rift south-east arm |
| Displaced City | **Lunatone** (Moon), **Nosepass** (Thunder) | Lunatone: the Rift; Nosepass: the Crags and Mining Town. Magnemite already live in the cavern |
| Northlight | Bergmite (Ice, not Rock; there is no rostered Rock-Ice) | yes, the glacial valleys |
| Gorge hamlet | Sableye (Dusk wall), Glimmet (Dawn wall) | Mining Town, Displaced City, the Rift |
| Mining Town | Rolycoly (Fire adit), Nosepass (the deep Thunder seam), Drilbur at the pithead | all rostered in the fossil levels |

Solrock at the Scar and Lunatone in the Displaced City make the exchange legible without a word of
dialogue.

**2. Ambient spawns from filler ore, where the policy allows.** VERIFIED from
`data/spawn_blocks.json`:

- coal ore draws the Rolycoly line;
- iron ore draws Aron and Alolan Geodude;
- diamond ore draws Carbink and Sableye;
- redstone ore draws Klink.

Each is a `neededNearbyBlocks` condition, and each needs a `data/spawn_block_policy.json` whitelist
entry with a reason (`tools/validate_data.py:2583-2637`). **Recommend filler only at the leg-6-and-later
places** (Northlight, the gorge and the Mining Town) **and at the Displaced City.** These spawns run
at upstream levels, not ours. An Aggron or a Coalossal drawn to Viltri Light at gym 1 is exactly the
balance call the owner already refused for the Route 1 old mine. A Habitat Block band per face would
fix the levels, and it is optional (R9E).

---

## 10. What this changes in ADR-003

ADR-003 stays **Proposed**. Its decision stands: native ore in the rock, shared faces, the ADR-002
floor, seven places and no town per stone. Five parts change, and the amendment in the ADR records
them:

1. **Thunder gains the Displaced City as its primary site (leg 4).** The Mining Town keeps a second,
   deep Thunder seam. Reason: verified demand is 6 families, needed from gym 4, not 1.
2. **Faces restore on approach, not on a timer:** a 600-second minimum, checked only when a player is
   within about 64 blocks and both corners are loaded. Reason: `fill` fails on unloaded chunks.
3. **The re-apply step is R9O (proposed), not R17 or R9M.** R17 is taken, and R9M is the dig camp's (decision 12 of SOUTHERN_RIFT_MEGA.md).
4. **The restore is filtered** to `#cobblers:face_resettable`, so it never deletes a player's
   container.
5. **The Mining Town carries the Exchange, which sells and never buys.** "Traded on" becomes a
   mechanism.

Also refined here, and not a change to the decision:

- the tier (iron pickaxe) and drop facts are now VERIFIED, and the floor is the answer to the tier;
- per-stone yields are tuned to demand;
- the bedrock skin applies only near authored voids;
- one visible ore per variant;
- `random value` is no longer ASSUMED.

---

## 11. Data files a builder would need

**These are proposals. None of these files or fields exists, and none should be created before
ADR-003 is accepted.** Ownership follows `docs/STATE.md`'s table.

### 11.1 `data/mines.json`, schema `cobblers.mines/1` (new; `datapack-content-dev`; validator `test-author`)

This refines `EVOLUTION_STONES.md` §5. The added fields are `approach_box`, `restore`, `visible_min`,
`resettable`, `resident`, the per-face `stone` and `skin_rule`.

```jsonc
{
  "schema": "cobblers.mines/1",
  "status": "proposed",
  "defaults": {
    "period_seconds": 600, "stagger_seconds": 300, "variants": 8,
    "resettable_tag": "cobblers:face_resettable",
    "host_backing": 2,
    "skin_rule": "bedrock_if_authored_void_within_24"
  },
  "sites": [{
    "id": "displaced_city_workings",
    "settlement": "displaced_city",          // must exist in data/towns.json
    "kind": "city_working",                  // exposure | worked | city_working | thermal
    "reading": "prose shown nowhere; the builder's brief, including 'the seam repairs the rock, not your things'",
    "stage_leg": 4,                          // recorded; the validator recomputes it from towns.json nearest_leg
    "approach_box": {"min": [0,0,0], "max": [0,0,0]},   // about 64 blocks out; the driver's only idle cost
    "faces": [{
      "id": "dc_thunder_a",
      "stone": "thunder",
      "ore": "cobblemon:thunder_stone_ore",  // or deepslate_ / dripstone_moon_ / terracotta_sun_ variants
      "host": "minecraft:deepslate",
      "box": {"min": [0,0,0], "max": [0,0,0]},           // 9 x 5 x 6; ground from tools/ground.py or plan data, never a world
      "exposed_face": "north",                          // which side the player works from; the tell goes here
      "yield": {"ore_min": 3, "ore_max": 5, "visible_min": 1,
                "filler": [{"block": "minecraft:iron_ore", "min": 0, "max": 2}]},
      "restore": {"offset_seconds": 0},                 // plus defaults
      "seed": 20260927
    }],
    "floor": {                                          // ADR-002 spine; a data/rewards.json record id, droppable
      "reward_id": "mine_displaced_city"
    },
    "resident": [{                                      // flavour only; nothing reads it but the placement
      "species": "nosepass", "at": [0,0,0], "yaw": 0,
      "spawn_properties": ["uncatchable", "no_ai"],
      "nbt": {"Unbattleable": "1b", "NoAI": "1b", "PersistenceRequired": "1b", "HideLabel": "1b"}
    }],
    "spawn_block_policy": ["mines_displaced_city_iron"], // whitelist ids for every filler block
    "habitat_block": null,                              // optional, a data/habitat_blocks.json id
    "reapply_step": "R9O"
  }]
}
```

### 11.2 `data/rewards.json`: floor records (existing schema `cobblers.rewards/1`; `datapack-content-dev`)

Add one record per place, of a new `kind: "arrival"`. It is a trigger box and contents, with no
container, so it is a cache without the barrel. `tools/rewards_pack.py` already turns a trigger box
into a `minecraft:location` advancement with a reward function.

```jsonc
{"id": "mine_displaced_city", "kind": "arrival",
 "place": "the Displaced City workings, at the foot of the gallery",
 "trigger": {"min": [0,0,0], "max": [0,0,0]},
 "contents": [
   {"item": "cobblemon:moon_stone", "count": 1, "verification": "<jar path>"},
   {"item": "cobblemon:thunder_stone", "count": 1, "verification": "<jar path>"}],
 "message": "A miner presses a stone into your hand: 'First one's free. The wall gives the rest.'",
 "why": "STONE_ECONOMY.md §4: the floor", "built_by": "none (no container)"}
```

### 11.3 `data/traders.json`: the Assayer (existing schema `cobblers.traders/1`; `world-content-dev` places it, `datapack-content-dev` the stock)

```jsonc
{"id": "mining_assayer", "settlement": "mining_town", "template": "<a shopkeeper template>",
 "stock": "stones", "status": "proposed"}
```

It also adds `stock_policy.stones`:

```jsonc
{"items": ["cobblemon:<each of the ten>_stone"], "price": 2100, "buys": false,
 "why": "STONE_ECONOMY.md §8"}
```

### 11.4 Other files

| File | Change | Owner |
| --- | --- | --- |
| `data/spawn_block_policy.json` | One whitelist entry per filler block per place, each with a `why` naming the place | `datapack-content-dev` |
| `data/habitat_blocks.json` | Optional: a level band per face that has filler | `world-content-dev` |
| `tools/mines.py` | New. `build`, `restore_*`, `tick`, the `face_resettable` tag, records and verify. Ground from `tools/ground.py` only (`tests/test_ground_rule.py`) | `datapack-content-dev` to implement; contract below |
| `tools/reapply.py` | New step **R9O** (R9M is the dig camp's), and the residents' RCON placement | `test-author` owns the file; the implementer supplies the contract |
| `docs/STATE.md` | Add an ownership row for `data/mines.json` when it is created | `content-architect` |

### 11.5 The validator contract (for `test-author`, never the implementer)

This is ADR-003's list, plus four checks:

1. Every stone has at least one face. The report prints each stone's **need-to-source lag**
   (§3's second table), computed from `docs/story/AVAILABILITY.md` and `data/towns.json`. The
   likeliest way this design decays is a silent slide back to "Thunder at leg 8".
2. Every filler block that appears in `data/spawn_blocks.json` is whitelisted for that place.
3. No face box intersects another box, a town plan, a street, a suppression zone, a route corridor
   or a Habitat Block range. A bedrock skin is present exactly where the skin rule says.
4. Every restore function fills only with the `face_resettable` filter, and every ore `setblock` is
   guarded.
5. The Exchange stock has `buys: false`, and no stone appears in any trader's buy list.
6. R9O exists and names every place. `prepare`'s own fail-closed check enforces the other direction.

---

## 12. What must run before more than one face is built

The jar has answered items 1 and 2 of `EVOLUTION_STONES.md` §7. What is left needs a game. A single
proof face comes first; principle 20 applies.

| # | Proof | What passes |
| --- | --- | --- |
| P-1 | Drop and tier, in game | An iron pick yields 1 stone per ore; a stone pick yields nothing; Fortune III averages about 2.2. This confirms the jar read |
| P-2 | A restore on approach | Idle, nothing runs. On approach after the period, the face restores once. A player in the box, or a Pokemon in the box, holds it back |
| P-3 | The filter | A chest placed in the box survives a restore with its contents. Torches and cobble are reset. No visible hitch |
| P-4 | Restart | The tick driver resumes after a restart without a double restore |
| P-5 | The floor | ADR-002's two-player advancement proof. It is one run shared with the badge flags and caches |
| P-6 | The resident | An awake, uncatchable, `NoAI` Pokemon holds its post across a restart. The asleep Celebi is proven; awake is not |
| P-7 | The Exchange | A `CobbleMerchantShop` with authored stone offers sells, and buys nothing |
| P-8 | A re-export rehearsal | R9O rebuilds every face, and an audit counts the ore per face against the record (a verify pass, never a placement input) |

---

## 13. Open decisions for the owner

- **O-1. Accept the handful-plus-Exchange shape?** That is seven places, three of them carrying two
  stones, and the Mining Town as industry plus clearing house. The alternative is ADR-003's
  alternative (a): Underground Pockets at the next export. That gives world-wide ore at zero runtime
  cost, and no place owns a stone.
- **O-2. Thunder at the Displaced City.** It is the one reassignment. The fallback is the Scar, which
  is also leg 4 and would carry Sun and Thunder, but the Magnemite are in the city.
- **O-3. Dusk and Dawn late (leg 7), on purpose?** Honchkrow, Mismagius and Chandelure are caught at
  the Route 1 mansion, and Gallade and Froslass by route 4. Keeping the stones at the gorge makes the
  delay a balance lever. Moving Dusk to the mansion would make it a gym-1 power spike.
- **O-4. Native ore, or Mega Showdown's meteorid ore, at any place?** Meteorid ore drops the same
  stone, needs no tool tier and looks foreign, which fits "matter from elsewhere". It costs a rung-2
  dependency in the faces and has a Silk Touch quirk. Recommended: native everywhere, with the floor
  covering the tier.
- **O-5. A small first seam in the Route 1 old mine?** It is the premise in one image, and it decides
  no spawn. It would make an early extra Water face, or a single "something is wrong with this rock"
  seam with no economy role at all.
- **O-6. The Exchange's price, and whether its stock is badge-gated** once badge-gated stock lands.
- **O-7. Filler ore and ambient Rock spawns only at leg 6 and later, plus the Displaced City?** The
  earlier places would rely on the resident alone.
- **O-8. Eevee.** If eeveelutions ever enter the rosters, Water, Thunder and Fire demand rise by one
  each per player, and the Exchange becomes their natural source.

---

## 14. What was built, 2026-09-28

**Built offline, not run in a game and not installed.** All 22 faces at all seven places, and the Exchange; no
site was skipped.

**Files.**
- `data/mines.json` (`cobblers.mines/1`): the geometry rules in words, the keep-clear rules, the restore, the ten
  stones, and seven sites with their faces.
- `tools/mines.py`. `site` and `author` search for boxes and write them into the data; `report` checks; `build`
  writes `build/datapacks/cobblers_mines` and `derived/mines/plan.json`.
- `tools/mines_audit.py`: the offline audit. It never imports the generator. It replays the pack and checks it
  against the data and against other systems' data and output. It is CLEAN (7 sites, 22 faces, 36,693 cells written,
  10 stones on sale). It fails on an empty pack or an empty build. It found each of four planted faults: an
  unfiltered fill, a missing Pokemon guard, a write on the hamlet's plaza, and stray bedrock.
- `tools/reapply.py`: step **R9O**. It runs `cobblers:mines/build_<site>` for each site, after R9S and before R9DC
  and R9E. The step is named from the committed data. The pack is a world-local server pack. `prepare` builds the
  pack, then audits it.

**The faces (box min corner, front).** One cut per face. On the surface each cut is a 3-row apron, then a ramp that
climbs one block a row until it meets the ground, 7 to 9 rows in all, about 300 to 460 blocks dug. It is skinned in
the host rock. The floor is the host's cobbled form.

| Place | Faces | Host / ore | Where |
| --- | --- | --- | --- |
| Viltri Light | Water ×2 | stone / `water_stone_ore` | x568, z4496 and z4530, both facing west, y67-68, on the rise east of the light |
| Tea town | Leaf ×2, Shiny ×2 | stone / `leaf_`, `shiny_stone_ore` | x2628-2673, z3604-3639, y107-108, just south of the town's centre (2654, 3605) |
| The Scar | Sun ×2 | terracotta / `terracotta_sun_stone_ore` | x2079-2088, z964-988, y274 |
| Displaced City | Moon ×2, Thunder ×2 | dripstone / `dripstone_moon_stone_ore`; deepslate / `deepslate_thunder_stone_ore` | the cavern's south wall, box z1850-1855, x3262-3398, y23-28; no digging, the apron is the cavern floor; bedrock skin; two lanterns a face |
| Northlight | Ice ×2 | stone / `ice_stone_ore` | x7302-7326, z1589-1596, y110 |
| Gorge hamlet | Dusk ×2, Dawn ×2 | deepslate / `deepslate_dusk_stone_ore`; stone / `dawn_stone_ore` | x6786-6828, z4288-4317, y107-108, north of the yard |
| Mining Town | Fire ×2, Thunder ×2 | deepslate / `deepslate_fire_`, `deepslate_thunder_stone_ore` | the mine head, round the adit portal: x6734-6767, z5765-5813, y135-139 (data hint `prefer_near`) |

**Where a face may stand.** Ground comes from `tools/ground.py`. For the Displaced City it is the cavern plan's floor.
No face writes on the town's plan (`tools/town_dressing.py` Mask). No face writes on painted water or within 4 of a
painted trunk, or within 8 of a column in `derived/water_shape/changed.npy`. A missing map is a failure. Faces keep
clear of dressing pieces, working Pokemon, and the cavern's trees, lights and tunnel. Viltri Light and the tea town
passed the water rule, sited in rock back from the changing shores.

**Supply as built.**
- Yields: 2-4 ore a restore, Thunder 3-5, Fire 1-3.
- One ore on the front plane's bottom row in every variant; the rest are at least 2 deep.
- 8 variants. The same variant never comes twice in a row.
- Period 12,000 ticks (600 s). The two faces of a stone at a place stay 6,000 ticks apart.
- The drive runs every 100 ticks, and only when a player is in the site's approach box: the faces' bounds plus 64
  across, 32 down and 64 up.
- A restore needs:
  - all four corners of the box, grown by one, loaded;
  - no player and no `cobblemon:pokemon` in that grown box.
- The restore fills host rock over `#cobblers:face_resettable` only. The tag holds air, fluids, hosts, cobble,
  gravel, dirt, snow, torches and the 23 stone ores; it holds no container. Every ore setblock is guarded by the tag.
- No filler ore (O-7).

**The Exchange.**
- `data/traders.json` `mining_assayer` stands on the pithead yard at (6614, 138, 5708), facing south, stock
  `stones`.
- `stock_policy.stones` sells the ten stones at 2,100 each (O-6), with `buys: false`.
- `tools/traders.py` replaces the template's shop with an authored one. Each offer has the shape
  `{Item:{count:1,id},Price:"2100"}`. That is the shape the shopkeeper template itself carries (read from
  `COBBLEVERSE-DP-v31.zip`).
- No stone is in `bank.json`.

**Not built:** the per-player floor (waits on ADR-002's proof), the residents (P-6), filler and Habitat Blocks.

**Must be proven in game:**
- P-1: drop and tier.
- P-2: the restore on approach and its guard, with a player and then a sent-out Pokemon standing in a box.
- P-3: the filtered fill, with a chest left in a box; and no hitch.
- P-4: no double restore across a restart.
- P-7: the Assayer sells all ten stones and buys none.
- P-8: R9O rebuilds the faces on a fresh export.
- A look at each cut, on staging.

---

## Found while checking, outside this design

**The blackout claim ledger is not carried across a re-export. VERIFIED.** `tools/blackout_pack.py`
keeps open claims in `storage cobblers:recovery`, which is the world file
`data/command_storage_cobblers.dat`. `tools/carry_players.py:65-81` carries no command storage.
`docs/mechanics/DEATH_AND_WIPE.md:190-196` requires the recovery store to be "in the explicit re-export
carry manifest". A stone or a ball taken in a blackout before an export would be lost for good after
it. `docs/STATE.md` already lists "re-export carry of the claim ledger" as open under the death and
wipe system. This confirms the open item is real: the carry tool does not do it yet.
