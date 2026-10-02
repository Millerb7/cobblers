# Handover: water life (2026-10-02)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts. The handover
this replaces (the 2026-10-02 integration, PR #108) is `git show 1a4b85f:docs/HANDOVER_SESSION.md`; its owner list
still stands.

## 1. Branch

- **`claude/water-terrain-features-f61690`**, from `main` at `1a4b85f`. One draft PR against `main`; re-read its head
  with `gh pr view <N> --json headRefOid` before quoting it, and merge with `--match-head-commit`.
- It merges three agent branches (`worktree-agent-ae83080f8a88845eb` lake builder, `worktree-agent-a35943f859e97d4da`
  sea builder, `worktree-agent-a9d8f7b8f66e8e224` auditor); all are in it.

## 2. Where the job stopped

- **Done and verified offline in this checkout:** `tools/lake_life.py build` and `tools/sea_life.py build` (0 builder
  problems), `tools/lake_life_audit.py` and `tools/sea_life_audit.py` (0 problems each), `tests/test_lake_life_audit.py`
  + `tests/test_sea_life_audit.py` 72 passed, the two packs share 0 columns, ground-rule/id-authorship/rewards tests
  200 passed. Wired: `SERVER_PACKS`, prepare jobs (build then audit), steps R9LL and R9SL after R9SD.
- **Not run:** `reapply.py prepare` (needs `--server-dir`, and the server was locked), the full suite, any install.
- **Next, once the lock is free:** the session-start checks, then
  `python tools/reapply.py prepare --server-dir <server> --only lake_life:build,lake_life_audit,sea_life:build,sea_life_audit`,
  install the two packs into `staging-2026-10-01`, run R9LL and R9SL, and verify a sample over RCON.
- **Held lock:** none by this session. The lock at `C:\Users\wnd\Documents\github\.cobblers-server-agent.lock` belongs
  to `cobblers-cobblemon-session-start-531d15` (staging up for the owner).

## 3. Waiting on the owner

- **In game, once applied** (`docs/mechanics/WATER_LIFE.md` "Not verified"): do kelp and seagrass stand in Shrew Lake
  (2914, 106, 4068 is the float) and on the Pallet flats; can Mesprit's lit ring (2790, 55, 4606) be seen from a boat
  over Arrow Lake by day; does the Windward Sink's chamber stay dry across a restart (mouth (318, 4580)); walk the
  waterline cave from the beach (376, 3503).
- Whether Shrew's case 49 deep (2864, 58, 3976) is the reach intended (WATER_LIFE "Found while building").

## 4. Do not rediscover

- `tools/water_shape.py` `build_protect` misfires on the applied heightmap and `resited_town` raises; both packs work
  round them (task chip raised to fix the helpers).
- Bubble columns, doors, beds, fence gates and cauldrons under water are breathing spots; none is written.
- The windward coast has no cliffs: a cliff-face cave mouth needs the next water export.
- Not built, each flagged in WATER_LIFE "Export flags": the river skin (proof P3), the Viltri Ravine stream (held),
  Lugia's trench, the wreck coves and the forge ruin, Habitat Blocks and spawns at the wrecks (Dhelmise).

## 5. Cost

`python tools/session_cost.py`: main session about 1.9M weighted at handover, three agents 9.7M (lake builder 2.3M,
sea builder 3.3M, auditor 4.2M): about 11.6M against the 4-7M estimated up front.
