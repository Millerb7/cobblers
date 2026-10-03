# Handover: legendary shrines from the Cobbleverse catalogue (2026-10-02)

> **FIRST, IF YOU HOLD THE SERVER LOCK: set `enable-command-block=true` in the live server's `server.properties`,
> with the server stopped.** It is a server requirement (the owner, 2026-10-02; STATE "What is decided"): the Necrozma
> towers and Mew's door are command blocks. The live file still says `false`; every session so far found the lock held
> elsewhere. `python tools/install_check.py --server-dir <server>` reports it as a PROPERTY problem until it is set.

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branches (a stack; merge in order, each pinned to its head)

1. **#109** `claude/legendary-shrines-placement-fa3eea` @ `735a3496c0b8fe3e090f78fe3c8ad6430219e03f` (frozen):
   schedules the Crown Cemetery and both Necrozma towers; `place_donor.py` `set_commands`.
2. **#110** `claude/legendary-followups-2026-10-02` @ `0b54100e5af58c3ee2e0b3cf8c5893184cb8cd00` (frozen):
   the install_check PROPERTY check, the decisions, the camp's `item_economy`.
3. **this one** `claude/legendary-followups-3-2026-10-02`: the Moltres site measured, feathers by dialogue at
   `gym8_cleared`, the PROPERTY tests, this handover. Its own draft PR, base #110's branch.

**COLLISION AHEAD, unresolved:** `origin/claude/south-map-world-audit-2219f3` (unmerged) adds `tools/articuno_tower.py`,
which moves Articuno to Frostpeak's SUMMIT and treats the shoulder site (904, 151, 320) as superseded, with its own edit
of `adopted_articuno_shrine`. This stack still carries the shoulder. Whichever merges second must reconcile
`data/adopted_legendary_sites.json` by field; do not delete either side's reasoning.

## 2. Where the job stopped

- **BLOCKED, asked of the owner: the three causes of EXP-048's inert results** ("/clone dropping shrine blocks, a
  missing ritual block, and a shrine placed 71 blocks from its record"). The owner reports pasted altars DO work. No
  file this session could read records it: not EXP-048's README (console half only), not main, not
  `build/2026-10-02-followups` (the lock-holder's worktree), not any pushed branch. No tool on main issues `/clone`. Do
  not build fixes until the owner points at the record (which session, which file). Plausible readings, NOT verified:
  "ritual block" = `lumymon:summon_anchor` (absent from the Articuno, Zapdos and Mew templates); "71 blocks" = some
  paste vs its record. Every altar-driven site depends on the answer.
- **Approved, not started: the Spectrier cap, two agents** (a datapack-content-dev builder, then a test-author; about
  0.5M each). Design: `data/adopted_legendary_sites.json` `adopted_crown_cemetery.spectrier_once_per_player`. The owner
  ordered it AFTER the three fixes. Builder brief: tick function guarded by a player within 32 of (4153, 112, 1999);
  copy a shaderoot carrot's `Thrower` to storage; on an untagged wild Spectrier within 16 of the anchor, tag it and
  grant `cobblers:legendary/spectrier_summoned` to that UUID by macro; thereafter kill that player's carrots within 4
  of the ring, with a tellraw. Generator + pack + reapply wiring; it never runs prepare or staging.
- Done offline: `adopted_moltres_tower` (6252, 168, 5344), checked by `tests/test_adopted_legendary_sites.py` (158
  passed); feathers by dialogue at `gym8_cleared` in `data/frostpeak_camp.json`; `tests/test_install_check.py` PROPERTY
  tests (33 passed; a generator mutation letting `false` through fails 2). **The check and its tests were written in
  the same session**, at the owner's direction.
- Not run: `prepare`, the full suite, staging, EXP-LEG-TOWER-GATE.

## 3. Waiting on the owner

- Where the three EXP-048 causes are recorded.
- In game after re-apply: Dawn tower summit chain (7491-7499, 176, 338); Dusk (1167-1175, 223, 7238).

## 4. Do not rediscover

- The End is unreachable (no stronghold, no portal room). Ruinous stakes are Nether-only features. Galar ore is
  overworld-only. No recipe or loot makes any bird feather or the Calyrex crown.
- `defeat_champion_blue` very probably IS granted by beating our Blue (`kanto_champion_blue`).
- A client copy of the pack is in the Modrinth profile `COBBLEVERSE - Pokemon Adventure [Cobblemon]`, readable with no
  server lock (`docs/research/notes/legendary-catalogue-reopened.md`).
- `data/frostpeak_camp.json` does not round-trip through `json.dumps`: edit it as text, or the whole file reflows.

## 5. Cost

`tools/session_cost.py`: main session 3.8M weighted at 328k context before this last unit; one test-author agent 0.44M.
