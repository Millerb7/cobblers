# F4 Relic Island — The Stranded Home

## Event summary

The Stranded Home is a fully optional medium event roughly 145 blocks off the
southern Pallet Town shore. From the broken dock, players can make out a familiar
red-roof house on a small island. The path in front of the house runs into the
sea, as though the land was cut out of Pallet Town and dropped offshore.

Pokémon fans should read it as probably Ash's house without requiring a literal
copy. The prototype uses an actual Pallet Town house from CobblemonCityTowns 1.0:
`cobblemoncitytowns:pallet_town/buildings/large2`. It has white quartz walls,
a mangrove-red roof, a furnished family interior, two beds, and a small garden.
The source is copied under our namespace because the pack is MIT licensed and
the NBT uses vanilla blocks only. The whole donor datapack is not enabled.

The donor archive also contains a complete Pallet kit: five houses, Oak's Lab,
roads, fences, lamps, trees, flowers, a pool, and a Pallet sign. Oak's Lab is a
verified 19×20×20 structure with Cobblemon healing and PC blocks. Those pieces
are candidates for the mainland town, but EXP-001 copies only the selected
12×9×10 house. The local `cobbleverse:ash` structure remains a nonredistributable
visual reference because it embeds NPCs, trainer spawners, and many modded blocks.

## Place in Route 1

F4 is a 1,000-block planning hex. Pallet Town occupies the south-central coast,
while Route 1 leaves inland. The island is the first optional landmark that
teaches players how this campaign treats exploration: leaving the main path can
reveal a useful Pokémon, a compact story, and a location that exists for reasons
beyond progression.

The house must be visible from the broken dock and one nearby coastal rise. At
the current ten-chunk server view distance, its 145-block offset keeps it inside
the practical reveal range. Trees and the coast should hide it from most of
Pallet Town so that discovering the correct shoreline matters.

## Access and flow

1. A broken dock and scattered planks point south from the Pallet shoreline.
2. The player sees the house roof across the water.
3. Swimming or using a normal boat reaches the island immediately; no badge or
   water mount is required.
4. The front path, mailbox, and fence stop at torn earth near the beach.
5. The ground floor looks abandoned in a hurry. The upstairs bedroom holds the
   reward point behind a damaged bookshelf.
6. A calcite/amethyst seam behind the house shows where the fragment was torn
   through the worldshift.

There is no quest marker, mandatory dialogue, or progression flag required to
visit. Later water mounts simply make revisiting more convenient.

## Environmental storytelling

- The front walk is aligned toward Pallet Town but ends in open water.
- Fence sections and dock planks continue along the same axis as if separated.
- The eastern upstairs corner is missing, with furniture exposed to weather.
- A lone tree survived, while its roots intersect stone unlike the mainland.
- Household debris becomes sparser toward the coast, implying the direction of
  displacement.
- One short note can eventually read: "Mom — went to the lab. Back before
  supper." Keep it optional and do not explain the worldshift directly.

## Build specification

| Element | Specification |
| --- | --- |
| Island | Irregular 70×58-block shelf; stone core, gravel/sand shore, raised grass center |
| House | 12×9×10 copied Pallet `large2` donor; minimal damage after placement |
| Orientation | Existing west-facing entrance and interrupted path point toward Pallet Town |
| Exterior | Donor quartz walls, dark trim, mangrove-red roof, garden edge |
| Interior | Donor furnished family interior; original chest becomes the event cache |
| Island dressing | One tree, broken fence, dock debris, mismatched geological scar |
| Dependencies | Vanilla blocks in donor geometry; Cobblemon items only in placeholder loot |
| Donor artifact | `cobblers:f4/pallet_house_large2` copied unchanged; placement function applies reversible scene edits |

The generated function builds the island, places the donor NBT, resolves its
three jigsaws, replaces its external loot-table reference, and removes a small
roof corner to sell the worldshift. Client review should focus on terrain seams,
sightline, and whether the donor reads clearly enough as Pallet architecture.

## Donor decision

CobblemonCityTowns is the canonical Pallet donor because version 1.0 directly
ships Pallet houses, Oak's Lab, and matching settlement pieces for Minecraft
1.21.1 under MIT. The Pallet house was traced to LastGreenseer's MIT-licensed
CobbleTowns 1.0.2; the maintained copy differs only in its internal namespace.
`large2` was selected for the relic because it is compact, furnished,
family-sized, and uses only vanilla block namespaces. No file labels one house
specifically as Ash's, so the event claims visual association rather than false
provenance. See `world/structures/manifests/pokemon-town-donors.json`.

CobbleJourneyTown V0.2 was inspected as the secondary donor. It contains useful
large settlement structures, a PokéCenter, and a Poké Mart, but no Pallet-, Ash-,
or Oak-named template. Radical Gyms remains a gym/League donor. CobbleStructures
is reference-only because its published license is All Rights Reserved.

## Reward options

### Recommended — displaced Pichu

A level 5–7 Pichu appears once per player in the upstairs room, accompanied by a
small weathered-cap lore collectible. Pichu is recognizable and exciting here,
but it does not overpower early teams. It also makes the reward about a new team
possibility rather than raw money or a universal stat boost.

Implement this only after EXP-006 proves authored Pokémon encounters and EXP-007
proves per-player claims. The prototype uses a modest repeatable cache instead.

### Alternative — Light Ball

A Light Ball is strongly thematic and useful only for the Pikachu line. It could
be available after the first or second badge if early Pikachu damage proves too
strong. This is a good fallback if static encounters are unreliable.

### Alternative — worldshift keepsake

A unique cap, photograph, or map fragment is safest for balance and strongest
for lore, but needs a custom item or resource-pack treatment to feel substantial.
Pair it with a small practical cache rather than presenting it alone.

## Prototype placement

Install `modpack/datapacks/cobblers_campaign`, reload datapacks, stand at the
intended island center at sea level, and run:

```mcfunction
/function cobblers:exp_001/f4_relic_island/place
```

For the planned F4-local coordinates, execute from the server console:

```mcfunction
execute positioned 420 62 675 run function cobblers:exp_001/f4_relic_island/place
```

The function is deterministic and intended only for a disposable prototype. It
rebuilds the placeholder cache when rerun. Do not execute it in a production
world until the donor placement, terrain, and scene edits are visually approved.

## Encounter intent

The island should not become a random-spawn hotspot. Its common coastal roster
should overlap Route 1: Wingull, Krabby, Wooper, and Buizel by day; Hoothoot and
Spinarak at night; Lotad in rain. Pichu is authored reward content, not a tiny
random percentage. Actual Cobblemon spawn JSON remains part of EXP-001's runtime
proof and must be based on verified 1.8 formats.

## Acceptance checks

- House roof is visible from the designated Pallet shoreline but not every town
  street.
- Swim/boat access works without progression commands.
- The silhouette reads as a displaced Pallet starter home.
- The front path and debris visually point back toward town.
- Interior supports exploration and contains one obvious reward point.
- Island remains smaller than Pallet Town and does not resemble a settlement.
- Rerunning the function does not duplicate entities.
- Save/restart preserves the build and loot container.
