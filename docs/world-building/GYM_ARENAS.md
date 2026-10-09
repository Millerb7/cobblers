# Gym arenas

The owner, 2026-10-08: leaders fight in cramped rooms. It should feel like a stage or a throne: a long
approach, the leader raised at the far end, the arena floor between. It matters mechanically too: battles
happen in the world, so large Pokemon clip into the walls of a cramped room. Fixed lots, so carve below: the
building is the entrance and the arena opens beneath it, our own authored space. Each reads as its leader's by
civic role, none like another, and is big enough for the largest Pokemon on that leader's team, measured. The
juniors and the puzzle route still lead to it. Each leader's spawner moves into its arena.

Tools: `tools/pokemon_sizes.py` (the sizes, from the jars), `tools/gym_arenas.py` (survey, check, build,
probes). Data: `data/gym_arena_sizes.json` (generated), `data/gym_arenas/<gym>.json` (one per gym, authored),
`data/gym_arenas/survey.json` (generated), `data/gym_arenas/SCHEMA.md` (the record format). Reapply step
**R16GA**, after R16G.

Status: gym 1 (Brock) authored and passing every offline check. Nothing here has been built in a world.

## The premise about the buildings

The brief called the buildings "Cobbleverse templates we cannot redistribute modified". That is true of one of
the eight. Seven are our own authored halls (`data/gym_buildings/gym1,3,4,5,6,7,8.json`, `tools/gym_buildings.py`,
step R16G), which replaced the COBBLEVERSE donor shells (R16F takes those down). Only Misty's gym 2 is still the
donor template `cobbleverse:misty`, with a carved interior below it (`data/gym_interiors.json` gym2, its
`dig` [1598, 84, 2861, 1626, 106, 2881] standing). The arenas carve below either way; the difference is only
where an arena's descent may start (inside our building's own masonry, or through the template, which we
cannot modify in the repository but can cut through in the world as the gym 2 dig already does).

## How big a Pokemon is in the world

Read from the 1.8.0 jar with `javap -c`, not assumed:

- `com.cobblemon.mod.common.entity.pokemon.PokemonEntity.getDimensions` (obfuscated `method_18377`):
  `hitbox.scale(form.baseScale * pokemon.getEffectiveScale())`, then `.scale(LivingEntity.getScale())` (the
  vanilla `generic.scale` attribute, 1.0 unless something sets it). A Transform/Illusion mock uses its own scale.
- `com.cobblemon.mod.common.pokemon.Pokemon.getEffectiveScale`: under `babyPokemonLevelDuration` (config: 9) a
  ramp from `babyPokemonSizeMultiplier` (0.9) to 1; an alpha uses the alpha multiplier; otherwise
  `scaleModifier`, default 1.0. Every leader's Pokemon is level 18 or more and none is alpha or carries a
  scale, so the factor is 1.0 (`tools/pokemon_sizes.py check_levels` fails if that changes).
- A species file with no `hitbox` takes the constructor's default (`Species.<init>`: 1 x 1, baseScale 1):
  Pawmot is one.
- **The rendered model is not the hitbox**, and a wall clips the model. Onix's hitbox is 2 x 4; its model, in
  its bind pose, runs 4.81 forward and 10.56 back from its origin. So each member's bedrock model
  (`assets/cobblemon/bedrock/pokemon/models`, through the species resolver) is measured too, in its bind pose,
  times the same scale. That figure is approximate: animations move the bones. Vikavolt and Pawmot have no model
  in any server archive (a client resource pack draws them); for them the hitbox stands alone.
- No leader's team names an aspect, a form, a Mega Stone, a Z-crystal or any item Mega Showdown adds (its
  339 item ids are the test). **Dynamax**: Mega Showdown's config has `dynamax: true`, `dynamaxScaleFactor 4.0`,
  `dynamaxAnywhere: false`, `powerSpotRange 32`: a Pokemon Dynamaxes only within 32 blocks of a power spot. No
  arena is sized for it; keep power spots more than 32 blocks from every arena.
- Every source is read: the Cobblemon jar, zamega and Mega Showdown (species and species_additions), and the
  COBBLEVERSE datapack (a world pack, which overrides a mod's file). Between two mod jars the load order is the
  loader's, so the design figure is the largest over every candidate (Vikavolt: Cobblemon's file and
  COBBLEVERSE's addition, 2.0 x 2.5 at 0.75).

### The table (`python tools/pokemon_sizes.py --markdown`, 2026-10-08, every tier: team, normal, challenge, rct)

| Gym | Leader | Widest hitbox (w x scale) | Tallest hitbox (h x scale) | Largest model, bind pose (extent / top) | Clear radius (sweep) | Clear height | Members over all tiers |
|---|---|---|---|---|---|---|---|
| 1 | Brock | onix 2.00 | onix 4.00 | onix 15.4 / onix 2.8 | onix 10.56 | onix 4.00 | bonsly, cranidos, dwebble, geodude, lileep, onix |
| 2 | Misty | pelipper 0.96 | floatzel 1.53 | pelipper 3.6 / floatzel 1.5 | pelipper 1.85 | floatzel 1.53 | barboach, floatzel, goldeen, horsea, lombre, pelipper, starmie |
| 3 | Lt. Surge | vikavolt 1.50 | vikavolt 1.88 | raichu 3.3 / electabuzz 2.0 | raichu 2.93 | electabuzz 1.96 | boltund, electabuzz, magneton, pawmot, raichu, vikavolt |
| 4 | Erika | tangrowth 1.80 | tangrowth 2.40 | tangrowth 7.1 / tangrowth 2.7 | victreebel 5.28 | tangrowth 2.72 | bellossom, cradily, roserade, tangrowth, victreebel, vileplume |
| 5 | Koga | drapion 2.02 | drapion 2.25 | crobat 6.1 / toxtricity 2.7 | drapion 3.13 | toxtricity 2.72 | crobat, dragalge, drapion, toxtricity, venomoth, weezing |
| 6 | Sabrina | exeggutor 1.53 | hatterene 2.80 | exeggutor 3.8 / hatterene 6.1 | slowbro 2.09 | hatterene 6.13 | alakazam, bronzong, exeggutor, hatterene, reuniclus, slowbro |
| 7 | Blaine | magmortar 1.53 | charizard 2.65 | magmortar 5.3 / magmortar 3.7 | charizard 4.09 | magmortar 3.67 | arcanine, charizard, magcargo, magmortar, torkoal, typhlosion |
| 8 | Giovanni | hippowdon 2.20 | rhyperior 2.75 | rhyperior 6.9 / rhyperior 3.8 | rhyperior 3.45 | rhyperior 3.78 | hippowdon, krookodile, mudsdale, nidoqueen, persian, rhyperior |

*Clear radius* is the farthest any model corner lies from the entity's origin, horizontally: the circle a
Pokemon sweeps turning on the spot, never less than its hitbox's half-diagonal. *Clear height* is the larger of
the hitbox height and the model's top. Every figure carries its archive and path in
`data/gym_arena_sizes.json`. Finding, not mine to fix: `data/gym_trainers.json` says Brock has 4 members; his
Normal team in `data/trainers.json` has 3 and his Challenge team 6.

## Where the Pokemon go: Cobblemon Battle Positions

Rung: a **Cobbleverse dependency** already installed (`cobblemon-battle-positions-1.1.3`, server and client), so
no new machinery. The donor gyms carry its blocks (`cobbleverse:brock` has three: trainer Pokemon, player
Pokemon and player stand, in a line with the spawner); our seven buildings dropped them when they replaced the
shells. What it does, read from the jar:

- At a PvN or PvP battle start, `PositionBlockFinder.findPositionBlocks(level, anchorPlayer.blockPos())` looks for
  the nearest of each of four blocks within `horizontalSearchRadius` (16) on each horizontal axis and
  `verticalSearchRange` (3) up or down of **the challenger's feet**
  (`base-pack/cobbleverse/config/cobblemonbattlepositions.json`, read by the tool, not restated).
- The set is valid only if **both Pokemon blocks** are found (`PositionBlockSet.isValid`); then each side's
  Pokemon is sent to its block's centre at `y + spawnHeightOffset` (2.0) (`BattlePositionStore.
  storeBattlePositions`). The two stand blocks are optional: one not found skips that teleport ("Trainer stand
  block not found; opponent teleport skipped", which the battle-freeze note saw in a donor gym that has none).
- The blocks are full cubes (`cube_all`). Set one course under the floor's top, `y + 2.0` puts the Pokemon's
  feet exactly on the floor and hides the block.

Without them Cobblemon places each Pokemon near its trainer, wherever that is; with them the stage is
deterministic.

## Design rules (each derived; `tools/gym_arenas.py check` enforces them)

1. **Cover, COVER = 2.** Two natural blocks between the arena's top and the lowest thing written above it (the
   ground; the lot's pad, below which the prep never writes; the building's lowest course). One is the cover;
   the second because `round(heightmap)` matches an export at 99.85% of columns and the rest are one block LOW
   (`tools/ground.py`): with one, the shell would be open sky there.
2. **Shell.** No open cell of the arena may touch unwritten ground. The rock is never relied on: a natural cave,
   or a refilled works, could open into it. Inside the building's bounds the building's own model governs.
3. **Clear disc.** No block within the leader's clear radius of either Pokemon block, from the floor to
   `floor_y + ceil(clear height) + 1`. The player's Pokemon is assumed as large as the leader's largest (the
   player's team is unbounded; an assumption, not a measurement).
4. **Clear height** `ceil(clear height) + 1`: the `+1` is the send-out's own slack, an author who puts the block
   IN the floor lands the Pokemon one above it until it falls.
5. **Hitbox gap.** The two Pokemon blocks farther apart than the widest hitbox, or the two overlap.
6. **Dais height 2 to 5.** At least 2: a player steps up 0.6 and jumps 1.25, so a two-course face cannot be
   climbed and the challenger stays on the floor. At most `verticalSearchRange + 2` = 5: the trainer stand, one
   under the dais top, must be within 3 of a floor player's feet.
7. **The search.** Both Pokemon blocks within Battle Positions' search from every cell a battle can start from:
   every cell a player can walk to within `forceBattleMaxDistance` (16, `modpack/config/rctmod-server.toml`) of
   the leader **with a line of sight** (eye to eye through open cells), which is when rctmod starts a battle on
   sight and the only way a player can also interact. The stands' coverage is reported.
8. **Approach.** The arena's first floor cell farther from the leader than `forceBattleMaxDistance + 1`: the
   player stands in the hall before the leader can call the fight.
9. **Light.** No standable cell at block light 0: since 1.18 vanilla monsters spawn only there. MobsBeGone removes
   them here anyway; how bright a hall looks is reported (median, cells under 8), not gated.
10. **Spawn-free.** The arena's x/z inside its gym's spawn-free zone, on the 8-block grid.
11. **The seat.** One spawner, flush in the dais top, powered from below, two open cells over it
    (`tools/npc_spot_sweep.py spawner_problem`). The build never writes the seat or its redstone, so a re-run
    never takes the spawner away.

A threshold not listed here (the dais depth, the hall's height, the approach's length beyond rule 8) is a
design choice per arena, and is said so in its record.

## The survey (`python tools/gym_arenas.py survey --write`; numbers from `data/gym_arenas/survey.json`)

Ground from `tools/ground.py` (rounded heightmap) over the lot plus 32 blocks. "Shell top max" is the highest
the arena's top course may be with COVER over it, over the lot, over the spawn-free zone, and over the lot plus
32. "Floor max" is that minus a 2-course vault and the team's clear height + 1. "Descent" is from where the
puzzle route ends (one over the building's spawner) to a floor at that maximum; a deeper floor makes it longer.

| Gym | Route ends (spawner now) | Lot, level | Building's lowest course | Zone (size) | Ground, window min/median/max | Water | Shell top max lot / zone / window | Floor max | Descent | Carved space in data |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 Brock | (1832, 155, 3696) gallery | 1806..1845 x 3656..3703, 141 | 141 | 1800..1847 x 3656..3711 (48x56) | 138 / 141 / 142 | none | 138 / 138 / 136 | 131 | 24 | old works [1812,114,3667..1838,139,3703], filled back by R16F |
| 2 Misty | (1605, 132, 2874) template hall | 1592..1631 x 2858..2891, none (template on 26 courses of its own rock) | 107 (template box) | 1592..1631 x 2856..2895 (40x40) | 88 / 107 / 109 | 2,287 lake columns, level up to 103 | 102 / 101 / 86 | 96 | 36 | the gym 2 well [1598,84,2861..1626,106,2881], **carved and standing**: an arena must join it or keep clear |
| 3 Surge | (1747, 190, 1414) | 1722..1752 x 1388..1432, 174 (cut into a flank to 276) | 174 | 1720..1759 x 1384..1439 (40x56) | 173 / 186 / 276 | none | 171 / 171 / 171 | 166 | 24 | old works [1732,150,1400..1750,172,1427], filled back |
| 4 Erika | (4308, 110, 1480) | 4288..4332 x 1470..1512, 110 | 109 | 4288..4335 x 1472..1519 (48x48) | 107 / 110 / 111 | none | 106 / 106 / 105 | 100 | 10 | old works [4296,94,1478..4324,106,1506], filled back |
| 5 Koga | (4594, 131, 2487) watch floor | 4574..4606 x 2463..2495, 116 | 112 (the sump) | 4568..4607 x 2456..2495 (40x40) | 114 / 116 / 118 | none | 109 / 109 / 109 | 103 | 28 | old works [4572,94,2466..4605,111,2494], filled back |
| 6 Sabrina | (6196, 111, 3312) lens chamber | 6180..6212 x 3302..3334, 97 | 92 | 6176..6215 x 3304..3335 (40x32) | 94 / 96 / 98 | none | 89 / 89 / 89 | 79 | 32 | none |
| 7 Blaine | (6178, 106, 5001) assay vault | 6154..6186 x 4980..5010, 106 | 103 | 6152..6191 x 4976..5015 (40x40) | 105 / 106 / 111 | none | 100 / 100 / 100 | 93 | 13 | old works [6156,70,4980..6182,102,5012], filled back |
| 8 Giovanni | (3565, 120, 6416) | 3556..3588 x 6400..6432, 112 | 104 | 3552..3591 x 6400..6431 (40x32) | 107 / 111 / 113 | none | 101 / 101 / 101 | 94 | 26 | none |

What sizes each arena, from rules 3 and 7: the clear floor across is at least `2 x clear radius` (Brock 21.1,
Erika 10.6, Blaine 8.2, Giovanni 6.9, Koga 6.3, Surge 5.9, Sabrina 4.2, Misty 3.7); the leader's Pokemon block
at least the clear radius from the dais face; the challenger's Pokemon block within 16 of the dais foot. Every
zone but Brock's is 40 wide or less on one side and three are 32 deep: an arena longer than its zone extends the
zone in `data/spawn_suppression.json` on the 8-block grid (rule 10 checks it). Nothing in `data/` records a mine,
cave or tunnel under any of the eight windows except the works above (a sweep of every six-number box in `data/`,
not a list of known places); the world can still hold a natural cave, which is what the shell is for.

## Gym 1: Brock, The Setting-Out Floor

The masons' floor where full-size work is drawn before a stone is cut, under the Stoneworks Hall: a vaulted
undercroft of finished ashlar, rough cobble at the foot of every wall and dressed stone above, a tuff string
course, two colonnades of polished andesite carrying ribs, calcite setting-out lines down the floor. At the
north end a stage of dressed stone wall to wall, three courses high, a trilithon (the masons' proof piece)
behind Brock, stacked blocks and spruce sheer-legs either side.

| | |
|---|---|
| Shell | x1808..1844, y120..138, z3658..3705 (37 x 19 x 48), two courses all round |
| Floor | y122 (stand at y123), clear 1810..1842 x 3660..3703, 33 x 44, air to y136 (14 high) |
| Stage | x1810..1842, z3660..3664, top y125 (3 over the floor), face at z3664 |
| Brock's seat | (1826, 125, 3662), redstone at y124; trainer stand (1826, 124, 3663) |
| Pokemon | Brock's (1826, 121, 3676), 11.5 from the stage face (clear radius 10.56); the challenger's (1826, 121, 3681), 5 apart; challenger stands (1826, 121, 3684) |
| Descent | a newel stair in the gallery's west end, ring x1811..1814 x z3695..3698: its first tread is level with the gallery floor (y155), its last a landing in the arena floor (y122), 33 levels in four turns and one step, stone brick stairs on the straights and full-block landings at the corners so it is walked up without a jump; out of the turret door (1815, 123..125, 3696..3697) onto (1816, 123, 3696) |
| Approach | 35.6 from the turret door to Brock |
| Written | 38,721 cells, 277 commands in `cobblers:gym_arenas/gym1` (the move and sweep apart) |
| Checks | cover slack 0 (y138 under a natural top at 140); 241 cells a battle can start from, both Pokemon blocks and the trainer stand found from all 241, the player stand from 212; block light min 1, median 8 |

Why each number is what it is: the shell's top course is the highest COVER allows under the pad (lot level 141,
natural top 140). Onix's tail sweeps 10.56, so Brock's Pokemon stands 11.5 from the stage face and 12.5 from
each colonnade. The challenger's Pokemon must be found from the foot of the stage (16 across), so it is 5 from
Brock's (z3681 = stage face 3665 + 16). The stage runs wall to wall so that no aisle reaches up beside it,
which would put a battle-start cell 21 from the challenger's block. The player stand is 3 behind its Pokemon,
as the donors set it; from 29 cells by the stage it is out of reach and the challenger is simply not teleported.

The descent opens the gallery floor only where its first treads need headroom (four cells along the ring's east
and south sides): nowhere can a player step off the gallery into more than a three-block drop (no damage). The
stair and its walls are built only below the building (`through_building` [1810, 139, 3694, 1815, 158, 3699]);
above y140 the building's own masonry is the wall (the building's model: stone bricks under the gallery from
y142 to y154). The walk the check runs is generous (it jumps one), so "walked up without a jump" is proved by
the tread heights (each step up is a stair's half-block front or level), not by the walk.

## The seat move and the one-leader swap

**The move, for every gym.** The building keeps placing its spawner in the hall: R16G and its audits are
unchanged. R16GA then, per arena: builds the arena; runs `<gym>_seat`, which sets the spawner in the dais and
puts the old cell back to its floor (polished andesite over stone bricks for Brock, the building model's own
neighbours) only once the new one stands and never with a player within reach (17) of either seat, and sets a
spawner at the seat if neither cell has one; sweeps the leader's two ids out of the building's bounds
(`tools/chunk_look.py sweep`, never one in a battle); reads it all back. R16G also runs each `<gym>_seat`
straight after the buildings, because a building puts its spawner back in the hall every run and `--only R16G`
would otherwise leave the leader two spawners; the move tests that its arena stands (its trainer Pokemon block),
so on a world without the arena it does nothing.

**One source of the seat.** `data/gym_arenas/<gym>.json leader.seat`, read through
`tools/gym_arenas.py leader_seats()`; before an arena exists, the building's `leader.spawner` or Misty's
`expect_spawner_at`, as before.

**Brock (in `single_leader.rollout`).** His one spawner is moved; the cycle's swap drives whatever
`challenge_mode.normal_seat` returns, now the arena seat. R17L's retire of his old second spawner
(1830, 155, 3696) still works: it is measured from the building's model, which still has the hall spawner; its
player guard widens to reach + the 45.5 between the old second spawner and the new seat; its keep-the-nearest
pass now looks round the arena seat. `single_leader_verify` checks the spawner at the arena seat. Order: R16GA
(after R16G) runs before R17L. One consequence, and it is the safe side: Brock now stands 45.5 from his retired
cell, outside the retire's kill radius (24), so no R17L kill can reach the one leader at all; the audit mutation
that proved the keep (`retire_keeps_nobody`) has no leader to bite on and xfails while no rollout boss stands
inside that radius (read from the data: it bites again when the rollout grows to a seat that did not move).
**Good: the move is built.**

**The other seven (not in the rollout).** Each keeps a SECOND, Challenge spawner, set by the trainers cycle at
`data/challenge_mode.json bosses.<id>.spawner.at` (two from the hall seat) whenever a player is within 48. When
its arena is authored, that position must move into the arena in the same change, and the old second spawner,
which the cycle stops setting but never removes, must be taken out once: the record's `challenge_spawner.old_at`
and `old_restore`, which `<gym>_seat` removes under the same guard. `tools/gym_arenas.py check` refuses an arena
for a non-rollout leader without both. Misty (gym 2) also needs `old_seat_restore`, from her template.

**Every consumer of a leader's position.** Changed to read `leader_seats()`: `tools/challenge_mode.py
normal_seat` (the swap, the retire's keep, `single_leader_verify`, and through it `tools/player_guide_battles.py`),
`tools/route_trainers.py leader_cycle_lines` (the rematch hold-off and its notice), `tools/trainer_world_audit.py
spawners`, `tools/nuzlocke_map.py gyms` (and through it `tools/challenge_guide.py`). Unchanged, on purpose:
`tools/gym_buildings.py` and `tools/gym_buildings_independent.py` (the building as R16G writes it, spawner
included); `tools/gym_trainers.py` and `tools/gym_trainers_audit.py` (they prove the juniors must be passed to
reach the hall seat, which is the gallery where the descent starts, so the proof still holds: reaching it is
reaching the arena); `tools/challenge_mode.py restore_blocks` (the second spawner's floor, from the building);
`tools/new_player_walk.py` (walks the hall to the hall seat; it does not walk the arena); `tools/npc_spot_sweep.py`
(replays the apply in order, so it sees R16GA's spawner and reports the hall one as `gone`). Changed in its
INPUT only: `tools/challenge_mode_audit.py` (an independent audit) replays each building's emitted text, and now
also each arena's emitted seat move after it, read as the world it leaves with nobody near, so its Normal spawner
is where the apply leaves it; its checks are untouched. `tests/test_one_leader_swap.py` reads Brock's seat
through `leader_seats()` instead of the building record; `tests/test_one_leader_retire_independent.py` counts a
leader moved into an arena as moved, as it already counted Lance's `single_leader.move`;
`tests/test_challenge_mode_audit.py` xfails `retire_keeps_nobody` as above. All are another agent's; their owners
should re-read the change. The badge flags and the rematch guard key on `kanto_brock` wherever he stands, so neither moves.

## Not verified

- Nothing has been built in a world. The arena, the move, the sweep and the read-back are offline only.
- That Battle Positions sends Brock's Onix to its block in our arena (the donors' blocks were seen only as a
  warning in a log). That a battle on sight starts at 16 from a leader three courses up. The bind-pose model
  sweep as the real clearance (animations move the bones).
- That a flying Pokemon in battle stays within the clear height.
- `tools/challenge_mode_audit.py` against the moved seat (see above).
