# Victory Road's regions — a proposal

**Status:** design only, nothing built, no roster changed. Written 2026-09-23 at the owner's direction after a
flight found the road reading as "a path with a few spherical rooms — pleasant, but not a place a player earned".

Everything numbered here is measured from `data/victory_road.json`, the canonical heightmap through
`tools/ground.py`, `data/spawn_blocks.json`, and the Cobblemon 1.8 jar. Nothing is estimated.

---

## 1. Why these regions, and why here

**The cap at eight badges is 65.** `rctmod-server.toml` computes it from the strongest Pokémon of the *next*
required trainer plus `relativeLevelCap` 5; the next required trainer after Giovanni is Lorelei at 60. (At the
offset of 0 that `GYM_SUFFICIENCY_AUDIT.md` recommends and `data/trainers.json`'s own contract assumes, it is 60.)

**Of the forty strongest fully-evolved non-legendary species the jar implements, exactly one — Gyarados — is
catchable anywhere in the campaign before gym 8.** The others are unplaced:

> Slaking 670 · Salamence, Metagross, Hydreigon, Dragonite, Dragapult, Baxcalibur, Archaludon 600 · Archeops 567
> · Arcanine, Florges 552 · Ursaluna, Kingambit, Gholdengo 550 · Milotic, Kingdra, Hydrapple, Haxorus,
> Electivire, Blissey 540 · Tangrowth, Swampert, Rhyperior, Porygon-Z, Noivern, Magnezone, Lapras, Duraludon,
> Annihilape 535

That is the argument. Victory Road is the last place in the campaign to put any of them, and a player arriving
at 65 with a team built from Route 1's Bidoof has nowhere else to have found better. **The regions exist to be
the endgame's catching ground.** Rewards and atmosphere are the reasons to walk in; the roster is the reason it
matters.

## 2. The shape: forks, not the road

The spine stays exactly as built — 666 blocks, 9×7 corridors, five caverns, the stair, the ramp onto the apron.
**Nothing below touches it.** Every region hangs off a fork in a connecting corridor, so a player who wants only
to reach the League walks past five side passages and never enters one.

This is the braiding originally asked for, arriving as content rather than as maze geometry: the branching is
optional depth, and the cost of ignoring it is only the things you did not catch.

Each fork should be **visible but not inviting** — a corridor mouth with its own lintel material, dark, with no
light placed in the first 12 blocks, so a player sees an opening and must decide.

## 3. The five regions

Sites are measured. "Cover" is the least rock between the room's dome and the canonical ground; the road's own
rule is a minimum of 4.

| # | Region | Site | Floor | Off spine | Cover | Character |
|---|---|---|---|---|---|---|
| 1 | **The Drowned Gallery** | (3470, 2984) | y8 | 78 | 62 | A flooded chamber: the Rift's floor water found a fault and came down. A still black lake in a pillared hall, waist-deep at the edges and 12 down in the middle. |
| 2 | **The Slagworks** | (3624, 2906) | y8 | 83 | 59 | The lava cavern. A magma shelf and two lava falls, the only lit place on the road, and the only place the floor hurts. |
| 3 | **The Raw Tear** | (3470, 2690) | y40 | 77 | 27 | Where the Rift did not heal. Distortion material floor to ceiling, no natural stone at all, the tear's own light and no other. |
| 4 | **The Bloom** | (3452, 2790) | y30 | 92 | 44 | Where the water and the dark meet: a fungal gallery grown on the drowned gallery's seepage. Soft, wrong, and the only green underground. |
| 5 | **The Abandoned Cut** | (3672, 2690) | y44 | 118 | 34 | The Rift dig camp's deepest gallery, collapsed and left. Rails, props, spoil heaps and whatever the diggers did not carry out. |

Five rather than four because each carries a distinct type family, and four would force two of them together.
**The Abandoned Cut is the one to drop** if five is too many: it is the furthest off the spine and the only one
whose character is human rather than geological.

## 4. The rosters, and the mechanism that makes them nearly free

**The terrain is already a spawn mechanism.** `data/spawn_blocks.json` records every block a loaded spawn
condition names, and the relevant ones are `neededNearbyBlocks` — the pack's own pools require them nearby:

| Block | What the pack's own pools will spawn beside it |
|---|---|
| `minecraft:lava` | magby, magmar, magmortar, slugma, magcargo, salandit, salazzle |
| `minecraft:magma_block` | gible, gabite, **garchomp**, magby, magmar, magmortar |
| `minecraft:water` | 43 species, including **dragonite, goodra, greninja, inteleon, politoed, slowking**, the poliwag and slowpoke lines, wooper/quagsire/clodsire, tympole/palpitoad/seismitoad |

So placing the lava gets a Fire roster and placing the water gets a Water one, from pools that are already live —
`data/spawn_suppression.json` retains upstream defaults in unauthored caves, and the suppression override pack is
not installed. **Magma blocks in the Slagworks would put Garchomp, a 600-BST pseudo-legendary, on Victory Road
for the cost of placing a block.**

**But the levels are wrong, and that is the whole problem.** Upstream pools spawn at their own bands — Gengar
36-50, gible 24-30 — against a player at 65. Terrain alone gives the right species at a trivial level.

**Therefore each region needs a Habitat Block with `replace_spawns`**, which is the only mechanism that sets both
the roster and the band. That costs three things, all known:

1. `data/habitat_blocks.json` places **no blocks at all** today, so this is the campaign's first use.
2. The block's influence is a **sphere**, and overlapping `ReplaceSpawns` blocks spawn nothing (EXP-021). Five
   regions 77-118 blocks off a spine are far enough apart that this is easy here — it is the *road* that is hard
   to tile, not the regions.
3. `tools/compile_spawns.py` **drops the authored `conditions` object for habitat entries**, so a darkness gate
   (`maxLight`) needs a generator change, not a roster change.

Proposed rosters, by region, drawing on the unplaced strong list. **These are candidates, not a decision:**

| Region | Anchor | Supporting | Why it belongs |
|---|---|---|---|
| Drowned Gallery | **Milotic** 540 or **Lapras** 535 | Politoed, Slowking, Quagsire, Wimpod | Still deep water, nothing that needs sun |
| Slagworks | **Garchomp** 600 (magma) or **Magmortar** 540 | Magcargo, Salazzle, Torkoal | The pack already puts Gible beside magma; we set the level |
| Raw Tear | **Dragapult** 600 or **Hydreigon** 600 | Duraludon, Noivern, Sableye | The Rift's own material should carry the Rift's own Dragons |
| Bloom | **Tangrowth** 535 or **Hydrapple** 540 | Foongus/Amoonguss, Shiinotic, Ariados | Damp, dark, grown rather than built |
| Abandoned Cut | **Metagross** 600 or **Archaludon** 600 | Gholdengo, Klinklang, Probopass | Steel and worked stone, left behind |

**One roster per region, one anchor each**, so no region is strictly better than another and a player chooses by
type need rather than by power. Level band **60-65** across all five, which is at and just under the cap.

**On above-cap spawns:** the owner asked whether some regions should carry things above cap that mostly refuse.
The honest answer is *not yet* — `fightorflight`'s `minimum_attack_unprovoked_level` is 25 and nothing in the
config gates catching by level, so "mostly refuses" is not a configured behaviour anyone has found. It is a real
design idea and it needs the over-cap research before it can be costed. Recorded, not proposed.

## 5. Rewards

Per **ADR-002**: per-player grants keyed to a vanilla advancement, containers as scenery with their loot
stripped. A re-export replaces region files but `tools/carry_players.py` carries advancements and player data as
required categories, so the grant survives what the world does not.

**What the pack actually has to give**, from `docs/research/notes/reward-item-inventory.md`:

| Region | The find worth the detour | Why this one |
|---|---|---|
| Drowned Gallery | **Water Stone** + a `net_ball` cache | See §7: this is the only Water Stone in the game |
| Slagworks | **Fire Stone**, and one **TM** no Pokémon learns naturally | Cobblemon 1.8's own ruin chests use "one named TM per site"; this is the mod's grammar, not an invention |
| Raw Tear | A **species-exclusive Z-crystal** or a Mega Stone | Unique, visibly special, useless to anyone who did not build for it |
| Bloom | **Leaf Stone**, **Sun Stone**, **Shiny Stone** | Three of the nine unobtainable stones in the one damp place they read as belonging |
| Abandoned Cut | **Gold Bottle Cap** and a **fossil** | Permanent, does not touch the level curve, and all 23 fossil sites are worldgen and therefore absent |

**Avoid Rare Candies entirely** — at a level cap they are the one item that breaks the curve.

**Where a cache must be visible to dialogue:** an advancement cannot write a Cobblemon quest field and dialogue
cannot read an advancement (`docs/STATE.md` records this as a live limit). So an advancement-granted cache is
**invisible to the dialogue system**. That is fine for four of these five — they are stashes nobody talks about.
It is **wrong for the Abandoned Cut**, if the diggers' story is ever to be referred to by an NPC at the dig camp:
that one needs `grant_reward_once` fired from a conversation, and it inherits the unproven two-player dialogue
run. Decide the Abandoned Cut's narrative role before choosing its mechanism.

## 6. The four things to solve, solved

### Containing a lake at this depth

The Deep needed a shell to keep cave water **out**; the Drowned Gallery needs one to keep authored water **in**,
and it is the same shell with the pressure reversed.

- **A closed basin, not a floor.** The Displaced City taught this the hard way — its roof had 224 voids because
  the shell was built in one direction. The basin must be sealed on the floor, all four sides *and* the water's
  own surface level, because any single face touching unauthored cave void leaks the lake into it.
- **Source blocks, not flowing.** Fill with `minecraft:water` source blocks in a fully enclosed basin. A water
  source with no lower or lateral air neighbour does not flow, so a sealed basin is static.
- **Pass ordering.** The road's build already runs walls → air → floor → fittings for exactly this reason. The
  lake adds a fifth: **shell → air → floor → water → fittings**, with the water after the floor and before
  anything that stands in it, or the fill erases the fittings.
- **The audit.** Extend the road's existing shell check: every block on the basin's outer face must be solid,
  counted, and zero. The Deep's `open to the sky` check is the same shape inverted.

### Lava is a light source, and Dark and Ghost will be calm near it — **a feature, and make it legible**

Lava emits light 15. `FOFAggressionCalculator` calms Dark and Ghost at block light 12 and above, so a radius of
roughly three blocks around any lava is calm, and eight blocks is neutral. In a cavern with two lava falls and a
magma shelf, most of the floor will sit at 8 or above.

**Take it as a feature.** The Slagworks becomes **the lit refuge on a dark road** — the one region where the dark
mechanic is off — and it pays for that with the only floor that damages you and a Fire roster that resists half
of what a player brings to a Rift. That is a legible trade a player can discover and use: *the safe room is the
one that burns you.*

Two consequences to accept deliberately rather than stumble into: the Slagworks cannot also be a Ghost region
(the mechanic would be off there), and the rest station on the spine is no longer the only safe ground, which
weakens it slightly. Both are acceptable; the alternative is lighting the cavern with something that is not lava,
which would be a lava cavern that is not lit by lava.

### Every block through the spawn policy

`data/spawn_blocks.json` holds 259 blocks that condition a spawn, and **water, flowing water, lava, magma block,
sand and red sand are all among them**. `tools/validate_data.py` fails on a placed template containing one unless
`data/placements.json` whitelists it. So:

- Every region's palette goes through the policy **before** any build, not after.
- The whitelist entries must name *why*, because in these regions the conditioning is the point: we are using
  `neededNearbyBlocks` deliberately to shape which upstream species appear.
- The interaction with the Habitat Block needs proving: a `replace_spawns` block should override the upstream
  pools the terrain summons, but **that is assumed and untested**, and it is the load-bearing assumption of §4.
  It belongs in the same experiment as the first Habitat Block placement.

### The walk-out check, including what water and lava can drop you into

The road already proves every one of its 666 route blocks has ground under foot. Extend it to the regions with
three additions:

1. **Every region floor walkable**, as the spine is.
2. **Nothing can drop a player somewhere they cannot leave.** For each region, flood-fill the reachable air from
   the fork mouth and assert that every air cell a player can fall into is in the same component as the exit.
   That catches a lake bottom with a lip, a lava pit with sheer sides, and a collapsed shaft with no ladder.
3. **Lava specifically**: assert no lava is adjacent to a walkable route block without a one-block lip, so a
   player cannot walk into it blind in the dark. The Slagworks is lit, which helps, but its approach corridor is
   not.

## 7. What this proposal depends on that is not yet true

- **No evolution stone can be obtained in this world.** All 66 stone recipes in the jar take ore, deepslate ore,
  or the stone's own compressed block as input; **not one takes ordinary materials**. The ore does not generate,
  because a WorldPainter export writes chunks as already generated. The single exception is
  `nether_fire_stone_ore`, which generates in the vanilla-generated Nether — and **zero** of the campaign's
  stone-gated families need a Fire Stone. So a stone placed in one of these caches is the only one in the game,
  which makes §5 load-bearing rather than decorative. See `docs/mechanics/SPAWN_PHILOSOPHY.md`.
- **ADR-002 is Proposed, not Accepted**, and no reward mechanism exists yet.
- **No Habitat Block has ever been placed**, so §4's mechanism is unproven in a running game.
- **`tools/compile_spawns.py` drops habitat `conditions`**, so a darkness-gated roster needs a generator change.
- The five regions add roughly 4,000 to 6,000 blocks of carve each; the road is 153,678 commands and the Deep
  5.8 million, so this is small by comparison and will not need new tiling.

## 8. What I would want decided before building

1. Five regions or four (drop the Abandoned Cut).
2. One anchor species per region, from §4's candidates.
3. Whether the Slagworks' calm is accepted as the design, per §6.
4. Whether the Abandoned Cut has a narrative role, which decides its reward mechanism.
5. ADR-002 accepted, so there is a reward mechanism to build against.
