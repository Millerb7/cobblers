# ADR-006: One client resource pack, delivered by the server

- **Status:** Proposed. The owner asked for it on 2026-09-26: "one pack, one delivery, and write the ADR". On
  2026-10-08 the owner gave the go-ahead to ship the AllTheMons models ("Starter line, ship ATM models"), so Flutter
  Mane and the other dolls render. Accepting this ADR, the hosting choice (below) and the licence permission
  (below) are still the owner's; everything up to hosting is prepared ("Prepared and verified, 2026-10-08").
- **Date:** 2026-09-26
- **Evidence:**
  - `docs/research/COBBLEVERSE_COMPATIBILITY.md`, "Client model audit, 2026-09-26";
  - `docs/research/notes/install-sweep-2026-09-26.md`;
  - `base-pack/cobbleverse/licenses/AllTheMons x Mega Showdown - License.txt`.

## Delivery decided (the owner, 2026-10-08)

"The players will get it, this pack won't go public." The pack is handed to our players directly, not hosted at a public URL, so the `server.properties` resource-pack delivery below is not used: each player copies the built `cobblers-client-AllTheMons-subset.zip` into their instance's `resourcepacks/`, and our overlay (`modpack/config/resourcepackoverrides.json`) enables it above COBBLEVERSE RP. The status stays Proposed until it is seen working in game (Flutter Mane, Iron Valiant and the 11 dolls rendering).

## Context

Two client-side model faults are visible in play:
- **40 spawnable species render as Cobblemon's substitute doll.** Eleven of them are in our spawn tables, Greavard in
  the Route 1 mansion among them. Their only models are in `ATMxMSD RP.zip`, which the overlay disabled because its
  Mega Mewtwo resolver broke the first Cobblemon 1.8 resource reload.
- **16 forms are mis-assembled**, Pidgeot, Talonflame, Skarmory and Tyranitar among them. COBBLEVERSE RP's 1.7.3
  models wear Cobblemon 1.8's redrawn textures.

The one existing fix pack, `cobblers-model-fixes.zip`, is on a single player's machine; nothing gets it to anyone
else. The Rift's connected-texture pack (`cobblers_rift_ctm`) was built and never installed, and it faces the same
delivery question.

## Decision (proposed)

- **One pack**, `cobblers-client-AllTheMons-subset.zip`, built by `tools/client_model_fix.py build --server-pack`
  into `build/client/`. It is never committed, because it holds third-party assets. It contains:
  - Cobblemon 1.8's own files for the mis-assembled forms, at the paths that override COBBLEVERSE RP's and
    CobbleMotion's;
  - the ATMxMSD subset for the missing species (265 paths derived, 263 shipped; screamtail and ironcrown stay with COBBLEVERSE RP), with no Mega Mewtwo resolver;
  - the existing crash fixes.

  The Rift textures join it once their own decision is made.
- **Delivered by the server**, through `server.properties`:
  - `resource-pack=<https URL>`;
  - `resource-pack-sha1=<the sha1 the build prints>`;
  - `resource-pack-id=<a fixed UUID>`;
  - `require-resource-pack=true`, with a short `resource-pack-prompt`.

  Minecraft applies a server pack above the player's own enabled packs, so it overrides COBBLEVERSE RP and
  CobbleMotion without any change to their order. Players install nothing by hand.
- **Licence: a blocker for the AllTheMons part (corrected 2026-09-26).** The `ATMxMSD RP.zip` we hold (3.6.1) ships
  **ALLTHEMONS LICENSE v3.2**, not the v3.1 in `base-pack/cobbleverse/licenses/` that this ADR first relied on. v3.2
  §1.3 says: "Only with explicit written permission can the User ... upload copies of the Software", modified or
  unmodified. Hosting the subset at a URL is an upload. **The AllTheMons files (265 derived, 263 shipped) cannot be
  server-delivered without written permission from the author (Lvnatic).** The zip is built locally only
  (`build/client/cobblers-client-AllTheMons-subset.zip`, sha1 `dfdd4f8118a66ff854d23a1e5c2f7651ff042e97`,
  deterministic).
  - **Option 1:** ask Lvnatic in writing, for a private, non-monetized server with credit. The pack is already built
    for that, with "AllTheMons" in its name and `CREDITS.md` and `LICENSE-AllTheMons.md` inside.
  - **Option 2:** redistribute nothing from AllTheMons. Every player already has `ATMxMSD RP.zip` from Cobbleverse,
    only disabled. Re-enable it on the client, and have the server pack neutralise what broke it: Cobblemon's own
    files placed over the Mega Mewtwo resolver, Ash-Greninja's poser, and the 89 species it overrides. More build work,
    and no licence question for AllTheMons.
  - **Either way:** the Cobblemon-only part (the crash fixes and the 16 mis-assembled forms) can be delivered now. It
    is Cobblemon's own files, from the jar every player already runs. The jar's licence file is MPL-2.0; whether
    Cobblemon's *assets* are covered by it is NOT VERIFIED.
- **Checked like everything else.** `tools/install_check.py` will verify that `server.properties`' sha1 matches the
  built pack, so a stale or missing pack fails the same way an uninstalled datapack does.

## Prepared and verified, 2026-10-08

After the owner's go-ahead. Nothing was hosted, uploaded or applied to a server.

- **The pack, rebuilt:** `python tools/client_model_fix.py build --server-pack --instance
  "C:/Users/wnd/AppData/Roaming/ModrinthApp/profiles/Fabric 1.21.10"` (the client instance the tool documents, read
  only; the build writes nothing there). 1,468,971 bytes, sha1 `dfdd4f8118a66ff854d23a1e5c2f7651ff042e97`: byte for
  byte the 2026-09-26 build. 303 entries: 36 Cobblemon files, 263 ATMxMSD files for 43 species, plus `pack.mcmeta`,
  `CREDITS.md`, `LICENSE-AllTheMons.md` and `cobblers-client-pack.json`. The derived path list matched the committed
  `modpack/manifest/client-pack-atm-subset.json`; the donor `ATMxMSD RP.zip` there has the recorded sha256
  `6d48b792…`, identical to the copy in `C:/Users/wnd/Documents/github/cobblers/COBBLEVERSE/resourcepacks/`.
- **Flutter Mane and Iron Valiant are in it, complete:** for each, the resolver (`0_<name>_base.json`), model
  (`<name>.geo.json`), poser, animation file and three textures (base, shiny, emissive; Flutter Mane's emissive file
  is spelled `fluttermane_emmisive.png`, as its resolver names it). Every model, poser and texture their resolvers
  name is in the pack.
- **The 11 dolls in our tables are in it:** Vullaby, Mandibuzz, Oranguru, Passimian, Gulpin, Swalot, Charjabug,
  Grubbin, Vikavolt, Greavard, Bombirdier, each with resolver, model, poser and textures (5 to 8 files). Six of them
  ship no animation file of their own: their posers' animation groups resolve elsewhere in the stack, which the build
  checks and fails on otherwise.
- **The species side is ready on the server.** In `Cobblemon-fabric-1.8.0+1.21.1.jar` (server snapshot 2026-10-05),
  `species/generation9/fluttermane.json` and `ironvaliant.json` carry no `implemented` key. `COBBLEVERSE-DP-v31.zip`
  `data/cobblemon/species_additions/fluttermane.json` and `ironvaliant.json` set `implemented: true`, and the DP
  ships `spawn_pool_world/0987_fluttermane.json` and `1006_ironvaliant.json`. The DP is force-loaded from
  `datapacks/` by Global Packs (relayed: `base-pack/cobbleverse/config/global_packs.toml`, not re-read). So their species and spawn data are live today, and they render as dolls only for want of a
  model. Not seen in game.
- **The licence verdict is unchanged: hosting needs Lvnatic's written permission.** The licence that ships in the
  donor (and is copied into our pack) is v3.2, which by its §4 covers releases after 2026-03-30. §1.3: "Only with explicit written
  permission can the User ... upload copies of the Software. This includes ... redistributing modified or unmodified
  copies of the Software publicly". A URL every client can fetch without login is public distribution by its own
  definition ("hosting, uploading, publishing, or otherwise providing access through websites, file-sharing services
  ... public repositories"). §1.1 (non-commercial use) is satisfied: no store, no donations. Credit is already in
  the pack (`pack.mcmeta` `credits`, `CREDITS.md`, `LICENSE-AllTheMons.md`, "AllTheMons" in the file name) and in
  the prompt. §1.3's second paragraph (permission from third-party asset creators) concerns *altered* artistic
  assets; ours are copied unaltered. The v3.1 in `base-pack/cobbleverse/licenses/` would allow redistribution with
  "AllTheMons" in the title, but it does not govern this release. Not legal advice. **So the owner's hosting choice
  is between: (a) ask Lvnatic in writing, then host as below; or (b) the v4.0 Modrinth reference (above), which
  uploads nothing.**
- **The server side, written, not applied:** `server/config/server.properties.example` carries
  `require-resource-pack=true`, `resource-pack=` (empty: the URL placeholder), `resource-pack-sha1=dfdd4f81…`, the
  fixed `resource-pack-id=43566b60-4e01-549a-95d3-2592c69f3454` (uuid5, URL namespace,
  `cobblers:client-pack/cobblers-client-AllTheMons-subset`) and a `resource-pack-prompt` JSON text component with the
  AllTheMons credit. All five keys are in the Minecraft 1.21.1 jar's dedicated-server properties class (`apo.class`),
  along with "Failed to parse resource pack prompt '{}'", which is why the prompt is JSON. The owner's steps are in
  `server/README.md`, "Client pack". `tests/test_server_client_pack.py` checks the example against this ADR,
  `CLIENT_MODEL_FIXES.md` and any built pack's `.sha1`.
- **The client overlay does not change.** `modpack/config/resourcepackoverrides.json` keeps `ATMxMSD RP.zip` out of
  `default_packs` (it has only a `pack_overrides` title). A server pack sits above the client's packs, but it does not
  remove what a lower pack contributes: an enabled 3.6.1 would still load its Mega Mewtwo resolver, which names
  models Mega Showdown 1.0.2 does not have, and that broke the first 1.8 reload. The subset ships no Mega Mewtwo
  resolver, so leaving the full pack disabled is what keeps the fix.
- **Not verified:** that the client downloads and applies the pack, that a Flutter Mane renders and animates, and
  that `require-resource-pack=true` with an empty URL sends nothing (the vanilla behaviour, not read in bytecode).
  `install_check.py` does not yet compare the live `resource-pack-sha1` with the example.

## Distribution by a Modrinth pack (researched 2026-09-26)

The owner will give the players a `.mrpack`. That changes the AllTheMons question:

- **Bundling any AllTheMons file in the `.mrpack` (its `overrides/`) is an upload of a copy** under v3.2 §1.3, and
  needs Lvnatic's written permission. Sending the file only to friends does not avoid this. The licence's own
  "Public Distribution" definition leaves out "a private, pre-approved group", but §1.3's "upload copies" has no
  such exception. Read conservatively: permission first. (Not legal advice.)
- **Referencing it needs no permission, because we host nothing.** The author publishes it on Modrinth: "AllTheMons x
  Mega Showdown", slug `allthemons-x-mega-showdown-legacy`, project `odZZdRCE`, by Lvnatic, under the same v3.2 licence,
  loaders `datapack, minecraft`. A `.mrpack` lists a file by its `cdn.modrinth.com` URL and hashes, and the launcher
  downloads it from Modrinth. Allowed download domains for a pack uploaded to Modrinth: `cdn.modrinth.com`,
  `github.com`, `raw.githubusercontent.com`, `gitlab.com` (Modrinth's `.mrpack` format page). COBBLEVERSE 1.7.42 itself
  lists `odZZdRCE` among its 186 dependencies.
- **The file differs from ours.** Modrinth hosts the unified zip, "ATM x MSD [v3.6.1].zip" (6,126,613 bytes, sha1
  `146545cb…`), with data and assets. Our `ATMxMSD RP.zip` (4,301,923 bytes, sha1 `071256e8…`) is Cobbleverse's own
  resource-only repack (Cobbleverse's licence listing marks it "Permission"). No Modrinth file has our hash.
- **v4.0 (2026-09-08) may remove the reason it was disabled.** Its changelog says "Updated to Cobblemon 1.8!" and
  "Compatible with MSD 1.0+ (for 1.8)". It drops models Cobblemon 1.8 now has and adds CobbleMotion animations. The
  3.6.1 we hold predates both, and its Mega Mewtwo resolver is what broke the first 1.8 resource reload. **NOT
  VERIFIED:**
  - that v4.0 reloads cleanly on our client;
  - that it models the 11 doll species in our tables;
  - that its forms match the species data COBBLEVERSE-DP serves;
  - how its CobbleMotion copy stacks with the CobbleMotion pack we already run.

  That is one client experiment, and it is the next step.
- **If v4.0 fails and no permission comes,** option 2 above still works with a `.mrpack`. Each player's pack
  references ATM x MSD from Modrinth, and our own pack of Cobblemon files, which the `.mrpack` may carry in
  `overrides/`, is enabled above it to neutralise what breaks. Nobody installs anything by hand in either case.
- **By hand, the worst case:** each player downloads the pack from Modrinth, drops it into `resourcepacks/`, and
  enables it above COBBLEVERSE RP. A one-time step, about two minutes, and a support burden on every update.
- **The Cobblemon-only part fixes none of the 11 dolls.** The Cobblemon 1.8.0 jar has no model, texture or animation
  for Vullaby, Mandibuzz, Oranguru, Passimian, Gulpin, Swalot, Charjabug, Grubbin, Vikavolt, Greavard or Bombirdier
  (control: Bulbasaur, 13 files). It fixes the 16 mis-assembled forms and the 7 crash forms only.
- **ATMxMSD was never on the server.** It is a client resource pack from each player's Cobbleverse install. The server
  tree has no copy, and `server.properties` delivers no pack. The server runs no AllTheMons files, and nothing so far
  has been distributed. The fix pack on one player's machine was built locally from that player's own copy.

## Hosting (the owner decides)

The URL must be reachable by every player's client, over HTTPS, without login.

| Option | Cost | Note |
|---|---|---|
| A static file host with a stable direct link (for example a public GitHub release asset in a *public* repository, or an object-storage bucket) | Free, and one upload per change | The simplest. A private repository's release assets need auth and will not work |
| A small HTTP server on the machine that runs Minecraft | No third party, but a second open port and TLS | Most self-contained, and most to maintain |
| A cloud-drive "direct download" link | Free | Links can change or throttle, which breaks the sha1-pinned delivery |

Recommendation: a release asset in a **separate public repository** holding only the built pack and its credits. The
campaign repository stays private.

## Consequences

- Every join downloads or validates the pack, a few MB. A changed pack means a new sha1 in `server.properties`.
- Singleplayer or offline testing still uses `tools/client_model_fix.py install`.
- The disabled `ATMxMSD RP.zip` stays disabled; only the subset is delivered.
- To revisit: the Rift CTM decision, Cobblemon or pack updates (rerun `scan`), and any public release.
