# Installing the Cobblers client (for a friend joining the server)

The server runs **Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0** (`docs/STATE.md`, "Runtime"). Your
game has to carry the same mods. The owner sends you one small file, `cobblers-client-<version>.mrpack`; your
launcher reads it and downloads every mod from Modrinth itself. A few COBBLEVERSE files cannot be downloaded
that way, and you copy those in once by hand (step 4).

**Status: written 2026-10-04, not yet walked through by anyone.** No instance has been installed from this
`.mrpack` and joined the server. If a step does not match what you see, tell the owner; that is a finding.

## What you need

- A **Minecraft: Java Edition** account. The server is in online mode with a whitelist, so it must be a real
  account.
- **Java 21.** Both launchers below can download it for you. If one asks which Java to use, choose 21.
- About **1 GB of disk** (the mods and packs are about 770 MB, plus about 205 MB of COBBLEVERSE packs in step 4).
- **Memory: give the game 6 GB (6144 MB).** COBBLEVERSE's own Modrinth page says it "requires at least 4GB of RAM
  to be able to play smoothly in single player (6GB+ recommended)" (read 2026-10-04). We add Distant Horizons on
  top, so do not go below 6 GB. If your computer has 16 GB or more, 8 GB is fine. Do not give it more than about
  half of your computer's memory.

## 1. Install a launcher

Either one works with a `.mrpack`:

- **Prism Launcher** (prismlauncher.org), or
- **Modrinth App** (modrinth.com/app).

## 2. Import the pack

- **Prism:** *Add Instance* -> *Import* -> pick `cobblers-client-<version>.mrpack` -> OK. It downloads
  Minecraft 1.21.1, Fabric Loader 0.19.5 and about 165 files.
- **Modrinth App:** create a new instance from a file (*Import* / *From file*) and pick the same `.mrpack`.

If the launcher asks about **optional files**, there is exactly one: `ATM x MSD [v4.0].zip`. It is a resource
pack the owner is still deciding on (it gives proper models to about 40 Pokemon that otherwise show as a stand-in
doll). It is safe either way: it is not switched on unless you turn it on yourself. Leave it unticked unless the
owner asks you to try it.

## 3. Set the memory

- **Prism:** right-click the instance -> *Edit* -> *Settings* -> *Java* -> tick *Memory* -> *Maximum memory
  allocation* 6144 MiB.
- **Modrinth App:** the instance's *Settings* -> *Java and memory* (or the app's default instance options) ->
  memory 6144 MB.

## 4. Copy in the COBBLEVERSE files (once)

Seventeen files belong to COBBLEVERSE itself and have no download link of their own, and their licences do not
let us pass them around. You take them from COBBLEVERSE's official download instead:

1. Download **COBBLEVERSE 1.7.42** from https://modrinth.com/modpack/cobbleverse/version/1.7.42 -- the file is
   `COBBLEVERSE 1.7.42.mrpack`, 239 MB. You do not install it; you only take files out of it.
2. Open your instance folder. Prism: right-click the instance -> *Folder*, then go into `.minecraft` (or
   `minecraft`). Modrinth App: the instance's menu -> *Open folder*. You should see `mods/`, `config/` and
   `resourcepacks/` there.
3. Then **either** run the helper (if you have Python and a copy of the repository):

   ```
   python tools/client_pack.py manual --cobbleverse "<downloads>\COBBLEVERSE 1.7.42.mrpack" --instance "<instance folder>"
   ```

   It checks the file is really 1.7.42, copies each file with its hash checked, and also adds COBBLEVERSE's menu
   and loading-screen art and its shaders without overwriting anything (`--no-cosmetic` skips those).

   **or** do it by hand: the `.mrpack` is a zip (open it with 7-Zip, or rename a copy to `.zip`). From inside it:

   | Copy from the `.mrpack` | Into your instance folder | |
   |---|---|---|
   | `overrides/mods/cobblemon-battle-positions-1.1.3.jar` | `mods/` | required |
   | every `.zip` in `overrides/resourcepacks/` **except `ATMxMSD RP.zip`** (16 files) | `resourcepacks/` | required |
   | `overrides/config/fancymenu/assets/`, `overrides/config/fancymenu/slideshows/`, `overrides/config/customsplashscreen/` | the same place under `config/`; skip any file that already exists | optional: menu art |
   | `overrides/shaderpacks/COBBLEVERSE - Shaders/` (and `... (High Quality)/`) | `shaderpacks/` | optional: shaders (K toggles them) |

   Do **not** copy anything else: not `overrides/config/*.json`/`*.toml` (ours are already in place and differ),
   not `overrides/datapacks/`, not `overrides/servers.dat`, and not `ATMxMSD RP.zip` (it breaks the first resource
   reload under Cobblemon 1.8).

## 5. Get whitelisted

Send the owner your **Minecraft username** (your Java profile name, not your Microsoft e-mail). The owner adds
you from the server console with `/whitelist add <your username>`. Until then the server refuses you with "You
are not whitelisted on this server".

## 6. Join

Start the instance. The first launch is slow (several minutes: hundreds of mods and large resource packs).
*Multiplayer* -> *Add Server* -> type **the address the owner gives you** -> *Done* -> join.

## Checking your instance

From a copy of this repository:

```
python tools/client_pack.py verify "<instance folder>"
```

It hashes every file the pack expects in `mods/`, `resourcepacks/` and `shaderpacks/` and prints `MISSING`,
`HASH MISMATCH`, `EXTRA MOD` (a jar the pack does not list) and `optional, absent`. Exit code 0 means every required
file is there with the right hash; 1 means something required is missing or different. It does not check
`config/` (mods rewrite their own config on first launch). If you have no Python, zip your `mods/` and
`resourcepacks/` folders and send them to the owner to run it.

If joining fails with a mod-mismatch or registry error, run `verify` first: an extra or missing mod is the usual
cause.

## For the owner: building and sending the pack

```
python tools/client_pack.py plan     # what it holds; writes nothing
python tools/client_pack.py build    # writes build/client/cobblers-client-<version>.mrpack and .report.json
```

The pack's choices are in `data/client_pack.json` (version, the optional entry, what is embedded); the mod list is
`modpack/manifest/` through `tools/pack_manifest.py`. Rebuild after any manifest or `modpack/config/` change and
send the new file; players re-import it (or update the instance from it). `build/` is never committed.

**What is inside, and why it is safe to send.** The `.mrpack` holds `modrinth.index.json` (every mod and pack as a
`cdn.modrinth.com` URL plus sha1/sha512, as the Modrinth modpack format specifies) and `overrides/` with only
plain-text files: COBBLEVERSE's tracked config, our `modpack/config/` on top, the shader settings `.txt`s and the
licence notices. It never carries a jar, a zip, an image or a no-redistribution file; `build` fails if one would be
embedded. `config/defaultoptions/servers.dat` is left out, so no server address ships in the pack. Datapacks are left
out too: a client joining a dedicated server gets the server's.

**Whitelisting** is yours alone: `/whitelist add <name>` from the console. Never record the names anywhere in the
repository.
