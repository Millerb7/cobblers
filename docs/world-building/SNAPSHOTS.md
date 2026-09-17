# Retired world snapshots: retention and boot check (2026-09-16)

`cobblers-server-retired/` sits outside Git. This records what is kept, the evidence that the kept full-world anchors are
real recovery points, and what may be deleted. Deleting is the user's act; no agent deletes snapshots.

## Retained

| Snapshot | Size | Why |
| --- | ---: | --- |
| `2026-09-16-pre-rescale` | 2.90 GiB | Full world before the vertical rescale. Boots (below). |
| `2026-09-17-pre-grass` | 2.47 GiB | Latest full world, before the thinned-grass re-export. Boots (below). |
| `2026-09-15-valley-head-files` | 0.10 GiB | Heightmap revisions `6b6352bc` and `924253ad` with the rivers record they belong to. |
| `2026-09-17-provenance-heightmaps` | 0.14 GiB | The only copies of `60b241d1` (the river cut the 2026-09-15 routes were derived on), `861d10ac` (the towns' earlier measurements) and `217d411c`, copied out of folders that are to be deleted. |
| `exp013de-site-backup`, `town-iteration-test`, `exp013de-nether-outside-border` | 0.02 GiB | Small EXP-013 and town-iteration fixtures. |

## Boot check

Each full anchor was copied to `cobblers-boot-check/` and booted on the pack's server runtime with
`--universe cobblers-boot-check --world <name>` (the anchors and `server.properties` untouched), under the coordination
lock, then probed over RCON and stopped.

| Anchor | Done | Game time (proves its own world loaded) | Stop | Crash |
| --- | --- | ---: | --- | --- |
| `2026-09-16-pre-rescale` | 3.39 s | 237,246 | clean, saved | no |
| `2026-09-17-pre-grass` | 3.15 s | 534,005 | clean, saved | no |

### Every error line, classified

Both anchors log 43 ERROR lines and no FATAL. Every line is classified, and every line also appears in the live world's
own boot of 2026-09-16 (`logs/2026-09-16-2.log.gz`, 92 error lines of the same classes; worker thread numbers ignored).
No line concerns chunks, regions, `level.dat`, entities or other world data.

| Class | Lines per anchor | What it is |
| --- | ---: | --- |
| `datafixer` | 26 | "No data fixer registered for <id>": mod entity and block-entity types registered without a DataFixerUpper schema. The fixer only runs when data from an older Minecraft version is upgraded; the anchors are the same 1.21.1 as the runtime. |
| `empty_registry` | 8 | VanillaBackport's backported variant registries (wolf, cat, frog, cow, pig, chicken variants; sulfur cube archetypes) have no entries on 1.21.1. |
| `raid_loot` | 7 | Cobblemon Raid Dens reward loot tables fail to parse. Affects raid rewards when raids run, not world data. |
| `dex_addition` | 1 | Mega Showdown's `mega_z` Pokedex addition names a sub-dex that is not present. Display data. |
| `advancements` | 1 | Two Cobblemon crafting advancements fail to load. Progress display. |

Verdict: both anchors boot exactly as cleanly as the live world. They are valid recovery points.

### `2026-09-16-pre-rescale` (43 error lines)

| # | Class | Also in the live boot | Line |
| ---: | --- | --- | --- |
| 1 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobbledollars:cobble_merchant` |
| 2 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobblemon:pokemon` |
| 3 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobblemon:empty_pokeball` |
| 4 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobblemon:boat` |
| 5 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobblemon:chest_boat` |
| 6 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobblemon:poke_bobber` |
| 7 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobblemon:generic_bedrock` |
| 8 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobblemon:npc` |
| 9 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:tracing_bullet` |
| 10 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:arrow_projectile` |
| 11 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:bullet_projectile` |
| 12 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:spike_projectile` |
| 13 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:floating_spike_projectile` |
| 14 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:sticky_web` |
| 15 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:tornado` |
| 16 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:whirlpool` |
| 17 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:magic_effect` |
| 18 | datafixer | yes | `[main/ERROR]: No data fixer registered for handcrafted` |
| 19 | datafixer | yes | `[main/ERROR]: No data fixer registered for trainer` |
| 20 | datafixer | yes | `[main/ERROR]: No data fixer registered for trainer_association` |
| 21 | datafixer | yes | `[main/ERROR]: No data fixer registered for ` |
| 22 | datafixer | yes | `[main/ERROR]: No data fixer registered for sulfur_cube` |
| 23 | datafixer | yes | `[main/ERROR]: No data fixer registered for creaking` |
| 24 | datafixer | yes | `[main/ERROR]: No data fixer registered for happy_ghast` |
| 25 | datafixer | yes | `[main/ERROR]: No data fixer registered for pale_oak_boat` |
| 26 | datafixer | yes | `[main/ERROR]: No data fixer registered for pale_oak_chest_boat` |
| 27 | empty_registry | yes | `[main/ERROR]: Registry 'minecraft:wolf_sound_variant' was empty after loading` |
| 28 | empty_registry | yes | `[main/ERROR]: Registry 'minecraft:cow_variant' was empty after loading` |
| 29 | empty_registry | yes | `[main/ERROR]: Registry 'minecraft:chicken_variant' was empty after loading` |
| 30 | empty_registry | yes | `[main/ERROR]: Registry 'minecraft:pig_variant' was empty after loading` |
| 31 | empty_registry | yes | `[main/ERROR]: Registry 'vanillabackport:wolf_variant' was empty after loading` |
| 32 | empty_registry | yes | `[main/ERROR]: Registry 'vanillabackport:frog_variant' was empty after loading` |
| 33 | empty_registry | yes | `[main/ERROR]: Registry 'vanillabackport:cat_variant' was empty after loading` |
| 34 | empty_registry | yes | `[main/ERROR]: Registry 'vanillabackport:sulfur_cube_archetypes' was empty after loading` |
| 35 | raid_loot | yes | `[Worker-Main-3/ERROR]: Couldn't parse element minecraft:loot_table/cobblemonraiddens:raid/tier/tier_three - Failed to parse either. First: Unknown registry key in ResourceKey[minecraft:root / minecraft:loot_condition_typ` |
| 36 | raid_loot | yes | `[Worker-Main-3/ERROR]: Couldn't parse element minecraft:loot_table/cobblemonraiddens:raid/tier/tier_five - Failed to parse either. First: Unknown registry key in ResourceKey[minecraft:root / minecraft:loot_condition_type` |
| 37 | raid_loot | yes | `[Worker-Main-3/ERROR]: Couldn't parse element minecraft:loot_table/cobblemonraiddens:raid/tier/tier_six - Failed to parse either. First: Unknown registry key in ResourceKey[minecraft:root / minecraft:loot_condition_type]` |
| 38 | raid_loot | yes | `[Worker-Main-3/ERROR]: Couldn't parse element minecraft:loot_table/cobblemonraiddens:raid/tier/tier_seven - Failed to parse either. First: Unknown registry key in ResourceKey[minecraft:root / minecraft:loot_condition_typ` |
| 39 | raid_loot | yes | `[Worker-Main-3/ERROR]: Couldn't parse element minecraft:loot_table/cobblemonraiddens:raid/tier/tier_two - Failed to parse either. First: Unknown registry key in ResourceKey[minecraft:root / minecraft:loot_condition_type]` |
| 40 | raid_loot | yes | `[Worker-Main-3/ERROR]: Couldn't parse element minecraft:loot_table/cobblemonraiddens:raid/tier/tier_one - Failed to parse either. First: Unknown registry key in ResourceKey[minecraft:root / minecraft:loot_condition_type]` |
| 41 | raid_loot | yes | `[Worker-Main-3/ERROR]: Couldn't parse element minecraft:loot_table/cobblemonraiddens:raid/tier/tier_four - Failed to parse either. First: Unknown registry key in ResourceKey[minecraft:root / minecraft:loot_function_type]` |
| 42 | advancements | yes | `[main/ERROR]: Couldn't load advancements: [cobblemon:craft_poke_ball, cobblemon:craft_pokedex]` |
| 43 | dex_addition | yes | `[main/ERROR]: Unable to apply dex addition cobblemon:mega_z as the sub-dex cobblemon:mega_z does not exist` |

### `2026-09-17-pre-grass` (43 error lines)

| # | Class | Also in the live boot | Line |
| ---: | --- | --- | --- |
| 1 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobbledollars:cobble_merchant` |
| 2 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobblemon:pokemon` |
| 3 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobblemon:empty_pokeball` |
| 4 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobblemon:boat` |
| 5 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobblemon:chest_boat` |
| 6 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobblemon:poke_bobber` |
| 7 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobblemon:generic_bedrock` |
| 8 | datafixer | yes | `[main/ERROR]: No data fixer registered for cobblemon:npc` |
| 9 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:tracing_bullet` |
| 10 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:arrow_projectile` |
| 11 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:bullet_projectile` |
| 12 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:spike_projectile` |
| 13 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:floating_spike_projectile` |
| 14 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:sticky_web` |
| 15 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:tornado` |
| 16 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:whirlpool` |
| 17 | datafixer | yes | `[main/ERROR]: No data fixer registered for fightorflight:magic_effect` |
| 18 | datafixer | yes | `[main/ERROR]: No data fixer registered for handcrafted` |
| 19 | datafixer | yes | `[main/ERROR]: No data fixer registered for trainer` |
| 20 | datafixer | yes | `[main/ERROR]: No data fixer registered for trainer_association` |
| 21 | datafixer | yes | `[main/ERROR]: No data fixer registered for ` |
| 22 | datafixer | yes | `[main/ERROR]: No data fixer registered for sulfur_cube` |
| 23 | datafixer | yes | `[main/ERROR]: No data fixer registered for creaking` |
| 24 | datafixer | yes | `[main/ERROR]: No data fixer registered for happy_ghast` |
| 25 | datafixer | yes | `[main/ERROR]: No data fixer registered for pale_oak_boat` |
| 26 | datafixer | yes | `[main/ERROR]: No data fixer registered for pale_oak_chest_boat` |
| 27 | empty_registry | yes | `[main/ERROR]: Registry 'minecraft:wolf_sound_variant' was empty after loading` |
| 28 | empty_registry | yes | `[main/ERROR]: Registry 'minecraft:cow_variant' was empty after loading` |
| 29 | empty_registry | yes | `[main/ERROR]: Registry 'minecraft:chicken_variant' was empty after loading` |
| 30 | empty_registry | yes | `[main/ERROR]: Registry 'minecraft:pig_variant' was empty after loading` |
| 31 | empty_registry | yes | `[main/ERROR]: Registry 'vanillabackport:wolf_variant' was empty after loading` |
| 32 | empty_registry | yes | `[main/ERROR]: Registry 'vanillabackport:frog_variant' was empty after loading` |
| 33 | empty_registry | yes | `[main/ERROR]: Registry 'vanillabackport:cat_variant' was empty after loading` |
| 34 | empty_registry | yes | `[main/ERROR]: Registry 'vanillabackport:sulfur_cube_archetypes' was empty after loading` |
| 35 | raid_loot | yes | `[Worker-Main-3/ERROR]: Couldn't parse element minecraft:loot_table/cobblemonraiddens:raid/tier/tier_three - Failed to parse either. First: Unknown registry key in ResourceKey[minecraft:root / minecraft:loot_condition_typ` |
| 36 | raid_loot | yes | `[Worker-Main-3/ERROR]: Couldn't parse element minecraft:loot_table/cobblemonraiddens:raid/tier/tier_five - Failed to parse either. First: Unknown registry key in ResourceKey[minecraft:root / minecraft:loot_condition_type` |
| 37 | raid_loot | yes | `[Worker-Main-3/ERROR]: Couldn't parse element minecraft:loot_table/cobblemonraiddens:raid/tier/tier_six - Failed to parse either. First: Unknown registry key in ResourceKey[minecraft:root / minecraft:loot_condition_type]` |
| 38 | raid_loot | yes | `[Worker-Main-3/ERROR]: Couldn't parse element minecraft:loot_table/cobblemonraiddens:raid/tier/tier_seven - Failed to parse either. First: Unknown registry key in ResourceKey[minecraft:root / minecraft:loot_condition_typ` |
| 39 | raid_loot | yes | `[Worker-Main-3/ERROR]: Couldn't parse element minecraft:loot_table/cobblemonraiddens:raid/tier/tier_two - Failed to parse either. First: Unknown registry key in ResourceKey[minecraft:root / minecraft:loot_condition_type]` |
| 40 | raid_loot | yes | `[Worker-Main-3/ERROR]: Couldn't parse element minecraft:loot_table/cobblemonraiddens:raid/tier/tier_one - Failed to parse either. First: Unknown registry key in ResourceKey[minecraft:root / minecraft:loot_condition_type]` |
| 41 | raid_loot | yes | `[Worker-Main-3/ERROR]: Couldn't parse element minecraft:loot_table/cobblemonraiddens:raid/tier/tier_four - Failed to parse either. First: Unknown registry key in ResourceKey[minecraft:root / minecraft:loot_function_type]` |
| 42 | advancements | yes | `[main/ERROR]: Couldn't load advancements: [cobblemon:craft_poke_ball, cobblemon:craft_pokedex]` |
| 43 | dex_addition | yes | `[main/ERROR]: Unable to apply dex addition cobblemon:mega_z as the sub-dex cobblemon:mega_z does not exist` |

## Delete (user runs these)

About 42.5 GiB. Everything else in `cobblers-server-retired/` is retained.

```powershell
$r = "C:\Users\wnd\Documents\github\cobblers-server-retired"
"2026-09-13","2026-09-14","2026-09-14-biome-tags","2026-09-14-foliage","2026-09-14-foliage-first-pass","2026-09-14-rivers","2026-09-14-tarn","2026-09-15-pre-relief","2026-09-15-pre-sculpt","2026-09-15-river-head","2026-09-16-pre-creek" | ForEach-Object { Remove-Item -Recurse -Force "$r\$_" }
Remove-Item -Recurse -Force "C:\Users\wnd\Documents\github\cobblers-boot-check"
```

`2026-09-14` contains the aborted partial export (0.96 GiB folder and a 110 MiB `.world`).
