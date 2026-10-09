# Morning report: the night of 2026-10-08/09

Branch `claude/night-shift-engine-gym-9b76f2`. Two briefs: the Night Shift's engine and the gym arenas (installed and
applied), then the world brief from ~01:10 (built on branches, NOT installed). Staging is UP for you at 12G, watchdog
60000, terminal tab "staging server"; the coordination lock is released.

## 1. What is IN THE WORLD (staging-2026-10-01, read back from the world)

Prepare 203/203 at `0b3a8b2`, installed (bank held: `install_check` 1 problem by design), then
`run --only R16GA,R16DG,R16DR` with the watchdog off: **0 problems, partial by design (3 of 98 steps)**, then a restart.
Read back after the restart: **8 of 8** leader spawners in their arenas; `presence_audit --only extra` **386 of 393**
(the 7 absent are the old stale ones: Copperway Khan x2, Orchard Sleeper x2, two residents' air, the relic gravel).
Snapshot before: `cobblers-staging/snapshot-2026-10-09-before-arenas`.

**The gym arenas** (each leader moved into his or her arena; the building is the entrance):

| Gym | Arena | Leader's seat | Floor y | Walk in from |
|---|---|---|---|---|
| 1 Brock | The Setting-Out Floor (mason's hall, wall-to-wall stage, trilithon) | (1826, 125, 3662) | 122 | the gallery (1832, 156, 3696), newel stair |
| 2 Misty | The Lifeboat House (boat hall, quay, launch channel) | (1627, 95, 2887) | 92 | ledger gallery door (1606, 99, 2877), slipway |
| 3 Surge | The Grounding Hall (copper switch hall, transformer banks) | (1748, 162, 1435) | 158 | the gallery (1747, 191, 1414), 49-tread stair |
| 4 Erika | The Root Court (round mediation court under the cherry) | (4311, 98, 1514) | 94 | the court (4308, 111, 1480), newel stair |
| 5 Koga | The Tracking Floor (screens hide him until the last turn) | (4586, 103, 2461) | 100 | the watch floor (4594, 132, 2487) |
| 6 Sabrina | The Observation Well (tallest; lens hung over the floor) | (6181, 70, 3320) | 66 | the lens chamber (6196, 112, 3312), terrace at y80 |
| 7 Blaine | The Core Gallery (banded strata, lava behind glass) | (6166, 87, 4981) | 84 | the assay vault (6178, 107, 5001), adit |
| 8 Giovanni | The Sally and the Muster Hall (bunker under the gate) | (3556, 94, 6419) | 90 | the gate walk (3565, 121, 6416), sally and blast door |

Sized to each leader's largest Pokemon, every tier, measured from the 1.8.0 jar; the independent audit re-measured
(no arena fails clearance at its sizes) and walked every arena down and back up standing. **None has been played.**

**The Night Shift engine:** four slot shells in `cobblers:pocket` (rows from z 1024; slot 1 at z 1056, slot 4 at
z 1440) on a PLACEHOLDER spine; the rip, also a placeholder, at **(1350-1354, 130, 4117)**, the old mine's notch on the
carts' trail (ground y129 measured). The probe pack `cobblers_dg_probes` is in the staging world only, its areas set up
in the pocket at z -704..-577.

**Not applied tonight (your call, unchanged):** the chunk-race fix's steps and the stale steps from the last handover.

## 2. The probes (section 14): RCON halves run tonight, owner halves waiting

| Probe | EXP | RCON result | Engine rule it gave |
|---|---|---|---|
| P1 discard | 069 | PASS on a wild Pokemon, all three forms | the recall sweep uses it (owned Pokemon unproven) |
| B1 bossbar | 070 | PASS: the name resolves from scores; value tracks | per-member bar as designed |
| B2 kill + totem | 071 | PASS (villager proxy): `kill` goes through a totem; `damage ... outside_border` is STOPPED by one | the timer's kill is `kill` |
| B3 sudden death | 072 | PASS (proxy): clock stops at 0, no kill while absent | |
| R1 mined stat | 073 | PASS: the criteria parse | |
| R2 can_break | 074 | PASS: both component forms parse | |
| F1 fall | 075 | READ (villager proxy): a teleport CARRIES the fall; resistance 5 covers it | catch bands give resistance 5 first |
| L1 lake | 076 | 3 PASS, 1 FAIL: glow given in the spawn's own function misses | effects a tick after a macro spawn |
| L2 underwater | 077 | PASS: spawns hold under water | |
| C1 chain | 078 | PART ONE PASS: a macro `spawnnpcat` works after a plain restart; a PLAIN one fails to parse at load | every NPC spawn is a macro line |
| XT1 timing | 079 | setup only | **all clocks stay tunable data until you time fights** |
| V1 visibility | 080 | displays parse | the 48-block particle radius cannot reach 64-128 (design issue) |
| I2 re-apply | 081 | PASS: 456,264 blocks in 2.64 s fresh, 1.75 s over a dressed interior | re-apply step only, never at entry |
| LO1 logout | 082 | setup only | |
| SG1 sigils | 083 | PASS: a Crafter crafts the Soot Sigil with its components; the predicate parses; **only the byte form `1b` matches a crafted sigil** | the engine uses `1b` |

**No probe killed a mechanism.** Probe-pack defects found and fixed: MobsBeGone deletes every summoned vanilla mob but
villagers (B2/F1 stand-ins changed); SG1's 19-character test name.

**What you do for each (the full steps, teleports and RCON lines are in each EXP's section (b)):**
- **P1** (12 steps): send out a Pokemon in the probe's no-deploy box; watch it recalled; check its HP is kept and it can be sent again.
- **B1** (6): stand in B1's area, read the bar; log out and in; see it clear.
- **B2** (5): hold a totem in the off hand while the session runs the kill; the blackout fires once.
- **B3** (6): be in a battle when the clock hits 0; die when the battle ends, not before.
- **R1** (4) and **R2** (7): mine the seam ores in adventure with the rift pick; nothing else breaks; the count rises.
- **F1** (7): fall into the catch tubes; read your health after the catch teleport.
- **L1** (4): from the gantry 40 above, say whether glow, lanterns, bubbles and beacon read as obvious.
- **L2** (10): start and finish a wild battle under water with Dive.
- **C1** (6): beat three chained NPCs; each next one should start about 3 s later.
- **XT1** (6, nine fights and a chain): fight the timing NPCs; the ticks are recorded as scores.
- **V1** (7): look at the rip from 32, 64 and 128 blocks.
- **LO1** (17): log out mid-run for less and more than the clock; mid-battle; and a one-minute server stop.
- **SG1** (7): the `recipe give` half under `doLimitedCrafting`.
- **EXP-084, the engine** (15 owner steps): a run end to end on the placeholder spine. **DX1** (the run tag in a real
  death) waits for it.

## 3. What the engine has (`tools/dungeon.py`, `data/dungeons.json`; EXP-084 RCON part 16/16 PASS)

The per-player clock in quarter-ticks, the per-member bossbar, the return margin, timeout and sudden death (the kill
waits for the battle and the clawback), the logout rule (gap charged, slot freed at its deadline, dead run killed on
return, run first); the greed ladder (x1.25/1.5/2/3 at 5/10/15/20; the seam will call `greed/take`); four slots with
shells by re-apply (28,145 blocks each); boss stages chained by the victory callback, NPCs by macro only; the recall
sweep; entry, exit, eject, lockout (an hour of uptime, never gametime), band frozen at entry, over-cap party refused,
adventure on arrival and survival on every way out; **E1, both halves**: tag `cobblers.dg_run` added before the
arrival delay, a 120-tick tail, no claim and no delivery while tagged (`tools/blackout_pack.py`), contract C24 now
passing. **Sigil entry is configurable: no free first run (Q20 OPEN), recipes gated by band (Q23 OPEN): staging values,
not decisions.** Not built (step 6): stands and their clawback, the seam, parkour, the lake, the den.

**Remember: Q20 (the Night Shift's free first run) and Q23 (ungated sigil recipes) still wait on your alternative.**

## 4. The world brief (built by its builders; MERGED into this branch at the end of the night; NOT installed)

| Place | Branch head | Where | What |
|---|---|---|---|
| Hummock Mere (swamp nest) | a775 `3af7466` | (5240, 1924) B6 | a drowned mangrove ring round a sleeping Clodsire L52 x2.2; catchable at gym 7 |
| The Drowned Quarry (Tilpey) | ac7d `bd39246` | road from (6340, 4108) y52 to the sump (6528, 47, 4132) | a flooded quarry under the lake's east wall; Gyarados L60 x2.0; **the Dive gate is the swim's LENGTH** (Tilpey is only 25 deep) |
| Lake Tilpey spawns | a033 `a9aa8f5` | the five Tilpey tables | +10 species (86 to 96); the two-table rule capped it: relax it for Tilpey? |
| Fungal Isle (Mushroom Island) | ac9d `f2f4ea4` | F1 | 101 giant caps, Cap Wood, Stump Court, Glowcap Hollow with its missing pool; three nests |
| The Sundown Watch (Sunset Isle) | ab7d `49a3580` | (1072, 7492) H2 | a dusk-only stone dial: Dreepy line, Dusk Lycanroc at dusk only; keeper Isaura Dray; rumour on both ferries |
| Wardenhold (Frostpeak Strand) | af82 `5a52d69` | (1548, 636), spire to y198 | a snow keep sited by sightline: its spire is seen from all ten Highwire street points (no Strand cell shows a point 20 up) |
| The ice fishing lodge (Merian) | a54e `7a669dc` | tarn x2738-2797 z1069-1101 | holes, shelters, Holekeeper Ketil Aune; prizes NOT built (no system yet; the hook designed) |
| Crownbreaker (Tri Peaks, A2) | aac9 `1e99d60` | (1478, 254, 1062) | a Tyranitar L35 on an open summit ringed by rock teeth, seen from Highwire |
| The Undertow (F8 dunes) | a6f9 `aaa9a82` | (7282, 5592) | a buried Sandaconda L55 x2.0 that rises when you step into its bowl |
| Gull Rock (C7) | a657 `01f9b13` | (6940, 2650) | an authored sea stack: Dragonite L55 and a bird colony on six tidal rocks |
| Route 5: The Bellwether | a7b3 `2c90346` | Route 5 | a four-scene shepherd chain, items only (7-11% of leg 5 income) |
| Route 4: The Thaw Road | aef5 `2a48d77` | Route 4's middle, headwall camp (2500, 1278) to the thaw gate (3033, 1714) | a lost Gogoat followed to the Displaced City's tunnel mouth, $0 cash; **the route passes 14 blocks from the Displaced City's centre, not the 250 STATE says** |
| The Long Count (C3, band 2) | a81e `7344e73` | camp (2136, 2160), lane to (2223, 2073) | a Grotle, Old Pace L29, that walks eight paces a year toward the world tree, a tree where it sat each year; Perrin Hale's request; the gym-2 band's first optional place. Its lantern is seen from Route 3 only at the fog edge (the 96-block rule pushed it 163 out). NOT in tonight's independent audits |

Designs written (not built): **dungeons 2 and 3** (`docs/mechanics/DUNGEON_2_STREET.md`, `DUNGEON_3_PATRIARCH.md`);
**catches on the clock** (`DUNGEON_CATCHES.md`); **the world sweep** (`docs/world-building/WORLD_SWEEP_2026-10-09.md`).

**The catch-loss verdict** (`docs/research/notes/dungeon-catches-on-the-clock.md`, `DUNGEON_CATCHES.md`): HOLDING
catches until a clean exit is NOT possible intact without a mod (the catch is in the party before any callback runs, and
nothing re-gives a Pokemon whole). So: mark each catch at the hook AND list it in a per-run ledger; on a named failure
only, remove by uuid when mark and ledger agree, after the death, outside the pocket, out of battle, never the party's
last Pokemon, held item returned first, then confirm it is gone. Anything uncertain is kept. A report-only build first.
**Beast Ball**: the design agrees a dungeon legendary is kept on failure, but anchors it by the dungeon's legendary
SPECIES, not the ball: a $5,000 Beast Ball catches anything, so a ball anchor would sell insurance on nest catches.
One catch counts as one block on the ladder (ten catches: x1.5). Nothing about it is runtime-proven (the research did
not open the jar; 17 probes listed).

**The economy result** (`tools/economy_sim.py`, `docs/mechanics/ECONOMY_SIM_2026-10-09.md`, simulated): **as
designed it holds**: a steady player ends $328,345 against $333,511 without dungeons (-1.5%), spend over income
0.67-0.68 at every badge, no loop prints money (the best dungeon hour is 0.05-0.53 of the fight hour), no new
starvation. **But the boss stages pay the NPC payout today (no clawback yet)**: band 6 nets $9,965 an hour instead of
-$1,459, and **stands built without the clawback WOULD print money (16.5x parity at band 6)**: the clawback must land
before step 6. The TM gate's `recipe give *` costs ~$0.

## 5. The review list (new tonight; the old list is `docs/OVERNIGHT_REVIEW_2026-10-06.md`)

1. **The OOM (my fault).** A `datapack enable` is a full reload and ran the 16G server out of heap at 02:00. The world
   was set aside (`staging-2026-10-01.oom-2026-10-09`) and the pre-install snapshot restored; nothing of tonight's apply
   was lost. N111 holds at 16G: never enable a pack by command.
2. **The arena pack was never installed** by the installer (listed `WORLD_LOCAL` only) while install_check said
   current. Copied by hand for this apply; fixed in `SERVER_PACKS` with a guard test.
3. **Arenas:** the swap: Brock's move is built; the other seven keep their Challenge spawner, moved into the arena.
   **Rolling any of them into the one-leader swap needs `tools/challenge_mode.py:344` `restore_blocks` fixed first**
   (it would write the hall's floor into the arena; strict xfail). GYM_ARENAS.md's size table is off for six leaders
   (the audit's bone transform); no arena fails clearance at the audit's sizes. Erika and Koga share materials.
4. **Engine:** a won boss stage pays CobbleDollars' payout (step 6's clawback); a player who leaves the slot alive in
   sudden death escapes the $600 (`tools/dungeon.py` `m/left`); stale text says the engine does not exist
   (`data/blackout.json:213`, DUNGEON_DEATH "E1 as built"). Fixed tonight: a freed slot kept its run id (a returning
   player resumed in a freed slot).
5. **Dungeons 2 and 3 need engine changes:** one clock table for all dungeons; every floor at y96 and the way back from x
   only; a healing machine in a dungeon would move the blackout respawn. The Scar is not in the live world.
6. **Catches:** `DUNGEONS.md` said catches are kept on failure: the new rule reverses it (lines marked). Q-C1 (D8/Q11
   "every catch after the Champion"), Q-C6 (nest spawns by macro outside `spawns.json`).
7. **Balance calls:** Tyranitar catchable at badge 3; Dreepy line anchoring a pool at 30-38; a Gyarados L60 and the
   residents return hourly even after a catch (farmable); a caught Dragonite (7 badges) is a Surf mount that opens the
   Northlight strait; Clodsire at 52 over its place's ceiling of 45.
8. **Records that disagree:** several data files say "not applied" where STATE says applied (residents, Khan, Frostpeak,
   Lopunny, fossil dig, training grounds, Coldwater, Seaward Drift); `adopted_legendary_sites.json:336` feather issuing;
   STATE's two location-title lines; `income_basis` is no longer model B (`tools/bank.py:450` still says so); the bank
   opens the Nether tier at leg 7 against the gate's badge 8; STATE's "EV/IV about $50,000" against $722,400 for a team;
   `regions.json` calls Sunset West and the Fungal Isle "empty"; the Merian hut is 690 blocks from the river's source.
9. **Owner choices waiting:** the Tilpey two-table rule; the native Fungal Dwelling; the quests `SQ-MERIAN-01/02` point at
   a keeper with no NPC (Ketil?); Wardenhold's name and story; the fishing-prize system; no rumour points at the
   Undertow.
10. **Self-graded:** most world-brief builders wrote their own audits (mutation-tested, but not independent); an
    independent audit of those places is owed before their install.
11. **Pre-existing, not tonight's:** two `test_spawn_habitat_audit`/`tiers` order tests (`7194e31`); the 61-vs-60 Cutter
    stones; four `600 == 200` blackout tests.

## 6. Cost (`python tools/session_cost.py`, weighted)

This session ~14M by the time of writing (context 599k: over the hand-over line); agents **99.3M** with two still
running, against the estimates given before spawning of about 100M in all (39M for the engine and arenas, 37M and
24M for the world brief's two waves). The arena pilot ran at 10.4M against 5M; the seven arena authors 7.1M against 18M. Per agent against its estimate: section 6 of `docs/HANDOVER_SESSION.md`.
