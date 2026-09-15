# Prefabs

Builds made by hand, usually in Axiom, stored as structure templates that `tools/place_town.py` can seat on the
ground and that `/place template` can place.

## Layout and naming

```
kits/structures/prefabs/<kind>/<set>/<name>.nbt    the structure template
kits/structures/prefabs/<kind>/<set>/<name>.json   its sidecar (written by the importer)
```

| Part | Rule | Examples |
| --- | --- | --- |
| `kind` | one of `buildings`, `services`, `gyms`, `landmarks`, `props`, `bridges`, `trees`, `paths` | `buildings` |
| `set` | the place or style it belongs to; `shared` when it is used everywhere | `viltri`, `pewter_stone`, `shared` |
| `name` | what it is; a variant takes a letter suffix | `cottage_a`, `cottage_b`, `pokecenter`, `gym_rock` |

Names use lowercase letters, digits and underscores, starting with a letter or digit. They never contain a
settlement id that may change.

Each prefab places as `cobblers:kits/<kind>/<set>/<name>`. For example
`kits/structures/prefabs/buildings/viltri/cottage_a.nbt` places as `cobblers:kits/buildings/viltri/cottage_a`.

**The sidecar** (`cobblers.prefab/1`) records:
- who made the prefab;
- the source file and format;
- size, block, block-entity and entity counts, and the block namespaces it uses;
- the **entrance** and **ground layer**.

Buildings, services and gyms must have an entrance: the placer seats them by their door.

## Saving a build from Axiom

Axiom writes Sponge schematics (`.schem`), not `.nbt`. The importer converts them.

1. **Select the build.** Include the ground layer the build stands on, which is the layer the door opens onto,
   plus the block directly in front of the door.
   - Do not include terrain beyond that layer.
   - Everything under the ground layer is foundation, and the placer builds it to fit each site.
   - Empty cells inside the selection are exported as air, and air clears terrain when placed.
2. **Note the entrance.** This is the ground block in front of the door, counted from the selection's minimum
   corner (lowest x, y and z = 0,0,0). Also note which way the door faces.
   - The Target Info window shows world coordinates. Subtract the selection's minimum corner from the entrance
     block's coordinates.
3. **Export.** Main menu → **Export Schematic...** → save into `kits/structures/incoming/` in this repository.
4. **Import:**
   ```bash
   python tools/kit.py import kits/structures/incoming/cottage.schem --kind buildings --set viltri --name cottage_a --entrance 4,0,0 --facing north --author <you>
   ```
   - Use `--no-air` if the empty cells should leave existing terrain alone. Props and paths usually want this;
     buildings usually don't.
   - Use `--replace` to overwrite an existing prefab.
5. **Check:**
   ```bash
   python tools/kit.py index --server-dir ../cobblers-server
   ```
   It fails on a bad name, a missing sidecar, an entrance outside the box, or blocks from a mod the server doesn't
   load.
6. **Make it placeable:**
   ```bash
   python tools/kit.py pack --install ../cobblers-server/datapacks
   ```
   Then run `/reload` in game or over RCON.
7. **Use it:** reference `cobblers:kits/...` and its file in `data/placements.json`, then run
   `tools/place_town.py`.

**A structure block also works** for builds up to 48 blocks on each axis: save it in game as
`cobblers:kits/<kind>/<set>/<name>`, then run `tools/kit.py import` on the saved `.nbt` with the same flags.
- **Where the server writes it:** under the world's `generated/` folder. The exact subfolder on this 1.21.1 server
  has not been checked yet, so look there on first use.
- **Not tested here:** saving by command wrote no file on this server. A player pressing Save is expected to
  work, but hasn't been tested.

## What has been verified

`tools/kit.py import` converted a synthetic Sponge v2 and v3 file (`tests/fixtures/kit/`).
- **Converted correctly:** block states with properties, a chest's custom name, a path block, and air.
- **Placement:** both placed on the live server from the packed datapack, and a door and the chest's name were
  checked over RCON. The placer reads the sidecar entrance.

**Not yet verified:** a real Axiom export. Your first export is that test, so tell me when there is one in
`incoming/`.
