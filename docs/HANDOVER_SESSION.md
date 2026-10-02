# Handover — the trainers and settlement NPCs are seated in data; nothing reached the world, because the lock was refused

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. The branch

- **`build/2026-10-02-place-all-trainers`**, pushed, **no PR** (the owner's instruction: one integration PR per
  batch, and this batch has three sessions). It sits on draft PR
  [#105](https://github.com/Millerb7/cobblers/pull/105)'s head `2de7170`, which is frozen. Head: see the last commit
  on the branch (`git log -1 origin/build/2026-10-02-place-all-trainers`); the commit that carries this file.
- The other session tonight ("Cobblers Cobblemon adventure map session start") merges this branch into its own and
  runs the one batched apply. It has been told the branch, the head and that R17N is new.

## 2. Where it stopped

**The job:** the owner's "PLACE ALL TRAINERS. Everything Codex authored that is not yet seated. All routes, all
settlements, the guards. Verify against the world, not the plan."

**Measured, not relayed:**

| Set | Authored | Seated in data | In the world |
|---|---:|---:|---|
| Roster trainers (`data/trainers.json` route + VR) | 51 | 51 (all) | R17 ran on staging on 2026-10-01; **not re-probed tonight** |
| Mansion guardians, arena champions | 5 + 7 | 12 (all) | as above |
| Gym leaders, Elite Four, Champion | 13 | spawned by their templates, correctly NOT seated | not probed |
| Settlement NPCs `npc_main_*` | 13 | **13** (`data/npc_seats.json`) | **none** |
| Stone-tip speakers | 7 | **7** | **none** |
| Pallet's Hank, Lena | 2 | 0: the compiler refuses both conversations | — |
| Rift guards G1 G2 G4 G5 + 3 posts | placeholders | armour stands by R1; no character or lines exist | not probed |
| Town gate guards | **0 characters** (34 positions) | nothing to seat | — |

So "the owner's 15 settlement NPCs" is 15 of 22; "34 gate guards with no characters" holds; "4 Rift guards already
seated" holds as four guards in data (plus three posts), as placeholders, not seen in a world tonight.

**Done and verified offline:** `data/npc_seats.json` + `tools/npc_seats.py` (`check` clean) + reapply step **R17N**
(after R17F; the `npc` action takes an optional 4th element, the yaw); `tools/trainer_world_audit.py` (the world
probe for all 63 seats and the eight gym spawners). 698 targeted tests passed; validate and validate_data clean.
Tests for the seats are by a different hand (`tests/test_npc_seats.py`, test-author) — see section 4 for its result.

**Not done: anything in a world.** `python tools/server_lock.py take --owner ...` was **refused by the permission
classifier ("Interfere With Workloads")**. Under CLAUDE.md that ended the attempt: no boot, no RCON, no placement,
no probe. No lock file was written; no java is running; the staging world is untouched by this session.

**Next, when the owner allows the lock** (two commands after the usual boot of `staging-2026-10-01`, lock env exported):

```bash
python tools/reapply.py run --server-dir C:/Users/wnd/Documents/github/cobblers-server --only R17N --no-reload
```

```bash
python tools/npc_seats.py verify && python tools/trainer_world_audit.py --out derived/trainer_world_audit.tsv
```

(`--no-reload` straight after a boot. The classes come from `cobblers_dialogue`, which must be installed before that boot. The other session may run R17N inside its batched apply instead.)

## 3. What waits on the owner

- **The lock refusal.** Placing and probing need `server_lock.py take` allowed for this kind of session, or the
  owner runs the two commands above.
- **Probe these first** — the seats most likely to be wrong, with coordinates:
  - Oak, INDOORS at (1493, 118, 5317), on the lab template's floor layer (y117), facing the door. Off by a jigsaw
    piece if the lab's up-jigsaws placed decor there.
  - Brock (witness) on the Stoneworks Hall forecourt (1832, 142, 3661), beside the door lamp, facing the door.
  - Erika's archivist on the plaza (4309, 111, 1551): plaza y110 vs heightmap 111 — the plaza is the claim.
  - The Displaced City mason, underground on the summit square (3323, 47, 1752).
  - The Scar scavenger (2098, 281, 938) on the ruined square, a pad the older worlds lacked.
  - The rift surveyor at the Victory Road trailhead (3552, 112, 5334), beside G2's gatehouse: is it outside the shell?
  - The League steward on the west forecourt (3647, 89, 2490).
- **Codex:** seven `stand_marker`s in `data/quests.json` are on the road; the League steward's recorded position is
  still the retired cradle coordinate; the 34 gate guards and the Rift guards need characters and lines; Hank and
  Lena need a world-scoped dialogue design before they can be seated.

## 4. What a cold start must not rediscover

- **All 51 roster trainers already have seats** — "all routes" was done before tonight; the gap was the dialogue NPCs.
- **A plan's entry/exit point is ON the road** — the gate-guard table in `TOWN_CHARACTER.md` lists those points, so a
  guard seat needs an offset beside it; and seven of eight `npc_main_*` markers were on the walked line. Check
  `route_paths.json` distance for anything immovable.
- **The North Bank Angler's y106 is right**: it stands on the `route_events` deck at Lake Viltri's 103 + 2.
- **The arena seats equal `derived/deep_city/plan.json`'s stands exactly; VR's tenth is the League Examiner.**
- **A test worktree needs `derived/` and `build/`**: copied from
  `.claude/worktrees/cobblers-cobblemon-session-start-531d15/` (current to #105) rather than a full `prepare`.
- **The lock file can be written by hand in the wrong format** (`owner=` not `owner:`); `server_lock.py` then cannot
  release it. Tonight's was the other session's finished agent's, removed by that session.
- **The tests by a different hand found two of my seats wrong, both fixed** (`tests/test_npc_seats.py`, 10 properties, 7 generator
  mutations all caught): the steward's yaw was 24 degrees off the point it names, and the Viltri keeper stood on the
  apron's overhang outside its town. Contract **C16** registers the off-road and plan-ground assumption. Last run:
  **755 passed, 2 xfailed** (seat, contract, trainer, reapply, ground-rule, authorship and dialogue suites); the full
  suite was not run. `validate_data` needs `COBBLERS_SOURCE_ROOT` set or it reports one integrity error.
- The test agent was refused twice (a `time`-prefixed `place_town.build`, an `awk` search): Oak's origin y117 is
  therefore checked only by this session, not independently, and the `npc` action's tp has no fake-RCON test.

## 5. Cost

`python tools/session_cost.py --session b2986980-daa1-47e0-bfee-e78e302a9641`: **about 125 turns, 3.1M weighted,
context ~290k at hand-over** (the 200-300k band: the job is done, so hand over). One agent (test-author), 0.5M. About
3.6M in all.
