# Decision queue

**Everything waiting on the owner, in one list, so it can be answered in a single pass.** The owner,
2026-10-01: *"That has cost more throughput than anything else."*

Each item: what is blocked, what the options are, and what a session will do with each answer. **Nothing
here is urgent in the sense of unsafe** — they are all "a session cannot choose this for you".

## A. Irreversible or world-shaping — these actually block work

| # | Decision | Why it is yours | Options |
|---|---|---|---|
| **A1** | **The Rift sculpt has drifted from its spec by 10,867 columns.** Tool commit `5c82e98` fixed a *normals bug* after the sculpt was applied (`835bbdf`) and nothing re-applied, so the heightmap in use holds a sculpt computed with a bug that is now fixed. | Re-applying rewrites the canonical heightmap and `data/world.json`, re-pins the sha256 every measured artifact is keyed to, and needs a full re-export. It also changes the Rift's *shape*. | **(a)** Leave it: the shape players will see is the one in the heightmap, and `derived/rift_sculpt/` stays unrebuildable. **(b)** Re-apply with the fixed tool and re-export, accepting a changed Rift. **(c)** Change `--plan` to *measure* the applied sculpt from the heightmap instead of recomputing it from the spec — makes the folder rebuildable but stops detecting exactly this class of drift. A test author's verdict on (c) is in this wave. |
| **A2** | **Whether `derived/rift_sculpt/plan.json`'s hand-edited sha stands.** Its sha was edited by hand on 2026-09-29 with a note arguing the water pass changed no Rift columns — true, and it carried a stale claim about the *sculpt* pass. | A hand-edit to a disposable artefact is what the layer model forbids; undoing it means A1. | Decide A1 first; this follows. |
| **A3** | **The proper staging world.** An export from the pinned heightmap is running or queued, carrying the seed from `cobblers-10240.pre-rescale` (you approved this). | Already approved — recorded here so the chain is visible. | Done unless you say otherwise. |

## B. Design decisions a session should not take for you

| # | Decision | Context |
|---|---|---|
| **B1** | **Which tenth trainer stands at Victory Road's exit ravine.** Main's **League Examiner** (4 Pokemon, Tailwind Crobat, Focus Sash) is what emits today; our **Gate Warden** (3 Pokemon, holds a door) is kept in `data/vr_trainers.json`'s `superseded_roster`. | Two different characters, not two versions of one. Whichever loses stays in the file. |
| **B2** | **38 superseded seat-file dialogue sets.** The roster's lines are what a player hears; the seat files' hand-written lines are the fallback and currently dead (the generator prints the count every run). | Ten Victory Road + 28 late-route trainers. Nothing is lost either way — it is *which lines play*. |
| **B3** | **Giovanni's hold: one stale field.** `data/trainers.json` has him authored, six Pokemon at 52–55 (top = his contract's 55), singles, `blocked_by: None`. Only `data/gym_trainers.json`'s `held: true` skips him, and its reason quotes an empty team that no longer exists. | Clearing it makes **eight** leaders' teams reach a player instead of seven. It changes what a player fights, so it was left. |
| **B4** | **The open-air Mega dens' gate.** Each of the seven has a 41-block zone round its pad with the turn-back facing the den — *seen, not reached*. The alternative is no zone at all, letting the level band (60 outer / 67 deeper against a cap of 50) be the only gate. | You said "the gates stay as designed", which is why the zone is there — but a turn-back in open country is a different thing from one at a rockslide. |
| **B5** | **Unit 3, the Slip: cancelled on measurement, confirm it stays cancelled.** There is no spur and no walls: the floor between the camp and the relic area is **182–211 columns wide everywhere** and nothing rises above y110. | You cancelled it. Recorded so it is not reopened. Unit 2 (relic underground) was the reason. |
| **B6** | **The ladder's shape.** `docs/mechanics/PROGRESSION_LADDER.md` argues the backpack is **not** the spine: the convenience arc finishes at **badge 3 of 8**, because gold/diamond/netherite add ~12 slots each. It recommends two strands per counter, and the power strand if only one. | Nine numbered questions at the end of that file. An income measurement is in this wave and may re-price several rungs. |
| **B7** | **`crafting_upgrade`'s home.** The ladder's own test failed one rung: portable crafting at badge 6 is too late for "never build a house". Proposed move: Brock's, priced out of reach until badge 3 — **price as the gate**, needing no flag, datapack or restart. | A cheap, reversible call. |

## C. In-game checks only you can make

| # | Check | Why a session cannot |
|---|---|---|
| **C1** | **Does Hoopa RENDER?** `pokespawn hoopa` spawns `cobblemon:hoopa` — the species exists in 1.8.0, measured tonight. Whether it draws a model or a placeholder is a **client** fact. | RCON sees entities, not models. `docs/world-building/DEEP_CITY.md`'s whole relic area rests on a visible Hoopa. One glance. |
| **C2** | **Does a gated counter fall back to `defaultShop`?** A plain merchant's shop NBT is empty, so nothing injects the global shop at summon — but the GUI's behaviour is unmeasured. | Needs a player to open a counter. Decides whether the trainer-card fix was even necessary. |
| **C3** | **Does Brock refuse a rematch with the badge in hand?** Long-standing: installed is not working. | Needs a fight. |
| **C4** | **Do two players share one NPC's dialogue?** EXP-022's two-player test is unrun, blocked on a second account. | Decides whether gated counters work in multiplayer. |

## D. Process questions

| # | Question | Context |
|---|---|---|
| **D1** | **Does the worktree guard's "split it into plain commands" count as a refusal?** Three agents hit it and then used the `Write` tool for the same in-worktree path. Strictly CLAUDE.md's rule is "a different tool reaching the same outcome", and that is what happened — three times. | It will keep happening. Either the rule gets an explicit exception for a guard that names its own remedy, or agents must stop and hand back. |
| **D2** | **`.worktreeinclude` did nothing.** It existed, listed the right paths, was tested, copied none of the 338 files, and was removed (`19838cc`). | A harness question, not a repo one. Worth raising upstream if fan-out needs those files — though tonight showed the heightmap is readable without it. |
| **D3** | **Seven doc/data/code disagreements** are recorded and deliberately not silently fixed (`docs/HANDOVER_SESSION.md` section 5): stair towers 8 vs 9, `rift_deep.json`'s dead `"banks": 10`, DEEP_CITY's "about 130 buildings" against 196 built, its stale status header, the cradle coordinate, `GYM_INTERIORS.md`'s stale cooldown rule, and `gulch_mine.json`'s `megas.why` referencing a key that was missing. | Each wants an owner's "fix it" or "leave it". |
