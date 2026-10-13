# Legendary homes in the overworld: rare spawns, area bosses and the cave kit

**Status: PROPOSED design (content-architect, 2026-10-12). Built offline the same night, by the CAVE-KIT unit: the cave kit (`tools/caves.py`,
`tools/caves_audit.py`, `data/caves.json`) and its first three caves, K1 Stoneford Cut, K2 The Singing Hollow and K3 The Relay Fault, with
the area-boss keeper for Miraidon (contract C25). Generated and audited offline; NOT installed, NOT applied (step R9CK), NOT seen in game.
The owner's decisions of 2026-10-12 that this build follows: Koraidon and Miraidon are post-Champion area bosses; Dialga goes to K5;
Tapu Fini is a repeatable chamber spawn (K4); the boss respawn rule and the rarity targets as proposed. Everything else here is still
proposed: K4, K5 and K6, the world rare spawns (section 2), the inherited-spawn suppression of finding 2 (Meloetta's DP spawn is
therefore still live), and the experiments of section 6 (RS-1, AB-1 and HB-1 decide whether K2's and K3's chambers behave as designed).**
The owner, 2026-10-12: "It might be cool to make some of them world spawns that are very rare, and make some of them
bosses in areas. I also would like more caves built out near towns or randomly placed that could have a room where
these creatures could be found." Decided by the owner the same day: a wild legendary is **repeatable**, rarity its only
limit; an area boss is a **catchable native alpha** at a landmark, fought at the area's top level, ordinary balls (the
Beast Ball key is dungeon-only, `docs/STATE.md:156`); the first pass is **6-8 caves** from a reusable **cave kit**.

**Built so far (2026-10-12, datapack-content-dev; generated and tested offline, not installed, not seen in game):**
- Unit 6, part: `data/spawn_suppression.json` `managed_species` switches off the five inherited DP spawns (Meloetta, Tapu
  Fini, Nihilego, Buzzwole, Pheromosa) through the existing `tools/suppress_inherited_spawns.py` mechanism (each of the
  five lives alone in its own DP file, so each is re-emitted `"enabled": false`).
- Buzzwole and Pheromosa are rare world spawns (`data/encounter_design.json` `rare_spawns`, expanded by
  `tools/build_encounters.py`) **on `long_isle_south`, not on `jungle_west` / `jungle_east`**: those two sub-regions are
  under the sea (`docs/STATE.md`: every column in the Jungle Isle polygon at or below y61, sea level y62), so their
  tier-8 tables spawn on no land. `long_isle_south` is the same tier and theme. Weight 0.05, ultra-rare, level 55 (the
  cap after gym 7), `model_gate: atm_subset`. Reverse by changing `table`.
- **Nihilego has NO home yet.** "The outer sea bands" do not exist: `data/spawns.json` `marine_zones` holds one zone, the
  Windward Sea (levels 16-30), and no tier-9 table has water. Its inherited spawn is off; it stays in the Cistern's pool.
  Needs the owner (a new marine band, or a tier-8 water body such as the Long Isle's jungle water).
- Registeel's "blocked" lines corrected (finding 1), the bucket weights corrected in `ENCOUNTER_DESIGN.md` (finding 4),
  and R14L made safe to re-run (look-then-act chain, `tools/legendaries.py`; `tests/test_legendaries_rerun.py`).

Labels: *read* = read at the cited line this session; *relayed* = taken from a document and not re-measured;
*ASSUMED* = no source; each ASSUMED item is an experiment in section 6.

---

## 0. Findings that change the brief

1. **Registeel is not blocked.** `data/legendaries.json:345` has `status: "sited"` with portal (4195, 3896) on the
   upper Rift (`:358-361`, `:367-380`), `docs/STATE.md:263` counts it among eight sited chambers, and
   `docs/REPORT_2026-09-30_DAY.md:64` records R14L placing it. The record still carries `blocked_by` (`:347`), and the
   roster (`data/dungeon_prize_roster.json:289`), `docs/mechanics/LEGENDARY_COVERAGE.md:29` and
   `docs/mechanics/LEGENDARIES.md:24` still say blocked. It needs no home. The stale lines should be cleaned up (the
   data owner's job). The final check against the built Rift plan (`legendaries.json:349`) has not been done.
2. **Five of the "unhomed" species already spawn wild today, uncurated.** COBBLEVERSE-DP spawns Tapu Fini
   (ultra-rare, 50-70, rivers), Meloetta (**rare** bucket, 50-55, sunflower plains), Nihilego (ultra-rare, 60-78,
   ocean), Buzzwole (ultra-rare, 60-70, jungle) and Pheromosa (ultra-rare, 55-65) wherever the bounded suppression does
   not reach (`docs/research/notes/unhomed-legendaries-1.8.0.md:36-45`, rows `:113, :130, :210, :213, :214`, relayed).
   They are above every pre-Champion cap, so they cannot be caught. Our suppression removes only the 22 species in
   `data/spawn_suppression.json:50-56` (the paradoxes plus Koraidon and Miraidon). **Any home given below must also
   remove that species' inherited spawn.** Otherwise the curated home has an uncatchable rival and the "one home each"
   rule (`dungeon_prize_roster.json:5`) is already broken.
3. **The alpha flag makes a pre-Champion legendary boss uncatchable.** When a player is within 32 blocks, a wild alpha
   re-levels to that player's highest party level plus 4/8/12/16/20, capped at 100. The owner kept this on 2026-10-05
   (`docs/mechanics/ENCOUNTER_DESIGN.md:360-377`, read from bytecode, relayed). `cobblers_levelcap` breaks any ball,
   the Master Ball included, on a Pokemon strictly above the thrower's cap (`docs/mechanics/CELEBI_WAKE.md:90-92`). A
   party at cap 60 meets a level-76 alpha that cannot be caught (`docs/research/notes/legendary-species-1.8.0.md:109-112`,
   relayed). The owner's "catchable native alpha" therefore works **only after the Champion** (cap 100, at which the
   alpha is clamped to 100). Section 3 uses that.
4. **The bucket weights in `ENCOUNTER_DESIGN.md:84-85` are stale.** It quotes 88.5/10/1.2/0.3, which is the base pack's
   v1 file (`base-pack/cobbleverse/config/cobblemon/spawning/best-spawner-config.json:9-26`). The server runs the v2
   file: world buckets common 94, uncommon 5, rare 0.5, ultra-rare 0.2, boss 0.3; activated Habitat Blocks
   83.25/11.25/4.125/1.375 (`server/config/mods/cobblemon/spawning/best-spawner-config.json:9-15, 28-33`, read).
   This doc uses the v2 numbers.
5. **Two dangling references.** `data/dungeons.json:1601` cites `data/heatran_boss.json`, which does not exist (glob,
   2026-10-12). Yveltal is the Patriarch's `boss_legendary` in the roster (`:91`), but no line of `data/dungeons.json`
   names it (grep).
6. For the unit placing the Tapus: `dungeon_prize_roster.json:235` sites Tapu Bulu on "Jungle Isle", and
   `docs/STATE.md:107` says the Jungle Isle is drowned (its elders were moved to the Long Isle).

---

## 1. The species, one home each

**Unhomed (the brief's definition, verified against `data/dungeons.json`'s 13 ids, `:210-1933`):** statuses
`planned` (5), `blocked` (2), `out` (1), and `to_dungeon` whose home is not in `data/dungeons.json`. That last group is
the Temple Calendar (6: `roster:124-135`), the Cistern (3: `:107-122`) and the Zero Dig (7: `:208-218`), 16 in all.
That makes **24**. The seven Forces and Tapus are excluded and are being placed by another unit.

Caps (relayed and consistent across sources): cap = the next required leader's ace, 20/25/.../55 for gyms 1-8, 60
after gym 8, 62 after Lance, 100 after the Champion (`data/encounter_design.json:36`; `docs/STATE.md:156`;
`CELEBI_WAKE.md:94-104`). A tier-*t* sub-region's cap is 15 + 5*t* (`DROPS_PROGRESSION_SPLIT.md:131`, relayed).

| Species | Proposed home | Mechanism | Gate | Level | Catch rule | Model gate | Overlap to clear |
|---|---|---|---|---|---|---|---|
| **Meloetta** | Cave K2, Viltri Quay | chamber rare spawn (activated Habitat Block) | partition on `gym6_cleared` | 50 | any ball, cap 50 | none (MSD) | Temple Calendar pool (unbuilt); DP rare spawn |
| **Tapu Fini** | Cave K4, Sunset West's strait | chamber rare spawn | partition on `gym8_cleared` | 60 | any ball, cap 60 | none (MSD) | Temple Calendar pool (D18's lake pick); DP spawn |
| **Nihilego** | the outer sea bands, at night | world rare spawn (compiled pool) | place (outer sea) | 60 | any ball; caught at cap 60+ | **atm_subset** | Cistern pool and `ub_boss`; DP spawn |
| **Buzzwole** | `jungle_west` (tier 8) | world rare spawn | place | 55 | cap 55+ | **atm_subset** | Temple Calendar pool and `ub_boss`; DP spawn |
| **Pheromosa** | `jungle_east` (tier 8) | world rare spawn | place | 55 | cap 55+ | **atm_subset** | as Buzzwole |
| **Miraidon** | Cave K3, Highwire | area boss (keeper, native alpha) | partition on `champion_cleared` | spawns 70, fought at party+20, max 100 | any ball, cap 100 | none (MSD) | **OWNER:** Q14, and suppression lists it with the paradoxes |
| **Koraidon** | Cave K6, the east dunes | area boss (keeper, native alpha) | `champion_cleared` | as Miraidon | as Miraidon | none (MSD) | as Miraidon |
| **Dialga** | default: stays the Temple Calendar's designed boss (D18). Option: Cave K5, Tilpey Cross | option: area boss | `champion_cleared` | as Miraidon | any ball | none | **OWNER:** only if Q13 drops the Temple Calendar |
| Kyogre, Rayquaza | `docs/world-building/KYOGRE_CAVE.md`, unchanged | designed | as designed | as designed | as designed | none | none |
| Heatran | the Crucible's boss room (`NETHER_ENCOUNTERS.md` 3.2), unchanged | designed (Nether) | | | Beast Ball | none | finding 5 |
| Yveltal | the Patriarch boss chain (`DUNGEON_3_PATRIARCH.md`), unchanged | designed | | | Beast Ball | none | finding 5 |
| Registeel | already sited (finding 1) | | | | | | none |
| Lugia | stays blocked (`legendaries.json:547-585`: the trench axis lies off the map, and a heightmap cannot express y-30) | | | | | | none |
| Eternatus | stays out until a Galar Particle supply exists (`STATE.md:143`) | | | | | | none |
| Walking Wake, Iron Bundle, Brute Bonnet, Scream Tail, Great Tusk, Sandy Shocks, Iron Treads, Iron Hands, Iron Thorns | stay dungeon content (`STATE.md:164`). They stay homeless until the Cistern, Temple Calendar or Zero Dig is built, or the owner moves them into a built dungeon's pool | none here | | | | 7 of 9 atm (`roster:369-385`) | none |

**Why each mechanism fits its species:**
- **The model-gated Ultra Beasts are world spawns, not cave centrepieces.** A chamber's whole point is its occupant.
  A player without the AllTheMons subset would find a substitute doll there. An incidental rare spawn is never
  required, which honours "NO required prize may depend on it" (`STATE.md:99`). The fiction fits too: Ultra Beasts
  arrive through wormholes, not to a shrine.
- **Meloetta and Tapu Fini get chambers.** Both render, and both have a place story: a song cave
  (`unhomed-legendaries-1.8.0.md:113`, "hidden reward behind a music puzzle") and a misted water guardian (`:130`).
- **Koraidon, Miraidon and Dialga are area bosses.** All three are labelled restricted, so they belong after the
  Champion (`roster:14`). That is exactly where a native alpha is catchable (finding 3).
- **Koraidon and Miraidon need the owner.** Their own jar label is legendary, not paradox. Even so, the owner's
  paradox instruction removed their wild spawns (`spawn_suppression.json:55-57`). A keeper-spawned boss is technically
  outside that list's reach (`:61` "not_covered: ... a scripted event"), but it reverses the decision in spirit. The
  Zero Dig was cut and its re-authoring waits on the owner's play (`STATE.md:99`), so their dungeon home is indefinite.
  **Default if the owner says "dungeon": K3 and K6 take section 4's fallback occupant.**

**Overlap rule.** Moving a species to the world removes it from its unbuilt dungeon pool, and adds it to the
suppression's removed list (finding 2). The Temple Calendar keeps Dialga and its two paradoxes. The Cistern keeps
Walking Wake and Iron Bundle. A UB `ub_boss` that an NPC holds (fight only, `roster:18`) may stay: it is a fight, not a
second catch. Nothing built loses an entry, because both dungeons are unbuilt.

---

## 2. Rare world spawns

**Mechanism.** These are ordinary compiled entries in the home sub-region's pool. They are authored in
`data/encounter_design.json` and compiled by `tools/compile_spawns.py`, which is the "ultra" role's path
(`encounter_design.json:27`). Each entry is non-alpha, at a fixed level (the place's cap), in the **ultra-rare**
bucket, with a fractional weight. Fractional weights are already authored: 180 occurrences in `data/spawns.json`
(read), installed in staging and not observed in game.

**How rare.** The bucket is drawn first, then an entry within it (`ENCOUNTER_DESIGN.md:292`). Within it, the place's
own ultra family carries weight 1. With the v2 world buckets summing to 100, a legendary of weight *w* is:

    P(per spawn) = (0.2 / 100) * w / (1 + w)

| w | P per spawn | one in |
|---|---|---|
| 1 (as an ordinary ultra) | 0.100% | 1,000 |
| **0.05 (recommended)** | **0.0095%** | **~10,500** |
| 0.1 | 0.018% | ~5,500 |

"Very rare" here means one twentieth of the place's own ultra-rare family. That is one setting the owner can change.

**Per hour of play.** No one has measured the spawn rate in this world (`docs/research/DROPS_AUDIT.md:70-71`). The
only hard bound is the config: one spawn pass every 10 ticks and at most one spawn per pass, so at most 7,200 spawns
per player-hour (`modpack/config/cobblemon/main.json:26, 29`, read). The real figure is lower, because of
`pokemonPerChunk` 0.25 (`:42`) and despawn ages of 600-3,600 ticks (`:116-117`). Assuming S spawns per hour round one
player inside the home sub-region, at w = 0.05:

| S (ASSUMED) | legendaries per hour | about one every |
|---|---|---|
| 500 | 0.048 | 21 h |
| 1,000 | 0.095 | 10.5 h |
| 2,000 | 0.19 | 5.3 h |
| 7,200 (config ceiling) | 0.69 | 1.5 h |

Each player's spawner runs separately, so two players in the sub-region double it. Experiment RS-0 measures S. The
weight is then set from the hours the owner wants, not from this table.

**Kept out of the dungeons and the Nether, three ways:**
- `compile_spawns.bind_dimension` writes `dimensions: [minecraft:overworld]` on any entry that names none. Before it,
  an absent list matched every dimension, and overworld pools spawned in `cobblers:pocket`
  (`tools/compile_spawns.py:107-113`; `STATE.md:226`). It is merged in #133 but **not installed**, and installing it
  is a prerequisite.
- New check (test-author): a compiled entry of a legendary, mythical or Ultra Beast fails unless its `dimensions` is
  exactly `[minecraft:overworld]`.
- The removed-species mechanism strips the DP's copies in every dimension (`spawn_suppression.json:48`). Give it a
  `managed_species` list, the five above, with its own `why`, kept separate from the paradox list.

**Catch.** At cap 55 or 60 an at-cap player catches with any ball. A player who walks in early sees one they cannot
catch, which is the owner's above-cap rule (`STATE.md:165`). There is no Beast Ball rule (`STATE.md:156`).

---

## 3. Area bosses

**Mechanism: a keeper, not a spawn pool.** One boss stands at its landmark (a cave chamber here). It is spawned by a
20-tick keeper through a macro `spawnpokemonat`, as the Hoopa cradle does: tag, a `PersistenceRequired` boss, and a
return after a cooldown (`tools/hoopa_cradle.py`; pattern in `legendary-species-1.8.0.md:114-127`, built and never run).
Macros are how a keeper spawns after a plain restart (`STATE.md:86`; EXP-046). Why not the other routes:
- A heart entry wanders and cannot control its respawn.
- An activated Habitat Block's refill cadence is unmeasured (RS-1).
- An unpersisted spawn despawns within a minute with nobody near (`.claude/rules/datapacks.md`).

**Properties.** `<species> alpha=true level=70 min_perfect_ivs=3 moves=<four> held_item=<one>`. These keys are read
from the jar's property set (`legendary-species-1.8.0.md:82-92`). The moves and item are trainer-balance-designer's
call.

**Level and catch.** The boss is post-Champion only. Near a player it re-levels to party+20, capped at 100. A champion
party at 62-80 therefore meets it at 78-100 ("the area's top level" once the cap is 100). It is catchable with any
ball, because nothing is strictly above cap 100. An unqualified friend's cap (62 or less) breaks every ball they throw.
The cap block itself is the per-player catch gate. **Pre-Champion area bosses are not proposed.** They would need
AB-1 (does `no_ai` stop the re-level?) or the owner reversing "keep the alpha scaling".

**Respawn rule (proposal; the owner confirms):** one alive server-wide, first come first served, as with Necrozma
(`STATE.md:143`). After a faint it returns in 24,000 ticks (an in-game day); after a catch, 72,000. It is spawned only
while a qualified player is within the chamber's reach. It is repeatable, matching the rare-spawn rule.

**What it pays.**
- The catch.
- On a faint, the native alpha drop: `loot_table/alpha/alpha_rewards_tier4` at level 66+ (`ENCOUNTER_DESIGN.md:355-356`).
- `cobblers_alpha_spoils` type gems (`STATE.md:157`).
- The species' own drop table.
- No money: wild pay is off (`STATE.md:154`).

The cooldown bounds the farm. test-author prices one boss-hour against `data/bank.json` as the economy audit does.

**The trainer rematch issues (`STATE.md:87-88`) do not apply.** A fainted or caught wild Pokemon is gone; there is no
rctmod record to forget. **What does apply:**
- (a) **The blackout guardian.** A wild victor that KOs a player is bound as a guardian holding the claim
  (`STATE.md:113`). The keeper must never despawn, replace or respawn a boss that holds a claim (it needs a
  `recovery/pid` check), or the player's items vanish. That is a new contract in `data/system_contracts.json`.
- (b) **One boss per keeper**, re-checked after a restart and a chunk unload. Duplicate summons are why R14L is never
  re-run (`STATE.md:263`).
- (c) **"Our list is not the world."** The keeper says in its docstring that it covers only `data/caves.json` bosses.

---

## 4. The cave kit

> **Superseded for K1-K6 on 2026-10-12** (the owner, after walking up to the Singing Hollow's mouth: "I hate the cave look, it
> feels out of place, and the inside being a small tunnel to a legendary feels worse. Need a different solution than a cave";
> and "we don't need the non-legendaries, just make something that looks good"). K1 (Stoneford Cut, Gible) is retired with no
> successor; K2-K6 are open-air **sanctuaries** in `data/sanctuaries.json` (`tools/sanctuaries.py`, audit
> `tools/sanctuaries_audit.py`, step R9SY after R9CK and before R9E): S2 The Singing Hollow (Meloetta, a ruined theatre on the
> hill over Lake Viltri's south shore), S3 The Broken Relay (Miraidon, a fenced compound under a snapped copper mast), S4 The
> Tide Shrine (Tapu Fini and Nihilego, sea-stone monoliths round a tide-pool court), S5 The Stopped Clock (Dialga, a sundial
> court under a ruined clock tower), S6 Sunscar (Koraidon, a half-buried sun arena). The occupants' mechanics are unchanged
> (the gate is the court's barrier door, the old antechamber is the forecourt); the antechamber pools and the boss caves'
> chamber pools went with the caves. The six retired caves are frozen in `retired_caves` and restored to the heightmap's
> terrain before anything is built over them. The rest of this section describes the kit as it stands for the natural caves
> (N1-N3) and as it stood for K1-K6.

**One record per cave in `data/caves.json`.** The generator is `tools/caves.py` (`site`, `author`, `report`, `build`,
as `tools/mining_caves.py:44-47` has). The pack is `cobblers_caves` with the plan `derived/caves/plan.json`. The record
holds:

| Field | Holds |
|---|---|
| `id`, `name`, `theme`, `status` | `planned` / `sited` / `built` |
| `near` | a town id or null (wild); `sub_region`, `tier` |
| `mouth` | x, z, facing, `frame` (`timber` / `natural` / `ruin`). Written only by `site` / `author` from the heightmap, never by hand |
| `passages[]` | `kind` (`drift` / `incline` / `crawl`), length, width, height, drop, turn. A near-town cave is about 40-90 blocks in all ("a short side trip") |
| `antechamber` | optional room before the gate: half-widths, height |
| `chamber` | `shape` (oval), rx, rz, h, `feature` (`pool` / `columns` / `crystal` / `none`) |
| `gate` | `none`, or `partition` with `flags[]`, the `legendaries.py` pattern |
| `dressing` | palette id (`docs/world-building/BUILD_PALETTE.md`), features, density |
| `light` | `lantern_every` (default 6), `chamber_lanterns`, `dark_by_design`. Lanterns only, never light blocks (`STATE.md:211`) |
| `habitat[]` | `natural`: the passages' cave pool, VR caves' tile pattern. `activated`: the chamber's occupant pool, schema as in `data/habitat_blocks.json:7110-7131`. Every block is also written into `data/habitat_blocks.json` |
| `occupant` | `mode` (`rare_spawn` / `area_boss` / `power_line`), species, level, alpha, catch rule, keeper cooldowns |
| `spawn_blocks` | the policy entry scoped to `caves` (`data/spawn_block_policy.json`, as for mining caves) |
| `mode: "natural"` | (2026-10-12, built) a cave with **nothing in it**: no `occupant`, `gate`, `habitat`, `antechamber`, `reward` or keeper (the loader and the audit refuse each), no timber frame, post, lantern or column, dark by design. A passage may carry `bend` (a lateral shift over its rows, `geometry.rules`), so the way winds; `dressing.vein_one_in` puts ore in exposed wall cells and `dressing.patch_one_in` patches the floor; the hall's `feature: "knobs"` stands `palette.knob` stubs on its floor. Palette: shell, floor, vein, patch, knob (copper, lapis and gold ore are not spawn conditions, so no policy entry is needed). **Hillside mouth (2026-10-12, the owner: "Natural hillside mouths": an organic opening in a slope, no trench, no frame, no cut stone):** the mouth and incline open no cutting; a rock lid (`geometry.natural_mouth.lid`) roofs them, the upper corners of the first rows are rock (a corbel arch), a mound of the hill's own surface block (`terrain.surface`) with rock showing at the face and a scree apron (`hillside.scree`, `hillside.rubble`) grow the slope the island's gentle ground does not have, and N2 hangs vines over the lintel; the incline floor is scree, not stairs. The first mouths' cutting (`legacy`, frozen) is restored to terrain from the heightmap by `restore_<id>`, which `build_<id>` calls first (R9CK, re-run safe). N1 Hoarfrost Hollow (south Pine Isle), N2 Greenwither Cleft (Long Isle south), N3 Dusk Burrow (Sunset West) |

**What it reuses, by name.** Read the cited lines, not whole tools: `reapply.py` alone is 119 KB.
- **Siting and clearance:** `mining_caves.Clearance` and `search` (`tools/mining_caves.py:323, :562`). They already
  keep clear of town footprints, route legs and paths, corridor boxes, other files' authored points, other packs'
  writes, painted water and the water export (`:31-37`). Add spawn-free zones and existing Habitat Block ranges.
  Ground comes from `tools/ground.py`, rounded.
- **Frame and hashing:** `mines.frame` and `mines.h32` (`tools/mines.py:104, :86`), via `mining_caves.py:11-12`.
- **Shell:** the legendary chambers' fill-solid-then-carve envelope with a 4-block `shell_margin`. It proves the
  sealing by arithmetic (`LEGENDARIES.md:62-69`). Roof cover follows the old mine's `MIN_COVER = 2` over every roof
  block (`tools/route1_old_mine.py:71`).
- **Gate:** the barrier partition. It opens while a flagged player stands in the antechamber and closes when none
  does, behind a single audited predicate (`LEGENDARIES.md:101-130`). Before the gate opens the occupant is visible
  behind the barrier. A barrier stops a ball and a sword (`:126-130`).
- **Dressing:** a timber set and lantern every 6 blocks of drift (`route1_old_mine.py:72`).
- **Habitat Blocks:** activated blocks are written by `tools/habitat_blocks.py`'s whole-NBT setblock
  (`STATE.md:85`: never `data merge` a style). Natural tiles come from the cave's model, as
  `vr_caves.py records --write` does (`STATE.md:221`). Verify after a restart (`STATE.md:217`).
- **Boss keeper:** the `hoopa_cradle.py` keeper (section 3).
- **Audit:** `tools/caves_audit.py` by test-author, modelled on `tools/mining_caves_audit.py:1-39` (its own command
  model, the walk on the heightmap, keep-clear against a full checkout) and on `legendaries_audit.py`'s `rct_caps`
  (every occupant at or under its gate's cap). It must not import `caves.py`. Its mutation test mutates the generator,
  for example the chamber's `rx + 2` inside the geometry, and never the record.
- **Not reused:** the Windward Sink and lake grottoes are water entries with an air budget. A kit cave is dry, apart
  from K4's pool feature.

**Occupant mechanics:**
- **`rare_spawn`:** one activated block in the chamber floor with `spawn_range` = the chamber's radius, TICK,
  `cancel_range -1`, `max_spawns 3`. Its pool: the chamber's residents (common/uncommon), plus the legendary and one
  local ultra family at weight 1 each in the activated **ultra-rare** bucket. Per spawn: 1.375% × ½ = **0.69%, about
  one in 145**. One visit fills 3 spawns, about **2%** (one visit in 49). Grinding the chamber at 20-30 KOs per hour
  (ASSUMED, `DROPS_AUDIT.md:467`) gives about one every 5-7 hours, in line with section 2. RS-1 confirms that an
  activated block rolls its buckets per spawn.
- **`area_boss`:** the keeper (section 3). The chamber's activated block holds residents only.
- **`power_line`:** the fallback. An early power line with no early wild home (`roster:257-271`: Beldum, Gible,
  Honedge and Munchlax are MISSING early; Bagon and Frigibax already have world proposals). It is a rare spawn at the
  tier's level, chosen by trainer-balance-designer. No overlap issue: rare lines may repeat (`roster:5`).

**Kyogre and Rayquaza.** No kit cave can host either. The Kyogre cave is about 260 x 300 x 180 in `cobblers:pocket`
(`KYOGRE_CAVE.md:127-136`). The kit carves small overworld caves, and Rayquaza's home is a sky island. If the kit later
gains a `dimension` field, its chamber and partition records could describe the Kyogre cave's inner rooms. That is not
in this pass.

### The first pass: 6 caves (candidate locations, approximate; `caves.py site` measures every one)

| # | Cave | Where (centre read from `data/towns.json`) | Sub-region (tier) | Antechamber | Chamber occupant |
|---|---|---|---|---|---|
| K1 | Stoneford Cut (the **pilot**) | 150-400 blocks off Stoneford (1743, 3628) (`towns.json:127-129`), off Route 2's line | `viltri_plateau` (1) | none | `power_line`, e.g. Gible, no gate |
| K2 | The Singing Hollow | the lake cliff near Viltri Quay (1605, 2801) (`:201-203`) | `lake_viltri_hollow` (2) | power line, e.g. Beldum | Meloetta, `gym6_cleared`, L50. A note-block puzzle as dressing is optional |
| K3 | The Relay Fault | Highwire (1688, 1410) (`:275-277`), on Mt Vessu's flank toward the signal array; keep clear of the Ursaluna den (1514, 158, 1424) and the Forces' summit chambers (other unit) | `mt_vessu` (3) | power line, e.g. Honedge | Miraidon boss, `champion_cleared` |
| K4 | Strait Grotto (wild) | the strait's mainland shore, well clear of Sunset West (2660, 6490) (`:1206-1208`), facing Sunset Isle, where the other unit is placing Tapu Koko and Lele | `sunset_west` (5) | none | Tapu Fini, `gym8_cleared`, L60, chamber `feature: pool` |
| K5 | The Clock Cellar (**OWNER**) | Tilpey Cross (6196, 3398) (`:899-901`) | Tilpey shores (6) | power line, e.g. Munchlax | Dialga boss if Q13 frees it, else `power_line` |
| K6 | Sunscar (wild) | a dune cliff in `east_coast_dunes` (7) or `south_east_dunes` (8) | wild | none | Koraidon boss, `champion_cleared` |

**Built offline 2026-10-12 (unit CAVE-KIT-2; `data/caves.json`, not installed, not seen in a game).** K4 is `cave_strait_grotto`
(mouth (2888, 6606) facing south, floor y67, hall y57; Tapu Fini and Nihilego, the chamber pool's two ultra-rare entries at level 60,
behind `gym8_cleared`; the chamber is dry, because the `pool` feature stays refused until its water has a spawn-block policy entry);
K5 is `cave_clock_cellar` (mouth (6368, 3482) facing west, floor y98; Dialga, a post-Champion area boss, level 70, moved out of the
Temple Calendar's boss slot by the orchestrator's decision); K6 is `cave_sunscar` (mouth (6814, 5272) facing east, floor y136; Koraidon,
a post-Champion area boss, level 70, out of the cut Zero Dig's pool). Nihilego's "outer sea bands" home does not exist, so it is K4's
second ultra-rare entry (a K7 would have repeated K4's block); it keeps `model_gate atm_subset`. The roster
(`data/dungeon_prize_roster.json`) records all four as `to_world`.

K1, K2, K3 and K5 are near towns (K5 depends on the owner). K4 and K6 are wild: K4 is on the open strait shore, sited
away from Sunset West's footprint. Near-town caves are early-reachable side trips: the antechamber pays at first visit,
and the legendary waits behind its partition, visible. This is the owner's revisiting rule (`STATE.md:165`). Each
occupant's level sits at or under its gate's cap (section 1). If Q14 says "dungeon", K3 and K6 take `power_line`
occupants, or they are not built.

---

## 5. Build plan

**Nothing is built until the owner answers section 7.** The owner's fan-out rule is a maximum of three unattended
agents, and play before building more (memory). A builder is estimated at about 4M (CLAUDE.md).

| # | Unit | Agent | Cost | Needs |
|---|---|---|---|---|
| 0 | RS-1, AB-1 and the Habitat-trigger questions (section 6) from the 1.8.0 jar | cobblemon-researcher | ~0.6M | none |
| 1 | RS-0: measure spawns per player-hour in one sub-region on staging (main session; lock and process checks) | main session | small | install #133's `bind_dimension` first |
| 2 | Occupants: levels, moves and items; the chamber pools; the power lines; the world-spawn weights from RS-0 (data only: `encounter_design.json`, `data/caves.json` occupant fields) | trainer-balance-designer (opus) | ~1M | 0, 1, owner answers |
| 3 | The kit: `tools/caves.py` + `data/caves.json` kit block + **K1 only** + its Habitat Blocks, the spawn-block policy entry, and a reapply step after R9OC | datapack-content-dev (worktree) | ~4M | 2 for K1's pool |
| 4 | `tools/caves_audit.py` + tests; the dimension check (section 2); contract C-next (keeper vs guardian) | test-author | ~2.5M | 3 |
| 5 | Main session: prepare, install, staging restart, probes. **The owner walks K1** | main + owner | small | 3, 4 |
| 6 | World rare spawns: `managed_species` in suppression (`suppress_inherited_spawns.py`), the three UB entries, roster moves (Temple Calendar, Cistern) | datapack-content-dev | ~2M | 2, owner |
| 7 | K2-K6 sited and built, plus the boss keeper `cobblers_cave_bosses` (hoopa pattern, guardian check) | minecraft-systems-dev | ~4M | 5 seen working; Q14/Q13 |
| 8 | Audit re-run on K2-K6 and the keeper; qa-reviewer grades the K1 and boss experiments | test-author, qa-reviewer | ~2M | 7 |

**About 16M** plus integration. The order is 0 → 1 → 2 → 3 → 4 → 5, then 6 and 7 in parallel, then 8. Unit 7 is the
only one that writes a keeper. Escalate its audit (unit 8) to opus (CLAUDE.md escalation rule 1: it can bind a
player's items).

---

## 6. Unknowns (experiment candidates)

- **RS-0.** Spawns per player-hour in a sub-region. It sets section 2's weight (`DROPS_AUDIT.md:70-71`: never measured).
- **RS-1.** An activated Habitat Block: does it roll its buckets per spawn, and does a refill re-roll? What do `Chance`
  and TICK mean per tick? Does a spawn need a player near?
- **RS-2.** Are empty buckets renormalised at a position (`ENCOUNTER_DESIGN.md:292`, ASSUMED)? If not, the place's
  ultra-rare family must be able to spawn wherever the legendary can.
- **AB-1.** `alpha=true no_ai`: does the brain's `alpha_level_matching` sensor stop? This is only needed for any
  future pre-Champion boss.
- **AB-2.** In game: a keeper boss that wins a battle is bound as a guardian, and the keeper leaves it alone. A
  re-check after a restart spawns exactly one boss.
- **HB-1.** An activated block in a sealed chamber floor fills only the chamber (`STATE.md:221`: replace-in-sealed-rock
  and the vertical influence are unmeasured, EXP-033).

---

## 7. Open questions for the owner (each with a default)

1. **Q14 for Koraidon and Miraidon: overworld bosses (K6, K3), or wait for a re-authored Zero Dig?** Making them world
   bosses partly reverses their removal alongside the paradoxes (`spawn_suppression.json:55-57`). *Default:
   overworld, post-Champion.*
2. **Dialga (Q13): keep it as the Temple Calendar's boss, or move it to K5?** *Default: keep it; K5 takes a power line.*
3. **Tapu Fini as a repeatable chamber spawn (K4), or a fourth one-off sealed chamber like its three siblings (the
   other unit)?** *Default: K4, which gives variety.*
4. **Rarity.** Are one in about 10,500 world spawns (w = 0.05) and one in about 145 chamber spawns right, to be
   re-set in hours once RS-0 lands? *Default: yes.*
5. **Boss respawn.** One server-wide, 24,000 ticks after a faint and 72,000 after a catch, repeatable. Or once per
   player? *Default: repeatable.*
6. **Should the five inherited DP spawns (finding 2) go now, even before their homes are built?** Today they are
   uncatchable above-cap spawns. *Default: yes, with unit 6.*
7. **Registeel (finding 1): confirm the sited upper-Rift chamber is your decision, so the stale "blocked" lines can be
   cleaned.**

## Relayed, not measured here

- The DP spawn levels and buckets in finding 2 (`unhomed-legendaries-1.8.0.md`).
- The alpha re-level steps (`ENCOUNTER_DESIGN.md`, bytecode).
- The caps (`encounter_design.json:36`, `STATE.md:156`).
- 20-30 KOs per hour (`DROPS_AUDIT.md:467`, ASSUMED there).
- The ~4M builder cost (CLAUDE.md).
- Registeel's R14L placement (`REPORT_2026-09-30_DAY.md:64`).
- Every cave location: these are town centres and sub-region names, not measured mouths.
