# The Legendary and Mythical Research Station (proposal)

**Status: APPROVED, BUILT AS DATA and RE-SITED, 2026-10-02. EVERY ITEM IS HELD.** The owner's decisions, verbatim:
"Shrew Lake south shore, the Latias and Latios shrine, hold every item until EXP-048 proves an altar responds, Moltres
yes, no waystone, surveyor stays at the dig camp." Then, the same day: **"research station should be near 552 2812 not
the lake".** The station now stands on the **west sea coast**: land buildings on dry ground y63-68 just east of
(552, 2812), a jetty over the 1-deep shoal, a boardwalk spine with the instrument huts over 3-4 deep, a pier west across
the shelf, the Eon shrine on a platform at **(422, 2812), 15 deep** (sea level y62) about 100 blocks off the beach, and
the observatory beyond it over 16. Every other decision stands. The measured site, every deck's depth and the lake
site's superseded record are in `data/research_station.json` (`site`, `superseded_site`); nothing of the proposal
below was re-written, so **sections 1, 5.1 and 5.4 describe the lake site, which is no longer the build**.

The build is `data/research_station.json`, `tools/research_station.py` (pack `cobblers_research_station`, four zone
functions run by R9RS before R9E), `tools/research_station_audit.py`, four conversations and quests
(`dlg_station_director`, `_field_officer`, `_archivist`, `_shrine_keeper`; two lines that named the lake now name the
sea), four `npc_grant` records placed by R9F (Vale (550, 67, 2823), Quill (569, 69, 2824), Brandt (484, 63, 2793),
Mireille (422, 63, 2819)), and one **Horsea** Habitat Block (`station_study_pool`, (456, 60, 2828); Horsea, not the
lake's Psyduck, because it is the coast's own water species and Psyduck is in no roster here). **The switch is
`data/research_station.json` `economy.issuing`** (false): read `economy.switch` there for what flipping it does.

**The lake build reached staging; the coast build has reached no world.** `python tools/research_station.py cleanup`
writes `build/staging/cobblers_research_station_cleanup` (staging only, one-off, outside `build/datapacks`): every cell
the lake build (commit 42ce560) wrote put back to the heightmap world (lake water to y106, air, the ground's top block
as sand or grass, ASSUMED from `tools/paint_maps.py`), the old Habitat Block's cell included, and the four old NPCs
removed by type in a tight box at their old seats. It cannot put back the trees and plants the lake build cleared.
Its run order and check are `data/research_station.json` probe P0.

Not built: replacements (bought copies), the town-ground paving tag and its roster, lily pads, a healer, and Halvard's
half of the courier inside her own conversation. Latias and Latios verified: `latias_altar` and `latios_altar` take
`ruby_dew` and `sapphire_dew` and a `summon_anchor`; Moltres rolls 50, 55 or 60 (`MoltresAltar.class`), so the ember
feather takes Zapdos's gate. **The name "Shrew Station" was kept** although it no longer stands on Shrew Lake; renaming it
(signs, four conversations, quest and reward places) is the owner's call.

**The Zapdos tower moved on 2026-10-03** to the Fungal Isle's east coast, corner (881, 67, 5569) (the owner: "move
zapdos tower to mooshroom island i think or its own off in the sea"). The storm log reads the tower's position through
`tools/adopted_sites.py` and follows it; the station was sited on the north-west coast to stand a walk from the old
tower and is now 2,777 blocks from the new one. Whether it moves too is the owner's call.

The proposal as written follows, unchanged. When it was written nothing was built, authored as data, or placed in
any world; no file in `data/`, `tools/` or any world was changed to write it. Every ground and depth figure was measured on the
post-export canonical heightmap through `tools/ground.py` (rounded; probe `ground(4528, 4416) = 122` and
`ground(5160, 7463) = 61` both reproduced). Figures marked **relayed** were not re-measured here and name their
source.

The owner's brief, in short: a legendary and mythical research station at **(2246, 3092)**, sprawling from the
shore onto the water (jetties into walkways into platforms), research buildings rather than fishing ones, a
Cobbleverse shrine at its centre, and the station as the answer to the three activation items nothing in the
game produces.

## 0. Verdicts

| Question | Answer |
|---|---|
| Does (2246, 3092) suit a shore-to-water sprawl? | **No. It is dry birch plateau at y112, with no water of any kind within 515 blocks.** |
| Nearest site that does | **Shrew Lake's south strand, centred about (2690, 4070)**, 1,058-1,090 blocks south-east. Two nearer shores were measured and rejected for named reasons (section 1.2). |
| A Cobbleverse shrine that suits a water site | **None, honestly.** All 20 catalogue records are already decided, and none is a water structure we may place. Recommended instead: an **authored shrine built from LumyMon's own altar blocks**, the Latias and Latios altars, which need no template (section 2). |
| Glacier feather, thunder feather, Calyrex crown | One route each: the thunder feather **earned** by field observation, the glacier feather **researched** by a courier commission to the Frostpeak camp, the crown **traded** for a harvest of the cemetery's carrots. All are per player, gated by badge so the summoned Pokemon is catchable, and **switched off until EXP-048 shows an altar answers** (section 3). |
| Is the rest of the catalogue worth importing? | **No.** The item economy changes the value of the four adopted sites and one Nether tower that stays where it generates. It changes none of the 16 refusals. What it does open up is LumyMon's altar *blocks*, which are cheaper than templates (section 3.6). |
| If the altar is inert | The station becomes the bureau for **our own** ten legendary encounters, which do not depend on LumyMon, plus the dragon pit's observatory and a museum. **It must not lean on "the items still craft TMs":** measured, those TMs teach only Galarian Articuno, Galarian Zapdos and Calyrex-Shadow, which nothing in the game produces (section 4). |

---

## 1. Survey

### 1.1 The owner's coordinate, (2246, 3092)

| Measure | Value |
|---|---|
| Ground | **y112** |
| Ground over a 33x33 / 129x129 / 513x513 window | y110-113 / y107-117 / y105-130. **0% of columns at or below sea level** in every window |
| Region / subregion | `viltri_woods` / `viltri_plateau` (paint preset `birch_woods`); cell D3 |
| Inside a lake basin polygon (`data/landmarks.json` `water_body`) | no |
| Nearest lake water | Lake Viltri (level y103), column (1742, 2982), **516 blocks** west; Shrew Lake (level y106), column (2634, 3780), **790** south-east |
| Nearest river centreline (`data/rivers.json` graded polylines) | `lake_viltri_outflow` at (1490, 3014), 760 |
| Nearest sea-level column outside every lake basin | (516, 2879), **1,743** west (the west coast) |
| Nearest authored things | the birch elder `elder_viltri_plateau_3` (habitat blocks at (2344, 3064)), 102; Route 2's corridor at (1779, 3149), 470; Steepside (tea town) centre, 655; Viltri Quay, 704; Stoneford, 735 |
| Ferries, legendaries, adopted sites, shrines within 1,200 | none, none, none, two shrines at 589+ |

Rays every 22 degrees out to 320 blocks never cross a shoreline. The ground is a gentle plateau rising to y126
in the south-west. **It cannot carry jetties, because there is nothing to jetty into.** Nothing in
`data/water_shape.json` touches it either (its nearest feature is 1,627 blocks away), so the water export did
not remove anything here.

### 1.2 The candidates, nearest first

| # | Site | From (2246, 3092) | Physically | Verdict |
|---|---|---|---|---|
| A | **Lake Viltri, east shore** (1735, 3004) | 515-531 | Fine: a 1-7 deep shelf for about 56 blocks, then 20 deep | **Rejected.** It is already a station. Route 2's Viltri sounding (`data/checks/water_props.json` scene `route2_viltri_sounding`, its first depth staff at (1722, 3006)) stands on this exact shore. The lake's one role is **the Surf school** (`docs/mechanics/WATER_MAP.md` allocation 4), Misty's town is 241 blocks away and the `dive_viltri_floor` portal (1652, 2996) is 83. A second research platform here would duplicate the first. |
| B | **Shrew Lake, the north-west tongue** (2690, 3770) | 789 | Excellent: a 1-deep natural causeway for about 40 blocks, then a shelf into 6-41 deep | **The alternative.** Its root is **41 blocks from Steepside's footprint** (`data/towns.json` tea_town, x2531-2778, z3482-3729), and Steepside's street polyline ends at (2662, 3726). Built here, it reads as Steepside's waterfront, not as a place of its own. |
| C | **Shrew Lake, the south strand** (2612-2760, 4012-4132) | 1,058-1,090 | Excellent: a dry beach, a 1-deep shoal and a pit wall falling to 37 | **Recommended.** It is its own place (379 blocks from Steepside), it is the only flat low beach on the lake, and its depths step down in exactly the order the brief describes. |

The open sea is 1,743 blocks away, too far to count as "near the coordinate". No ferry dock in
`data/ferries.json` lies within 1,200 blocks of any candidate.

### 1.3 Shrew Lake, the body of water

- **Level y106** (`data/landmarks.json` `shrew_lake.water_body.level_y`). Measured: 176,416 wet columns, max
  depth 51, the deepest lake on the map.
- **Its one role is already fixed:** "the dragon's pit: deep Dratini, the lost surveyor's case on the floor",
  set piece **none**, gate Surf, stage S2 (`WATER_MAP.md` allocation 6). A research station that *studies* the
  pit fits that role. The shrine would be the lake's one set piece, a slot the allocation leaves free.
- **Story already pointing here:** `SQ-DIG-02`, the Missing Surveyor (`docs/story/SIDEQUESTS.md:599-607`). The
  West Spur Dig's roster lists a surveyor last seen heading for Shrew Lake.
- **Encounters now:** subregion `shrew_lake_shores`, `signature_overlay_keep_defaults`, wild levels 10-22
  (`docs/story/ENCOUNTERS.md:94`). The lake roster is Barboach, Dratini (rare, deep only), Goldeen, Magikarp and
  Surskit (`WATER_MAP.md:78`).
- **Neighbours:** the `dive_shrew_pit` portal at (2856, 3960) (`data/portals.json`); Steepside; the Cherry Elder
  (3408, 3840). The planned, uncut **River of Shrews** (`data/landmarks.json` `river_of_shrews`, status
  `planned`, "a canal candidate, never cut", `docs/world-building/RIVERS.md:123`) has its low end at
  (2722, 3978), so **site C is where that river would enter the lake if it were ever cut**. It is on file only.
  If it is ever built, the station is at its mouth. That is worth knowing, and it is not a conflict today.

### 1.4 Site C, measured

Depth map, every 4 blocks. Land is shown as height above the y106 water level (`.` 0-2, `+` 3-6). Water depth:
`1`, `2`, `~` 3-5, `o` 6-9, `O` 10-19, `#` 20 or more. x runs 2548 to 2792, left to right.

```
 4020 +.....1122oOOOO##OOOOOOOOOOOOo~~~212~~ooOOOOO################
 4028 ++......112~OOOO###OOOOOOOOOoo~111111~~oooOOOO###############
 4036 +++.......12OOOOOO##OOOOOooOo~21111111~~~~oOOO###############
 4044 ++++......12OOOOOOO###OOOOoo~~222111112~~~ooOO###############
 4052 ++++......12OOOOOOOOOOOOOOOooo~2221112~~~~oOOO###############
 4060 ++++.....12oOOOOOOOOOOOOOOOOOoo~2122~~~~~~oOOOO##############
 4068 ++++....12~OOOOOOOOOOOOOOOOOOOoo~~~oooooooooOOO##############
 4076 +++...112ooOOOOOOOOOoOoOOOOOOOOOoooooooooOOOOO###############
 4084 ++...122ooooooooo21111111111OOOOOOOOOOooOOOOO################
 4092 +....12oooooooo211.........111oOOOOOOOOOOOOO#################
 4100 ....12oooooo2211.............1112oOOOOOOOOOO#################
 4108 ...12ooooo~211.................1111222oOOOOOOO#########Oo~222
 4116 ..12ooooo211........................111222222~ooOOOo~22211111
 4124 112ooooo211.............................111111111111111......
 4132 22~~~~~21....................+...........................++++
```

Four features, south to north and west to east. Each was measured along the line given:

| Feature | Where | Measured |
|---|---|---|
| **The strand** (shore base) | box x2612-2668, z4108-4132 | 1,425 columns, ground **y106-109, median 108, none wet**. A flat beach at the waterline: no cut, no terrace |
| **The spit and the channel** (jetty) | line (2640, 4108) to (2648, 4090) to (2660, 4078), 37 blocks | beach 0-1 above water, then **1 deep for 10 blocks**, then **13-14** where it crosses the channel |
| **The shoal** (walkways) | line (2660, 4078) to (2690, 4058) to (2712, 4044), 62 blocks; then (2684, 4064) north to (2684, 4020) | 14 falling to **1-4** across the channel's far side; then **1 deep for 40 blocks** north along the shoal, a natural causeway |
| **The pit wall** (platforms) | line (2700, 4030) east to (2790, 4030); box x2712-2760, z4012-4048 | 5, 6, 6, 7, 10, 12, 15, 17, 20, 23 ... **37**; the box is ground y66-102, so **4-40 deep, median 25** |
| **The lagoon** (study pool) | x2560-2600, z4084-4124 | **6-9 deep**, sheltered on three sides by the strand |

Clearances: the shrine platform at (2740, 4030) is 23 deep and **136 blocks from the `dive_shrew_pit` portal**,
centre to centre. Measured from a pavilion edge it is about 128, above the 120 the adopted sites hold to
(`data/adopted_legendary_sites.json` `cross_system_consequences`). No route corridor passes within 992 blocks.
The station is off-route, reached from Steepside along the west shore.

---

## 2. The shrine

### 2.1 The full inventory, against a water site

`data/structures.json` holds **20** records of class `LEGENDARY`, not the 21 the brief relayed. (The 21st is
probably `legendarymonuments:outskirt_stand`, a roadside merchant stand of class `NAMED`.) Every one of the 20
is already decided in `data/adopted_legendary_sites.json`:

| Record | Template biome | Decision | Suits a water site? |
|---|---|---|---|
| `cobbleverse:mythical/mew` | jungle | **adopted**, Long Isle summit (7604, 142, 7082) | no |
| `cobbleverse:crown_cemetery` | old-growth pine taiga | **adopted**, Peak Pond Hollow (4118, 109, 1982) | no |
| `cobbleverse:legendary/zapdos` | **stony_shore** | **adopted**, the Fungal Isle's east coast, corner (881, 67, 5569), since 2026-10-03 (the owner moved it off the windward cliff (562, 74, 2614); `data/adopted_legendary_sites.json` `superseded_coast_site`) | water's edge, but a sea cliff, and adopted where it "finds itself" |
| `cobbleverse:legendary/articuno` | snowy plains | **adopted**, Frostpeak's summit, the owner's word of 2026-10-02 | no |
| `legendarymonuments:lake_acuity`, `lake_valor`, `lake_verity` | lakes (Sinnoh pack tag) | **refused**: we author Uxie, Azelf and Mesprit ourselves; a paste yields only a 37x48x37 jigsaw start piece | **the only lake structures in the catalogue**, and each would give one of our legendaries a second author |
| `legendarymonuments:stark_mountain` | — | **refused**: 120x90x137 region, ships Sinnoh RCT trainers | no |
| `legendarymonuments:giratina_island`, `distortion_portal` | Distortion World | **needs a dimension decision** | an island, but in another dimension |
| `cobbleverse:crown_spire` | snowy plains | **refused**: a swap for the cemetery, not an addition | no |
| `cobbleverse:legendary/moltres`, the four Ruinous shrines, `dawn_tower`, `dusk_tower`, `eternatus_cocoon` | Nether / End | **left where they generate** | no |
| `legendarymonuments:turnback_cave` | — | **refused as a paste** (jigsaw) | no |

**Verdict: nothing in the catalogue fits a water site honestly.**

- **Zapdos**, the one water's-edge template, is adopted elsewhere for a reason that would be lost. Moved to an
  inland lake, it would also lose the biome it was built for.
- **The lake trio** are the only lake structures there are. They are refused because of an authorship
  collision. A research station is no reason to give Mesprit a second home.
- **Giratina's island** is a dimension question, not a placement one.

### 2.2 Recommended instead: an authored shrine from LumyMon's own blocks

**A finding from this survey that changes the options:** LumyMon 0.6.6 registers **39 altar-family block
states** (read from `assets/lumymon/blockstates/` in the jar copy at
`.claude/worktrees/cobblemon-campaign-setup-64929d/experiments/EXP-000-cobblemon-1.8-compat/runtime/server/mods/LumyMon-0.6.6.jar`).
Among them are `kyogre_altar`, `lugia_altar`, `latias_altar`, `latios_altar`, `jirachi_shrine` and
`cresselia_altar`, most with **no template in our install**. Altars are plain blocks, not block entities
(`docs/research/notes/lumymon-altars.md`, VERIFIED). So an authored build can `setblock` one, and **a shrine
does not need a Cobbleverse template at all.**

**Pick: the Eon shrine, `lumymon:latias_altar` and `lumymon:latios_altar` with a `lumymon:summon_anchor`, on
the central platform.**

- **Water fiction.** Latias and Latios are the guardians of a city built on canals. A shrine reached only by
  walkways over the water is the right home for them, and a better story than any template on the list.
- **No author anywhere.** Neither species appears in `data/legendaries.json`, `data/adopted_legendary_sites.json`
  or `data/spawns.json`. The only mention is Mega Showdown's `latiasite` and `latiosite`, already rewards in
  `data/gulch_mine.json:2858-2859`. Those stones currently have nothing to evolve.
- **Self-contained, like the cemetery.** VERIFIED from the class strings in the jar:
  - `LatiasAltar` and `LatiosAltar` extend `SummonAltar`;
  - they activate on `RUBY_DEW` and `SAPPHIRE_DEW`;
  - both reference `SUMMON_ANCHOR`;
  - they spawn at **level 50, 55 or 75**.

  Neither dew is named by any data file in LumyMon's own jar. COBBLEVERSE-DP-v31 was **not** checked for them:
  its only copy is on the server, under another session's lock. If the station issues the dews too, the
  centre works the moment altars are shown to work.
- **The cost, stated:** this adds **two legendaries** to the campaign (Tier B by `docs/mechanics/LEGENDARIES.md:8-11`),
  and the **level-75 roll can never be caught**. The catch block (`data/level_cap.json`) breaks free anything
  above the thrower's cap, and no cap we have reaches 75. How often the 75 is rolled was not read; it sits in
  bytecode logic. The 50 and 55 rolls are catchable from 7 badges (cap 55).
- **Not a Cobbleverse template.** It is the brief's "best alternative": an authored centrepiece, built from the
  same LumyMon blocks the templates are made of.

### 2.3 The fallbacks, ranked

1. **The Reliquary, with no altar.** Use this if the owner wants no new legendaries, or if EXP-048 finds altars
   inert. The central platform becomes a closed pavilion with the four activation items shown in item frames
   and a lore wall. Nothing on it can fail, because it promises nothing.
2. **Move the Zapdos tower here.** Not recommended. It is the one template that wants a water's edge, but moving
   it trades a decided sea-cliff site for an inland lake, and a 66-block tower over a 23-deep platform needs a
   foundation the cliff did not.
3. **Reopen a lake-trio template as scenery.** Rejected. It would give Mesprit, Azelf or Uxie two homes, which
   is the collision `data/id_authorship.json` exists to catch, and a paste is only the start piece.

---

## 3. The item economy

### 3.1 What already exists to build it with (no new mechanism)

| Need | Existing system | Evidence |
|---|---|---|
| A once-per-player gift | ADR-002 `grant_reward_once`: claim receipt is an advancement, carried across a re-export by `tools/carry_players.py` | `data/rewards.json` `mechanism`; `data/quests.json` `effect_kinds` |
| Hand something in | quest conditions `inventory_contains` and `held_item`; effect `consume_held_item` | `data/quests.json` `schema_definition` |
| Give an item | `execute as <uuid> run give @s <item>`, the give shape EXP-022 proved | `docs/mechanics/MARKET_GATING.md:132-135` |
| Show an option only to a qualified player | dialogue `visible_when` compiled to `isVisible`, plus the `cobblers:flag/<id>` advancement probe | `MARKET_GATING.md:24-34`; `tools/compile_dialogue.py` |
| Charge money safely | the ferry's checked CobbleDollars sequence: read, refuse if short, charge by macro, verify the drop | `data/ferries.json` `mechanism`; `tools/ferries.py` |
| Badge gates | `gym1_cleared` to `gym8_cleared`, `champion_cleared` as advancements | `tools/progression_pack.py` |
| A reason to reach a place | the cache-kind advancement on entering a trigger box | `data/rewards.json` `fields.kind` |
| NPCs that look like people | authored NPCs now render as Cobblemon's standard trainer | `experiments/EXP-051-npc-models/README.md` (relayed by the brief) |

### 3.2 The gate is catchability, and it is measured

Each altar's levels are **VERIFIED** from the class strings: Articuno and Zapdos 50, 55 or 60; Calyrex 70;
Latias and Latios 50, 55 or 75. A player's cap is the next required leader's ace
(`docs/mechanics/PROGRESSION_LADDER.md:469-470`): 50 after six badges, 55 after seven. After eight it is the
Elite Four's ace, **60** (`data/trainers.json` `elite_01_lorelei` .. `elite_04_lance`, all topping at 60;
`champion_blue` tops at 62).

**Relayed and unverified:** that these authored levels are the live RCT levels, and the "65 upper bound at
champion" in `data/adopted_legendary_sites.json`. **The cap after the Champion is not known.** That one
number decides the crown.

### 3.3 One route per item

**Every route below is switched off until EXP-048's right-click half shows an altar answers to its item.**
The repository's own rule says so (`data/adopted_legendary_sites.json` `a_dead_altar_must_not_block`: "No
quest ... refers to them, and none may until an experiment shows the altar responds").

| Item | Route | How | Gate | Why that gate |
|---|---|---|---|---|
| `lumymon:thunder_feather` | **EARNED**: a storm log | A trigger box on the Zapdos tower's upper storey grants `cobblers:reward/station_storm_log`, but only while it is thundering. The proposed form is a vanilla `minecraft:location` advancement whose `player` conditions include `minecraft:weather_check {thundering: true}` (ASSUMED valid 1.21.1; experiment 4). Back at the station, the storm desk's option is `visible_when` that advancement **and** `gym8_cleared`, and it runs `grant_reward_once` for one feather | `gym8_cleared` | Zapdos rolls 50, 55 or 60. At cap 60 every roll is catchable; at cap 55 a 60 breaks free and the feather may be spent for nothing |
| `lumymon:glacier_feather` | **RESEARCHED**: a courier commission | The station gives a named instrument case (`give_item` with a `custom_name` component). Dr. Halvard at the Frostpeak camp takes it (`consume_held_item`) and gives her field notes. The station checks for the notes (`inventory_contains`), takes them, and runs `grant_reward_once` for one feather | `gym8_cleared` | Same levels as Zapdos. It also ties the station to the camp that already watches the Articuno tower |
| `lumymon:calyrex_crown` | **TRADED**: a harvest offering | Hand in 16 `lumymon:shaderoot_carrot` grown from the Crown Cemetery's own crop. The template pastes it at age 7, and the jar ships `loot_table/blocks/shaderoot_carrot_crop.json`, so the crop replants. In return the station's archivist gives the crown through `grant_reward_once` | `champion_cleared`, **and held back until the post-Champion cap is measured at 70 or more** | Calyrex is a fixed level 70. Below a cap of 70 the crown summons a Pokemon nobody can catch. Then it should be an exhibit, not a reward |
| `lumymon:ruby_dew`, `sapphire_dew` (only with the Eon shrine) | **RESEARCHED**: the station's ledger | Option visible when the player holds all three lake guardians' `cobblers:legendary/<id>/met` advancements (`docs/mechanics/LEGENDARIES.md:138-143`) | implied `gym7_cleared` (Uxie's gate) | 50 and 55 are catchable at cap 55; the 75 never is |
| `lumymon:origin_fossil` (Mew) | nothing to issue | It already has a LumyMon recipe (`recipe/origin_fossil.json`, VERIFIED in the jar). The station only tells you so | — | Mew is 75-90, uncatchable under any cap we have |

**Replacements.** Whether an altar consumes its item is unknown. If it does, a second copy should be **bought,
not gifted**: a dialogue counter option, visible once the player holds the first grant's advancement, paid
through the checked CobbleDollars sequence. That is the shape `MARKET_GATING.md` recommends (option 7).
Proposed price: around **6,000**, the ladder's price for one late consumable (the Giovanni gold cap,
`PROGRESSION_LADDER.md:184`). The final figure belongs to trainer-balance-designer.

### 3.4 Multiplayer fairness

- **Each player earns their own.** Every grant is a per-player advancement with its own claim receipt
  (ADR-002), so nobody's commission is consumed by a friend.
- **Summons queue themselves.** VERIFIED strings: LumyMon refuses a second summon while a wild one of the same
  species is nearby (`isPokemonNearby`) and keeps a per-player cooldown, so two friends take turns. Relayed from
  the note: the cooldown map is in memory, so a restart clears it.
- **What is not enforced, stated plainly:** an item can be dropped, traded or chested, and a summoned legendary
  is a wild Pokemon that whoever throws first may catch, at the thrower's own cap. In a four-friend co-op this
  is probably fine. It is a pacing tool, not an enforcement (`MARKET_GATING.md:151-153`).
- **Two players at one counter at once** is untested (EXP-022's two-player half needs a second account,
  `docs/STATE.md:143`).

### 3.5 What waits on other owners (proposed, not authored)

| Change | Its file's owner |
|---|---|
| Halvard's new topic | `data/frostpeak_camp.json` |
| The station NPCs' dialogue | `data/dialogue.json` and `tools/compile_dialogue.py` |
| Quest records and their `quest.<id>.<field>` registrations | `data/quests.json` and `data/progression.json` |
| The storm-log trigger | `data/rewards.json` |

### 3.6 Does this make the rest of the catalogue worth importing? **No.**

The economy fixes a problem the **four adopted** sites have: three of their altars have no obtainable item. It
does not touch the reason for **any** of the 16 refusals:

- the trio is refused for authorship;
- Stark Mountain for its size and its Sinnoh trainers;
- Giratina for its dimension;
- the Crown Spire as a swap;
- the eight Nether and End structures because they are better left generating where they are;
- Turnback Cave because it is a jigsaw.

There is nothing left in the catalogue to import. What the economy *does* open up is two things:

1. **One refused-in-place structure could start to work without being imported.** The Nether Moltres tower
   generates naturally and has the same missing-item problem: `ember_feather` is named by no data file in
   LumyMon's own jar, and Cobbleverse's datapack was not checked. A fourth route at the station would make it
   function where it stands. That would be a **gain without an import**.
2. **The cheaper catalogue is LumyMon's blocks, not Cobbleverse's templates.** The 39 altar-family block states
   can be placed inside builds we author, with ground, gates and audits we control. **If EXP-048 passes, future
   legendary content should be authored around those blocks** (as section 2.2 does), not pasted.

---

## 4. If the altar is inert

**First, the premise to correct.** "Even with inert altars, each item has a real use, because it crafts a TM"
does not hold up when measured:

- **The three TM moves are signature moves.** In Cobblemon 1.8.0's species data (1,025 files, read in the jar
  copy named in the brief):
  - Freezing Glare is learned only by **Articuno, Galar form** (level 45);
  - Thunderous Kick only by **Zapdos, Galar form** (level 45);
  - Astral Barrage only by **Calyrex, Shadow form** (level 1).

  No species carries any of them as a `tm:` move.
- **TMCraft checks learnability.** INFERRED from the class strings of `tmcraft-1.4.19+1.8.0.jar`:
  `isPokemonAbleToLearnMove`, `isLearnedByTM`, `isLearnedByLevelUp` and the error
  `item.tmcraft.error.cannot_learn_move`.
- **Nothing produces those forms.** The altars summon the **base forms** (VERIFIED: no `galar` or `shadow` in
  any `Articuno`/`Zapdos`/`Calyrex` spawn string), and none of Cobblemon's 1,546 `spawn_pool_world` files names
  Articuno, Zapdos or Calyrex.

So the TMs the items craft teach their move to almost nothing a player can own. **The station must not be
designed around them** (experiment 5 settles it in two minutes).

**What the station becomes:**

1. **The bureau for our own legendaries**, which never needed LumyMon. The ten encounters in
   `data/legendaries.json` have badge gates (Mesprit `gym3_cleared`, Regirock 4, Azelf 5, Regice 6, Uxie 7,
   Groudon and Regigigas 8, Lugia `champion_cleared`) and a per-player `cobblers:legendary/<id>/met`
   advancement.
   - The station's **sightings board** shows each lead only to players who qualify (`visible_when` on the
     badge flag), and acknowledges each `met`.
   - Each acknowledgement grants a small ADR-002 reward.
   - This is a real loop with a real payoff, built only from the repo's own mechanisms.
2. **The dragon pit's observatory.** The platforms stand over the pit wall, 23-37 deep. Their purpose is the
   lake's own role: Dratini in the deep, the floor's lost surveyor. Rather than rewriting `SQ-DIG-02`, the
   station gives it a second hand-in and a second voice ("she was one of ours").
3. **A museum that says what it does not know.** The three items stand in item frames as exhibits, not rewards,
   with the same honesty as the Frostpeak camp's Halvard: "we have not made it do anything".

With an inert altar: no item is issued as a reward, the Eon shrine (section 2.2) falls back to the Reliquary
(section 2.3), and the station's value is items 1-3, which do not depend on LumyMon at all.

---

## 5. Layout

### 5.1 Jetties into walkways into platforms (site C)

| Zone | Measured site | Over | What stands there |
|---|---|---|---|
| **1. The strand** | x2612-2668, z4108-4132, ground y106-109 | dry beach | **The Institute** (reception, the Director, the sightings board); **the Archive** (records of the Kanto birds, the Crown, Mew; the exhibits); **the Quartermaster** (the gated counter for replacements, MARKET_GATING option 7); **the Bunkhouse**; **the Infirmary** (a healing machine: Rotom by the machine is the precedent the owner approved, `data/spawn_block_policy.json` whitelist) |
| **2. The jetty** | (2640, 4108) to (2660, 4078), 37 blocks | beach, 1 deep for 10, then 13-14 | skiff moorings; the **hydrophone shed**, listening down into the channel. Not a depth staff: Lake Viltri's sounding already has those |
| **3. The bridge and the shoal** | (2660, 4078) to (2712, 4044); the shoal (2684, 4064) to (2684, 4020) | 14, then 1-4, then **1 deep for 40 blocks** | boardwalks on short piles; **instrument huts** (the weather mast, the sample store, the darkroom) |
| **4. The platforms** | x2712-2760, z4012-4048 | 5 falling to 37 | **The shrine** at (2740, 4030), 23 deep (section 2.2 or 2.3); **the Observatory**, a glass-floored room over 31-37 at about (2760, 4020), looking into the dragon's pit; **the dive platform**, the station's departure point for the `dive_shrew_pit` portal 136 blocks east |
| **5. The lagoon** | x2560-2600, z4084-4124 | 6-9, sheltered | **the study pool**: a fenced water pen and a wet lab on its shore |

**Construction rules.** Borrow `data/sea_town.json`'s rules rather than inventing new ones:

- the same `min_depth` table (pier 3, bridge 2, boardwalk 1, jetty 0), the same `lamp_every`, `min_light` and
  lantern-only rule, and the same refusal of a deck over land;
- **one change:** the deck level is the **lake's** y106, not `vertical.sea_level` y62. In the sea town the
  deck replaces the top water layer and the walk is deck + 1.

A generator for the station is that tool with the water level made a parameter, not a new idea.

**Instruments must avoid spawn-condition blocks** (`data/spawn_blocks.json`, measured):

| Block | Draws |
|---|---|
| `lightning_rod` | Magnemite, Voltorb, Joltik, Plusle and others |
| `daylight_detector`, `comparator`, `redstone_lamp` | Rotom |
| `iron_block` | Meltan |
| `bell` | Chimecho |
| `kelp_plant`, `seagrass` | Skrelp, Dragalge, Pincurchin, which are sea species |

A weather mast is therefore copper, glass and a weathervane of fences, never a lightning rod. **A PC or monitor
draws Rotom and Porygon.** Allow one, by a whitelist entry with a reason, only if the owner wants a Porygon in
the lab, as he did for Sabrina's observatory monitor.

### 5.2 The signature paving

The concept is designed but not yet implemented. Each town records a paving tag
`#cobblers:town_ground/<town_id>`, town spawns require it, and curated wild spawns exclude it
(`docs/story/ENCOUNTERS.md:339-357`, `docs/world-building/STRUCTURE_DATA_FALLOUT.md:57-58`). No such tag exists
in `data/` or `tools/` today.

**Proposal for the station:**

- **Paving:** `minecraft:polished_tuff` and `minecraft:tuff_bricks` on the strand and the platform floors, with
  `minecraft:waxed_oxidized_cut_copper` inlays. A cool grey-green, instrument-coloured, and distinct from:
  - Brock's andesite and stone brick, and Misty's mud brick and prismarine (`spawn_block_policy.json`
    `checked_paving`);
  - the sea town's jungle, mangrove and bamboo decks;
  - Northlight's terracotta.
- **Decks:** `minecraft:spruce_planks` on `minecraft:stripped_spruce_log` posts.
- **Checks:** none of these is in `data/spawn_blocks.json` (measured). Polished tuff, tuff bricks and cut copper
  are not in Cobblemon's `#cobblemon:natural`, which lists raw stone through `#minecraft:base_stone_overworld`
  (read in the jar). Membership of the conventional `#c:stones` tag was **not** read, so experiment 7 confirms
  the tag with `tools/spawn_blocks.py`.
- **A note of overlap:** Northlight is already "a cold research station" (`data/rematerial.json:256`, its
  instrument tower in `data/town_dressing.json:243`). This station must read differently: Northlight is an
  applied-science town that sells vitamins; this is a place that studies legends.

### 5.3 What lives in the water (proposals for the owner of world spawns, not authored here)

- **Keep the lake's roster as it is.** Above all, **no Dratini Habitat Block**: the station studies the pit and
  does not farm it, and a nest by the platforms would cheapen the rare deep find that is the lake's whole role.
- **Lily pads along the jetty's 1-deep run.** `minecraft:lily_pad` is a spawn condition for the Lotad and
  Poliwag lines (`data/spawn_blocks.json`) and is `#cobblemon:natural`, so a pad field is a deliberate,
  block-keyed micro-habitat. It needs a policy entry with its reason, in the observatory-monitor precedent.
- **One water Habitat Block in the study lagoon** (the Seaward Drift precedent: ten water Habitat Blocks,
  `docs/STATE.md:514-516`). A freshwater study species inside the 10-22 band; Wooper or Psyduck are the
  proposal.
- **A station-ground roster on the signature paving**, once the tag exists. Proposed: Slowpoke, Psyduck,
  Ducklett, Magnemite, Bronzor, Natu and Elgyem (lake birds, instruments, artifacts, watchers, anomalies), in
  the shores' 10-22 band.

### 5.4 Ferry and arrival

**It joins no ferry line, and should not.** A ferry is "the gate for players without a water mount"
(`data/ferries.json` `status`): a teleport between docks on one body of water. Shrew Lake is a closed basin:

- no dock lies within 1,200 blocks of any candidate;
- the station is walkable from the strand by design, so nothing sits behind water;
- a new lake line (like `tilpey_launch`) would need a second dock on Shrew Lake with something to reach, and
  nothing on the lake needs one.

Arrival is on foot from Steepside, 379 blocks north along the west shore. **A waystone is the owner's call.**
Steepside deliberately has none (`data/towns.json` tea_town `waystone`). The station's items unlock at eight
badges and at the Champion, so players come back to it late, from far away. That argues for one here. Its
record would be a new `data/towns.json` entry (proposed id `shrew_station`, tier `outpost`).

---

## 6. Cost, and the experiments, in order

| # | Experiment | Who / cost | What it answers |
|---|---|---|---|
| 1 | **EXP-048, the right-click half** (coordinates in its README): Articuno's altar with a `/give`n feather; the Calyrex statue with a `/give`n crown; a thrown shaderoot carrot at the cemetery | the owner in game, about 15 minutes | **Whether the item economy exists at all**, plus whether items are consumed and whether an anchor is required |
| 2 | **The cap after the Champion**: `rctmod player get level_cap` on a Champion-cleared player, or the RCT series read offline | main session, minutes | Whether the Calyrex crown is a summon item or an exhibit |
| 3 | **A setblocked altar behaves as a pasted one**: `setblock` a `latias_altar` and a `summon_anchor` on staging, then `/give` a `ruby_dew` | the owner in game, 5 minutes; only if 1 passes | The Eon shrine, and the general claim that **templates are not needed** |
| 4 | **A location advancement with a `weather_check` player condition** fires in a thunderstorm | main session on staging, one throwaway pack | The storm-log route; fallback is a plain location advancement |
| 5 | **TMCraft learnability**: use `tm_freezingglare` on any Pokemon that is not Galarian Articuno | in game, 2 minutes | Confirms section 4. If TMCraft ignores learnsets, the inert-altar answer improves |
| 6 | **Two players in one station dialogue at once** (EXP-022's unrun half) | needs the second account (`docs/STATE.md:143`) | Multiplayer at the counters |
| 7 | **The paving tag**: `tools/spawn_blocks.py` against the proposed paving and instrument blocks | main session, seconds | Section 5.2's claims |

**Then the build**, in the repository's usual division:

- **Data:** `data/research_station.json`, the authored layout on `data/sea_town.json`'s pattern, plus the
  `data/towns.json` record.
- **Generator and audit:** `tools/research_station.py` (the sea town's generator with the deck level as a
  parameter), and an audit written by a different agent.
- **Dialogue and quests:** owned by `compile_dialogue` and `quests`.
- **Placement:** NPCs placed by `tools/reapply.py`'s `npc` action (a restart, not a `/reload`), and one re-apply
  step.

The site is a box of about 250 by 150 and every measurement here took seconds, so **nothing iterates over the
whole heightmap**. The comparable build is the sea town: 10,332 blocks, verified block for block. Token cost
was not measured for this proposal; quote `tools/session_cost.py` when the build is scoped.

---

## 7. Open questions for the owner

1. **The site.** Is it **C, the south strand** (standalone, 1,090 from your coordinate), or **B, the north-west
   tongue** (789, but in Steepside's lap)? Or did you mean a different water entirely? (2246, 3092) is dry
   plateau.
2. **The shrine.** Do you accept **no Cobbleverse template**, and if so, which centre?
   - the **Eon shrine**: two new legendaries; the level-75 roll uncatchable;
   - the **Reliquary**: nothing can fail;
   - or reopen a refusal.
3. **Issuing the items before EXP-048.** Never, as proposed? Or as exhibits only?
4. **Replacements:** bought (about 6,000) or not at all?
5. **Ember feather:** should the station also supply it, so the Nether Moltres tower works where it stands?
6. **A waystone at the station**, yes or no?
7. **`SQ-DIG-02`:** does the lost surveyor belong to the station, the dig camp, or both?

**What the missing earlier brief would have settled.** It was not found in the repo or in any session
transcript:

- the **scale** of the sprawl (how many jetties and platforms, and its length);
- the **building list** for the fishing version, which this replaces "with research";
- the **signature paving** the owner chose, if he chose one;
- **"what lives in the water"**: whether he named species or habitats;
- **whether it joins a ferry line**, and which one he had in mind;
- **whether (2246, 3092) was read off a map of the live world, and which water he was looking at.**

## 8. Verified, and not

**Measured or read here:**

- every ground, depth, distance and box in sections 1 and 5 (`tools/ground.py`, `data/landmarks.json` basin
  polygons, `data/rivers.json`);
- the 20 catalogue records and their dispositions (`data/structures.json`, `data/adopted_legendary_sites.json`);
- LumyMon's block states, the Latias, Latios, Articuno, Zapdos and Calyrex class strings, and the absence of the
  feathers, crown, dews and ember feather from LumyMon's own data files (jar copy);
- the TM moves' learners and the 1,546 spawn-pool files (Cobblemon 1.8.0 jar copy);
- TMCraft's learnability method names (jar copy);
- the E4 and Champion team levels (`data/trainers.json`);
- the spawn-condition blocks and `#cobblemon:natural`.

**Relayed:**

- that no recipe or loot table in COBBLEVERSE-DP-v31 or the other 101 jars makes the three items (the brief;
  `docs/research/notes/lumymon-altars.md`, head);
- the TMCraft recipes in that datapack;
- EXP-051's NPC fix;
- the 65 champion cap.

**Not verified anywhere:** that any altar answers; whether items are consumed; the anchor requirement; the
weather condition in an advancement; the Champion cap; two players at one counter. **Nothing in this document
has been seen in game.**
