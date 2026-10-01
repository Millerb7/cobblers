# The gym leaders' rosters reach a player

Written 2026-09-30, closing **F11** in `docs/FLIGHT_FINDINGS_2026-09-29.md`.

Data: `data/gym_trainers.json`. Generator: `tools/route_trainers.py`.
Pack: `build/datapacks/cobblers_trainers`, the same one the League five go into.

## The finding

Our eight authored gym leader teams reached no player. `grep -rl gym_01_brock build/ modpack/
server/` returned nothing on 2026-09-29. `tools/route_trainers.py` was the only tool writing
`data/rctmod/trainers/*` and it wrote Routes 1-3; `data/progression.json`'s
`upstream_neutralised` emptied each leader's loot table at the upstream id but never replaced the
roster behind it. So a player walked into our gym, fought **Cobbleverse's** leader, and won our
badge and our first-win rewards for it.

## Why an override, and not a new trainer id

Because the id is load-bearing in four places at once, and the spawner cannot be re-pointed:

- `data/gym_buildings/gym1.json` sets `rctmod:trainer_spawner{TrainerIds:["kanto_brock"]}` in the
  gallery, and records the verified consequence: *"a persistent kanto_brock anywhere awards the
  badge (verified on staging 2026-09-24)"*. The five built gyms all do the same —
  `kanto_brock`, `kanto_ltsurge`, `kanto_erika`, `kanto_koga`, `kanto_blaine`.
- `data/progression.json` binds `gym1_cleared` .. `gym8_cleared` to the upstream ids.
- `first_win_rewards` is keyed by the upstream ids; the badge and the TM come from there.
- Cobbleverse's own gym template carries a spawner locked to the same id.

Overriding the upstream id's team at the upstream path (`.claude/rules/datapacks.md`) is the only
change that puts our roster in front of a player while leaving every badge, flag and reward
pointing where it already points. It is the same mechanism, and the same reason, as
`data/league_trainers.json`.

## What a player now fights

Read back out of the emitted files, not out of the generator:

| our record | emitted as | ace | contract | the team a player now fights |
|---|---|---|---|---|
| `gym_01_brock` | `kanto_brock` | 20 | 20 | geodude 18, bonsly 18, cranidos 19, **onix 20** |
| `gym_02_misty` | `kanto_misty` | 25 | 25 | horsea 22, lombre 23, goldeen 24, **starmie 25** |
| `gym_03_surge` | `kanto_ltsurge` | 30 | 30 | electabuzz 27, magnezone 28, boltund 29, **raichu 30** |
| `gym_04_erika` | `kanto_erika` | 35 | 35 | bellossom 33, roserade 33, victreebel 34, **vileplume 35** |
| `gym_05_koga` | `kanto_koga` | 40 | 40 | crobat 38, weezing 38, drapion 39, toxtricity 39, **venomoth 40** |
| `gym_06_sabrina` | `kanto_sabrina` | 45 | 45 | hatterene 42, mrmime 43, bronzong 43, rapidash 44, **alakazam 45** |
| `gym_07_blaine` | `kanto_blaine` | 50 | 50 | torkoal 47, arcanine 48, magcargo 48, magmortar 49, typhlosion 49, **charizard 50** |
| `gym_08_giovanni` | — | — | 55 | **held: nothing emitted, see below** |

**Every one of the seven matches `generation_contract.gym_ace_levels` exactly.** No team
disagreed with its contract level, so nothing was adjusted; `tools/route_trainers.py` now
re-checks it on every run and refuses to emit on a disagreement rather than quietly fixing one —
a mismatch belongs in `docs/story/TRAINER_RULES.json`, upstream of the generated
`data/trainers.json`.

## What a player fought before, and what is not known

**Not recorded in this checkout.** Upstream's rosters live in the Cobbleverse RCT datapack
(`COBBLEVERSE-RCT-DP-v20`), which is gitignored and not present in this worktree, and no document
here transcribes them. The one upstream roster fact the repo holds is an observation, not a
guess: `docs/research/notes/battle-freeze-double-ko.md` records that on 2026-09-25 Cobbleverse's
`kanto_brock` fielded a **Cranidos with a recoil move, probably Head Smash**, which fainted
itself and froze the battle. Our Brock also fields a Cranidos, at level 19 and not as the ace,
with whatever moveset `data/trainers.json` gives it — **whether our roster still reproduces that
freeze has not been checked and is not claimed here.**

Writing out what upstream's eight rosters were, for the record, needs the RCT datapack opened.
That is a `dependency-auditor` job, not this one.

## Giovanni is held, deliberately

`data/trainers.json` gives `gym_08_giovanni` `status: "held"`, `team: []`, and
`blocked_by: "Giovanni battle-format decision"` — *"Roster intentionally withheld until the
singles-versus-doubles decision is settled."* Nothing is emitted for him. An override with an
empty team would stand a leader with no Pokemon in front of a player, which is strictly worse
than leaving upstream's roster in place; the generator names him and skips him rather than
failing the run, and refuses outright if any *un*held entry has an empty team.

The fix is upstream: a roster in `docs/story/TRAINER_RULES.json` once the owner settles singles
versus doubles. `data/trainers.json` is generated and was not hand-edited.

## Deliberately not emitted

For all eight: **no dialogue file** (story is Codex's; nothing is invented here, so upstream's
lines stand), no rctmod mob file (the spawner owns how each is spawned; a `spawnWeightFactor: 0`
override could break it), no loot table (`upstream_neutralised` empties them and
`first_win_rewards` pays instead), no advancement (each `gymN_cleared` already fires from the
upstream id through `tools/progression_pack.py`), and no entry in `placements()` — these stand
where their spawner puts them, so `tools/reapply.py` has nothing to summon.

## The dialogue sweep (finding 2, widened)

Every `dlg_*` id in `data/trainers.json` resolves nowhere.

- **63 trainer records** carry dialogue ids; **189 ids in total**; **189 of 189 are absent from
  `data/dialogue.json`** (checked 2026-09-30).
- Only **13** records — Routes 1-3 — also carry `dialogue_text`, which is what the generator
  actually emits. So **50 records have no usable lines at all**: 8 gym leaders, 4 Elite Four, 1
  Champion, 36 route trainers and 1 optional-route trainer.
- The Victory Road ten and the League five now have text authored beside their seats
  (`data/vr_trainers.json`, `data/league_trainers.json`). The remaining **50 minus those 14 = 36**
  records, gym leaders included, still have none.

`generation_contract` calls the ids *"campaign metadata; RCT sidecars require a future compiler"*.
Until that compiler exists the ids are decoration. This is a story job, not a tooling one.

## Verified / not verified

**Verified:** the seven emitted files were read back off disk and compared to
`data/trainers.json` — species, levels, movesets, `ai`, `battleRules`, `bag` and the name literal
all match; every top level equals its contract level; no gym dialogue file was written; no file
exists for Giovanni. `tools/validate_data.py` reports 0 errors.

**Not verified:** nothing has been seen in game. That a datapack override at
`data/rctmod/trainers/kanto_brock.json` actually replaces the roster rctmod loads from its own
jar is the one assumption this rests on. It is the same assumption `upstream_neutralised` already
makes for the same trainers' loot tables at `rctmod:trainers/single/kanto_brock`, and that one
has been run — but **the team path has not been tested, and a single staging fight with Brock
would settle it.** If the override does not take, everything here is inert and a player keeps
fighting Cobbleverse's leader.
