# Handover — end of the 2026-09-30 run

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

**This session ran far too long.** `session_cost.py` said HAND OVER for hundreds of turns and was
overridden to keep the thread: 934 turns, **826k of context, 42.9M weighted**, every turn costing 82k
to send. The agents were cheap — eleven units, about 12M together. The integration is what inflated
it: prepare, install, boot, apply, probe, nine stop/boot cycles, and it cannot be delegated. **So it
has to be split across sessions. Start cold, do one unit, hand over.**

## 1. Branch and PR

- Branch `build/2026-09-29-phase2`, head **60883dc**. Tree clean apart from `.codex/config.toml`,
  **deliberately uncommitted** — it is Codex's (`docs/HANDOVER_CODEX.md` item 29).
- Stacked on `night/2026-09-29-water-export`, whose **PR #95 is OPEN and FROZEN**. Push nothing there.
  **No PR exists for this branch and one is overdue** — it carries about forty commits. Open it as a
  draft (`open-pr` skill), report it with its full head SHA and
  `gh pr merge <N> --match-head-commit <sha>`, and do not mark it ready.

## 2. Server state

Up on `cobblers-dryrun12`, `max-tick-time=60000`, process confirmed. The coordination lock at
`C:\Users\wnd\Documents\github\.cobblers-server-agent.lock` is **still held by this session's owner
line** — take it over or release it.

**Start it detached, never with PowerShell `Start-Process` from a tool call** (now a CLAUDE.md rule).
One started that way died silently and was down three and a half hours before the owner asked. Check
the PROCESS before reporting a server up, not just that RCON answered once.

## 3. The five things the owner asked be kept visible

### F12 — two authored trainer points sit inside town boxes, and the fix is Codex's

`docs/FLIGHT_FINDINGS_2026-09-29.md` F12. Two of the 28 points in `docs/story/TRAINER_RULES.json` fall
inside a settlement, where a route trainer must not stand:

- **`route_07_trainer_01`** — authored at (6248, 3546), inside Saffron's `gym6_town` box
  (6092, 3292)-(6314, 3596), which route 7 does not leave for **253 blocks**. Seated 48 path cells on,
  68 blocks moved; the along-route reach had to widen to 120 cells to find a legal shoulder.
- **`route_07_trainer_04`** — authored inside `gorge_hamlet`. Seated at offset 6 instead of 3, 9.2
  blocks moved.

**The fix belongs in Codex's `TRAINER_RULES.json`, not in ours.** Nothing on our side was adjusted to
hide it: the seats moved, the authored points did not, and each move is recorded on its own seat. If
those two were meant to be *town* trainers rather than route trainers, re-author them upstream and
delete these two seats. **Do not "correct" the authored points from this side.**

### The 32 settlement NPCs and four Rift guards — still unplaced

The route trainers are done: all 51 authored, 56 placements applied and probed. The rest of Codex's
delivery is not.

- **32 settlement NPCs.** Not located precisely this session. `data/dialogue.json` holds 74
  conversations and `data/scenes.json` 10 scenes; the NPCs are conversation-bearing and need seats in
  their settlements. **The first job is to establish what the 32 actually are** — that number came
  from the owner, not from a file anyone verified. Do not take it on trust.
- **Four Rift guards (G1, G2, G4, G5) and two posts.** These now **have seats**: the gatehouses stand
  in the world with armour-stand placeholders where Codex's NPCs go (`data/rift_zones.json`, applied
  by R9Z). This half is unblocked and is the easier of the two.

Whatever is placed next, **verify against the world, not the plan**. The pattern that worked is
recorded at the end of the findings doc: make the agent nominate, in advance and in coordinates, the
seats most likely to embarrass it, then probe those over RCON. It corrected its own prediction on five
of ten seats and cost one pass.

### The four withheld zone walls, and what unblocks them

R9Z installs **5 of 9**: the throat wall and the four gatehouses of z1 and z2. Held back:
`wall_league_gate`, `wall_behind_league`, `gatehouse_z4`, `gatehouse_z5`.

Installing them would wall off the apex and **seal the League's precinct**, ending the game for anyone
who reaches it. A wall nobody can pass is not a gate.

Which half is live is read from the DATA, never a list: a zone declares `needs_progression` or
`needs_dialogue`, and R9Z installs its wall and gatehouses only when it declares neither.
`held_functions()` in `tools/reapply.py` derives the same set so `unreferenced()` does not flag them.
**When Codex lands either half, the field goes from `data/rift_zones.json` and the wall follows with
nothing to remember.** Two things must land:

- **z4** needs Codex's dialogue to read `q.player.pokedex.caught_count` and call
  `cobblers:rift_zones/z4/grant`. No command reads species owned, so `z4/qualify` can only refuse.
- **z5** needs `rift_crisis_resolved` — below.

### `rift_crisis_resolved` still has no setter on Codex's branch

Checked on `origin/codex/trainer-modes` (head `0cea344`). Its own `data/quests.json` says of itself:
*"approved in ARC.md but absent from the progression ledger; unlock_league_after_rift_resolution
defines the required per-player handoff, but no authoritative setter invokes it"*, and *"no current
dialogue node invokes this transition"*.

So z5 is shut to everyone — closed rather than open, which is the safe direction. **Do not invent the
setter**: it is the finale's quest stage and it is story data. `tools/rift_zones.py report` exits 1 on
3 OWED and that is correct, not a failure to fix from this side.

### Giovanni's roster is still held and still empty

`data/trainers.json` `gym_08_giovanni`: `status: "held"`, `team: []`,
`blocked_by: "Giovanni battle-format decision"`. The generator **refuses to emit an override with an
empty team** — one with no Pokemon is worse than upstream's roster — so seven leaders carry our teams
and Giovanni carries Cobbleverse's.

His **building exists and is applied** (gym8, the Gate of the South; spawner probed at
(3565, 121, 6416)), so the eighth badge is winnable against the upstream roster. The independent audit
flagged that as a MEDIUM defect. The blocker is the singles-versus-doubles decision in
`docs/story/GIOVANNI_FORMAT.md` and it is the owner's.

Now relevant to it: our twelve overrides each declare `battle_format` explicitly, because an override
REPLACES upstream's whole file and all twelve were silently dropping `battleFormat`. Whatever
Giovanni's format decision is, it goes in `data/gym_trainers.json` as his `battle_format`.

## 4. What is in the world (probed, not inferred)

Seven authored gym buildings with every leader's spawner; the demolition; the twelve re-skinned
portals; the lake beds laid back (F5 — (3009,104,4008) reads `minecraft:clay`); the zone walls'
passable half; the dig camp's reshape; eight ferry docks; 56 seated trainers; Registeel and Regigigas;
`25_reshell` inside R2.

**Unproven, and only the owner can settle it:** whether Brock now REFUSES a rematch with the badge in
hand. The guard is installed; installed is not working. They were refighting him as this was written.

## 5. What a cold start must not rediscover

- **A nested isolation worktree is based on the MAIN checkout's HEAD**, far behind, and
  `git merge --ff-only` fails outright. Authorise `git reset --hard <sha>` explicitly in the brief as
  the one permitted base-fixing command. Every agent this session hit it.
- **An agent's audit is provisional until integration re-runs it (F8).** It caught real faults twice
  today: `rift_zones.py trace` crashed without `--source-root`, and the zone pack was filling into
  chunks nobody loads — 9 functions of silent no-ops, found by `function_limits` inside prepare.
- **"Our list is not the world"** and **"How to prove an audit is independent"** are both now in
  CLAUDE.md. Read them before writing an audit or a system that enumerates our own data.
- The suite's honest baseline is **8 pre-existing failures** (heightmap provenance,
  `mines_independent`, `no_swallowed_crashes`, two `rift_heightmap`, three `sea_town`), plus C3 and
  C14 as strict xfail in `data/system_contracts.json`. All reproduce at 36eb267. Do not chase them.
- `COBBLERS_SOURCE_ROOT` must be `C:\Users\wnd\Documents` in every shell; `COBBLERS_SERVER_LOCK` and
  `COBBLERS_LOCK_OWNER` must match the lock file's owner line exactly or `runtime_guard` refuses.

## 6. Also open

- **`tilpey_launch`** is held: `ferries.py` walks every crossing at sea level 62 and that launch
  crosses a lake at y77, so its water has never been walked. Its docks and ferrymen stand.
- **`pacifidlog_south_jetty`** is back to `planned` — it stood seven blocks under the sea. The shore
  is at about z6574 along x5160.
- **Four charters** gate on `quest.sq_sunset_01.completed`, declared and never set. One line from the
  owner drops the gate and leaves them on `champion_cleared` alone.
- **`no_build` boxes are authored and unwired** in all seven gym buildings — no scene record, so a
  player with blocks pillars past every gate.
- **Nine MEDIUM/LOW defects** in gyms 6 and 8 from the independent audit, listed in
  `docs/REPORT_2026-09-30_DAY.md`.
- **The carry** still needs the owner in dryrun11 to revoke `gym5_cleared`/`gym6_cleared`.
