# Core regional structure library

This shortlist is the standard kit to prototype after world-critical dependencies
are frozen. It references upstream assets by ID; it does not copy them.

| Need | Starting asset | Decision | Why |
| --- | --- | --- | --- |
| Rural Pokémon Center | `CBM-CENTER-PLAINS-01` | REUSE + REGIONALIZE | Small, command-tested, and contains PC/healing blocks; operation still needs a client test |
| Main-town Pokémon Center | `BCA-CENTER-01` | REUSE + REGIONALIZE | Recognizable larger Center with Waystones; verify all block entities first |
| Poké Mart | `BCA-MART-01` | REUSE + REGIONALIZE | Verified dedicated Mart template; exterior palette can follow biome |
| Outdoor battle area | `BCA-BATTLEPAD-01` | REUSE | Small generic pad placed successfully with transforms |
| Houses, roads, market pieces | selected BCA village components | REUSE + REGIONALIZE | Broad themed vocabulary; compose authored layouts instead of generating identical towns |
| Academy / civic landmark | `BCA-ACADEMY-01` | REFERENCE ONLY | Useful design vocabulary but too large and entity-heavy to adopt before inspection |
| Department store | `BCA-DEPARTMENT-STORE-01` | REUSE + REGIONALIZE | Candidate medium/large-city anchor |
| Gym exterior | BCA battle pad or regional civic shell | REUSE + REGIONALIZE | Saves exterior work while keeping challenge spaces authored |
| Named Cobbleverse gyms/leagues | `CBV-GYM-BROCK`, `CBV-LEAGUE-KANTO` | REFERENCE ONLY | Region-specific content and embedded trainers are poor defaults for this campaign |
| Legendary monuments | `LM-*`, `LUMY-*` | REFERENCE ONLY | Strong reference material, but license, custom processors and persistent mechanics require care |
| Route landmarks | selected Cobblemon habitats/ruins | REUSE + REGIONALIZE | Native 1.8 content can make routes memorable after placement/function tests |
| Villain facilities | Rocket/Galactic assets | REFERENCE ONLY | Campaign hideouts and HQs remain Tier 3 authored landmarks |

## Missing families

No verified standalone trade tower or professor lab exists. Treat BCA's Academy,
department store, Mega Showdown observatory, and villain towers as references.
Create campaign-owned versions only when their experiment reaches implementation.

## Gym reuse rule

- **Exterior:** reuse or regionalize a service/civic shell when it suits the town.
- **Interior:** author the challenge path for the campaign mechanic.
- **Trainers and leader arena:** campaign-owned data and geometry.
- **Team, rules, rewards, and progression:** campaign-owned systems.
