# campaign/

Authored campaign design data. This is the Pokémon region: what spawns where,
who the trainers are, what the gyms and bosses run, how progression unlocks.

Nothing here exists yet, on purpose. **Formats are decided by experiments, not
guessed.** Until EXP-001 (encounters), EXP-002 (trainers), EXP-003 (level caps),
EXP-004 (gauntlets), EXP-005 (dungeons), EXP-006 (static encounters) and EXP-007
(progression) have findings, these folders hold only READMEs.

| Folder | Will hold | Implemented through (candidate, unverified until the experiment) |
| --- | --- | --- |
| `progression/` | Chapters, level caps per chapter, unlock conditions | RCT series and level-cap config; advancements; functions |
| `encounters/` | Per-area encounter tables (10 to 20 species each) | Cobblemon spawn pools with biome, structure, coordinate, height, time, weather conditions |
| `trainers/` | Ordinary and notable trainer teams | RCT trainer JSON |
| `gyms/` | Gym Leader teams, gym rules, badge rewards | RCT trainer + mobs JSON, CobbleverseBadges items |
| `bosses/` | Rivals, admins, champion, optional superbosses | RCT trainer JSON |
| `gauntlets/` | Multi-trainer sequences with restrictions | RCT + functions or scripting (EXP-004) |
| `dungeons/` | Dungeon specs: rooms, puzzle states, flags, rewards | functions, scoreboards, structures (EXP-005) |
| `villain/` | Villain team arc, hideouts, admins | composition of the above |
| `quests/` | Side quests and their rewards | unknown (EXP-007) |
| `rewards/` | Reward tables: items, TMs, Pokémon, one-time flags | loot tables, functions |
| `dialogue/` | Trainer and NPC dialogue | RCT dialog JSON, Cobblemon NPC dialogue |

Design definitions live here. The datapacks that implement them live in
`modpack/datapacks/`. Keep the two apart so a format change does not rewrite the
design.

Validation (`tools/validate.py`) grows checks for these folders only after real
formats exist.
