# Campaign structure assets

This directory contains structures owned or intentionally modified by this campaign.
Upstream Cobblemon and Cobbleverse structures stay in their jars/datapacks and are
referenced by verified IDs in `manifests/structure-dependencies.json`.

## Layout

- `campaign/towns/` — regionalized settlement and service-building variants.
- `campaign/gyms/` — reusable exteriors and authored gym shells; gameplay interiors remain custom.
- `campaign/villain/` — campaign-owned villain structures.
- `campaign/dungeons/` — campaign-owned puzzle and exploration structures.
- `campaign/landmarks/` — campaign-owned story landmarks.
- `manifests/structure-dependencies.json` — provenance and permanent block/mod dependencies.

Do not copy an upstream NBT here merely to make it convenient. Create a campaign
copy only after its license permits derivation, record `based_on`, list every
required component, and verify the exported artifact in a disposable world.

