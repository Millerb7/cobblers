# Rollback plan

Written 2026-10-14. **Tonight nothing on the server or in any world was changed**: the mods swap, the staging install
and the live export were all blocked. So today there is nothing to roll back. This is the plan for when they run.

## What exists to roll back to
- **Snapshot** `D:\cobblers-snapshots\staging-2026-10-14-before-1.8.2`: the staging world, the server's `mods/`
  (Cobblemon 1.8.0, 102 jars) and `config/`, taken with the server stopped; 32,200 files compared by size and sha256.
- **The live world `cobblers-10240`**, untouched. When the live export runs it is RETIRED (renamed, never deleted),
  and that retired folder is the rollback.

## Rolling back the mods (after a 1.8.2 swap)
With the server stopped:
1. Move `cobblers-server/mods` aside (e.g. to `cobblers-server-retired/mods-1.8.2-<date>`).
2. Copy `D:\cobblers-snapshots\staging-2026-10-14-before-1.8.2\server-mods` back as `cobblers-server/mods`.
3. Copy the snapshot's `server-config` back over `cobblers-server/config` (CobbleDollars Beta-6.1 rewrites its bank
   file on first start; 1.8.0's Beta-5.1 expects the old `bank.json`).
4. Friends go back to the previous client pack (the 1.8.0 set).

## Rolling back the live export
With the server stopped:
1. Rename the exported world folder aside (never delete it: it holds whatever players did since launch).
2. Rename the retired live world back to `cobblers-10240`.
3. Restore `mods/` and `config/` as above if they changed with the export.
4. Boot, check the process twice (not just RCON), and run `python tools/install_check.py --server-dir <server>`.

Players lose anything done on the new world since the export. Player data carried INTO the export came from the
retired world, so the retired world still holds each player's state as it was at export time.

## Never
- Delete the retired world, the snapshot, or `session.lock`.
- Roll back while the server runs.
