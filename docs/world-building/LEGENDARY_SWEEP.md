# The legendaries sweep: the rest of the catalogue, and a catchable Hoopa

The owner, 2026-10-06: *"Go through the whole Cobbleverse catalogue and place what is left, in obscured spots --
behind waterfalls, at the back of caves, down dive portals, on islands with no reason to visit, in Rift dead ends.
Use /place template, not /clone. Each one: what gates it, what a player gets, and how anyone would find it. Re-open
the ones left where they generate. If any has a better home in our world than a Nether tower nobody visits, move
it."* And, decided the same day: Hoopa is catchable after the Rift release.

Authored data: `data/adopted_legendary_sites.json` `sweep_2026_10_06`, `sweep_sites` and `catalogue_2026_10_06`;
`data/placements.json` `legendary_giratina_shrine`, `legendary_newmoon_island`; `data/rewards.json`
`sweep_red_chain`, `sweep_nightmare_weaver`; `data/hoopa_cradle.json`. Tools: `tools/legendary_sweep.py`
(`measure`, `check`, `catalogue`), `tools/hoopa_cradle.py`, `tools/rewards_pack.py` (`requires_flags`, new).
Tests: `tests/test_legendary_sweep.py`, `tests/test_hoopa_cradle.py`. **Nothing here was placed, booted or clicked.**

## The premise, checked

The 2026-10-03 pass (`HIDDEN_LEGENDARIES.md`) had already found the loaded catalogue used up except three templates
the jars ship outside `data/structures.json`, each blocked by an altar item with no source and by a record that only
knew surface seats. This sweep unblocks two of them by authoring each item's one source and two new seat kinds. It
does not invent the rest: everything else has a status and a reason below.

The owner's named homes, measured:

- **Behind waterfalls, cave backs, dive portals:** no catalogue template fits (pocket rooms are 7-13 wide; every
  remaining template is 42+ across; a heightmap cannot describe an overhang).
- **Rift dead ends: none.** Over `the_rift`'s polygon, 82 footprints of the Giratina piece's 42x38 clear the
  keep-outs, the portals and the 800 spread (Registeel, Mesprit, Regirock, Hoopa's cradle) - and **none** is 156 from a
  route path (the residents' 128 plus half the footprint). The Giratina piece went to the Glacial Tear's trough.
- **Islands with no reason to visit:** Newmoon Island over the Fungal Isle's empty west end.

## The catalogue (39 templates)

`python tools/legendary_sweep.py catalogue`: adopted 8, placed by this sweep 2, ours authored 11, planned 2, stays
where it generates 4, out by the owner 1, refused 2, unplaced 2, not loaded 7. Read from every `.nbt` in the server
snapshot's loaded packs, the three disabled region packs and the mod jars (altar, shrine, statue, pedestal, cocoon or
summon blocks, or a spawning command chain). **Loaded** = `/place template` reaches it today.

| Template | Legendary | Loaded | Status |
|---|---|---|---|
| `cobbleverse:mythical/mew` | Mew | yes | adopted |
| `cobbleverse:crown_cemetery` | Spectrier, Calyrex | yes | adopted |
| `cobbleverse:crown_spire` | Glastrier | yes | adopted (hidden) |
| `cobbleverse:legendary/zapdos`, `/articuno`, `/moltres` | the birds | yes | adopted (Moltres moved from the Nether) |
| `cobbleverse:dawn_tower`, `dusk_tower` | Necrozma x2 | yes | adopted (moved from the End) |
| `legendarymonuments:giratina_island/main/222` | Giratina | yes | **placed by this sweep** |
| `lumymon:newmoon_island` | Darkrai | yes | **placed by this sweep** |
| `legendarymonuments:lake_guardians/*` (3) | Uxie, Azelf, Mesprit | yes | ours (`data/legendaries.json`) |
| the four Ruinous shrines | Chi-Yu, Wo-Chien, Ting-Lu, Chien-Pao | yes | **stay in the Nether** (re-opened) |
| `legendarymonuments:eternatus_cocoon` | Eternatus | yes | out (the owner, until a Galar Particle supply) |
| `legendarymonuments:stark_mountain` | Heatran | yes | unplaced: an owner's call (below) |
| `lumymon:temple_of_sinnoh` | Arceus | yes | unplaced: 18 plates with no source |
| `turnback_cave`, `distortion_portal` | (Giratina's road, a portal) | yes | refused (jigsaw; a dimension) |
| Hoenn `legendary/groudon`, `regice`, `regirock`, `registeel` | | no | ours (`data/legendaries.json`) |
| Hoenn `secret_garden` | Latias, Latios | no | ours (Shrew Station's Eon shrine) |
| Hoenn `legendary/kyogre`, `sky_pillar` | Kyogre, Rayquaza | no | planned (`KYOGRE_CAVE.md`; not built here) |
| Hoenn `mythical/deoxys`, `mythical/jirachi` | | no | not loaded |
| Johto `bell_tower` | Ho-Oh | no | not loaded |
| Johto `whirl_island`, `celebi_shrine` | Lugia, Celebi | no | ours (`data/legendaries.json`) |
| Sinnoh `snowpoint_temple` | Regigigas | no | ours |
| Sinnoh `spear_pillar`, `split_decision_temple`, `flower_paradise`, `fullmoon_island` | Dialga/Palkia, Regidrago/Regieleki, Shaymin, Cresselia | no | not loaded |

**Re-opened, the Ruinous four stay.** Their stakes are a Nether worldgen feature; an overworld paste would have no
stakes near it and the Nether copies would still generate. The Nether is reachable by a vanilla portal, so it is not
"a tower nobody visits": it is where the stakes are.

**Heatran, the owner's call.** Placeable as the two sites below were: empty its two Sinnoh RCT spawners
(`remove_blocks rctmod:trainer_spawner`) and give a Champion-gated `lumymon:magmatic_cluster` cache, which the
template's own `stark_forge` turns into the Magma Stone. Not done because a 120x90x137 volcano is a landmark by
construction, not an obscured spot.

**The seven not loaded** need their pack enabled (a world-critical dependency decision, CLAUDE.md principles 9-10).

## The two new sites

| | Giratina: the Distortion shrine | Darkrai: Newmoon Island |
|---|---|---|
| Template | `legendarymonuments:giratina_island/main/222` (42x43x38) | `lumymon:newmoon_island` (101x58x100) |
| Command | `place template ... 4374 66 2862 none none`, jigsaws set to their final states | `place template lumymon:newmoon_island 24 141 5582 none none` |
| Seat | **sunk**: the 12-layer slab buried, layer 11 at the trough's cheapest seat y77; the glass dome and altar above; top y108 | **floating**: bottom 24 over the highest ground (y117); top y198 |
| Where | Glacial Tear, lower trough (cell C5); 635 columns cut a block or two, 64 filled | over the Fungal Isle's west end (cell F1); writes over nothing |
| Rules | authored 115, route path 458, Habitat margin 312, portal 918, nearest legendary 912 (Crown Cemetery); 0 route sightings; 0 wet columns | authored 97, route path 1,369, portal 2,855, nearest legendary 823 (Zapdos, same isle); no route point within 1,200 |
| Altar | `giratina_altar` (4397, 78, 2882), anchor (4397, 81, 2882) | `darkrai_shrine` (73, 187, 5615), anchor (83, 178, 5606) |
| Item, ONE source | `lumymon:red_chain`: cache `sweep_red_chain` at the altar. Nothing loaded makes one (a disabled Sinnoh recipe; Cyrus, never seated) | `lumymon:nightmare_weaver`: cache `sweep_nightmare_weaver` at the shrine. Nothing loaded makes one; the island's loot holds none |
| Gate | `champion_cleared` on the cache: Giratina rolls 85-99, only the Champion's cap (100) holds it | `champion_cleared`: Darkrai rolls 70-85; flight to reach it |
| A player gets | Giratina, once per player (one chain each), sometimes holding a Griseous Core | Darkrai once per player; the island's loot (Dusk/Moon Balls, dark and psychic Tera Shards, Darkinium Z, TM Night Slash, books) |
| Found by eye | from the anchor of `major_river` (the Tear's river, 450 off): follow it upstream | from the top of Zapdos's tower (y132), 823 off: a black island in the western sky |
| Rumour (proposed, NOT authored) | the Compact binder after the release: *"When the ring went dark something else answered. North-east, where the ice tore."* | Shrew Station's archivist, to a Champion: *"Sailors west of the Fungal Isle swear there's an island up in the air out there."* |

The rumours are not authored: `tools/finale_audit.py` models the binder's conversation, and the station's
conversations belong to their own session (the Crown Spire precedent).

**Why `sweep_sites`, not `sites`.** `tests/test_adopted_legendary_sites.py` holds every `sites` record to a surface
seat and a registered structure; these are neither. `tools/adopted_sites.py sites()` now returns both lists, so the sea
life keep-out, the hidden-site spread and the research station see the two new sites.

## Hoopa at the cradle

`tools/hoopa_cradle.py` -> `cobblers_hoopa_cradle`. The release (`dlg_main_relic_hall_release` `release_001`) runs
`unlock_league_after_rift_resolution`, whose first effect grants `cobblers:flag/rift_crisis_resolved`. A 20-tick
keeper finds every player holding that flag and not `cobblers:hoopa_cradle/caught` within 20 of the spot
(3357, 13, 3306) (the binder is 8.5 off), gives them a number (`hp.id`) and their own level-60 Hoopa (owned by
`hp.own`, `PersistenceRequired`) at once; a lost one returns 1,200 ticks after it is first missed, the next time they
stand in the cradle. Only the owner's ball holds (`poke_ball_capture_calculated` -> `ball_check`, `set_shakes(0)` for
anyone else); a catch within 40 of the spot grants `caught`. **Not an effect on the transition**: the finale audit
reports a spawn there as "the release changes the world", and its test pins `release_fx` last. Keying on the flag
reaches the same player within a second and covers players who released before the pack existed.

## Reapply steps needed (not edited here: `tools/reapply.py` is not this unit's)

1. **R9** already pastes every `pack_template` placement: the two new donors need nothing new.
2. **`rewards_pack`** (prepare job) rebuilds `cobblers_rewards` with the two Champion-gated caches.
3. **New:** a prepare job `add("hoopa_cradle", "hoopa_cradle.py")`, `cobblers_hoopa_cradle` in `WORLD_LOCAL` (it
   spawns Pokemon on its own, so never the global folder), and a self-driving note: "its own load tag schedules the
   keeper; spawns one Hoopa per eligible player; writes no blocks".

## What an audit must check

Derive each expectation yourself; do not import `tools/legendary_sweep.py`, `tools/hidden_sites.py` or
`tools/adopted_sites.py` for it.

1. Read the two templates (snapshot jars, read only): sizes 42x43x38 and 101x58x100; the altar at [23, 12, 20] and
   anchor [23, 15, 20] of the Giratina piece; the shrine [49, 46, 33] and anchor [59, 37, 24] of Newmoon Island; the
   six jigsaws and their final states; and that no container in either holds `red_chain` or `nightmare_weaver`.
2. Search every jar and datapack in the snapshot, loaded and `extra`, for producers of the two items; confirm the only
   ones are the disabled Sinnoh recipes and `team_galactic_cyrus`, and that no loaded record seats Cyrus.
3. `round(ground(x, z))` by your own loop: Giratina's box x4374..4415 z2862..2899 has min 72, max 80, its unique
   cheapest seat y77, and cut 639 / fill 86 there; Newmoon's box x24..124 z5582..5681 has max 117, so y141 is 24 over.
4. Re-measure the rules with your own code: route paths (`data/route_paths.json`) edge distance >= 128; every activated
   Habitat Block's spawn range plus 28; every portal >= 120 from the edge; 800 centre to centre from every adopted,
   sweep and `data/legendaries.json` site and Hoopa's spot; 96 from every authored coordinate except the sites' own
   records and caches.
5. The Rift claim: re-run a search of `the_rift` polygon for a 42x38 that clears those rules, and say whether it is
   really empty.
6. The sightlines: Zapdos's tower top to Newmoon's middle; `major_river`'s anchor to the dome; and 0 route sightings.
7. Mutate the GENERATOR: drop `type_specific` in `rewards_pack.advancement()`, drop `caught=false` from the Hoopa
   keeper, move the Hoopa spawn by one block; your tests must go red.
8. Hoopa: the keeper's position equals `data/relic_underground.json` cradle centre + 0.5 and floor + 1; the binder is
   within 20; the release transition's first effect is the flag's grant; only one dialogue node runs it.
9. In game, on staging only: after R9, the two pastes stand with their altars; a Champion standing at each altar gets
   the item once and a non-Champion nothing; whether each altar CONSUMES its item (if not, it is a farm and needs a
   cap like `cobblers_spectrier_cap`); whether the Darkrai shrine answers outside LumyMon's Nightmare dimension; the
   Hoopa checks in `data/hoopa_cradle.json` `runtime_checks`.

## Defects recorded (not chased)

- `tests/test_system_contracts.py::test_contract_c4_every_tool_that_reads_the_spawn_conditions_is_accounted_for`
  fails at this branch's base: `tools/bank.py` reads `spawn_blocks.json` and is not in `data/system_contracts.json` C4
  `tools`.
- `tests/test_no_swallowed_crashes.py` fails at the base: broad handlers in `far_south_audit.py`,
  `jungle_temples_audit.py` and a dozen tests.
- `tools/hidden_sites.py search` crashes with an IndexError when a candidate sits within 160 of the map edge
  (`enclosure()` samples past the heightmap).
- `tools/hidden_sites.py check` checks only `sites` marked hidden; the two sweep sites are checked by
  `tools/legendary_sweep.py check` instead.
