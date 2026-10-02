# The legendary catalogue, re-opened: what needs no altar, and where the eight really stand

**Answered for:** Cobblemon 1.8.0 + COBBLEVERSE-DP-v31, LumyMon 0.6.6, LegendaryMonuments
(`version: "Cobbleverse"`, MPL-2.0), 2026-10-02. Companion to
`docs/research/notes/cobbleverse-legendary-structures.md` (the inventory) and
`docs/research/notes/lumymon-altars.md` (the altars).

## Source, and what was not read

- **Read from the CLIENT profile, not the server**: `%APPDATA%/ModrinthApp/profiles/COBBLEVERSE - Pokemon
  Adventure [Cobblemon]/` (`datapacks/COBBLEVERSE-DP-v31.zip`, `mods/LumyMon-0.6.6.jar`,
  `mods/LegendaryMonuments-Cobbleverse.jar`). Same DP and LumyMon versions as the server's, per
  `lumymon-altars.md`. The server was running and its coordination lock held by another session, so
  its copies were not opened. **That the server's LegendaryMonuments jar is byte-identical to the
  client's is ASSUMED.**
- Python `zipfile` and `tools/nbt.py` only: template palettes, block positions and block-entity NBT;
  for jars, `fabric.mod.json`, data JSON, lang, and printable strings of class constant pools. No
  bytecode was decompiled. Numeric constants in bytecode (for example how many stakes a shrine wants)
  were NOT read.
- Nothing here was placed, booted or clicked.

## 1. The Necrozma towers need no altar (VERIFIED, template NBT)

`cobbleverse:dawn_tower` and `cobbleverse:dusk_tower` are the same 46x90x45 build with one line
different. Template-relative positions:

| Block | Position | What it does |
|---|---|---|
| `light_weighted_pressure_plate` | [23, 2, 22] | powers the impulse command block at [23, 0, 22] |
| `command_block` (impulse) + chain | [23, 0, 22], [24, 0, 22] | `effect give @p[distance=..5] levitation 15 5`, then `resistance 30 10`: **the only way up** (the template has one stair and 34 slabs, no ladder) |
| `polished_blackstone_pressure_plate` | [19, 79, 22] | at the summit; powers the impulse block two below it |
| `command_block` (impulse) | [19, 77, 22] | `effect give @p slow_falling 20 1`, and starts the chain westward |
| chain, `auto:1`, unconditional | [18..16, 77, 22] | empty |
| chain | [15, 77, 22] | `effect give @a[distance=..25] blindness 3 2` |
| chain | [14, 77, 22] | `playsound ... lightning_bolt.thunder` |
| chain | [13, 77, 22] | `effect give @a[distance=..10] slowness 5 10` |
| chain | [12, 77, 22] | `pokespawnat ~ ~2 ~ necrozma prism_fusion=dawn level=80` (dusk: `prism_fusion=dusk`), all six IVs 30, four fixed moves |
| chain | [11, 77, 22] | `fill ~5 ~5 ~5 ~-5 ~-5 ~-5 deepslate_bricks replace chain_command_block`: **the chain destroys itself** |

So each tower is **one Necrozma, once, for the whole server**, triggered by standing on a plate.
No item, no altar, no LumyMon block. It needs `enable-command-block=true`, which the server does not
have (`server.properties:10`, per `lumymon-altars.md` section 3). Level 80 is above every cap until
the Champion falls (60 through the Elite Four, 62 before Blue, 100 after him:
`docs/mechanics/LEAGUE_LEVEL_CAP.md`), so a pre-Champion player on that plate would burn the one
spawn on a Pokemon nobody can catch. **Placed as shipped it is a trap; it needs a gate.**

## 2. Moltres is scenery wherever it stands (VERIFIED, jar strings and recipe/loot scan)

`MoltresAltar` takes `EMBER_FEATHER` and spawns Moltres 50-60. The Nether template's two barrels hold
blaze powder, fire gems and glass panes. **No recipe or loot table in any client mod jar or datapack
produces `ember_feather`, `glacier_feather` or `thunder_feather`** (0 producers). This extends the
2026-10-02 finding for Articuno and Zapdos to the third bird: a Moltres altar in the Nether is as dead
as one anywhere else.

## 3. The Ruinous four are the one case the Nether serves (VERIFIED, jar strings)

- `github/jorgaomc/world/StakePlacement` "Registered stake placements for all nether biomes": a
  worldgen FEATURE adds `*_stake` blocks to every biome in `#minecraft:is_nether`.
- `StakeBlock` and `ShrineBlock` both call `getPlayerProgress`/`setPlayerProgress` per
  `ShrineTracker$ShrineType` (FIRESCOURGE, GRASSWITHER, ICEREND, GROUNDBLIGHT); `ShrineTracker` keeps
  `worldPlayerProgress` with a `PROGRESS_MAX` in a JSON file under `minecraft-shrine-data` in the
  server's run directory, keyed on a world id built from level name, seed and spawn. Shrines have
  `spawnPokemon`. The `*_seal` items are "Used to locate the ... Shrine".
- INFERRED: a player collects stakes of one colour across the Nether, then the matching shrine spawns
  its Pokemon. The count and the levels are bytecode constants and were not read.

**Consequence:** the stakes exist only because the Nether generates normally. A shrine pasted into
our exported overworld would have no stakes anywhere. **Leave all four in the Nether.** Note also
that progress lives OUTSIDE the world save, keyed partly on the spawn point, so a re-export that moves
spawn may reset it (INFERRED).

## 4. Eternatus is unreachable twice over (VERIFIED, jar data and strings)

- `EternatusCocoonBlockEntity` consumes `GALAR_PARTICLE` from the player: "/500 galar particles
  consumed", "The cocoon is ready to break", then `spawnEternatus`.
- Galar Particles come from `galar_particle_ore` / `deepslate_galar_particle_ore`, added by
  `ModOreGeneration` with `BiomeSelectors.foundInOverworld`: **overworld ore only.** Our overworld is
  a WorldPainter export that never runs ore features (`docs/world-building/WORLDGEN_FEATURES.md`), so
  no particle ore exists anywhere in our world.
- The cocoon template itself carries 5 `galar_particle_block` (9 particles each, by the jar's own
  recipe): 45 of the 500.
- And the cocoon generates in the End, which no player can reach (section 5).

## 5. The End cannot be entered (repository, re-checked 2026-10-02)

`docs/world-building/DIMENSIONS_AND_BORDERS.md` section 4: no stronghold can generate inside the
border, so eyes of ender find nothing, and "the fix is a hand-built portal room". **No portal room is
authored anywhere in `data/` or `tools/`** (grep for `portal_room` and `end_portal`: no hits outside
`data/structures.json` classification). So three of the "eight left where they generate" — both
Necrozma towers and Eternatus — are in a dimension the campaign has no door to.

## 6. A repository claim that does not survive the read: "our progression never grants defeat_champion_blue"

`data/adopted_legendary_sites.json` and `docs/STATE.md` say Mew's door is inert "by construction"
because our progression never grants `cobbleverse:trainer/kanto/defeat_champion_blue`. But:

- that advancement is granted by `rctmod:defeat_count` on `trainer_ids: ["kanto_champion_blue"]`
  (VERIFIED, `lumymon-altars.md` section 2);
- **our Champion IS `kanto_champion_blue`**: the League template's own spawner, and the id
  `data/progression.json` `champion_cleared` keys on (VERIFIED, `data/league_trainers.json:125`);
- `data/progression.json` `upstream_neutralised.why` empties `cobbleverse:blue_champion_defeated`
  and its siblings **precisely so "the advancement grants cleanly"**.

So the advancement very probably IS granted when a player beats our Blue (INFERRED from the three;
not seen in game). Mew's door is not inert by construction: it is inert only because command blocks
are disabled. If they are enabled, the temple opens for Champions exactly as Cobbleverse intended.

## 7. Mew's temple, read (VERIFIED, template NBT)

A 5x4 wall of `chiseled_stone_bricks` at template z26, x16-20, y2-5 seals the sanctum; the stone
pressure plate outside it at [18, 2, 27] drives the command blocks under it ([18, 0, 24..27]), which
clear that wall for a player with `defeat_champion_blue`. The `mew_shrine` stands inside at
[18, 2, 18]. Four `gilded_chest` at y2 and four `gimmighoul_chest` at y15 are elsewhere in the
temple. The Origin Fossil is `ancient_dna` + 5 fossils + an ancient origin ball; `ancient_dna`'s other
source, `kanto_giovanni`'s first-defeat loot, is EMPTIED by `data/progression.json`
`upstream_neutralised`, so the temple's own container is now its only source (ASSUMED that it is
reachable; its position was not read).

## Candidate experiments

1. **Does beating our Blue grant `cobbleverse:trainer/kanto/defeat_champion_blue`?** One
   `advancement test`-style check (`execute if entity @p[advancements={...=true}]`) after a Champion
   win on staging.
2. **The towers' gate, once placed** (see `data/adopted_legendary_sites.json`): a non-Champion on
   the summit plate gets the message and nothing else, the chain survives; a Champion gets Necrozma
   and the chain fills itself.
3. **How many stakes, and what level** the Ruinous shrines want: one Nether trip with a stake.
