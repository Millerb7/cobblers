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

`sophisticatedcore-common.toml` is Cobbleverse's file with the town markets' backpack items switched off in
`enabledItems` (`"<id>|true"` -> `"<id>|false"`, 26 of them, 2026-10-03). The key's own shipped comment is "Disable
/ enable any items here (disables their recipes)"; in the jar it removes the recipe and the creative-tab entry and
nothing else, so a disabled tier or upgrade can still be bought, given and used, but not crafted
(`docs/mechanics/TIERED_GOODS.md` 2.1). It is WRITTEN, not hand-edited: `python tools/markets.py overlay` builds it
from the base file and `data/markets.json`, and `tools/markets.py audit` fails if the committed file differs from
what the data writes. That the recipes vanish in game is not run.

`cobbledollars/bank.json` is CobbleDollars' sell-back list, the Bank every CobbleDollars merchant opens on shift +
right-click (2026-10-05, the owner: a way to earn money from the Minecraft loop). It is Cobbleverse's 80 entries
unchanged, followed by ours: ores and ingots, apricorns, common berries and Pokemon drops. It is WRITTEN, not
hand-edited: `python tools/bank.py write` builds it from `data/bank.json`, and `tools/bank.py check` fails if the file
differs from the data or if any authored shop sells a bought item at or below the bank's price. The list is one
server-wide file (read in the jar: `data/bank.json` `mechanism.verified`); `cobbledollars reload` re-reads it without
a restart. That a sale pays in game is not run (`data/bank.json` `experiment`).

**Getting this folder onto the server.** `tools/reapply.py install` copies it onto `<server>/config/` and then fails
unless `tools/server_config_record.py check` finds the server's config recorded exactly. The same copy can be run on
its own with `python tools/server_config_record.py install --server-dir <server>`. Until 2026-09-26 nothing did this
(`server/scripts/assemble-server.ps1` builds `mods/` only). Five of these files had never reached the server, and a
playtest offered the starters this folder drops.
