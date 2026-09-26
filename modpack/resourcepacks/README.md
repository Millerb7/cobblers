# modpack/resourcepacks/

Client-side resource packs we add on top of the base pack. Zips are gitignored
(`modpack/resourcepacks/*.zip`); record each one in `manifest/overlay.json`
under `add` with `"kind": "resourcepack"` and a hash/URL so it can be fetched.
Small, authored packs may be kept as folders (tracked) instead of zips.

Resource packs are never installed on the dedicated server.

## Local fix pack

`cobblers-model-fixes.zip` is built on each client by `tools/client_model_fix.py` from the local Cobblemon jar and loaded at the top of the pack list. It restores Cobblemon's own models for forms a third-party pack breaks under Cobblemon 1.8. It is never committed. Recheck after every pack update: `docs/research/CLIENT_MODEL_FIXES.md`.

## Server-delivered pack (proposed, ADR-006)

`tools/client_model_fix.py build --server-pack` writes `build/client/cobblers-client-AllTheMons-subset.zip`: the same Cobblemon fixes plus the ATMxMSD files for the species that would otherwise render as the substitute doll. It is never committed. Its path list is `../manifest/client-pack-atm-subset.json`. Hosting it waits on the ATMxMSD licence question in `docs/research/CLIENT_MODEL_FIXES.md`.
