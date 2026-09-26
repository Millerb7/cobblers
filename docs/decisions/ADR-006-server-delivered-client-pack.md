# ADR-006: One client resource pack, delivered by the server

- **Status:** Proposed. The owner asked for it on 2026-09-26: "one pack, one delivery, and write the ADR". The
  hosting choice is still open (below).
- **Date:** 2026-09-26
- **Evidence:**
  - `docs/research/COBBLEVERSE_COMPATIBILITY.md`, "Client model audit, 2026-09-26";
  - `docs/research/notes/install-sweep-2026-09-26.md`;
  - `base-pack/cobbleverse/licenses/AllTheMons x Mega Showdown - License.txt`.

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
  (`build/client/cobblers-client-AllTheMons-subset.zip`, sha1 `dfdd4f81…`, deterministic).
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
