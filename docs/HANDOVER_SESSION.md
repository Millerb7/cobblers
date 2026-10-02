# Handover: legendary shrines from the Cobbleverse catalogue (2026-10-02)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branches

- **PR #109** `claude/legendary-shrines-placement-fa3eea` at `735a3496c0b8fe3e090f78fe3c8ad6430219e03f`, draft, FROZEN.
  Schedules the Crown Cemetery and both Necrozma towers; `place_donor.py` `set_commands`.
- **Stacked on it:** `claude/legendary-followups-2026-10-02` (the owner's decisions of 2026-10-02), its own draft PR
  with base `claude/legendary-shrines-placement-fa3eea`. Merge #109 first.

## 2. Where the job stopped

- Done offline: `enable-command-block=true` is a server requirement (`tools/install_check.py` PROPERTY check, the
  example properties, STATE); decisions recorded in `data/adopted_legendary_sites.json` `owner_decisions_2026_10_02`;
  `data/frostpeak_camp.json` `item_economy` (Kubfu's scrolls, the three feathers, gate `gym8_cleared` proposed,
  mechanism not chosen). Tests on the touched files: 224 passed.
- **NOT done: the live server's `server.properties` still says `enable-command-block=false`.** The coordination lock was
  held by `cobblers-cobblemon-session-start-531d15`. Next session holding the lock: stop the server, set it, and
  `install_check` will then report clean on that key.
- **NOT built: Spectrier once per player.** Design in `adopted_crown_cemetery.spectrier_once_per_player` (tick
  function near (4153, 112, 1999); record the carrot's `Thrower`; grant `cobblers:legendary/spectrier_summoned` when an
  untagged Spectrier appears; thereafter kill that player's carrots at the ring). Build it only after EXP-048's owner
  half shows a player-thrown carrot fires the trigger. Two agents: a builder (datapack-content-dev: generator + pack +
  reapply wiring) and a test-author, roughly 0.5M each. Owner approval needed for two agents.
- Also not done: `prepare`, the full suite, staging, EXP-LEG-TOWER-GATE.

## 3. Waiting on the owner

- EXP-048's owner half (Spectrier thrown carrot; Articuno and Calyrex right-clicks).
- Feathers: which mechanism the camp hands them out by (quest, dialogue give, trader), and confirm `gym8_cleared`.
- In game after re-apply: Dawn tower summit chain at (7491-7499, 176, 338); Dusk at (1167-1175, 223, 7238).

## 4. Do not rediscover

- The End is unreachable (no stronghold, no portal room). Ruinous stakes are Nether-only features. Galar ore is
  overworld-only. No recipe or loot makes any bird feather or the Calyrex crown.
- `defeat_champion_blue` very probably IS granted by beating our Blue (`kanto_champion_blue`).
- A client copy of the pack is in the Modrinth profile `COBBLEVERSE - Pokemon Adventure [Cobblemon]`; readable
  with no server lock (`docs/research/notes/legendary-catalogue-reopened.md`).
- `data/frostpeak_camp.json` does not round-trip through `json.dumps`: edit it as text, or the whole file reflows.

## 5. Cost

`tools/session_cost.py`: main session about 2.8M weighted at ~300k context; one test-author agent 0.44M.
