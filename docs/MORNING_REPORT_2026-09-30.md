# Morning report — the night of 2026-09-30

Server is **up** on `cobblers-dryrun12`, watchdog restored (`max-tick-time=60000`), 0 players.
Branch `build/2026-09-29-phase2`, head `7f50728`. No PR opened yet; #95 above it is still frozen.

---

## 1. What is IN THE WORLD

Probed block by block over RCON, not inferred from exit codes. 24 of 24 probes matched.

| What | Where | Probe |
|---|---|---|
| **Brock — the Stoneworks Hall** | 1832 156 3696 (spawner) | spawner ✓, the repaired hoist ladder at 1829 155 3697 ✓ |
| **Surge — the Relay Works** | 1747 191 1414 | spawner ✓, lantern + redstone ✓ |
| **Erika — the Great Glasshouse** | 4308 111 1480 | spawner ✓, cherry planks ✓ |
| **Koga — the Reed House** | 4594 132 2487 | spawner ✓, flue ladder ✓, landing bale ✓, stair head narrowed ✓ |
| **Blaine — the Assay House** | 6178 107 5001 | spawner ✓, rail gap ✓, drowned adit ✓, soul sand ✓ |
| The five donor shells and the rejected underground works | — | demolished, two sampled cells now stone ✓ |
| The twelve portals, re-skinned | e.g. 4530 127 1950 | sky apron cobblestone ✓, frame mossy stone brick ✓, dive lamp dark prismarine ✓ |
| Routes 1–3 event sites, re-applied | — | step R12 ran after the re-route |

**Not in any world**, though done in the repo: the lake-bed fix (needs a full R1 re-skin), Victory
Road's ten fights and the League's five (R17 not run), the dig camp's reshape (R9M holds the old shape).

---

## 2. Where to fly — most important first

1. **Blaine's Assay House, (6178, 107, 5001).** The most-changed building and the one resting on an
   unproven mechanic. Get into the vault, beat him, then find the sump in the floor at (6178, 4999),
   swim down and north through the adit, and see whether the **bubble column actually lifts you sixteen
   courses** to (6178, 120, 4997). If it does not, you are sealed in — that is the one thing the whole
   building depends on and nothing has tested it.
2. **Koga's Reed House, (4594, 132, 2487).** Walk in and try to mount the reed stair from the flood at
   z2478. It was a two-block rise and unclimbable; there is now a landing bale. Then check that you
   **cannot** hop from the stair head straight onto the west plank walk — the top course was narrowed to
   one bundle to stop exactly that.
3. **Brock's Stoneworks Hall, (1832, 156, 3696).** The hoist ladder was broken at y155 and the gallery
   unreachable. Climb it.
4. **The sky portals, e.g. (4530, 127, 1950).** You asked for relics rather than portals: cobblestone
   apron, mossy stone brick frame, no glass sheet, cracked stone brick lamps. Say whether it reads right.
5. **The dive portals, e.g. (1652, 76, 2994).** Lights removed — dark prismarine where the sea lanterns
   were. Check they are still findable underwater without them.
6. **Erika's (4308, 111, 1480) and Surge's (1747, 191, 1414)** — both audited completable, neither has
   the drama of the other three.

---

## 3. The things you should know before you fly

**The eight gym leaders are not fighting with our teams.** `data/trainers.json` authors
`gym_01_brock`..`gym_08_giovanni` with ace levels 20/25/30/35/40/45/50/55. Nothing emits them —
`grep -rl "gym_01_brock" build/ modpack/ server/` returns nothing. We write the leaders' loot tables
and never their trainer definitions, so every gym battle uses the COBBLEVERSE roster. Recorded as F11.
An agent is fixing it now; **the fix changes all eight fights at once and wants your word first.**

**Three of the five gyms could not be finished on foot**, and my own pre-flight said all five were
fine — spawners present, no healers, validate clean, generator passed. All true, all the wrong checks.
The independent audit found ten problems; fixing each opened the stages behind it and it found more.
Twelve repairs in all. Two of them were the *same defect written twice by two builders who never saw
each other's work*: a ladder's course through a floor re-cut to air instead of ladder.

**Your ferry already exists on paper, three times over.** `charter_jungle_ruins`,
`charter_appearing_island` and `charter_trench` are all $600 postgame charters from `sunset_quay` to an
island you cannot otherwise reach — exactly the shape you asked for. **One line of ten can actually
run** (`relic_row`): 12 of 16 docks are `planned`, 2 built, 2 retired. Building the docks is the unit
that turns the design into the thing you wanted. And the Jungle Isle's destination was worthless until
last night — see below.

---

## 4. The standing faults, settled

| Fault | Result |
|---|---|
| **The drowned jungle ruins** | They were not drowned. All six stood **60–67 blocks above the seabed**, hanging over the water. Re-seated onto their own ground (y59–62 against a sea of y62), which is what the plan asked for in words: "half sunk". |
| **F5, lake beds** | **Proved and fixed.** `tools/rift_skin.py` filled every column it touched to its own top, including the 113,841 under a lake, overwriting the gravel/clay bed `paint_maps.py` already paints. 227,682 of its fills reached a bed; **zero now.** The recorded hypothesis blamed the water-shape pass — it was wrong; the water shape excludes the Rift outright. |
| **The Routes 1–3 water props / the re-route call** | Made the call: re-route. **Routes 1–8 did not move one column.** Only `victory_road` moved, 246 of 3,677, in its surface approach, nowhere near its caves. The guard is cleared and `prepare` runs again. |
| **F7, the fail-open water check** | Not reached. Still open. |
| **The 12 voids in the Displaced City cavern shell** | Not reached. Still open. |

And two fail-opens found while working, both fixed:

- **`reapply.py run --only` ran zero steps at exit 0** for a comma-separated list — an apply that
  reported success without applying anything. Caught because the run log was six lines long, never by
  the exit code.
- **`portals_audit.py` built a `Counter` from a dict literal with duplicate keys**, so once two roles
  shared a block the frame count silently vanished.

New gate: `tools/placement_ground_audit.py`, fail-closed, which would have caught the ruins the day
they were written. It found two more buildings buried in their own lots. Clean over all 32 absolute
placements now.

---

## 5. Cost, and the pricing you asked for

`python tools/session_cost.py`: **573 turns, context 446k, 16.7M weighted** for the main session;
**25.5M across 19 agents**; **42.2M together** for the whole session (both days).

Tonight's three agents, against what I would have quoted:

| agent | quoted | actual | verdict |
|---|---|---|---|
| Rift status inventory | ~1M | **0.76M** | close |
| Victory Road + League fights | ~2–3M | **0.99M** (unit 1) | **2.5x over-quoted** |
| Rift zone system | ~3–5M | **1.07M** and still running | over-quoted so far |

**You were right that I am 2x out in both directions.** The correction: a research or
placement agent that reads and writes data lands near **0.8–1.1M**, not 2–3M. What actually costs is
an agent that *builds and iterates* — the gym interiors agent was 3.82M, the independent review 2.99M,
the dig camp 2.20M. The rule I will use from now on: **reading and authoring ≈ 1M; building and
re-running a generator ≈ 2–4M.** Tonight's three were all the first kind and I would have said 6–9M
for what cost 2.8M.

The main session is the expensive half again — 16.7M — and at 446k of context every turn costs 44k to
send. `session_cost.py` says HAND OVER. This ran long because you asked for the night and could not
compact.

---

## 6. What waits on you

1. **F11** — confirm the eight authored rosters should replace COBBLEVERSE's before it is applied.
2. **Fly the five gyms**, Blaine's first (§2).
3. **The ferry**: build the twelve planned docks? That is the unit that makes the charters real.
4. **`patriarch_from_victory_road` is fragile** — 10 observer points of 137. Taller wedge, or downgrade
   the claim?
5. **The ferry migration** (contracts C3/C14, both now recorded as `fails_today`): which line replaces
   the Sound ferry, and where is Pacifidlog's square now?
6. **Lugia's level** — its gate is `champion_cleared` and that cap is `null`.
7. **Registeel's location** — `upper_rift` (4195, 3896) recommended; it also fixes Regigigas, which is
   otherwise permanently unreachable.

---

## 7. Added after the report was first written — the two agents landed

**F11 is fixed.** Seven leaders' teams now emit as overrides at their upstream ids, verified off disk
against `data/trainers.json`: brock ace 20, misty 25, ltsurge 30, erika 35, koga 40, sabrina 45,
blaine 50 — every one exactly `gym_ace_levels`, zero mismatches. Giovanni is `status: held` with an
empty team and is deliberately not emitted. **It rests on one untested assumption**: that a datapack
override at `data/rctmod/trainer/kanto_brock.json` replaces the roster rctmod loads from its jar. The
same assumption is already proven for these trainers' *loot* tables; the team path never has been.
**One staging fight with Brock settles it, and if it does not take, all of it is inert.**

**The Rift Z1–Z5 zone system is built and deliberately NOT installed.** `data/rift_zones.json` (2,297
lines), `tools/rift_zones.py`, four zones, three walls, four gatehouses. Re-run here rather than
trusted, and the re-run found what the agent's worktree could not:

> R9Z places **obsidian walls** across the Rift's throat, the League's gate and behind the League. The
> functions that let a player *earn* a pass — `z{1,2,4,5}/qualify` — **are called by nothing at all.**
> Installed as it stands, the walls go up and nobody can ever pass them.

`reapply.py`'s own `unreferenced()` check caught it, which is exactly what that check is for. The pack
is EXCLUDED and the step withdrawn until two things hold: every zone's guard calls its qualify, and
`progression.json` declares `rift_crisis_resolved` with something that sets it. **The setter is the
finale's quest stage — story data, and Codex's.** The agent was right to refuse to invent it.

Its one argued mechanism change is the unit's real value: `RIFT_ZONES.md` §4 put
`minecraft:entity_scores` in the `in_zone` advancement, which **fails open** — it does not match an
unset score, and nobody has one until a guard sets it. Now the advancement tests location and the
reward function tests the score.

Three more of its findings: the cradle belongs at (3357, 3306), not FACTION.md's (3297, 2603), which
is outside the Rift entirely; **Z3 is superseded** by the gulch's own zone; and Registeel's effective
gate is **8 badges, not 7**, anywhere in the Rift.

**The suite:** 4,937 passed, 8 failed, 8 xfailed. All 8 failures fail identically at 36eb267 — checked
in a throwaway worktree — so nothing tonight regressed anything. Three tests that Victory Road's ten
broke were taught about the new seats rather than having their numbers bumped.

**Cost, final:** the zone agent came in at **1.07M**, Victory Road + League at **0.99M + 0.62M** for
two units, the inventory at **0.76M**. Four agent-units for ~3.4M against the 6–9M I would have
quoted. The corrected rule stands: reading and authoring ≈ 1M, building and re-running ≈ 2–4M.
