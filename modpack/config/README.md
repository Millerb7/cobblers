# modpack/config/

Our configuration overrides. A file here replaces the base-pack file at the
same relative path (base: `base-pack/cobbleverse/config/`). Keep only the files
we actually change, and say why in a comment or a sibling `*.md` when the
format has no comments (plain JSON).

The three Default Options/Resource Pack Overrides files intentionally remove
`ATMxMSD RP.zip` from the default enabled list. The pack remains installed for
provenance, but its 3.6.1 Mega Mewtwo resolver names a model removed by the
Cobblemon 1.8 Mega Showdown build and breaks the first client resource reload.

`cobblemon/main.json` starts from the generated Cobblemon 1.8 configuration and
changes `pokemonPerChunk` from `1.0` to `0.25`. The default produced severe
crowding during the first EXP-009 multiplayer playtest. This is a provisional
global density cap; EXP-001 will replace generic survival spawning with curated
route encounter control.

`rctmod-server.toml` is Cobbleverse's file with one change: `relativeLevelCap` 0 instead of 5 (the owner,
2026-09-24). The authored rosters and leader teams assume a player's cap is exactly the next required leader's
strongest Pokemon; 5 let players arrive five levels over every ace. `tests/test_rct_config_overlay.py` fails if
anything else in the file drifts from the base. Nothing copies this folder to the server by itself
(`server/scripts/assemble-server.ps1` builds `mods/` only): copy the file into `<server>/config/` before a boot
(`docs/world-building/REEXPORT.md`, before the day).
