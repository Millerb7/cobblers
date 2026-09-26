# Committed configs against the running server (2026-09-26)

Asked after the Distant Horizons catch. `modpack/config/DistantHorizons.toml` said `enableServerGeneration = true`,
the server had run `false` since the 10240 export, and a copy would have re-enabled generation that ignores the border.

The check is read-only. Every committed config (`modpack/config/**`, `server/config/server.properties.example`) was
compared key by key with the file the server directory runs (`cobblers-server/config/**`, `server.properties`), shared
by staging and the live server, and with the staging client's copy. Secrets were masked and never printed. A second
pass compared every server config file that has no overlay with the base pack's copy
(`base-pack/cobbleverse/config/**`), to find hand edits the repo does not record.

## Committed file against server

| File | Server | Finding |
|---|---|---|
| `cobblemon/main.json` | identical | none |
| `cobblemon/starters.json` | identical | none |
| `rctmod-server.toml` | identical | none |
| `resourcepackoverrides.json` | identical | none |
| `DistantHorizons.toml` | `enableServerGeneration` fixed today. 5 client fog values differ, plus the auto `serverId` | Client graphics only; they do nothing on a server. The server's file was never a copy of the repo's. |
| `defaultoptions/options.txt`, `defaultoptions-common.toml` | the server's copies still list `file/ATMxMSD RP.zip`; the repo's remove it | Client defaults only, unused on a server. The server copy is stale. |
| `server.properties.example` | runtime has **`white-list=false`**, the example `true` | **The server directory runs with the whitelist off.** Staging and the live server share this file (staging only swaps `--universe`/`--world`). Also `motd` is an old test motd and `enable-rcon` is on (expected). Left unchanged: it is the owner's call. |

## Committed file against the staging client (the client's own copies)

- `cobblemon/main.json` size 0.95-1.05 and `rctmod-server.toml` `relativeLevelCap` 5. Both are decided by the server
  in multiplayer, so the client's copies do not matter there. They would matter in singleplayer.
- `DistantHorizons.toml` `enableServerGeneration = true`. It is harmless, because DH needs the server's value too.

## Server config files with no overlay that differ from the base pack

46 files differ, 114 are identical, and 204 exist only on the server. Most of the 46 are mods rewriting their own
configs after version upgrades: new keys, reformatted files, Cobblemon 1.8's new `best-spawner-config.json` buckets
and Mega Showdown's renamed keys. Values that look like choices rather than migrations:
- `mega_showdown/config.json`: `likoPendentDuration` is 1,440,000 on the server; the base is 72,000.
- `capture_xp.json`: no XP awarded to fainted Pokemon in or out of battle, on the server only.
- `playerxp/playerxp.json`: the base's daily cap keys are gone and exp share is on (35 blocks); probably a newer mod
  version.
- `c2me.toml` is still on the server, although C2ME was removed (commit 7a9cdf0). It is dead config.

None of these is recorded in the repo. Whether each was a deliberate choice is not known.
