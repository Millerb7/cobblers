# Handover: session 74260a, 2026-10-12 evening (far past the context line)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branch
`build/2026-10-12-sanctuaries` (draft PR, stacked on #135 `build/2026-10-12-overnight` head fca0a76, which is OPEN)
in worktree `.claude/worktrees/night-shift-engine-gym-9b76f2`. #133 and #134 are merged to main. Merge #135 first,
then this one (retarget it to main if GitHub deletes #135's branch on merge).

## 2. Where it stopped
- **Staging is UP at 12G** (terminal tab "staging server 12G"), installed from prepare 238/238 at bff8baf, applied,
  build packs STRIPPED (held in `cobblers-server-retired/stripped_20261012_193652`). Idle live heap 5.66 GB.
- The cycle for any next install: snapshot to D:, prepare, stop, install (puts build packs back), boot 24G with the
  watchdog off, run, stop, watchdog 60000, `reapply.py strip`, boot 12G, check twice, read back.
- Open small items: the block outside Hoarfrost Hollow's mouth (6722, 100, 1348) is not air (probably snow); the
  Scar Tarn's water wards are unverified (look in the water with a player there); TM_POWER_GATE.md section 9's
  table is off by one at badges 5 and 6.

## 3. Waiting on the owner
- Sealed-chamber markers (a visible cairn/sealed door + sign on every plug): proposed, not built.
- Which places feel crowded (the owner wants more empty space, not a bigger map).
- The world tree (B then C, WORLD_TREE_PLAN.md), Kyogre/Rayquaza: later.
- Gible has no wild home again (K1 removed); confirm the antechamber species' removal.

## 4. Do not rediscover
- Datapack functions stay parsed in heap; strip build packs after every apply (memory: apply-heap-24g).
- Snapshots go to D:\cobblers-snapshots, sha256-verified (memory: snapshots-on-d-drive).
- presence_audit's per-place probes run under `--only extra`; in its --out file a pass is "ok" in column 4.
- Agent branches started before another agent's merge conflict in data/caves.json, data/world_probes.json and the
  roster: resolve structurally (load each side, take each side's own records), never by hand.

## 5. Cost
`python tools/session_cost.py`: this session ran far past the hand-over line at the owner's request.
