# Session handover (2026-09-27, branch `session/morning-tests`)

The open threads of the session that ended on 2026-09-27, for a cold start. `docs/STATE.md` holds the durable state;
this file holds only what STATE does not: where work stopped, what waits on the owner, and the next steps. Delete this
file once its threads are picked up or moved into STATE.

## 1. The branch and the PRs

- **`session/morning-tests` is the whole batch**: every commit since main's `b5bb9bb` (PR #82), about 77 commits. It
  merged in its topic branches as it went: `tests/gulch-and-boats`, `design/water-shape-run` and
  `design/water-shape-polish`. **No PR is open.** The owner's rule is one draft PR per batch, not a stack
  (memory `one-big-pr-per-batch`). Open it from this branch with the `open-pr` skill, and report its full head SHA
  with `gh pr merge <N> --match-head-commit <sha>`.
- **Main does not have any of this batch.** A new session that starts from `origin/main` starts without the blackout
  recovery, the swim rules, the gulch prototype, the ferries, the water-shape design and this file. Either merge the
  batch's PR first, or start the new session on `session/morning-tests`.
- **Other remote branches not merged into main:**

  | Branch | What it has | Action |
  | --- | --- | --- |
  | `world/rift-mines`, `world/town-character`, `towns/batch1-placement` | Only merge commits. Their content reached main by other PRs (#72 and #73 were closed) | Nothing to merge. Deleting them is the owner's call |
  | `codex/exp-009-hex-prototype` | One real commit, 2026-09-10: "Document world generation playtest limitations" (Codex's) | The owner's call; not needed by anything open |

## 2. Staging at handover

- **Staging world:** `cobblers-dryrun11`, packs world-local in its own `datapacks` folder.
- **Server stopped** at the end of the session.
- **Coordination lock released** (`C:\Users\wnd\Documents\github\.cobblers-server-agent.lock`).

A new session runs CLAUDE.md's live-server checks, takes the lock, and runs
`python tools/install_check.py --server-dir <server> --world-dir <staging world>` before anything else.

Scratch scripts from this session (RCON helper, restart, verifiers) lived in its scratchpad and are gone. Anything
lasting is in `tools/`.

## 3. Mid-flight, and where it stopped

### 3.1 The water export (waiting on the owner's go)

- **Design:** `docs/world-building/WATER_SHAPE.md`, `data/water_shape.json`, `tools/water_shape.py`.
- **Audit:** `tools/water_shape_audit.py`, clean (181 checks) on the copy.
- **Owner decisions:** answered in section 14 (the scour hole, the dive-site rule, the ravine dry and dressed, the
  ferry length, the flats), and Part B in section 15 (the Jungle Isle removed, Pacifidlog on the sea, the Long Isle
  half desert and half jungle).

**Where it stopped:** one open item, **the margin's continuation** (section 7, section 14's last paragraph). The margin
relief image copies each edge column straight outward. The close-ups show combed parallel streaks, not headlands. It
must be reworked, with land carried off the edge as shaped headlands that fall to the sea, before the export.

**The next steps, in order:**
1. Rework the margin, re-run the maps and the audit.
2. Add the Viltri Ravine's bed pattern to the paint (it goes into the export; section 14 item 3).
3. With the owner's go: section 11 steps 3-11. These are the apply (it writes beside the canonical heightmap and
   repins `data/world.json`: never without the go), the dependent re-measures, and the staging export
   `cobblers-dryrun12`. Then the re-apply, the water verify (still to be written, by an agent that did not build the
   shape), and the owner's flight.
4. After the export: the ravine's block dressing (boulders, driftwood, the dry falls lip, the ford at Stoneford, the
   silted dead arm).

**Cost estimate given to the owner:** about **0.9-1.7 million tokens**. The main session does the margin, the paint,
the apply and the export; one `test-author` subagent writes the water verify. It re-runs the heightmap pipeline, so
it will say its number of passes before starting.

**The owner has not said go.**

### 3.2 The southern Rift redesign (waiting on the owner's go)

The owner redesigned the gulch site after playing its gate. The decisions are in `docs/world-building/SOUTHERN_RIFT_MEGA.md`
section 13, and nothing there is built:
- the gate wall raised to the crag tops;
- the town filling the whole cove in worker, miner and extractor sections, with an unplanned layout;
- Megas as the only source of raw mega stones: about level 60 (65-70 deeper), a 15% drop per defeat (more deeper), in
  the Rift's two western zones around (4090, 116, 5289) and (3738, 87, 5164), dressed with caves, dens and broken
  houses;
- the price: 2 raw stones plus a diamond per keyed stone, and no arrival floor of free stones;
- the crystal faces kept as scenery that cannot be mined;
- the West Spur Dig reshaped: fitted to its pocket, a large deep quarry over about half of it with strip mines above,
  an unplanned layout.

**Built now:** Fight or Flight's `always_aggro_aspects` includes the four Mega aspects (the owner's go; server config,
recorded in `server/config/mods/fightorflight.json5`). Staging restarted on it with 0 load problems. Unseen in game.

**Cost estimate given to the owner: about 1.2-1.9 million tokens.**

| Who | What | Tokens |
| --- | --- | --- |
| The main session | The gate wall, the drop roll (the `battle_fainted` and kill paths in `tools/blackout_pack.py`, for Megas carrying the farm's tag), den respawns on a timer nothing can reset, the price (`tools/mega_recipes.py` and the Cutters' offers), the installs | 150-250k |
| One build subagent with a shell | The cove town, the two broken zones, the dig camp reshape, with fail-closed audits. It reports after its first pass, with about three passes at most | 700k-1.2M |
| One `test-author` at the end | Independent tests; fixes batched before sending tests back | 300-450k |

The main session recommended doing this in a fresh session. **The owner has not said go, nor which of 3.1 and 3.2
comes first.**

### 3.3 Nothing else is running

No subagent is running. Every other thread of the day is finished and recorded in STATE:
- the blackout recovery, all paths passing in game (EXP-042 session 5);
- the Mega Bracelet (EXP-045 PASS);
- the ferries, played and approved;
- swim fatigue and boats, installed;
- the town-dressing spire and mast, rebuilt;
- the spur cut back.

## 4. Decisions made on 2026-09-27 that are not built

- **The southern Rift redesign and the dig camp reshape:** section 3.2 above (`SOUTHERN_RIFT_MEGA.md` section 13).
- **The margin, the ravine and Part B:** the water decisions in `WATER_SHAPE.md` sections 14-15. The ravine stays dry
  and is dressed. Part B (the Jungle Isle removed, Pacifidlog on the sea, the Long Isle split) is designed and applies
  with the export (STATE "Pacifidlog moves onto the sea").
- **The planned Pacifidlog ferry** (`data/ferries.json`): built with the export's Part B.
- **The 20-level exemption from Mega aggression (proof M-3b):** Fight or Flight 0.11.0 has no player-level key. It
  matters only once the cap passes 80.
- **The large bridge to the Long Isle:** the owner asked for "a large bridge from somewhere to the Long Isle when we
  update that island". It is not designed yet; it belongs to the Long Isle work after Part B.

## 5. Waiting on the owner

### In game, on staging

| What | Where | Records to |
| --- | --- | --- |
| Megas attack on sight: in daylight and in the dark (M-3; `light_dependent_unprovoked_attack` is on server-wide) | The gulch's Cutting Floor, with `gym6_cleared` | `SOUTHERN_RIFT_MEGA.md` section 10 |
| A Mega refuses a ball (M-4), the Cutters' trade (M-6), the Megas' models, Excadrill above all (M-7) | The gulch | The same |
| Swimming again with a Surf-and-Dive party after the fatigue-reset fix, and whether trained swimmers tiring on the surface at half rate is wanted | Any sea | EXP-044 |
| Boats tipped at 48 blocks, and safe in Pacifidlog's bay | The Sound, Pacifidlog | EXP-044 |
| The town-waystone checkpoint, a mid-dive swap, a trainer loss (money and the return, no claim) | Any town waystone | EXP-042 |
| The spur's grille ward and the daily crystal | The West Spur Dig, drift C | STATE |
| The rebuilt spire (Sabrina's) and mast (Blaine's) | Their towns | STATE "Town character" |
| The Deep's city and the relic area's surface | The Rift pit | STATE |

### Decisions

- The go for 3.1 and for 3.2, and their order.
- The gorge hamlet's visibility: move it, clear a line, or accept "found, not seen" (STATE "Visibility claims are
  stale").
- The level-cap trap fix (STATE "The level-cap trap").
- STATE "Blocked on the owner" under client models.

## 6. Tests: the known failures

Full run at handover, 2026-09-27, `python -m pytest -q` at `aab8156` plus this file: **3,785 passed, 5 xfailed, 0
failed** (12 min 35 s). The five are xfails: known, unfixed defects that the tests pin until the fix lands.
None is a regression from this session.

| # | Test | The defect |
| --- | --- | --- |
| 1 | `tests/test_client_model_fix.py::test_server_pack_build_refuses_when_what_it_ships_differs_from_the_committed_record` | `tools/client_model_fix.py:764`. The server pack build compares only `paths` and `species` with the committed manifest, not `left_to_stack`. A donor file can enter the zip without the manifest changing |
| 2 | `tests/test_install_check.py::test_packs_refuses_the_live_world_when_called_directly` | `tools/install_check.py:51-86`. `packs()` reads the world's datapacks without the runtime guard; only `main()` checks `--world-dir`. Latent: the one other caller, `reapply.py install`, guards first |
| 3 | `tests/test_server_config_record.py::test_install_keeps_the_server_id_when_the_overlay_omits_the_key` | `tools/server_config_record.py:96-100`. Distant Horizons' `serverId` is kept only by substituting it into the overlay's own line. An overlay with no such line would drop it. Latent |
| 4 | `tests/test_server_config_record.py::test_record_does_not_mirror_a_file_that_differs_from_the_base_pack_only_in_form` | `tools/server_config_record.py:122`. `record` compares bytes, while `check` compares values. A file differing only in line endings, comments or layout is mirrored |
| 5 | `tests/test_server_config_record.py::test_no_mirrored_config_repeats_the_base_pack_values` | Caused by 4. `server/config/mods` holds 38 files whose values equal the base pack's |

**A practical warning from 4 and 5:** running `server_config_record.py record` rewrites about 40 mirrored files, with
line endings and properties-file timestamps only. This session kept only the intended file
(`fightorflight.json5`): it staged that file with `git add`, then restored the rest with
`git checkout -- server/config/mods/`. Do the same until the tool
is fixed.

## 7. Codex's items (story text; not ours to edit)

When Part B applies, these need Codex's rewrite, because they point at the Jungle Isle or its ruins:
- `SQ-SUNSET-02`, `SQ-JUNGLE-01`, `SQ-JUNGLE-02` in `docs/story/SIDEQUESTS.md`;
- the encounter notes for the island;
- `docs/HANDOVER_CODEX.md` items 17 and 18 (Sunset West moved; the jungle ruins' cache).

`WATER_SHAPE.md` section 15 lists the coordinates.
