# Handover: the 2026-10-03 follow-ups (session a292b1c5)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file. `docs/REVIEW_2026-10-02.md` (items 1-52) lists every
call made and every defect recorded and not chased; read it before reversing anything.

## 1. The branch

- **`build/2026-10-03-followups`**, stacked on #114 (merged into main 2026-10-03 08:21). One draft PR against main;
  re-read its head before quoting it (`git fetch --prune; gh pr view build/2026-10-03-followups --json headRefOid`).
- #109-#113 are MERGED (nothing to close). Delete when convenient: every `worktree-agent-*` branch.

## 2. Where it stopped

- **Applied and verified in staging-2026-10-01** at 12:43 (`--only R9Z,R9DC,R9RU,R9NR,R9E,R9F,R17,R18RU,R18NR`,
  0 problems), restarted: `presence_audit` 257 of 266 (the nine absent are the known stale/open probes, STATE
  "Latest applies"), `npc_seats.py verify` 20/20, `install_check` 0. Snapshot before it:
  `C:/Users/wnd/Documents/cobblers-staging/snapshot-2026-10-03-before-batch2`.
- **Server UP** (started `nohup ... & disown` from the server dir with `--universe C:/Users/wnd/Documents/cobblers-staging
  --world staging-2026-10-01`; `level-name` is the LIVE world). `max-tick-time=60000` (set -1 with the server stopped
  before a `reapply.py run`). The lock is released at the end of this session.
- Next, in order:
  1. Z2's gate, once the owner says where (review 44).
  2. Fly-checks below; then the review list's open items.
  3. `python tools/reapply.py stale --server-dir C:/Users/wnd/Documents/github/cobblers-server` after the next full
     apply: every step reads `unknown` until it runs with a hash.

## 3. What waits on the owner

- **Z2's gate "to the gatehouse, 1,316 blocks"**: not reproduced. G2 stands in its own trailhead gatehouse (3548, 112,
  5322); Gym 8's building (3572, 6416) is 1,094 straight / 1,164 walked. Is the intended move into Gym 8's gatehouse?
- **In game, with coordinates:** Heaven's Arena (3609, 3249): win tier 1 at (3609, 17, 3257), then walk the stair up
  from the east exit (3612, 16, 3243); without the win the shaft should set you back at (3613.5, 16, 3243.5)
  (review 51 is the tag-timing risk). Gatehouses: G2 (3548, 112, 5322), G5 (3573, 85, 2680) from the south, the wilds
  slip (4200, 95, 4300) west mouth. Zapdos on Fungal Isle, altar (895, 69, 5583); the coast site (577, 2628) should
  be bare ground. Northern residents: stubborn_tree (1588, 3280), wandering_stone (5264, 2680), hide_and_seek (6700, 3710).
- Shrew Station was sited to study the coast Zapdos; it is now 2,777 blocks away. Move it too?
- The standing list: the shared server config (review 20, 25), z5's binder grant (22), EXP-049/054/048 in-game
  checks, the Sinnoh pack, Mega field levels and night aggression, the diamond pack price, unsited markets.

## 4. Do not rediscover

- `reapply.py prepare` needs `--server-dir` and the lock env (`COBBLERS_SERVER_LOCK`, `COBBLERS_LOCK_OWNER`); with them
  it ran 140 jobs clean in 1,046 s.
- A gatehouse rebuild leaves the OLD shell standing wherever the new one does not write: the one-off used here is
  scratch (regenerate the old functions at 1cbce5c, voxelise, air what the new shell does not overwrite at/above the
  guard's feet). Same shape for any shell that moves.
- Run records now carry `hash` and `world_dir`; before 2026-10-03 they held only function counts, which is why a
  changed function under an unchanged step was invisible.
- Pre-existing failures, not from this work: `tests/test_rift_mines.py` x2 (review 45), contracts C12/C14 on the Mega
  field's multi-Mega den (50), `test_mines_independent` vl_water_a (52).
- The Zapdos cleanup (`tools/zapdos_tower.py build`) and any staging cleanup pack are built on demand into
  `build/staging/`, copied into the world's datapacks for one run, and deleted again.

## 5. Cost

`python tools/session_cost.py`: main session ~300k context at the end (over the hand-over line; it ran on to finish
the integration and apply); agents together ~57M weighted before today's five (gatehouses, arena audit, northern
audit, northern re-site, Zapdos, qa).
