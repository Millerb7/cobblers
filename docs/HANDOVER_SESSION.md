# Handover: after the 2026-10-05 play test (session a292b1c5)

A cold session reads CLAUDE.md, `docs/STATE.md`, this file and **`docs/PLAYTEST_2026-10-05.md`** (the owner's notes,
decisions and every open item), and nothing else, before it starts.

## 1. The branch
- **`build/2026-10-05-p0`**, draft PR [Millerb7/cobblers#119](https://github.com/Millerb7/cobblers/pull/119) against
  main (#115-#118 merged). Re-read its head before quoting it (`git fetch --prune; gh pr view 119 --json
  headRefOid`). Commits were pushed after #119 was reported (a breach of the frozen-branch rule, told to the owner);
  treat #119 as frozen from now: new work goes on a new branch stacked on it.
- Merge command (pin to the head you re-read): `gh pr merge 119 --match-head-commit <sha>`.

## 2. Where it stopped
- **Staging is UP** (PID 53680 at hand-over, started 16:18 after a watchdog crash on a `/reload`), with the
  play-test build installed: native starter chooser, badge carry, trainer refusal lines and the over-cap notice,
  the spawn overhaul with alpha bosses, Elara at the HQ door, all gym spawners. `max-tick-time=-1` is still set:
  **restore 60000** at the next stop. The coordination lock is held by this session: release or take it over
  explicitly (`C:/Users/wnd/Documents/github/.cobblers-server-agent.lock`).
- **Deferred apply** (built and audited, not in the world; needs one prepare, which is stale since later commits):
  farms (R9AF, R9PF, R18AF, R16C), the bank buy list (config, then `cobbledollars reload`), Coldwater Station (R18CW,
  R16H, R17F), the arena spawn-free zone. **Held by the owner:** the Mega field rebuild (R9S/R9SX/R9MD/R9MB), the
  jungle temples (R9JT), the portal sheets (R1S).
- **Live staging-only changes to carry or undo:** Old Knot frozen with NoAI at (1588.5, 134, 3280.5); test grants on
  the owner's and the friend's accounts (all badges, rctmod progress through Giovanni; the friend's
  `rift_crisis_resolved` and stage `rift_released`); `cobblers_test` (Giovanni setup) in the world's datapacks; the
  unapplied waystone override parked in the scratchpad (not installed).
- **Done:** `docs/world-building/KYOGRE_CAVE.md` (committed) (Kyogre full design; Groudon in
  a volcano under lava and Rayquaza on a sky island through a relic portal, as companion outlines). If it is
  uncommitted when you start, read it, then commit it.
- **Published pages:** Region Nuzlocke Map https://claude.ai/artifact/TbFP4bqU6hmpkUR3ZBv1mW (`tools/nuzlocke_map.py`),
  Challenge Mode Trainers https://claude.ai/artifact/8mWdCTJYhYSJfjV9dsyBw3 (`tools/challenge_guide.py`; the owner will
  add fights; re-run and republish). Both private until the owner shares them.

## 3. Next, in order (the plan proposed to the owner; get cost approval before fanning out)
1. **Wave 1 -- fixes and research (~10M).** Fixes in the main session: remove the bird towers' feather chests (free
   Moltres), Azelf's gate (REVIEW 87), Old Knot still at spawn (84), Pallet's Caterpie weight (85), Dr. Vale's locked
   line and mid-chain resume (88), waystones ungated and one per gym town (89), spawn-block policy flipped to allow
   (owner decision). Research agents: a per-player chest mod (Lootr or similar; ADR first); Cobblemon 1.8's native
   Ability Capsule/Patch, EV items, held items, and whether a Mega "carry" is possible; per-player Normal/Challenge
   selection in rctmod.
2. **Wave 2 -- builds (~25M):** Challenge mode chosen at Oak; the economy (Mart scales with badges, TM sellers every
   few gyms, ability items, held items with a big Elite Four mart, a gym token for a held item, 15-20 free balls a
   gym, the Nether and a netherite-gated tier); gym junior trainers plus optional hard route trainers; direction to
   the Mega pits after Koga (the gulch is gated on gym 6 today: confirm); side-island detours.
3. **Wave 3 -- designs:** the Kyogre cave build from its design; Long Isle (access, band, jungle, quests); a purpose
   for the cavern city; a reason to build a house and craft; the Mega Ball (needed to catch a Mega -- NOT now: Megas
   stay uncatchable).

## 4. Do not rediscover
- `prepare` stamps data/ and tools/: any commit there forces a full ~25 min rerun; run the cheap audits first.
  `function_limits` fails a function that writes into chunks it does not force-load (declare `# chunks-loaded-by:`).
- The donor pack never deletes stale functions; old files in `build/` can fail later audits (24 retired jungle-ruin
  functions did).
- `/reload` mid-session takes ~60 s and the watchdog kills the server at max-tick-time 60000.
- Player story stages live in Cobblemon player data (`q.player.data()`), written with `runmolang "..." @s` as the
  player; read back with a ternary that returns a number.
- rctmod's level cap follows its own defeat record: `execute as <p> run rctmod player set progress after <id>`;
  party levels: `pokemoneditother <p> <slot> level=<n>`.
- Cobblemon's chooser cannot be re-opened for a player who chose (`openstarterscreen` says "already chosen").
- A dialogue resumes at its cursor, not its hub: a conversation can trap a player in a sub-chain (Dr. Vale).
- CobbleDollars merchants buy through the server-wide Bank (`config/cobbledollars/bank.json`, shift+right-click).

## 5. Cost
`python tools/session_cost.py`: 1,633 turns, 88.0M weighted for the main session, context 754k at hand-over (far over
the 300k line: the next session must compact or hand over at phase boundaries).
