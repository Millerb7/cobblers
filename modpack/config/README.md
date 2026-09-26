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

`DistantHorizons.toml` has `enableServerGeneration = false` (2026-09-26). This is the value the server has run since
the 10240 export (`docs/world-building/REEXPORT.md`, "The border holds"). Distant Horizons ignores the world border,
and with server generation on it generates real chunks up to 4,096 chunks around a player, past the border and the
canvas. The repo copy said `true` until then, so a copy of this folder onto the server would have switched that back
on. DH keeps the setting in its multiplayer session config and needs both it and distant generation for a session to
generate (`SessionConfig`, DH 3.2.0-b, read from the jar). The server's `false` therefore governs, and clients still
receive the pregenerated LODs by sync. The comment DH writes above the key is its own; DH rewrites the file.

`rctmod-server.toml` is Cobbleverse's file with one change: `relativeLevelCap` 0 instead of 5 (the owner,
2026-09-24). The authored rosters and leader teams assume a player's cap is exactly the next required leader's
strongest Pokemon; 5 let players arrive five levels over every ace. `tests/test_rct_config_overlay.py` fails if
anything else in the file drifts from the base.

**Getting this folder onto the server.** `tools/reapply.py install` copies it onto `<server>/config/` and then fails
unless `tools/server_config_record.py check` finds the server's config recorded exactly. The same copy can be run on
its own with `python tools/server_config_record.py install --server-dir <server>`. Until 2026-09-26 nothing did this
(`server/scripts/assemble-server.ps1` builds `mods/` only). Five of these files had never reached the server, and a
playtest offered the starters this folder drops.
