# Report — 2026-09-30, the day run

Server **up** on `cobblers-dryrun12`, `max-tick-time=60000`, process confirmed (not just RCON).
Branch `build/2026-09-29-phase2`, head `f36cb2c`.

---

## 1. THE BROCK FIGHT — do this first

Everything about F11 is ready except the one fact only you can get. **Run this, then fight him:**

```bash
rctmod trainer summon_persistent kanto_brock <x> <y> <z>
```

or walk into the Stoneworks Hall and meet him at **(1832, 156, 3696)**.

**The tell, in the first ten seconds.** I read Cobbleverse's own Brock out of
`COBBLEVERSE-RCT-DP-v20.zip` — nobody had recorded it before:

| | Cobbleverse's Brock | ours |
|---|---|---|
| lead | geodude **16** | geodude **18** |
| then | bonsly 16, cranidos 18 | bonsly 18, cranidos 19 |
| ace | onix 20 | onix 20 |
| items | **2 Full Restores**, maxItemUses 2 | **none**, maxItemUses 0 |

So: **if his lead is level 18 and he never heals, the override took and all eight leaders are ours.
If it is 16 and he heals twice, they are inert and F11 is not fixed.**

What I could establish without you, and did: the path is right (`data/rctmod/trainers/kanto_brock.json`
— plural, matching upstream's own layout), and the load order puts us last, which is what decides a
same-path resource:

```
[rctmod (Fabric mod)] → [COBBLEVERSE-RCT-DP-v20.zip (Global)] → [file/cobblers_trainers (world)]
```

`rctmod trainer get` exposes only type and win/defeat counts, none of which differ, so there is no
command that reads a roster. It has to be a fight.

**A second fault found while setting this up.** Our override REPLACES upstream's whole file, so any key
we do not write is lost. Checked every key across all twelve overrides: exactly one was being dropped,
on all twelve — `battleFormat`, which upstream sets to `GEN_9_SINGLES` on every one. The generator's
docstring justified omitting it with "singles is the default". Probably true; also an assumption about
a mod standing between a player and every gym battle, and 9 of upstream's 155 trainers are
`GEN_9_DOUBLES`, so the field does something. Giovanni is held in our data for precisely this reason.
Now declared per record and emitted. Keys still dropped: **none**.

---

## 2. WHAT IS IN THE WORLD

Probed by block over RCON after the runs, never inferred from a step's exit code.

| | evidence |
|---|---|
| **The lake beds are fixed** | (3009, 104, 4008) — the column you flew over — now reads `minecraft:clay` under water at y105. It read `legendarymonuments:distortion_stone` before. |
| **The Rift zone walls, the passable half** | throat wall at (3293, 110, 3191) obsidian ✓, z1 gatehouse at (3098, 87, 3270) ✓ |
| **The dig camp's reshape** | R9M ran on the current data for the first time |
| **The ferry docks** | R16H, 8 docks |
| **Victory Road's ten and the League's five** | R17, 165 s |
| **The ferrymen** | R17F, 38 s |
| **Registeel and Regigigas** | R14L, 32 s — Regigigas was unreachable forever until Registeel was sited |

**R1 alone did not fix the lake beds, and that matters.** Re-running the re-skin left the bed still
purple: the skin fix stops it *writing* the cell, but the gravel only exists in a fresh export, so
nothing put it back. Probed, not assumed. `tools/lakebed_repair.py` lays it back using
`paint_maps`' own rule from the same noise and seed — 113,841 columns, 65,840 gravel, 48,001 clay.
That count is derived independently of the skin fix and equals the 113,841 the skin now skips; two
separate derivations agreeing is what says the scope is right. Step **R1L**, straight after R1.

---

## 3. THE REVIEW LIST — calls I made

1. **The zone walls go in for the half that can be passed, and only that half.** Every guard calls its
   qualify now, so your condition was met — but z4 and z5 still cannot *grant* (z4 needs Codex's
   dialogue to read caught_count; z5's flag has no setter, and I checked: it has **not** landed on
   `origin/codex/trainer-modes`, whose own `quests.json` says "no authoritative setter invokes it").
   Installing all nine would have sealed the **League's precinct**, which ends the game for anyone who
   reaches it. R9Z installs 5 of 9. Which half is live is read from the data, so when Codex lands
   either piece the wall follows with nothing to remember.
2. **`pacifidlog_south_jetty` went back to `planned`.** The audit measured its ferryman and landing at
   y63 on ground y55 — seven blocks under the sea. It is a `host` dock whose position comes from the
   sea town, and the sea town has moved out from under it: the same migration C3 and C14 record.
3. **`tilpey_launch` is held, not emitted.** Its docks are built and its ferrymen stand, but
   `ferries.py` walks every crossing at sea level 62 and that launch crosses a **lake** at y77, so its
   water has never been walked. A built line with an unmeasured crossing is what the audit refuses.
4. **`quest.sq_sunset_01.completed` declared and never set.** Four charters gate on a sidequest that
   exists only in a story doc. Declaring it makes them build and stay **shut**, which is the safe
   direction. *Your call, one line: drop the gate and leave the charters on `champion_cleared` alone.*
5. **Gyms 6 and 8 are merged but NOT applied**, pending your reading of §4.
6. Registeel's coordinate is its `portal` (the field its siblings use) and it got the spawn-free box
   its siblings have — both fail-closed checks caught the bare coordinate.

---

## 4. THE INDEPENDENT AUDIT OF GYMS 6 AND 8 — it earned its place again

Verdict: **both completable, with defects.** Eleven found. `tools/gym_buildings_independent.py` said
CLEAN, and was right to: the route passes. What it cannot see is that the room stopped being the room.

**Two HIGH, both fixed:**

- **Giovanni's two blind wells filled themselves in.** `mode: keep` fills **air only**, so a collar
  written after the cut laid mud brick into the hole and never touched the paving — the exact opposite
  of the record's own words. Stage 1 is three well heads of which two are blind; this deleted both.
- **The sap filled its own mouth.** One solid 5×5 collar written after the 3×3 shaft was cut put eight
  of nine mouth cells back; the route passed through a 1×1 hole while the record promised three by
  three. Now a ring of four fills. (`mode: outline` cannot say it: a box one course high has every cell
  on its y face, so outline returns the whole disc.)

I checked the systemic worry it raised: the audit **does** model `keep`, and only gym8 used it, twice.

**Nine remain, none blocking** — Giovanni's held roster against his live spawner; a headframe five
courses tall where the record claims nothing exceeds y114; two of gym6's three clerestories lighting a
wall and a well rather than the chamber; a decoy flush against the gallery edge where the record claims
three cells clear; stair courses 11–14 open above; a floating lamp; an eye set proud instead of flush;
an undeclared 7-block drop; a one-sided tell.

---

## 5. CODEX'S DELIVERY — and the "1–2 hours per item" question

**Codex's own doc answers it:** *"this pass does not place or move entities"* and *"World placement and
per-player defeat-state integration remain unimplemented."* The delivery is **data**; placement is the
open job, which is what you were told.

**Placing a trainer is not 1–2 human hours. It is a generator reading seats from plan data.** Last
night one agent seated **all ten Victory Road fights in a single unit** by reading the stands
`vr_caves.py` had already carved — no coordinates invented, no world read — and the same generator
wrote the League's five as overrides. That agent-unit cost **0.99M**, not 28 × 1–2 hours.

So: **the generated version, and it is already the version we have.** What is genuinely left is the
settlement NPCs and the Rift guards, which need seats to read — and the Rift guards now have them
(the four gatehouses and two posts stand in the world with armour-stand placeholders where Codex's
NPCs go).

---

## 6. STILL NOT DONE

- **The 12 voids in the Displaced City cavern shell** — not reached, second day running.
- **F7, the fail-open water check** — not reached, second day running.
- Gyms 6 and 8 not applied (§4).
- `tilpey_launch` needs `ferries.py` taught a per-crossing water level.

---

## 7. COST, against the corrected rule

The rule from yesterday — **reading and authoring ≈ 1M, building and re-running ≈ 2–4M** — held.

| agent | kind | predicted | actual (`session_cost.py`) |
|---|---|---|---|
| Rift zone guards | building | 2–4M | **0.94M** |
| Ferry docks | building | 2–4M | **1.96M** |
| Gyms 6 and 8 | building | 2–4M | **2.34M** |
| Independent audit of 6 and 8 | reading | ~1M | **0.59M** |
| Victory Road + League (unit 2, F11) | building | 2–4M | **1.41M** |

Five agent-units, **7.2M**. Every one at or below the band, three of the five well below it. The rule
holds but is too pessimistic: **a build lands at 1–2.5M and a read at 0.5–1M**, and I will quote that
from here rather than 2–4M.

**The main session is the expensive half, again and worse.** 792 turns, context **683k**, weighted
**30.8M** — more than four times all five agents together. At 683k every turn costs about 68k to send,
and `session_cost.py` has been saying HAND OVER for hundreds of turns. That is the real cost lesson of
today, not the agents: the integration work — prepare, install, boot, apply, probe, six stop/boot
cycles — all happens here, and it cannot be delegated, so it has to be **split across sessions**
instead. The next job should start cold.
