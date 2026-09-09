# modpack/resourcepacks/

Client-side resource packs we add on top of the base pack. Zips are gitignored
(`modpack/resourcepacks/*.zip`); record each one in `manifest/overlay.json`
under `add` with `"kind": "resourcepack"` and a hash/URL so it can be fetched.
Small, authored packs may be kept as folders (tracked) instead of zips.

Resource packs are never installed on the dedicated server.
