# Handover — there is a world, six decisions are in, and the tests are the debt

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. The branch

- **`build/2026-10-01-rift-builds`**. **Re-read the head** — `git rev-parse HEAD` — it was `604e249` when
  this was written and has moved since.
- **[PR #104](https://github.com/Millerb7/cobblers/pull/104)** is open, draft, against `main` for the
  earlier part of this branch. **Its body is now badly out of date**: it describes the Mega farms as
  *parked*, which they are not. Update it or open a second PR for the night's second half. The freeze rule
  says check a branch's PR state **before** pushing — `gh pr list --head $(git branch --show-current)`.
- [#102](https://github.com/Millerb7/cobblers/pull/102) and [#103](https://github.com/Millerb7/cobblers/pull/103) are the earlier drafts. `origin/main` is still `a271532`; **none of tonight is merged**.

## 2. There is a world, and most of the campaign is standing in it

**`C:\Users\wnd\Documents\cobblers-staging\staging-2026-10-01`** — 484 regions, exported from the pinned
heightmap with the paint, seed `-472167725407180184` carried from a disposable copy of
`cobblers-10240.pre-rescale`'s `level.dat`. **Boot it as a disposable universe, never by `level-name`:**

```
cd /c/Users/wnd/Documents/github/cobblers-server
java -Xmx16G -jar fabric-server-launch.jar nogui --universe C:/Users/wnd/Documents/cobblers-staging --world staging-2026-10-01
```

**38 of 38 apply steps ran.** The floor verify covers 27 places and **26 have zero gaps**; `sea_town` has
**92** and its own verify exits 1 — the known migration (contracts C3/C14), now measured rather than
inferred.

**Probed in the world, not in the plan:** the arena stands (shell solid r=16 from y5 to y127, tier 7 floor
solid r=4→16 with air at r=17, crown floor y127, balustrade y129); the pit around it is dug (air y10–y80
at r=25, rock at r=60); a trainer answers at Victory Road's first seat ("League Applicant") and **the
tenth is the League Examiner**.

**`cobblers-10240` was never opened.** `server.properties` is unchanged — `level-name=cobblers-10240`, and
`max-tick-time=60000` restored after the run forced `-1`.

**The server may still be running** with the owner on it, and **this session holds the coordination
lock**. Check `python tools/server_lock.py status` and release it when they are done.

## 3. What the apply taught, and it will bite again

**R14C (the Celebi) failed twice, and re-running did not help.** The step guards with `unless entity
@e[type=cobblemon:pokemon,distance=..3]` so a re-run never stacks a second Celebi — but **wild Pokemon had
spawned at the sapling**, satisfying that guard and suppressing the spawn entirely. Clearing them made it
pass, count 1. **`tools/sapling_celebi.py`'s guard is not idempotent against wild spawns** and will fail
this way on any world where something wanders in first. It wants a narrower selector — a tag, or the
species.

## 4. The six decisions, and the two follow-ups

| # | Decision | State |
|---|---|---|
| **A1/A2** | `--plan` measures the applied sculpt | Done, **and the gate was KEPT** |
| **B1** | The League Examiner | Recorded as settled; the Gate Warden kept as history |
| **B2** | The roster's lines play | **10 deleted, 28 kept** — the count was wrong |
| **B3** | Clear Giovanni's hold | Done: **8 leaders emit, not 7** |
| **B4** | Drop the open dens' zones | Done; `zone` optional per farm; audit CLEAN |
| **B6/B7/B9** | Two strands, crafting to Brock's, re-price | Ladder revision 2, against 1.25 |
| **B10** | Blackout off a cap | Flat **$600**; contract **C15** registered |
| **D1** | The guard exception | Written into CLAUDE.md |
| **D3** | Fix all seven | Six fixed **from the code**; the seventh was B4's |

**A1 kept its verification gate** against the letter of the decision, and the owner endorsed that: with the
entrance gaps *measured*, the sculpt reproduces the applied heightmap **pixel for pixel**, so the price the
decision accepted need not be paid. **`derived/rift_sculpt/` is rebuildable** — `--plan`, ~40 s.

**The two follow-ups:** the arena's seven champions (aces 56→76, three to six members, **no gating**,
endlessly repeatable because `repeatable: true` drops our own `Cooldown` line — rctmod never refuses a
rematch with a persistent trainer anyway), and the Victory Road trailhead moved onto the walked line at
**(3548, 114, 5322)**, with the route reaching it by *being* the route.

## 5. THE TESTS ARE THE DEBT. Fix this first.

**29 failed, 5,235 passed** on the last full run (658 s), against a baseline of **6**. **Not one is a fault
in the data** — every one is a test asserting something a decision deliberately changed. Chip
**`task_4e2821f9`** carries the brief. Known contributors:

- **C15 has no test, on purpose.** `test_every_contract_names_existing_tests` and
  `test_every_contract_test_here_is_registered` fail until it is written. C15 carries a verbatim
  `note_for_the_test_author` and a reserved test name.
- **8 in `test_trainer_cycle.py`** — one asserts 56 seats where there are now 63; seven are the cooldown
  parametrisation hitting arena seats that **deliberately have no cooldown line**.
- **6 in `test_blackout_pack.py`** near lines 690 and 717, still asserting `ceil(balance*pct/100)`.
- **1 in `test_id_authorship.py`** — `test_a_diverging_dialogue_text_is_superseded_rather_than_faulted`
  asserts `RT.SUPERSEDED` is non-empty, and B2 deleted the ten sets that made it so. **Proved
  pre-existing** by stashing the arena work out, where it still fails.
- **2 in `test_rift_heightmap.py`** — `_maps()` reads `heightmap["path"]`, which the water pass moved.
  They want `plan_target()`.

**Re-run the suite and account for all 29 by name before building anything.** The list above is assembled
from agent reports and may be incomplete: the run that produced the number had its output truncated by a
`tail`, which is my error and exactly the kind this handover warns about.

## 6. What waits on the owner

`docs/DECISION_QUEUE.md` is the single list. The live ones:

- **C2b, and it gates a change already in the repo.** Sell one `minecraft:emerald_block` on the running
  server (still at **0.5**). Raw price **3,750**. **3,750 means sales are untouched and 1.25 is safe;
  1,875 means the multiplier applies, and at 1.25 that block sells for 9,375** — a money printer that
  invalidates the re-price. `modpack/config/cobbledollars/common.json` carries 1.25 and **has not reached
  a server**.
- **C1** does Hoopa *render* — the species exists (measured in game), the model is a client fact, and the
  Deep's relic area rests on it. **C3** does Brock refuse a rematch. **C4** two players on one NPC.
- **B11** — the route runs 1–2 blocks from an **18-block drop** at (3556–3573, 5287–5302): railing or route
  review. And `rift_entry` plus the zone system's **G2 gatehouse** both sit at (3738, 5082), **145 blocks
  inside the basin**, so the warden's marker and its gate are now in two places.
- **The arena's two open questions** — `healPlayers: false` on an endless ladder with **no healer recorded
  in the Deep**, and whether the crown deserves a prize (none authored).
- **Giovanni has never been fought.** He emits now; gym 8, lot x3556–3588 z6400–6432. **If he fights with
  the Cobbleverse roster, the whole override path is inert** — and that is the assumption all eight
  leaders rest on.
- **Nobody has checked the arena's seven species learn their authored moves.** No identifier was invented,
  but the Cobblemon jar is absent from an agent worktree and `validate.py`'s `missing_pokemon_refs` is
  still a stub, so **nothing in the repo checks them.**

## 7. What a cold start must not rediscover

**Four times tonight the orchestrating session reported a number it had not measured, and an agent caught
each one.** This is the standing lesson, not an anecdote:

1. A Mew site at (5160, 7463) that is **under water** — ground y61 against sea level y62, 0 of 961 sampled
   columns above water, because the water export removed that isle. Relayed from a research note.
2. **"38 superseded dialogue sets"** was **10**. `ownership()` counted divergence from an *empty* roster
   value as supersession, so 28 live sets were reported dead on every run.
3. **"A sculpt built with a stale normals bug"** — false. `rift_sculpted_from` records the same 12,811,417
   blocks and 512,952 columns that `5c82e98`'s own message reports: the fix **was** applied. The drift is
   one entrance, moved by a deliberate re-route.
4. **"44 blocks"** was **44 ring stations** = 53.5 blocks.

**And "not air" is not evidence of a structure.** Probing `if block … minecraft:air` inside a sculpted rock
pit reads solid almost everywhere, and a vertical probe down a tower's own light core proves nothing.
Probe a horizontal slice and look for floor, then air, then void.

**The delegation facts, now measured** (`docs/research/AGENT_WORKTREE_INPUTS.md`, CLAUDE.md): agents read
the heightmap fine; `derived/` was the only gap and `--plan` now closes it; **nothing is refused by a
permission classifier**; and a **shell-less agent cannot run `git reset`**, so it sees its worktree's
original base and must be given absolute paths.

## 8. Cost and the shape that worked

Fourteen agents across the night. The orchestrating session is the expensive half, as always — measure
with `python tools/session_cost.py`, never the harness's per-agent figure.

**The division that worked: authoring, research, generation and tests fan out; the server and the
integration run serialise.** Six at once was the right number, and the collisions it surfaced — two
agents pricing a card in a town another proved had no income; a relayed coordinate that was under water —
were worth more than any single unit.
