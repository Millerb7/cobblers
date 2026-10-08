# Ultra Beasts on this server (read 2026-10-08, main session)

**VERIFIED** by reading the server's own archives (`cobblers-server/mods/`, `cobblers-server/datapacks/`,
`COBBLEVERSE/` resource packs) with Python zipfile. Not seen in game.

| Species | Cobblemon 1.8.0 jar | Made available by | Model (client) | Inherited wild spawn |
|---|---|---|---|---|
| Poipole | species, `implemented: true`, model and resolver | the jar | the jar | none (the jar has no spawn file; ours: the two overworld towers) |
| Naganadel | species, `implemented: true`, model and resolver | the jar | the jar | none |
| Nihilego, Buzzwole, Pheromosa, Xurkitree, Guzzlord, Stakataka, Blacephalon | species data labelled `ultra_beast`, no `implemented` | `COBBLEVERSE-DP-v31.zip` `species_additions` | `ATMxMSD RP.zip` | `COBBLEVERSE-DP-v31.zip` `spawn_pool_world` |
| Kartana | as above | as above | `MissingMons RP.zip` | as above |
| Celesteela | as above | as above | `PlanetaCobblemon RP.zip` | as above |

The three resource packs are in the client pack (`modpack/manifest/client-pack-atm-subset.json`,
`base-pack/inventory/pack_hashes.csv`). The archives marked "z DO NOT ENABLE z" carry other copies and are not used.

Sample inherited spawns (`COBBLEVERSE-DP-v31.zip`, first entry):
- Nihilego: ultra-rare, levels 60-78, `#cobblemon:is_ocean`;
- Kartana: ultra-rare, 55-70, `minecraft:cherry_grove`, open sky;
- Guzzlord: ultra-rare, 70-75, `#cobblemon:is_end`.

Our route suppression strips them inside the route boxes; outside those, these above-cap wild spawns are still live.
Nothing in `data/` uses an Ultra Beast today (grep, 2026-10-08).

**So they can be dungeon bosses** with no new dependency. A boss built from them inherits the dependency on
COBBLEVERSE-DP and the three resource packs, the same way Entei depends on Mega Showdown
(`docs/research/notes/legendary-species-1.8.0.md`). **ASSUMED, to check in game** before a boss uses one: that each
model renders and animates, and that Showdown battles them normally (their abilities, Beast Boost among them).
