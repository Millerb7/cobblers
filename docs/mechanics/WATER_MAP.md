# The water map: every body of water and its one role

**Status:** proposal, 2026-09-26. The inventory and the allocation were drafted by content-architect, then revised
with the measured air ladder and the owner's rule. A plan, not a build: nothing placed in the water is implemented,
and every allocation marked **Proposal** waits on the owner. Line citations are to commit `cc49349` (main plus the
death/wipe experiments). Facts marked **measured** were probed on staging on 2026-09-26 (`cobblers-dryrun11`): the
depths over RCON, and the air ladder in game (EXP-042). Nobody has yet seen a water spawn in game. The fix that lets
underwater spawns work at depth is in draft PR #61.

**The owner's rule (2026-09-26):** "we can make most lake content accessible underwater for this [Surf] and then all
dive content with dive." Lakes are Surf content; Dive content is the sea.

Stages used below: **S0** before Brock, **S1-S8** after gym N, **L** the League, **P** postgame. The caps are
20/25/30/35/40/45/50/55 (`data/spawns.json:30299`).

## 0. What each rung of the air ladder reaches (measured, EXP-042)

The ladder is built (`cobblers_blackout`, `tools/blackout_pack.py`) and was run in game on 2026-09-26. The rule starts
with the player's eyes **5 blocks** below the local surface; above that, water is vanilla.

| Rung | Air at depth | Measured | What it reaches in practice |
|---|---|---|---|
| **No mount** (S0-S1) | vanilla 15 s, then one hit to half health and a lethal second hit a second later | Run 1: air ran out, 20 → 10 at once; the fix makes the second hit lethal whatever regeneration adds | Surfaces, shores, rivers and shelves. A floor 23-25 deep (Tilpey, the sea at x431 z4943) is a sprint there and back with nothing to spare. The 41-46-deep pits (Arrow, Shrew) are out of reach |
| **Surf** (training after gym 2, with a Surf- or Dive-capable Pokemon in the party) | 45 s held full, then vanilla 15 s, then the same two hits: about 61 s | Run 2: the owner reached **Shrew Lake's floor at y56, 50 blocks down**, spent the whole 45 s bonus there, and still had 216 of 300 air | **Every lake floor in the region**, with time to work: Tilpey 25, the sea deep 23, Arrow 41, Shrew 46-50 |
| **Dive** (training after gym 6, with a Dive-capable Pokemon) | unlimited | Not yet run | Everything: long or enclosed structures, the trench, any depth |

So in practice:
- **Tilpey (25) and the sea at 23:** a no-mount player can touch the floor and come back. They cannot search it.
  With Surf, it is comfortable.
- **Arrow (41) and Shrew (46, 50 where the owner dived):** out of reach without Surf. With Surf they are workable,
  with about 45 s on the floor per dive.
- **Dive** matters where a place is longer or more enclosed than one 60-second breath: a wreck's rooms, a ruin's
  corridors, the trench's descent.

**Measured (EXP-042 session 3):**
- **A sprint-swim is 5 blocks per second,** down 5.0 and up 4.9. So a no-mount player can reach about 37 deep with no
  time at the bottom, and the 41-46-deep pits are out of reach.
- **Dive adds a swim boost the owner chose:** about 10 blocks per second, below Dolphin's Grace. Also ASSUMED: that a player riding a submarine-style mount (Wailmer, Relicanth) does not keep air
underwater (EXP-038 step 2, not run). If they do, that mount bypasses the ladder.

**The design rule this gives:** content on a lake floor is Surf content (S2). Content that needs more than one
breath's worth of time below the surface is Dive content (S6), and in this region that means the sea. A lake floor
never needs Dive, and nothing a no-mount player needs sits more than about 10 blocks down.

## 1. What is already decided

| Item | Where it is recorded | Status | Conflicts and gaps |
|---|---|---|---|
| **Lugia in the Maelstrom Trench** | `docs/STATE.md:54`; `docs/story/ENCOUNTERS.md:392` ("Lugia: the Maelstrom Trench"); `docs/story/FUTURE_SIDE_CONTENT.md:9`; `docs/world-building/STRUCTURE_DECISIONS.md:173` | **Decided** as a location lock. How it behaves (one-time or repeatable, shared or per player) is deferred (`ENCOUNTERS.md:397`) | `OCEAN.md:299` still reads "Lugia, if the legendary recommendation ... is accepted"; it is stale. The gate is contested: see "Lugia's gate" below |
| **The Maelstrom Trench** (set piece, not a route) | `docs/world-building/OCEAN.md:176, 277-309`; `data/regions.json:1117-1140` (`trench_axis` from (9000, 5200) to (6200, 8900), floor y-20 to y-40, south-east border margin) | **Proposal.** `OCEAN.md:5-9` says everything except the re-import is a proposal. No seabed pass, no build. `data/routes.json` has no trench route | `LONG_ISLE.md:238-239` makes the sea town its "natural base" (a hook, out of scope). OCEAN's three door keys come from three shipwreck coves in three marine regions (`OCEAN.md:296-298`) |
| **Lugia's gate** | `OCEAN.md:304-306`: "gated by depth (tier 3) and by the key search, not by a badge ... players can reach it as soon as they can breathe underwater". `DEATH_AND_WIPE.md:329-331` and `:401-403`: "late underwater set pieces such as the Lugia trench still need their own story gates"; "Dive at Gym 6 removes air as a gate everywhere" | Contested | **Conflict.** OCEAN.md also says the trench "stays after the League" (`:305`) without gating it there. Its depth tiers (below) are superseded by the water ladder |
| **The depth ladder** | `docs/mechanics/DEATH_AND_WIPE.md:30-37` (rules 8-10), `:250-261` (depth starts 5 blocks below the local surface), `:310-331` (Surf from Misty after `gym2_cleared` at Lake Viltri; Dive from a glacial survey diver on Tilpey's north shore after `gym6_cleared`) | **Approved direction** (`DEATH_AND_WIPE.md:3-5`); nothing implemented. ADR-005 (Proposed) picks datapack plus MoLang | **Conflict:** `OCEAN.md:237-242` gates depth by Respiration and turtle shells (tier 1), Water Breathing potions after gym 7 (tier 2) and conduits (tier 3). Those vanilla items would bypass the ladder, and DEATH_AND_WIPE does not mention them. **Gap:** `docs/story/ARC.md:255-298` (Misty) and `:452-490` (Sabrina) have no Surf grant, no "lake-rescue chapter" and no survey diver. `data/progression.json` has no Surf or Dive field |
| **Who can carry you on or under water** | `experiments/EXP-038-riding-capability/README.md:22-28` | **VERIFIED as static data** (45 Surf species, 10 Dive species); the in-game steps are not run (`:63-64`) | `LONG_ISLE.md:149` still says water riding is "NOT VERIFIED" and that the water mounts "have not been read"; EXP-038 has since read them |
| **Legendary tiering** | Not found as a document. The nearest is `docs/STATE.md:54` with `FUTURE_SIDE_CONTENT.md:9` and `STRUCTURE_DECISIONS.md:171-185`, which together give three tiers: **A** bespoke (Lugia, the three Regis, Regigigas, Groudon, the Celebi sapling); **B** "paste a compatible structure into a fitting biome and gate it by badge count", "without a bespoke altar chain or shrine puzzle"; **C** not placed ("roaming, event or mythical mechanics that need their own systems") | A and B **decided**; C a recommendation | The owner's "legendary tiering" may be a document I cannot reach. **Finding:** it is in no file in this repository or its worktrees |
| **Manaphy and Phione as appearing-island candidates** | Not in the repository. `STRUCTURE_DECISIONS.md:185` parks both in tier C | **Idea** (the owner's brief) | They have **no client model today**: both are among the 40 species that lost their only assets with ATMxMSD RP (`docs/research/COBBLEVERSE_COMPATIBILITY.md:108-109`). The fix is built but blocked on that pack's licence (`docs/STATE.md`, "Client models") |
| **The Dive reef near Relic Island** | Not in the repository. The only related records are the Southern Shallows' planned "reef habitats and warm ocean ruins" (`data/regions.json:794-797`) and coral as a spawn requirement (`OCEAN.md:222-224`) | **Idea** (the owner's brief) | Relic Island (1092, 5532), with seabed y35 (`docs/world-building/SETTLEMENTS.md:188`), and the First Cast jetty at x1049-1057 z5347-5351 (`docs/world-building/EARLY_ROUTES.md:136`) both lie **outside** the authored `windward_sea` box (x ≤ 991, z ≤ 5215; `data/spawns.json:30287-30292`), in the Southern Shallows. That sea has no authored roster |
| **Codex's gated-interactions spec** | `docs/decisions/ADR-004-pocket-spaces.md:9-10`: "The spec is not in this repository" | ADR-004 is **Accepted**: carve in place what the fiction puts "right there"; use a pocket dimension only for spaces that are really elsewhere; the western-ocean grid of chambers is dropped (`:28-35`) | The spec itself is unavailable, so no Strength or boulder rule can be cited from it |
| **The western sea's rosters** | `data/spawns.json:30281-30300`; `docs/STATE.md:147-150` | **Decided and compiled; not installed, not seen in game** | The owner: "a player on Route 1 for the first time can't swim without a surf mon" (`spawns.json:30298`) and "i dont think it should be magikarps and small frys" (`STATE.md:147`). **Conflict:** `ENCOUNTERS.md:367` still says the open ocean outside authored sites retains the pack's defaults, and `STATE.md:139` records the same suppression-versus-policy contradiction for lakes |
| **Lake rosters, with rare fish in the deep** | `docs/STATE.md:137-146` | Compiled; not seen in game | The owner: the lakes "spawn nothing or just surskits near the edges" (`:137`); Dratini is "the good find in the deep ... 'some good spawns deeper'" (`data/spawns.json:9562`). Rare Dratini, Relicanth and Dondozo are awaiting the owner's review (`STATE.md:146`) |
| **Water in the story** | Lake Viltri: sounding, north bank and Lake Surveyor built on staging (`EARLY_ROUTES.md:138-139`; `EARLY_ROUTE_BUILD_HANDOFF.md:244`), and `SQ-G2-01` surveys its floor at y75.1 (`docs/story/SIDEQUESTS.md:82-92`). `SQ-G2-02` Viltri's Path (`:94-103`). The tarn: `SQ-G4-01` and `SQ-G4-03` (`:122-159`). Shrew Lake: `SQ-DIG-02`, a surveyor lost there (`:599-607`). Marshy Marsh: `SQ-G6-01` (`:188-198`). Tilpey: `SQ-GORGE-01` (`:445-454`). Sunset West: `SQ-SUNSET-01` (`:293-303`). The Wooper pond on Route 3 (`STATE.md:69`) | Story source, not built (except the Route 2 and Route 3 stops, on staging) | `ARC.md:664-665, 671`: Relic Island, Viltri Light and Sunset West must never gate the critical path |
| **Other water already in use** | Rods: First Cast gives the Poké Rod and better rods go "at other waters" (`STATE.md:57, 94`). Water Stone at Viltri Light (`EVOLUTION_STONES.md:108`). The major river is a barrier crossed by bridge (`data/landmarks.json:6222-6225`; `ARC.md:484`). Victory Road's Drowned Gallery holds Milotic (`STATE.md:211`). The sea town Pacifidlog is built on staging in the Sound (`STATE.md:166`). The Weeping Elder stands on a Tilpey island (`STATE.md:74`). The Shrew Lake tea grower is parked (`FUTURE_SIDE_CONTENT.md:3-5`) | Decided or built on staging, as cited | none |
| **Name collision** | "Windward Deep" is both the marine region (`data/regions.json:494-495`, `OCEAN.md:124`) and the Rift's terraced pit (`STATE.md:180`) | — | **Conflict:** one of the two needs renaming |

## 2. The water inventory

Depth is the measured surface y and the deepest of 10 sampled points, unless it is marked as a landmark figure. "Now"
means what exists or compiles; nothing underwater is built anywhere.

### Lakes, ponds and the tarn

| Body | What it is | Surface, depth | In it now | Could carry | What gates it; stage | Route |
|---|---|---|---|---|---|---|
| **Lake Viltri** (1654, 3004) | Misty's lake, a 30-deep closed basin at the head of Viltri's Path (`landmarks.json:1977`) | y103, 27 | Barboach, Chinchou, Goldeen, Magikarp; Surskit. Levels 18-21. Sounding, north bank, Lake Surveyor (staging) | Surf lesson; floor survey (`SQ-G2-01`); a cache | Wading from S1; depth needs Surf (S2) | On Route 2's end (Misty's town, 86 blocks) |
| **Shrew Lake** (2873, 3988) | A 52-deep pit in the cherry vale (`landmarks.json:2149`) | y106, 46 (the deepest lake) | Barboach, Dratini (rare, deep only), Goldeen, Magikarp; Surskit. Levels 10-22 | Deep find; the lost surveyor's case (`SQ-DIG-02`); a cache | Swimming from S0; the floor needs Surf time or Dive | Off Route 2 by 385 blocks (`docs/story/AVAILABILITY.md:861`) |
| **Arrow Lake** (2711, 4613) | A 46-deep pit (`landmarks.json:2433`) | y100, 41 | Arrokuda, Barboach, Goldeen, Relicanth (rare, deep); Surskit. Levels 10-22 | Mesprit's grotto (decided: in the lake) | Swimming from S0; the deep needs Surf | Off Route 2 by 721 (`AVAILABILITY.md:874`) |
| **Pond west of Mt Clay** (2080, 1733) | Unnamed closed basin; the Route 3 Wooper pond (vertex (2204, 1580), `landmarks.json:2802-2803`) | y119, 18 | The foothill_woods roster; the Wooper stop (staging) | Nothing more: "players are not sent back to this pond" (`STATE.md:69`) | None; S2 | On Route 3 |
| **Ravine Head Tarn** (3286, 938) | Hollow at the head of the dry ravine; drains north (`landmarks.json:2939`) | y127, 4 measured. The landmark gives 23 deep (floor y105, spill y128.3): the samples may have missed the middle | The Peak Pond Hollow roster reaches it (`spawns.json:7096`) | Story evidence only (`SQ-G4-01`, the Sentinel `SQ-G4-03`) | None; S3-S4 | Off-route, Erika's quest |
| **Peak Pond** (4018, 1448) | Erika's pond, a 20-deep basin in the northern downs (`landmarks.json:1777`) | y105, 18 | Barboach, Basculin, Goldeen, Gyarados, Magikarp, Whiscash. Levels 30-32 | A cache; fishing | Swimming; S4 | At Route 4's end (Erika's town) |
| **Marshy Marsh** (5158, 2166) | A 38-deep pit ringed by swamp, "not a shallow wetland" (`landmarks.json:3188`) | Not measured this session (spill y101.6) | Whiscash; Dondozo ultra-rare. Levels 34-44 (`spawns.json:7712-7772`). Marsh foliage on staging | Azelf's grotto (decided: in the lake); `SQ-G6-01` | Swimming; S5 | Off Route 5 (311 blocks from Koga's town, `ARC.md:417`) |
| **Lake Tilpey** (5964, 4135) | The largest lake, a closed basin at the glacier's end with two islands (`landmarks.json:1297`) | y77, 25 | Arrokuda, Barraskewda, Basculin, Basculegion, Dondozo, Goldeen, Gyarados, Magikarp, Seaking; Surskit, Masquerain. Levels 39-48 | The Dive school; the Weeping Elder island | Swimming; the Dive school after S6 | Sabrina's town, north shore; Route 7 crosses its outflow |
| **Watering Hole** (2983, 5273) | A small 14-deep basin on the Arrow Lake creek (`landmarks.json:2609`) | y95, 9 | The arrow_creeks roster | Fishing water; a rod find | None; S7-S8 | Off Route 8 by 377 (`AVAILABILITY.md:860`) |
| **Drowned Gallery**, Victory Road | The cave's lake, all of it inside Drowned tiles (`STATE.md:211`) | Not measured | Milotic, submerged, as the zone's prize (staging) | Nothing more | The Victory Road gauntlet; L | On the critical path |

### Rivers (from `data/landmarks.json`)

| River | What it is | In it now | Could carry | Gate; stage | Route |
|---|---|---|---|---|---|
| **Major river**, Glacial Tear to the east coast (`:6125-6226`) | 2,618 blocks; a meltwater creek, then 18-32 wide and up to 9 deep; role `barrier` | Tilpey system rosters | Nothing underwater (9 deep at most); crossing only | A bridge at (6632, 3904) (`ARC.md:484`); S6-S7 | Crossed by Route 7 |
| **Viltri's Path** (`:3392-3545`) | Lake Viltri's real outflow to the north-west coast; 1,711 blocks, 4-10 wide, 1.4-2.9 deep | Nothing authored | An optional water road from Misty's lake to the sea (`SQ-G2-02`) | Vanilla (shallow, `DEATH_AND_WIPE.md:30-31`); S2 | Off-route |
| **Mouth of Viltri** (`:3547-3551`) | Estuary outline; the channel ends at y65, above the sea | Viltri Light stands over it | Story evidence (`SQ-G1-01`); Water Stone cut (`EVOLUTION_STONES.md:108`) | None; S0-S1 | Off Route 1 |
| **Arrow Lake creek** (`:5143-5147`) | Arrow Lake through the Watering Hole to the south coast | arrow_creeks roster | Nothing (the creek quest, `SIDEQUESTS.md:243`) | None; S0 onward | Off-route |
| **Marsh outflow** (`:6045-6049`) | 395 blocks, 2.1 deep, to the north-east coast | Marsh roster | Nothing | None | Off-route |
| **Tilpey south-west inflow creek** (`:5536-5540`) | An inflow creek | Tilpey rosters | Nothing | None | Off-route |
| **River of Shrews** (`:3610-3614`) | "Not a river": an uncut canal proposal | No water | Nothing | — | Route 1 passes its vale |

### The sea

| Band or region | What it is | In it now | Could carry | Gate; stage | Route |
|---|---|---|---|---|---|
| **Windward shallows**, 0-96 blocks from land (`spawns.json:30303-30311`) | The shelf; 1-3 deep near Route 1 (x903 z5175, measured) | Levels 16-20: Tentacool, Wingull and others; compiled, not installed | Fishing, shore finds | Swimming; S0 | Route 1's coast |
| **Windward open water**, 96-256 (`:30536-30544`) | The slope | Levels 20-25: Wailmer (uncommon) and others | A travel lane to Viltri Light; a sunlit fishing-boat wreck (`OCEAN.md:267`) | A surface mount (not gated in data, `STATE.md:149`); S1-S2 | Off-route |
| **Windward deep**, 256 to the border (`:30801-30809`) | The basin; 23 deep at x431 z4943 (measured) | Levels 25-30: Wailmer, Relicanth, Dhelmise; Lapras on the surface | Shipwrecks on the slope (`regions.json:549`); the submerged forge ruin (`STRUCTURE_DECISIONS.md:125`); the ocean monument (not a template, `OCEAN.md:320`) | Distance plus a mount; the interiors need Dive; S2 surface, S6 underwater | Off-route |
| **Southern Shallows** (`regions.json:739-797`) | The warm south, including First Cast, Relic Island and the Sound | No authored roster around Pallet. Relic Island islet and First Cast jetty; Pacifidlog on staging | Coral reefs (the Corsola home, `OCEAN.md:222-224`), buried treasure, the Relic Island Dive reef | Swimming at the shore; Dive at depth; S0 to S6 | Route 1's coast; Route 7 near the Sound |
| **Frostwater Shelf** (`regions.json:272-335`) | Cold north | Nothing authored | Iceberg habitats, cold ruins, a lush shipwreck cove (a Lugia key) | Dive; S6 onward | Off-route |
| **Eastern Reach** (`regions.json:621-676`) | The lukewarm sea lane | Nothing authored | Wrecks, warm ruins, a submerged shipwreck cove (a Lugia key, `OCEAN.md:269`) | Dive; S6 onward | Off-route |
| **Outer Deep** (`regions.json:1045-1168`) | 512-1024 blocks out, to the border | Nothing authored | The trench; the magma cove (a Lugia key); seamounts | Dive plus the key search; P | Off-route |

The marine regions' extents predate the 2026-09-14 coastline and have not been re-measured (`regions.json:1171`,
`OCEAN.md:3`).

## 3. Allocation

**Proposal.** Each body of water gets one role. A role may carry several small things, but only one kind of gate
and at most one set piece.

| # | Body | One role | Set piece or legendary | Gate | Stage |
|---|---|---|---|---|---|
| 1 | Windward shallows | The first sea: fishing and shore finds | none | Swimming | S0 |
| 2 | Southern Shallows, Pallet coast | First Cast and Relic Island's surface (decided) | none | Swimming or a boat | S0 |
| 3 | Windward open water | The first ride: a lane to Viltri Light; one sunlit wreck | fishing-boat wreck (a cache) | A surface mount | S1-S2 |
| 4 | Lake Viltri | **The Surf school**: Misty's training, the sounding, the floor survey | none | Surf (S2) for the floor | S1-S2 |
| 5 | Viltri's Path | The water road to the sea | none | none (shallow) | S2 |
| 6 | Shrew Lake | **The dragon's pit**: deep Dratini, the lost surveyor's case on the floor | none | Surf (measured: its floor is reachable) | S2 |
| 7 | Arrow Lake | **Mesprit's grotto**, the first of the lake trio, under the lake | Mesprit | Surf, and 3 badges | S3 |
| 8 | Mt Clay pond | The Wooper stop (decided) | none | none | S2 |
| 9 | Ravine Head Tarn | Story evidence (the channel, the Sentinel) | none | none | S4 |
| 10 | Peak Pond | Erika's pond: fishing water and the tarn's story (no legendary; the trio moved) | none | none | S4 |
| 11 | Marshy Marsh | **Azelf's grotto**, the second of the trio, under the 38-deep pit | Azelf | Surf, and 5 badges | S5 |
| 12 | Lake Tilpey | **Uxie's grotto**, the last of the trio, under the glacial basin. The Dive school stays on the north shore as a teaching post; the lake's own content is Uxie (the one exception to one role per body, see below) | Uxie | Surf, and 7 badges | S7 |
| 13 | Major river and the other creeks | Barrier and scenery; nothing underwater | none | A bridge | S6-S7 |
| 14 | Relic Island reef, Southern Shallows | **The Dive reef**: coral, Corsola, a reef cache | reef cache | Dive | S6 |
| 15 | Windward deep | **The far water**: Lapras and Wailmer; the forge ruin | forge ruin; the only Strength room, if Strength exists | Distance; Dive inside | S2 / S6 |
| 16 | Frostwater, Eastern Reach, Outer Deep coves | **Lugia's keys**: one cove each | three coves | Dive | S6+ |
| 17 | Watering Hole | Fishing water: a rod find | none | none | S7-S8 |
| 18 | The Sound (Pacifidlog) | The fishing town; base for the trench | none | none | S7 |
| 19 | Victory Road's Drowned Gallery | Milotic's lake (built) | Milotic (not a legendary) | The gauntlet | L |
| 20 | Outer Deep trench | **Lugia** | Lugia | Dive, three keys, `champion_cleared` (**decided**) | P |
| 21 | Appearing island, off Sunset West | **Manaphy and Phione** | both | A postgame event | P |

### Lugia, the Maelstrom Trench

Keep the decided site and OCEAN's descent: three air-pocket chambers, a flooded shrine, three door keys from three
coves. **Proposal:** add `champion_cleared` as the story gate. Two reasons:

- the depth tiers no longer gate it once Dive arrives at gym 6 (`DEATH_AND_WIPE.md:401-403`);
- a Lugia met at the gym-6 cap is either too weak to matter or a level-cap trap (`STATE.md`, "The level-cap trap").

The keys stay findable earlier, so the search can start before the League. The sea town is the base. Nothing
else in the trench.

### The lake trio: Mesprit, Azelf and Uxie (decided: in the lakes, at three stages)

**The owner, 2026-09-26:** "Put Mesprit, Uxie and Azelf IN the lakes. A scavenger hunt across three bodies of water is
the point ... three lakes, one each, and at DIFFERENT stages of the journey ... one early, one mid, one late."

| Order | Lake | Legendary | Stage (badge gate) | Why this lake |
|---|---|---|---|---|
| Early | **Arrow Lake** (2711, 4613), 41 deep | **Mesprit** | 3 badges, soon after Surf (gym 2) | The nearest deep lake to the start (off Route 2): a player sees it before they can use it. At 41 deep it is out of reach without Surf (section 0), so the first find is also the first reason to use the new training. Mesprit is Sinnoh's lake nearest the start |
| Mid | **Marshy Marsh** (5158, 2166), 38 deep | **Azelf** | 5 badges, around Koga | A true pit, "not a shallow wetland" (`landmarks.json:3188`), off Route 5 in the middle of the game. It is the region's strangest water, which suits the willpower legendary |
| Late | **Lake Tilpey** (5964, 4135), 25 deep | **Uxie** | 7 badges, after Blaine | The glacial basin, as Uxie's Lake Acuity is Sinnoh's frozen lake. Sabrina's and Blaine's towns sit either side of it, and Route 7 crosses its outflow, so a player passes it twice: once on the way to Blaine, and once to come back with the seventh badge |

Rejected: Peak Pond (18 deep, so a player with no mount can nearly reach its floor, and it would not be Surf content);
Shrew Lake (the dragon pit already has its one role); Lake Viltri (the Surf school).

**How each one is met:** in a **flooded grotto under the lake floor whose inner chamber holds air**. A legendary battle
lasts minutes, and Surf gives about 61 seconds at depth (section 0). A legendary met in open water could only be
fought with Dive, which would make the trio Dive content. So the player dives with Surf, finds the grotto's
mouth on the floor, swims up into the air chamber, and fights there. This is carving in place, as ADR-004 allows.
Whether a battle pauses the air timer is not known and should be tested (it would not change this plan).

**The badge gate** makes the stages hold in an open world: the legendary is present only for a player with enough
badges. That uses the badge flags `cobblers_progression` already sets. Shared or per player is an open decision.

**Tilpey's exception:** Uxie and the Dive school share the lake. They do not compete: the school is a teaching post on
the north shore and sends the player to the sea, Uxie's grotto is in the lake, and the lake needs no Dive (25 deep,
Surf-reachable).

**For Codex (the arc):** three legendaries hidden under three lakes is story material, not three encounters with no
context. The questions are what they are, why they are here, and whether anyone in the world knows. A line in
`docs/story/ARC.md` should answer them. For example: someone at Viltri Light or the Lake Surveyor knows the old
three-lakes story, and each grotto holds a trace tied to the Worldshift. The owner asked for this; it is not yet
written.

### Manaphy and Phione, the appearing island

**Proposal:**
- **When:** postgame.
- **Where:** off Sunset West, the "post-game port and stories from the outer sea" (`ARC.md:671`; `SQ-SUNSET-01`
  already charts the outer sea).
- **What:** one site holding both species: Manaphy once, Phione repeatable.

Two blockers: the mechanism (below) and the missing client models. Not the Relic Island reef: that stays a Dive
cache, so the start area is not also the mythical site.

### The Surf school and the Dive school

Lake Viltri and Lake Tilpey host the two unlocks, as `DEATH_AND_WIPE.md:312-322` decides. Each is a school and
nothing else: no shrine, no crevice. Tilpey's floor is the Dive practice ground (25 deep).

### The forge ruin and the only Strength room

The planned submerged forge ruin in the windward deep (`STRUCTURE_DECISIONS.md:125`) gives the ocean bands a
destination. **Proposal:** if and only if a Strength mechanism is found, its inner room is the one underwater
Strength crevice in the game, holding a cache and never a legendary.

### Balance check (all proposals)

| Kind | Count | Where | Stages |
|---|---|---|---|
| Shrines on land | 1 | The trench's flooded shrine (Lugia) | P |
| Water legendaries and mythicals | 6 species at 5 sites | Mesprit (Arrow Lake), Azelf (Marshy Marsh), Uxie (Lake Tilpey), each in an air-chambered grotto; Lugia; Manaphy and Phione | S3, S5, S7, P, P |
| Dive-required sites | 7 | The Tilpey school, the Relic reef, the forge ruin, three coves, the trench | all S6 or later, by construction |
| Surf depth sites | 6 | The Viltri floor survey, the Shrew pit (Dratini, the surveyor's case), and the three trio grottos (Arrow, Marshy Marsh, Tilpey) | S2-S7 |
| Strength crevices | 0 or 1 | The forge ruin, only if Strength exists | S6 |
| Bodies with nothing added | 9 | Mt Clay pond, the tarn, Watering Hole, all rivers, the shallows | — |

Spread by stage: S0 (the sea, Relic Island's surface); S2 (the Surf school, Mesprit, the Shrew pit, the first ride);
S3 (none: Route 3 climbs a mountain); S4 (Uxie, the tarn); S5 (Azelf); S6 (the Dive school, then the reef, forge
ruin and coves); S7 (the Sound); L (Milotic); P (Lugia, the appearing island).

Dive content is back-loaded. That is a direct consequence of Dive at gym 6, and the Surf-time sites are what keep
the middle game wet. No body carries more than one gate kind, and none carries a shrine together with Dive or
Strength. The trench combines Dive and keys, but the keys are its whole puzzle.

## 4. The owner's questions

1. **Which legendaries live in water, where, and how are they reached?**
   - Lugia in the SE trench: Dive, three cove keys, and (proposed) `champion_cleared`.
   - Manaphy and Phione on the appearing island off Sunset West, postgame (proposal).
   - Mesprit, Azelf and Uxie under Arrow Lake, Marshy Marsh and Lake Tilpey, in air-chambered grottos reached with
     Surf, gated by 3, 5 and 7 badges (decided: in the lakes, one early, one mid, one late).
   - Kyogre and Suicune stay unplaced (`STRUCTURE_DECISIONS.md:85, 182`).
2. **Which water needs Dive, and which is reachable by Surf or swimming?**
   - Swimming: every surface, every shore, every river, and the top 5 blocks of any lake or sea
     (`DEATH_AND_WIPE.md:243-261`).
   - Surf (about 61 s at depth, measured in EXP-042): **every lake floor**, the Shrew pit included. The owner
     reached its floor at 50 deep with most of a breath to spare.
   - Dive: only the sea's long or enclosed places: the reef, the forge ruin, the coves and the trench.
   - Open sea beyond the shallows needs a ridden mount (the owner, `spawns.json:30298`); that is not the Surf unlock.
3. **Where do shrines go, if at all?** On land beside water, never underwater: the trench's flooded shrine
   (decided). The lake trio are not shrines: they wait in air-chambered grottos under their lakes. No shrine in a river, the ocean bands or the Dive schools.
4. **Where does an underwater Strength crevice make sense?**
   - At most one: the windward forge ruin's inner room, a cache.
   - Never at a legendary, a school or on the critical path.
   - UNKNOWN whether any Strength mechanism exists (section 5).
5. **What are the ocean bands for, beyond spawn levels?**
   - Shallows: the first sea (First Cast, shore finds).
   - Open water: the first ride and the lane to Viltri Light's Water Stone, with one sunlit wreck.
   - The deep: the mount reward (Lapras on the surface, Wailmer), the slope wrecks and the forge ruin, which is the
     reason to come back with Dive.
   - The other marine regions carry Lugia's three coves, the reef and the appearing island.
6. **Does any place stack a shrine, Dive and Strength?** No. That is the allocation's one rule. The trench is Dive
   plus keys, and its shrine is the reward, not a second gate.

## 5. Blocked by unbuilt systems

| System | Waits on it | What in the repo would build it |
|---|---|---|
| **The water ladder** (Surf and Dive unlocks, the depth rule, harsh drowning) | The unlocks' story events only | **Built** (`tools/blackout_pack.py`, `cobblers_blackout`). No-mount air and Surf are verified in game (EXP-042); Dive is not yet run. The training is granted by `cobblers:water/grant_surf` and `grant_dive`: Misty's and the survey diver's story events must call them, and they are not written. `data/progression.json` has no Surf or Dive field |
| **In-game riding proof** | Every "a mount" gate | EXP-038 steps 1-3, not run (`README.md:52-59`). **UNKNOWN:** whether a ridden submarine mount (Wailmer at 20-25, Relicanth before Brock) keeps its rider underwater with air. If it does, the ladder is bypassed from S1. `OCEAN.md:253-255, 367` (EXP-015) asks the same question |
| **Underwater spawns at depth** | Dratini, Relicanth, Dondozo, the deep band | Draft PR #61; the owner's spawn observation (EXP-035). Not seen in game |
| **Seabed pass, coral, wreck and cove placement** | The reef, wrecks, coves, trench, forge ruin | Specified in `OCEAN.md` §4-5, not built. No tool: `tools/` has `islet.py`, `waterways.py` and `grade_rivers.py` only. Coves and the monument need capture and jigsaw flattening (`OCEAN.md:318-333`) |
| **Authored legendary encounter** | Lugia, the trio, the appearing island | EXP-006 static encounter, planned (`docs/research/EXPERIMENT_BACKLOG.md:14`). `spawnpokemonat` does work inside a function, from the tick loop too (EXP-042, contradicting the older `STATE.md` line), so an authored spawn can be a function. Whether pasted LumyMon altars work without structure data is UNKNOWN |
| **The appearing island** | Manaphy and Phione | Nothing exists. ADR-004 allows block swaps carved in place (shared world state) or a pocket dimension. Also blocked on the client models (ATMxMSD licence) |
| **A Strength mechanic** | The forge ruin's inner room | None found. No record in `docs/research/` or `base-pack/inventory/`. EXP-038 lists MoLang `has_learned` (`README.md:36`), which could check a party move (ASSUMED). Route to `cobblemon-researcher` |
| **Keys and caches** | Trench keys, reef and wreck caches, rod finds | ADR-002 (Proposed) with `data/rewards.json` and `tools/rewards_pack.py`, proven only as static files for Victory Road's five finds |
| **NPCs and trainers** | Misty's Surf grant, the survey diver, the Shrew surveyor, the Sound's divers | `tools/compile_dialogue.py` exists; no dialogue is written. Trainer work is paused (`STATE.md`, "Custom leaders") |
| **Marine rosters outside the west** | The Pallet coast, the reef, the Sound | None. Only `windward_sea` exists (`spawns.json:30281`). Owner: `datapack-content-dev` |
| **Vanilla air items** (Respiration, turtle shells, Water Breathing, conduits) | The integrity of the ladder | Undecided (decision 6). ASSUMED to bypass it |

## 6. Open decisions for the owner

1. **The lake trio.** *Decided* (the owner, 2026-09-26): in the lakes, not on the shore, one early, one mid, one late.
   Proposed: Mesprit at Arrow Lake (3 badges), Azelf at Marshy Marsh (5) and Uxie at Lake Tilpey (7), each in an
   air-chambered grotto. Still open: shared or per player, and the arc line (for Codex).
2. **Lugia's gate.** *Decided* (the owner): Dive **and** `champion_cleared`. "It is the deepest thing in the world
   and it should not be reachable before the League." 
3. **The appearing island.** Postgame, off Sunset West, holding Manaphy and Phione, as shared world state. *Recommend:*
   yes, and build nothing until the client models and EXP-006 land.
4. **The Relic Island reef.** A Dive reef in the island's deeper water (seabed y35), with a sunlit edge visible from
   S0 as a hook. *Recommend:* yes, as a cache and the Corsola home, not a legendary.
5. **Strength.** *Recommend:* research first; with no mechanism, no crevices; with one, only the forge ruin.
6. **Vanilla air items.** *Decided* (the owner): removed. "A mount-gated system with a potion bypass is not
   gated." The cost was checked and is low:
   - Respiration's whole effect is data, so it is overridden to nothing with nothing to apply it to;
   - Water Breathing and Conduit Power are cleared the tick they land, with a one-time message;
   - no mod grants either effect in code;
   - seven mod loot tables can still roll a now-useless Water Breathing potion.

   Built in `cobblers_blackout` (EXP-042).
7. **The name collision.** *Recommend:* rename the marine region to "the Windward Sea", the display name
   `spawns.json` already uses, and keep "the Windward Deep" for the Rift pit.
8. **Shrew Lake's floor.** *Settled by measurement:* Surf reaches it (EXP-042 run 2, 50 deep), so the surveyor's case
   can lie on the floor and `SQ-DIG-02` is Surf content. No ledge is needed.
9. **Rosters for the southern sea.** *Recommend:* author a Southern Shallows marine zone around Pallet and Relic
   Island before the reef is built.
10. **Kyogre and Suicune.** *Recommend:* leave them unplaced.
