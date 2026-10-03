# Handover: legendary shrines from the Cobbleverse catalogue (2026-10-02)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branch

- `claude/legendary-shrines-placement-fa3eea`, from `origin/main` at `1a4b85f` (#108). Draft PR: see the PR list for
  this head; it is frozen once reported. Pin any merge with `--match-head-commit` to the head the PR report gives.
- Commits: `dfad147` (data, generator, research note), `2147ffc` (tests, by a separate test-author agent), and a
  final commit (test-fixture key rename, `ceiling.verdict`, STATE, this file).

## 2. Where the job stopped

- **Done and verified offline:** three sites SCHEDULED in `data/placements.json` (`legendary_crown_cemetery`,
  `legendary_dawn_tower`, `legendary_dusk_tower`, status planned); `tools/place_donor.py` `set_commands`
  (`command_rewrites`) emits the towers' six gated `data merge block` lines; `tests/test_adopted_legendary_sites.py`
  + `tests/test_donor_set_commands.py` 175 passed; id_authorship 0 faults; validate_data's 263 errors are all
  un-hydrated kits in the worktree (pre-existing, environmental).
- **Not run:** `prepare`, the full suite, staging. The staging server was up with another session's lock held
  (`cobblers-cobblemon-session-start-531d15`), so `install_check` was NOT run and nothing touched the server.
- **Next, in the main session:** `prepare` (it emits the three donors), re-apply on staging, then EXP-LEG-TOWER-GATE
  (`data/adopted_legendary_sites.json` experiments_needed).

## 3. Waiting on the owner

- **`enable-command-block=true`** in server.properties: the towers' lift and summit (and Mew's door) need it. Not changed.
- **One Necrozma per tower for the whole server** (upstream design, kept). Keep, or make it per player?
- **Spectrier is probably repeatable** (regrowing crop, in-memory cooldown). Reward or farm?
- EXP-048's owner half still decides Mew, Zapdos, Articuno (held: altar-only).
- In game, after re-apply: Dawn tower (7480, 99, 316) summit chain at (7491-7499, 176, 338); Dusk tower (1156, 146, 7216)
  chain at (1167-1175, 223, 7238).

## 4. Do not rediscover

- The End is unreachable: no stronghold can generate, no portal room is authored (`legendary-catalogue-reopened.md` s5).
- No recipe or loot makes ember/glacier/thunder feathers or the Calyrex crown (client jars + DPs, 0 producers).
- Ruinous shrines' stakes are a Nether-only worldgen feature (`StakePlacement`, `#minecraft:is_nether`): keep them there.
- Galar Particle ore is overworld-only (`foundInOverworld`), so absent from our export; the cocoon needs 500.
- `defeat_champion_blue` very probably IS granted by beating our Blue (`kanto_champion_blue`); the old "never grants" was wrong.
- A client copy of the pack (DP-v31, LumyMon 0.6.6, LegendaryMonuments) is in the Modrinth profile
  `COBBLEVERSE - Pokemon Adventure [Cobblemon]` and can be read with no server lock.

## 5. Cost

`tools/session_cost.py`: main session 2.5M weighted (82 turns, 294k context at hand-over); one test-author agent 0.44M.
