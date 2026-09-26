# server/config/mods/

This folder records the server's running copy of each config that differs from the base pack
(`base-pack/cobbleverse/config/`) and has no overlay in `modpack/config/`. It also holds the config files that exist
only on the server. It is written by `python tools/server_config_record.py record --server-dir <server>`, and
`... check` reports any disagreement between the server and the repo. Everything the server runs is now in exactly one
of three places: `modpack/config/` (our overlay), this folder, or the base pack.

The folder started on 2026-09-26, after the committed `DistantHorizons.toml` was found to disagree with the running one.
At that point `check` reported 0 disagreements. On the same day:
- `c2me.toml` was deleted from the server (C2ME was removed in 7a9cdf0);
- the overlay's `starters.json`, `rctmod-server.toml`, `resourcepackoverrides.json`, `defaultoptions/options.txt` and
  `defaultoptions-common.toml` were copied to the server, which had never received them;
- `DistantHorizons.toml` was set to the repo's values, keeping the server's own `serverId`.

These are records, not decisions. A file here holds whatever the server runs, whether or not anyone chose that value.

## Values that look like choices rather than mod upgrades

| File | Value | Base pack | Origin |
|---|---|---|---|
| `mega_showdown/config.json` | `likoPendentDuration` 72,000 ticks (1 h), **set back from 1,440,000 (20 h)** on 2026-09-26 by the owner: "nothing records why it was 20 hours and a mod default is a better baseline than an unexplained value" | 72,000 | Mega Showdown 1.0.2's own default is also 72,000 (`MegaShowdownConfig`, read from the jar). The 20 h value had been written on 2026-09-09 with no record of who set it or why. It takes effect at the next restart. |
| `capture_xp.json` | `inBattleAwardExperienceToFaintedPokemon` false, `outOfBattleAwardExperienceToFaintedPokemon` false | keys absent | Probably a newer mod version's keys, with its defaults |
| `obc-common.toml` | `breedingBuff` false | key absent | Probably a newer mod version's key |
| `playerxp/playerxp.json` | daily cap keys gone; exp share on at 35 blocks | daily cap keys present | Probably a newer mod version |
| `cobblemon/spawning/best-spawner-config.json` | Cobblemon 1.8's bucket blocks (`activatedHabitatBuckets`, `fishingBuckets`) | 1.7.3's `buckets` list | Migration to Cobblemon 1.8 |

The other files are mods rewriting their own configs, or client-side settings a server never reads: Iris, Sodium,
Sound Physics, BetterF3, the Xaero HUD, `rctmod-client.toml`, FancyMenu and keybindings.
