# Unfinished-items sweep, 2026-10-06 (overnight)

The owner: "Go back through STATE, the handovers and the review lists and finish what was discussed and never
completed." Sources read: `docs/STATE.md` (What is open / blocked), `docs/HANDOVER_SESSION.md` and its history,
`docs/MORNING_REPORT_2026-09-30|10-04|10-06.md`, `docs/REVIEW_2026-10-02.md` (1-89), `docs/NIGHT_REVIEW.md`,
`docs/OVERNIGHT_REVIEW_2026-10-06.md` (N1-N60), `docs/PLAYTEST_2026-10-05.md`, `docs/DECISION_QUEUE.md`,
`docs/research/OBTAINABILITY_SWEEP_2026-10-05.md`. Branch `wave1-2026-10-06`, from `4811ebc`. Nothing here touched a
server, a world or `derived/`; nothing was applied.

Status: **done** (closed, tonight or before), **open** (an agent or session can do it), **owner** (blocked on a
decision or an in-game check only the owner can make), **obsolete** (superseded or answered). Size: **S** under an
hour of data/doc/code, **M** a tool change or one build unit, **L** design plus build plus apply.

## 1. Closed tonight

| # | Item | Source | What was done | Commit |
|---|---|---|---|---|
| U1 | **The Marts never grow** ("The Poke Mart never sells more than the default few items: scale it with gyms") | PLAYTEST note 9; the owner tonight | Built: section 2 | `78985e5` |
| U2 | `tests/test_markets_audit.py` jar fixture defaulted to the LIVE server's mods folder (a lock-rule breach) | OVERNIGHT N56 | Falls back to the 2026-10-05 offline snapshot; an assert refuses the live path | `test_markets_audit` commit |
| U3 | `rift_skin.py`, `rift_deep.py` crash on `Path(None)` without `--source-root` | N16 | Both resolve through `terrain.env_source_root()`, else a usage error; `tests/test_rift_source_root.py` (4) | `rift_skin, rift_deep` commit |
| U4 | `gym_buildings.py build --out` accepted and ignored | N31 | Honoured; built to a scratch dir, 8 functions written there, nothing in `build/` | `59c9a3b` |
| U5 | `data/relic_underground.json` `why_not_the_finale_flag` said `rift_crisis_resolved` has no setter | N17 | Corrected (the binder's release, `unlock_league_after_rift_resolution`); STATE's lines are in section 6 | `relic_underground` commit |
| U6 | `test_system_contracts` C4 fails on `tools/bank.py` | N1, STATE "Wave 1 play-test fixes" | `bank.py` declared a checker in `data/system_contracts.json` C4 `tools`; C4 34 passed | `C4 accounts` commit |
| U7 | Decision B3 "Giovanni's hold: one stale field" | DECISION_QUEUE | Obsolete: `data/gym_trainers.json` reads `held: false`; marked CLOSED | same |
| U8 | Decision D1 "does the guard's remedy count as a refusal?" | DECISION_QUEUE | Answered in CLAUDE.md 2026-10-01; marked ANSWERED | same |
| U9 | Three spawn-policy entries "OWNER TO CONFIRM" (kelp/seagrass, dandelion/cornflower, apricorn fruit) | REVIEW 66, 79, 83; PLAYTEST "Waiting on the owner" | The owner ruled 2026-10-05 "Spawn-condition blocks: allow them"; the ruling is appended to each `decided` (history kept) | `spawn policy` commit |
| U10 | Elite Four leader rejection unverified | HANDOVER Queue 2; the owner tonight | Proved offline: section 3. One in-game check remains | this file |
| U11 | "The 11 items still unobtainable": which block something | HANDOVER Queue 3; the owner tonight | Section 4 | this file |

## 2. Built: the Marts scale with the gyms (U1)

- `data/traders.json` `stock_policy.mart.tiers`: eight badge tiers on top of the owner's 2026-09-25 basics (Poke
  Ball, Potion, Antidote). 1: Paralyze Heal, Awakening, Burn Heal, Ice Heal. 2: Super Potion. 3: Great Ball. 4: Full
  Heal, Revive. 5: Hyper Potion, Ether. 6: Ultra Ball, Elixir, Max Ether. 7: Max Potion. 8: Full Restore, Max Revive,
  Max Elixir (no Mart reaches 8 today; kept for a League Mart).
- **Tier = the town's position, not the player's badges.** Since 2026-10-06 every seller is a CobbleDollars merchant
  (`data/markets.json` decision `counters_are_merchants`); its screen shows one list to every player and cannot gate
  a line per player. So a Mart's tier is the badges a critical-path player holds ARRIVING at its town (gym N's town:
  N-1; Pallet and Stoneford 0). An off-path clerk takes the tier of the critical town nearest where it stands:
  Steepside 0, Northlight 5, the Mining Town 6, Pacifidlog 7, Sunset West 7. Recorded in `tier_rule`; a record may
  override with `mart_tier` + `mart_tier_why`. `python tools/traders.py tiers` prints the table.
- **Nothing authored.** The Mart clerk's template (`bca:stores/store_workers/shopkeeper_ds_general`, read from the
  snapshot's `COBBLEVERSE-DP-v31.zip`) already stocks every tier line; the filter keeps more of it at the template's
  prices (great 600, ultra 800, super 700, hyper 1,500, revive 2,000, max potion 2,500). `function` mode refuses a
  clerk whose template lacks a tier line.
- **Fits the counters.** The seven lines the counters also sell enter the Mart at the counter's own badge, so the
  counter is first and the Mart catches up one town later; no Mart sells what its own town's counter sells.
- **No money printer.** `tools/bank.py check --server-dir <snapshot>` with the wider shelves: 0 problems. Even if
  `cobbleDollarsIncomeMultiplier` 1.25 scales sell-backs (C2b, unrun), every bank price x2.5 stays under the template
  price.
- Tests: `tests/test_mart_tiers.py` (20), plus `test_traders`, `test_mart_clerks`: 43 passed, 31 skipped. Mutating the
  generator's rule (`order - 1` to `order`) fails 5. **Written in the same session as the code: a second reader is
  wanted.**
- **Caveats for the owner:** Sunset West is walkable from Pallet with no badges (1,694 blocks) and sells tier 7;
  Pacifidlog the same by sea. Override per record if wanted. **Not applied; not run in game.** Reaches the world by
  prepare (`traders.py function`), install `cobblers_vendors`, and the vendors step (the clerks are re-summoned with
  the new shelf).

## 3. The Elite Four and the Champion refuse an over-cap player (U10)

**Verdict: VERIFIED offline for the mechanism and our data; ASSUMED for the five spawners standing in the world.**

| Claim | Status | Evidence |
|---|---|---|
| The refusal is a property of every rctmod trainer entity, whatever spawned it | **VERIFIED** | rctmod v0.19.0-beta `TrainerMob.canBattleAgainst` requires `tm.getPlayerLevel(player) <= tpd.getLevelCap()` (line 172) with no branch on origin; both battle paths, `mobInteract` and force-battle-on-sight (line 602), go through `startBattleWith` -> `canBattleAgainst`, and on refusal `replyTo` sends `over_level_cap` (line 266-267). Source: `gitlab.com/srcmc/rct/mod/-/raw/v0.19.0-beta/common/src/main/java/com/gitlab/srcmc/rctmod/world/entities/TrainerMob.java` |
| A spawner-spawned trainer is that same entity | **VERIFIED** | `TrainerSpawnerBlockEntity` (line 292) calls `TrainerSpawner.attemptSpawnFor(..., noOrigin=true)`, which builds `TrainerMob.getEntityType().create(level)` and `setTrainerId` (`TrainerSpawner.java` 482-484). It spawns for any nearby player; eligibility is checked at interaction, not at spawn |
| Lorelei, Bruno, Agatha, Lance and Blue are in the player's required series, in order | **VERIFIED** | snapshot `COBBLEVERSE-RCT-DP-v20.zip` `mobs/trainers/single/kanto_league_*.json` and `kanto_champion_blue.json`: `series ["kanto"]`, `requiredDefeats` Giovanni -> Lorelei -> Bruno -> Agatha -> Lance -> Blue |
| Our overrides keep that | **VERIFIED** | `tools/route_trainers.py` 406-432 writes only the team (`data/rctmod/trainers/<id>.json`) and the dialog at the upstream ids; `data/league_trainers.json` `not_emitted`: no mob file. The dialog override goes through `with_refusals`, which carries `over_level_cap` from `data/trainer_refusals.json`, so the refusal is not silent |
| The cap at each | **VERIFIED** (from `docs/mechanics/LEAGUE_LEVEL_CAP.md`'s source reading) | 60 at Lorelei through Lance (each ace 60), 62 at Blue, 100 after Blue. A level-100 party is refused at all five |
| The League template's five spawners name those ids and stand in staging | **ASSUMED** | `data/league_trainers.json` `order_enforced_by` quotes the template's five spawners; `order_not_verified`: the template's blocks are not in the repo and no session has walked the League |
| Our team override is the one loaded | **ASSUMED** (STATE "The leaders' teams are ours") | the team-path override has not been seen in a League fight |

**Why the HQ fights were different (N57) and these are not:** the HQ tower and arena opponents are Cobblemon NPC
battles, which never reach `canBattleAgainst`. The League's five are rctmod `TrainerMob`s.

**The in-game test (5 minutes, staging):** a test account with rctmod progress recorded through Giovanni (the
`cobblers_test:giovanni_ready` approach, extended), a party holding one Pokemon at 61. Walk to Lorelei's room: she
appears; right-click: expect the `over_level_cap` line and no battle. Drop the party to 60: the battle starts. For
each later member record the earlier defeats and repeat with 61; at Blue use 63. Also try the second account
standing next to the first (a co-op party member's over-cap Pokemon).

## 4. The "11 items" (U11)

**The figure 11 is relayed and does not appear in any document** (searched every doc, data file and the handover's
history). It reproduces as the rows of the obtainability sweep's section 4 still without a route after tonight's
builds: 15 rows, minus fossils (the Scorchbone Dig, built), the Z-Ring (the Raw Tear cache), the Ability Capsule
(Northlight) and the purely decorative Legendary Monuments row. "The research station or Blaine's exchange" matches
no file either; the research station is a one-off source (E) for the legendary items, which are not in this list.

| # | Item(s) | What it actually blocks | Cheapest route |
|---|---|---|---|
| 1 | **18 type gems** | Every crafted TM (none of 3,596 recipes is craftable from renewables). No evolution: Metal Coat (Steelix, Scizor) also has a gem recipe but is in two caches (`data/rewards.json`, the Copperway Khan and Arrow Creeks). Gyms and the League hand out 23 TMs | **Sell finished TMs** on gym counters (playtest note 7): data, but it prices every TM: the owner's |
| 2 | **Mint seeds** (6) | Natures and the 6 Power items. No evolution, no legendary | Six counter lines of the seeds (one purchase each is renewable) |
| 3 | **Dynamax** (band, wishing star, max mushroom, power spot) | Nothing in the campaign; a live but dead mechanic | One config line, `dynamax: false` (owner) |
| 4 | **Brewing stand** (blaze rod) | Renewable Ability Capsules (dragon's breath, four rostered droppers), PP Up by brewing, potions. Capsules are already sold | One counter line of the stand |
| 5 | **Exp. Candies, Rare Candy, Ability Patch, PP Up/Max** | Nothing required; the candies are cut by design (the cap). The Patch is an arena prize | None |
| 6 | **Ancient balls** (15), Beast Ball | Nothing | None |
| 7 | **`lumymon:ancient_dna`** (Giovanni's first win) | **Mewtwo**: the grant is dead without `cloning_catalyst` (a never-spawning admin trainer's drop) | One reward edit: add the catalyst to the grant, or drop the DNA (owner) |
| 8 | **Plain bottle cap** | One-stat hyper-training only (gold caps are sold at Holdfast) | One line beside the gold cap |
| 9 | **Red Orb, Silvally memories, plates, Prison Bottle, Griseous items** | **Silvally's 17 types**: Type: Null is a mythical STARTER (`data/mythical_starters.json`), so a starter's final is stuck Normal. **Primal Groudon** (Groudon is sited, `data/legendaries.json`). **Hoopa Unbound** (Hoopa catchable at the cradle is the owner's 2026-10-06 decision). Plates and Griseous: nothing (no Arceus; Giratina not adopted) | Hand each with its species: memories at Silvally's evolution or a research-station line; the Orb in Groudon's chamber; the Bottle with the cradle release |
| 10 | **Dubious Disc, Sachet, Chipped Pot, Masterpiece Teacup** | **Porygon-Z** (Porygon is rostered, weight 12) and **Aromatisse** (Spritzee rostered, weight 6). The pot and teacup are cosmetic forms (Antique Polteageist, Artisan Sinistcha); the base evolutions use the cracked pot and unremarkable teacup | One cache each, or two counter lines |
| 11 | **LumyMon's nine Kanto gym locators** | Nothing; misleading (they point at gyms that never generate) | A recipe kind in `progression_pack.py upstream_neutralised` (generator change) |

**What actually blocks something:** 1 (crafted TMs), 7 (Mewtwo), 9 (Silvally's types, Primal Groudon, Hoopa
Unbound) and 10 (Porygon-Z, Aromatisse). Items 2 and 4 cut a convenience; 3, 5, 6, 8 and 11 block nothing. Item
status is relayed from the sweep (its model); the evolution items were re-read from the 1.8.0 jar's species files
tonight.

## 5. The ledger

### Done before tonight (found while checking)

| # | Item | Source | Status | Size |
|---|---|---|---|---|
| U12 | Ability Capsule on sale | PLAYTEST 8 | done (Northlight, 10,000 is a proposal price: owner) | S |
| U13 | Feather chests out of the bird towers | PLAYTEST 14 | done, read back | S |
| U14 | Old Knot still; Pallet Caterpie; Azelf's gate; Dr Vale's line; waystones ungated | REVIEW 84, 85, 87, 88, 89 | done in staging, not seen in game | S |
| U15 | Spawn tiers strict xfail now XPASS | REVIEW 82 | done (marker removed 2026-10-05) | S |
| U16 | The play test's deferred apply (farms, bank list, Coldwater, docks) | PLAYTEST | done (applied 2026-10-06) | M |
| U17 | Kubfu's scrolls from the research station | REVIEW 26 | done (the station's errand; REVIEW 88 fixed its locked line) | S |
| U18 | Mega den lines catchable | PLAYTEST | done (the owner: stay catchable) | S |
| U19 | Decisions A1-A3, B16 | DECISION_QUEUE | done | - |
| U20 | Hoopa renders? | DECISION_QUEUE C1 | done: N59, Mega Showdown ships its model; a display Hoopa was shown to the owner | S |

### Obsolete

| # | Item | Source | Why |
|---|---|---|---|
| U21 | The Nether question | REVIEW 69, PLAYTEST | the owner: "the Nether exists" |
| U22 | "Nothing invokes the story" | N12 | wrong premise; the chain runs |
| U23 | Z2's gate, NPC skins, Frostpeak heart, Pidgey swarm, HQ loss as blackout, as OWNER questions | REVIEW 44, 53-54, 60, 61; MORNING 10-04 | the owner did not recognise them (PLAYTEST); the Pidgey swarm stays a recorded defect (U70) |
| U24 | Jungle Isle residue (B15) | DECISION_QUEUE | the isle is gone; elders moved (STATE) |

### Owner: decisions and in-game checks

| # | Item | Source | Size if yes |
|---|---|---|---|
| U25 | Challenge mode: both leaders standing in each gym | PLAYTEST 1, MORNING 10-06 #6 | L |
| U26 | Deep city purpose; the Displaced City market (held) | PLAYTEST 5, N26, N35 | S to apply |
| U27 | A reason to build a house; `crafting_upgrade`'s home | PLAYTEST 6, B6, B7 | M |
| U28 | TM seller and the obtainability proposals (mint seeds, brewing stand, Z/Dynamax config, Ancient DNA, plain caps) | PLAYTEST 7, N23 | M |
| U29 | Mega carry (no stoneless Mega Evolve; permanent Mega form is the candidate) | PLAYTEST 13 | M |
| U30 | N8 badgeless tellers reach the finale's door | N8 | S |
| U31 | N39 evolution stones gated or open | N39 | S |
| U32 | Route species lists grew to 35: accept | MORNING 10-06 #5 | - |
| U33 | N6 summit barrel loot | N6 | S |
| U34 | Waystone sites: second Viltri Quay, research stations | REVIEW 89, STATE Navigation | S |
| U35 | Kyogre questions 1 and 8 (defaults kept) | MORNING 10-06 #9 | - |
| U36 | Far-south residents L56-58 over gym 7's cap | REVIEW 65 | S |
| U37 | Co-op hold-off at leaders; Elara's door re-entry | REVIEW 78 | S |
| U38 | The Champion beats every starter (KNOWN) | REVIEW 77 | - |
| U39 | Portal sheets, the temples, the Mega field rebuild (held) | REVIEW 73, PLAYTEST | M |
| U40 | C2b: does the multiplier scale bank sell-backs (sell one emerald block) | DECISION_QUEUE C2b, STATE | S (30 s in game) |
| U41 | C2 defaultShop fallback, C3 Brock rematch, C4 two players in one dialogue | DECISION_QUEUE | S each in game |
| U42 | B1 VR's tenth trainer, B2 which lines play, B4 open-air den gate, B5 Slip stays cancelled, B10 blackout vs 20,000, B11 railing at the 18-block drop, B11b/B14 gate and marker coordinate | DECISION_QUEUE | S-M |
| U43 | `patriarch_from_victory_road` fragile; Pallet relocation; Route 1 middle feature; hometown and midpoint waystones; Route 8 landmark; street light | STATE What is open | S-M |
| U44 | In-game: West Spur Dig stall walk (N37), held item on ~40 Geodude, a Steepside stone purchase, the evidence signs, the wreck, the Oak starter failure path (REVIEW 74) | MORNING 10-06 #10 | S |
| U45 | Elite Four refusal, the one in-game check | section 3 | S |

### Open: an agent or the next session can do it

| # | Item | Source | Size |
|---|---|---|---|
| U46 | **Apply the next batch**: merchant conversion and the fossil dig (prepare, install, R9FD, R17M, R17N; read back 15 counter merchants, 12 seams); now also the Mart tiers (vendors) | HANDOVER 2 | M (server) |
| U47 | Direct the player to the Mega field after Koga: no dialogue points there today (searched `data/dialogue.json`) | PLAYTEST 2 | S |
| U48 | Side islands so the path is not gym-to-gym | PLAYTEST 3 | L |
| U49 | Gym juniors (Brock's has none; withheld until an unavoidability model places them) | PLAYTEST 4, REVIEW 86 | M |
| U50 | Held items more directly (Choice Band, Life Orb); a gym token swapped for a held item | PLAYTEST 10, 11 | M |
| U51 | EV training without the grind (vitamins sold at Northlight; feathers/mochi native) | PLAYTEST 12 | M |
| U52 | Per-player chests: the ADR | PLAYTEST 15, STATE Wave 1 research | M |
| U53 | Where to go after gym 8 (no in-world explanation of Victory Road or the finale) and the other five P1s | HANDOVER Queue 1 | M |
| U54 | HQ and arena fights ignore the level cap (Cobblemon NPC battles) | N57 | M |
| U55 | Elara: R18HQ re-run so staging matches; the finale's stage write did not persist | N58, Queue 5 | M |
| U56 | A catchable Hoopa at the cradle on release (decided) | Queue 5 | M |
| U57 | Mega dens hold 2-3 Megas, respawn clock unset (P1) | N50 | M |
| U58 | `crater_operation_stopped` has no setter | N9 | S-M |
| U59 | `data/quests.json` marks the 8 evidence objects "unbuilt"; Elara/Brann recorded as rctmod trainers | N10, REVIEW 78 | S (datapack-content-dev / Codex) |
| U60 | Three placeholder lines for Codex; the Harbour Mark's "5.8 km" (measured 5.0) | N19, PLAYTEST defects | S (Codex) |
| U61 | Coastal strips have no campaign pool (sub-region polygons predate the water export) | N2 | M |
| U62 | `sea_drift_audit` needs `COBBLERS_SERVER_ROOT`; give it a settings fallback | N40 | S |
| U63 | Ambient: generator does not enforce shares (N3); plaza_centre/mines steer clear of ambient.json workers only (N4); compose does not replay build/ (N43); no square levelling in the replay (N44); Greenhollow furniture (N45); `TownBuildings.door()` misses the Displaced City's doors (N46) | N3-N4, N43-N46 | M |
| U64 | Failing tests: `test_ambient_composed` 11, `test_ambient_idle` 11 (N47); `test_ambient_sites` duplicate-worker sample (N25); `test_npc_seats` 3+2 without build/ (N34); `test_no_swallowed_crashes` (N11) | N11, N25, N34, N47 | S-M |
| U65 | Second readers wanted: `ambient_idle_audit` exemptions (N48), the implementer-edited tests (N5), `fossil_dig_audit`'s waiver (N60), deep_walk/hq_tower/town_squares audits and oak_starter P4 (REVIEW 71), the STOPPED tower (72), and tonight's `test_mart_tiers.py` | N5, N48, N60, REVIEW 71-72 | M (test-author) |
| U66 | No no-crafting audit; `upstream_neutralised` cannot empty a recipe; `rewards_pack`'s jar check cannot read an offline snapshot | N24 | M |
| U67 | R17M runs merchants only where a stall is sited; a Steve off its seat is not removed | N55 | S |
| U68 | `data/towns.json` stale: Pacifidlog at its pre-move site, Rimwatch ~170 off, the Displaced City 300+ (the Mart tiers read clerk positions to avoid it) | N27, REVIEW 58 | S (world-content-dev) |
| U69 | Before Misty the wilds stop at L19 and every starter loses to her | N29 | M |
| U70 | Pidgey swarm at the Route 1 sapling; four trainers with feet in a block; the nest hint has only two NPCs | REVIEW 61, 62; N33 | S |
| U71 | z4 covers the League, held only by needs_dialogue | N30 | M |
| U72 | Trail Novice beats a fresh L5 starter (all but Meltan); gym team sizes planned 4/4/4/4/5/5/6/6 vs authored 3/3/4/4/5/5/5/6; E4/Champion Challenge teams are placeholders | REVIEW 76; PLAYTEST balance | S-M |
| U73 | Victory Road's walked line stops 352 short of the League (never re-walked); Route 2 crosses two areas | PLAYTEST balance | M |
| U74 | Apricorn farm barn step, lantern on leaves, 282 dark cells; Arrow Creeks gate and Combee (N49) | REVIEW 81, 83 | S |
| U75 | Long Isle full design (access, band, jungle, quests); the weather trio's sites (Groudon in a volcano, Rayquaza's sky island) | PLAYTEST owner decisions | L |
| U76 | Mega field: Cutters' raw stones ~7x; 4 dens 0.26 under road_clear; aggro_reach 16; two border sides without their den's scrape | PLAYTEST | S |
| U77 | Do apricorns sell at the bank? Does Stoneford's board "buy ore"? | PLAYTEST | S |
| U78 | B12 gatehouse walkways impassable on foot; B11 marker vs gate; B14 stale (3738, 5082) references | DECISION_QUEUE | M |
| U79 | Ferry migration (contracts C3, C14 fail today) | STATE, MORNING 09-30 | M |
| U80 | `max-tick-time` back to 60000 and the play-test grants on two staging accounts: check at the next boot, reset before release | PLAYTEST | S (server) |
| U81 | A staging launcher that outlives the tool (memory: the Terminal panel); CLAUDE.md still names only Start-Process | N53 | S |
| U82 | The suite figure in STATE is from 2026-10-02 | STATE "The suite" | S (main session) |
| U83 | `presence_audit` probes the arena crown one under its floor; 9 stale probes | REVIEW 43, N51 | S |
| U84 | **New tonight:** `tests/test_gym_buildings_independent.py::...occupies[gym1]` fails: `data/npc_seats.json` seats[10] at (1832, 142, 3661) stands inside Brock's building (the evidence display's teller is at (1831, 142, 3663)) | found tonight | S |

## 6. Proposed STATE edits (the orchestrator's file; not edited here)

1. **What is built, new line:** "**The Marts scale with the gyms** (`data/traders.json` `stock_policy.mart.tiers`,
   `tools/traders.py tiers`): a clerk's shelf is the template's, filtered to the basics plus every tier at or below
   its town's position (gym N's town N-1; off-path by the nearest critical town). Built 2026-10-06, not applied, not
   seen in game."
2. Line 205 (Town squares): "the 12 badge-gated counters stay dialogue clerks" -> "since 2026-10-06 every counter is
   a CobbleDollars merchant (decision `counters_are_merchants`, 53 gates dropped, N54); built, not applied".
3. Line 207 (Market stock can be gated per player): mark superseded by `counters_are_merchants`; per-player stock is
   gone from the markets until a per-player merchant mechanism is proven.
4. Line 216 (Hoopa): "Whether its model renders ... NOT answered" -> "Mega Showdown 1.0.2 ships Hoopa's confined and
   unbound models (N59); a display Hoopa was shown to the owner 2026-10-06".
5. Line 243 (Town centres: "bare paved rectangles ... nothing built") -> obsolete: twelve towns have built squares
   (line 205).
6. Line 198 (Wave 1 play-test fixes): drop "C4 fails on `tools/bank.py`" (fixed tonight).
7. The two N17 lines saying the finale has no setter (N17 names them; the relic file is corrected).
8. "What is open", new line: "**The Elite Four refuse an over-cap player**: VERIFIED offline (rctmod 0.19.0-beta
   `TrainerMob.canBattleAgainst` for every trainer entity, spawner-spawned included; the five are kanto-series by
   upstream mob files our overrides keep); the League's spawners in the world and one in-game refusal are not seen
   (`docs/UNFINISHED_SWEEP_2026-10-06.md` section 3)."
9. Line 232 or the obtainability lines: point at section 4 here for which of the remaining items block something.
10. Line 201 (the suite): re-measure; the 2026-10-02 figures are stale.
11. The spawn-condition policy: the three OWNER TO CONFIRM entries are confirmed by the 2026-10-05 ruling.

## 7. Counts

84 items in the ledger (U1-U84; several rows group related findings). **Closed tonight: 11** (U1-U11). **Done
before tonight, confirmed: 9** (U12-U20). **Obsolete: 4** (U21-U24). **Owner: 21** (U25-U45). **Open: 39**
(U46-U84, one new tonight: U84). Proposed STATE edits: 11.
