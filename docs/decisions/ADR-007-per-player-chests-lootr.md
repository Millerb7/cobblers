# ADR-007: Per-player chests by Lootr

- **Status:** Proposed. **The owner chose the mechanism on 2026-10-07** ("per-player chests: Lootr",
  `docs/STATE.md:137` answer 8, `docs/HANDOVER_SESSION.md:54-56`). This record says what that choice commits us to.
  The template's vocabulary has `Accepted`, but marking an ADR `Accepted` is the owner's act, not an agent's
  (the content-architect role may not). Read this as "decided by the owner, not yet implemented, not yet
  proven": nothing below has been run in a game.
- **Date:** 2026-10-07 (the owner's decision as recorded; the record was written the same wave).
- **Evidence:**
  - `docs/research/PER_PLAYER_CHESTS.md` (researched 2026-10-04 from Modrinth, the Lootr wiki and the Lootr source on
    branch `mdg-1.21.1`, all read through a summarising fetch tool; nothing run);
  - `docs/decisions/ADR-002-reward-delivery-mechanism.md` (how rewards reach a player today);
  - `experiments/EXP-056-lootr-per-player-chests/README.md` (the proofs this decision waits on; NOT_EXECUTED).

## Context

Play-test note 15 asked for "an instanced-chest mod and make every chest per-player"
(`docs/PLAYTEST_2026-10-05.md:33`), after a friend emptied a shared container that held a summoning feather (note
14, `:32`). Note 14 itself is fixed without a mod: the three bird templates' Sophisticated Storage barrels have the
feather removed by `remove_items` (`data/adopted_legendary_sites.json:378`, `data/placements.json:27876, 27935`,
emitted by `tools/place_donor.py:186-200` and `tools/articuno_tower.py:104-106`). That also settles a disagreement the
research note raised (`PER_PLAYER_CHESTS.md:40-46`): the altar note was right, the feather sat in the barrel's
`storageWrapper.contents.inventory.Items`, not in a loot table.

What remains is the owner's wish for per-player containers as world texture: lootable rooms, portal caches, flavour
stashes a party can each open.

### What the evidence says, graded

Each figure the brief relayed from `docs/STATE.md`, checked against the research note:

| Claim | Note's own grade | Source in the note |
|---|---|---|
| Lootr Fabric build `1.21.1-1.11.38.127`, Modrinth project `EltpO5cN`, version `nar56EsW`, 1,111,591 bytes, published 2026-09-25 | VERIFIED (Modrinth API, via the summariser) | `PER_PLAYER_CHESTS.md:62-65` |
| sha1 `6671786d...`, sha512 `6a0d5042...` | **relayed, "re-measure"** | `:65-68` |
| Licence MIT | VERIFIED | `:59-61` |
| Required on client AND server; no server-only build | VERIFIED (Modrinth page, wiki FAQ) | `:72-74` |
| World-critical once used: "Removing Lootr will unfortunately also remove all containers from your world" | VERIFIED (FAQ quote) | `:75-76` |
| "Converts only loot-table containers" | VERIFIED for the **automatic** path (source read: `BlockEntityTicker.isValidEntityFull` rejects a null loot table). **Incomplete as stated:** an operator command, `/lootr custom-chest`, converts a vanilla `chest` or `barrel` of explicit `Items` into a per-player copy | `:115-136` |
| "ADR-002 rewards are already per player" | VERIFIED **as design**; ADR-002 is Proposed and its two-player proof is unrun (`ADR-002:144-174`; `docs/STATE.md:338` "NOT VERIFIED ... that two players each receive once") | `:25-31` |

Every runtime behaviour Lootr is relied on for below (conversion of a command-placed chest, of a pasted template's
chest, what re-placing does) is **ASSUMED** in the note (`:161-171`).

### Rungs (CLAUDE.md principle 6)

- **Cobblemon native:** no per-player container is recorded in `docs/research/`; ADR-002 names one as a revisit
  trigger (`ADR-002:196-198`). Not available.
- **Vanilla / datapack / functions:** a container's loot table rolls once and is shared (ADR-002 alternative (a),
  ASSUMED there for 1.21.1); N physical chests per cache were rejected (`ADR-002:132-133`). ADR-002's advancement
  grant is per player but has no container a player browses.
- **Compatible addon:** Lootr, SlashLoot, Instanced Containers (below). This is the first rung that gives a browsable
  per-player inventory.

## Decision

1. **Add Lootr `1.21.1-1.11.38.127` (Fabric) to the overlay, client and server, exact pin**, the way
   Distant Horizons is added (`modpack/manifest/overlay.json:546-573`: `add[]`, `side: "both"`, `pin: "exact"`, the
   Modrinth ids, sha512 and sha1, a `verification` line, `reason`, and a `world_save_risk` line). The hashes are
   computed from the downloaded jar, never copied from the research note. Its one non-Fabric-API dependency, Cloth
   Config, is in the base pack (`base-pack/inventory/pack_hashes.csv:53`, `cloth-config-15.0.140-fabric.jar`;
   measured) and is not in the overlay's `server_exclude` (grep of `overlay.json` for `cloth`, no match; measured).
   Whether Lootr's declared Cloth Config range accepts 15.0.140 is read from the jar's `fabric.mod.json` at download.
2. **Lootr is a world-critical dependency from the first converted container**, and is listed with the others in
   `CLAUDE.md` ("World-critical") when it is installed on any world a player keeps. Under principle 11 it is never
   removed after that.
3. **The division of labour with ADR-002 holds and is sharpened:**
   - anything that matters, once per player, ever (a TM, a patch, a key item, a summoning item) stays an ADR-002
     advancement grant or a dialogue grant. **A Lootr container never holds it**, because a re-export (and possibly a
     re-apply) is expected to reset a container for everyone (EXP-056 case D), which would hand it out again;
   - a Lootr container holds **texture**: flavour stock, portal caches, a lootable room, where receiving it again
     after a world rebuild costs nothing.
4. **Every per-player container's contents come from a deterministic loot table we author** (one pool per item,
   `rolls: 1`, `set_count`, the shape of `tools/portals.py:311-313`), so every player gets the same items and an
   audit can predict them. Literal `Items` and donor loot tables are not used for per-player content (conversion plan,
   below). `/lootr custom-chest` is not the authoring path: it is an operator command per block, it only accepts
   vanilla `chest` and `barrel` (`PER_PLAYER_CHESTS.md:130-136`), and it would have to be re-run after every
   rebuild.
5. **`clear_loot` stays the default** for donor and town templates (`tools/place_donor.py:170-183`,
   `tools/place_town.py:96-97, 387-389`, `tools/deep_city.py:2334-2336`). A site that wants per-player donor loot
   says so in its record and names our deterministic table instead; nothing turns per-player by accident.
6. **Configuration:** refresh and decay stay off (their defaults, `PER_PLAYER_CHESTS.md:148-152`); `team_loot` off;
   break protection on (the default, players must sneak to break, `:154-155`); dimension whitelist/blacklist set only
   if EXP-056 case A shows the pocket dimension needs it. Config keys are the summariser's reading of the source
   (`:143-145`) and are confirmed against the config file Lootr generates on first boot before any is written.
7. **Nothing is authored for Lootr until EXP-056 cases A to D pass on staging** (principle 20), and Lootr is not put
   on the live server until then.

## Alternatives considered

- **SlashLoot** (server-only, CC-BY-4.0, `PER_PLAYER_CHESTS.md:78-97`). No client install and it covers Cobblemon
  gilded chests itself; but it was first published 2026-05-24 with under a thousand downloads at fetch time, and it
  never instances explicit `Items`. The owner chose Lootr. It stays the fallback if EXP-056 finds Lootr unworkable,
  and its absence of new blocks means it would not be world-critical.
- **Instanced Containers** (`:101-103`). All Rights Reserved, and one player at a time per chest. Rejected.
- **Lootrmon** (`:104-106`), a Lootr add-on for gilded chests. Not adopted: last file 2026-02-20, before Cobblemon
  1.8; unverified there. Gilded chests stay shared until it is checked.
- **No mod; ADR-002 only** (`:218-228`, the research note's own first recommendation). Covers every reward that
  matters and adds no dependency, but has no browsable per-player container. The owner asked for one.
- **N physical chests per cache** (`ADR-002:132-133`). Rejected there; still rejected.
- **Not researched: the vanilla 1.21 vault block.** ASSUMED from memory, not in `docs/research/`: a vault hands each
  player a loot-table roll once in exchange for a key item. It is not a chest a player browses, and it needs a key.
  Named so the omission is visible; not pursued unless the owner asks (`cobblemon-researcher` would grade it).

## Consequences

- **World-critical lock-in.** Lootr adds blocks (`lootr:lootr_chest`, `lootr:lootr_inventory`, and others,
  `PER_PLAYER_CHESTS.md:74`). From the first conversion, removing it deletes those containers. Updating it is treated
  as a removal if a changelog renames a block (`.claude/rules/world-critical.md`). The rule file requires a status in
  `docs/research/COBBLEVERSE_COMPATIBILITY.md` and a boot test in `experiments/` before the manifest entry lands;
  EXP-056 case 0 is that boot test.
- **Installing it changes the world by itself.** Conversion is automatic for every container that still carries a
  loot table when its chunk loads (`:115-129`, VERIFIED from source; the "when" is ASSUMED). So every container we
  place **without** `clear_loot` becomes per-player the day Lootr is installed, with no change to our data. Known
  cases: the portal cache (`tools/portals.py:572-577`, `data/portals.json:124-130`, today "SHARED, first-come"), and
  any adopted or donor template whose loot is deliberately kept: the bird-tower summit barrels ("the summit barrel's
  loot (gems and gear) is kept", `data/adopted_legendary_sites.json:378`), Mew's gilded and Gimmighoul chests
  (`:135, 869`; gilded chests are not converted without Lootrmon), and any other `pack_template` record with no
  `clear_loot`. **Each player then gets that loot.** The set is not counted here (it needs the templates, read with
  `--server-dir`); counting it is plan step 2, and the owner sees the list before install.
- **Every player installs it.** Lootr is client and server; a client without it cannot join (Modrinth: "required on
  both"). It reaches players in the `.mrpack` the owner hands out (`ADR-006:62`; `tools/client_pack.py`,
  `tools/pack_manifest.py` handle mrpacks), not through ADR-006's server resource pack, which carries assets, not
  mods. Every player updates their instance once, and the client and server versions stay identical (exact pin).
- **Multiplayer.** Each player has an independent inventory in each converted container; with a deterministic table
  every inventory is the same list. Players' own chests carry no loot table and stay shared (`:188`, VERIFIED for
  the auto path). Hoppers and comparators against a Lootr container: unknown for Lootr (`:91-92` is SlashLoot's
  behaviour). Storage-network mods (Tom's Simple Storage, Sophisticated Storage) and server-side Distant Horizons:
  no report either way (`:209-212`).
- **`clear_loot` ordering.** Our functions run `place template` and `data remove block ... LootTable` in the same
  function, so the same tick. The note reads Lootr's check as delayed (`:162-166`, ASSUMED "tick delay 20"); if that
  is right the strip always wins and nothing changes for stripped sites. EXP-056 case B proves it.
- **`remove_items` is unaffected** as far as is known: it targets Sophisticated Storage barrels, which `custom-chest`
  cannot take (VERIFIED tag contents) and which the auto path converts only if their block entity is a vanilla
  randomizable container (ASSUMED not). EXP-056 case B checks one.
- **Re-apply and re-export.** Lootr's opener state lives in the overworld's `data/lootr/` (`:158-159`), which
  `tools/carry_players.py:66-88` does not carry (measured: the categories are playerdata, advancements, stats,
  cobblemonplayerdata, pokedex, pokemon, cobbledollars, rctmod_player, tm_moves, cobblenav, molang, rctmod_trainers,
  scoreboard, recovery_ledger). And a re-placed container is expected to get a new identity (ASSUMED, `:169-171`).
  R16P rebuilds every portal room on every re-apply run (`tools/reapply.py:1903-1906, 1919-1921`), so the portal
  cache would refill for everyone each run. Decision 3 makes that harmless by design. If EXP-056 case D shows a re-
  placement resets, the steps that place a Lootr container get a guard (place only where the block is not already a
  Lootr container) or the owner accepts the reset; carrying `data/lootr/` across a re-export is useless if the
  container ids are new, and is not proposed.
- **Audits change.** A converted chest is expected to stop being `minecraft:chest` (ASSUMED: the note lists Lootr's
  own blocks and says `custom-chest` "replaces" the block, `:130-136`; that the automatic path swaps the block too is
  EXP-056 case A's first check), so every
  audit and `presence_audit` probe that reads back a container's block id must accept the Lootr id at a per-player
  site. And `minecraft:chest` is a Gimmighoul spawn-condition block (`data/portals.json:113`): whether a
  `lootr:lootr_chest` still counts is unknown.
- **What stays the same.** ADR-002's grants, the scenery caches (`data/rewards.json`, empty barrels with no loot
  table, never converted), the fossil seams (`tools/fossil_dig.py:15-17, 149-150`: suspicious gravel with a loot
  table; brushable blocks are not in Lootr's convert list, `:122-124`, so ASSUMED untouched) and the suspicious sand
  kept in the Mega Showdown dig site (`data/placements.json:8756`).

## Conversion plan: literal `Items` and kept loot to deterministic tables

### What writes containers today (grep of `tools/`, audits excluded, 2026-10-07; measured)

| Tool | What it writes | Per-player under Lootr as it stands |
|---|---|---|
| `tools/sea_town.py:851-852` | `minecraft:barrel[facing=up,open=false]{Items:[...]}`, N `oak_boat` per boat rack (`r["boats"]`) | No: explicit `Items`, shared. **The only literal-`Items` container any generator writes** (patterns searched: `Items:`, `"Items"`, `item replace block`, `Items append`; one hit. A pattern search is not a proof that nothing else fills a container) |
| `tools/portals.py:572-577` | `minecraft:chest[facing=north]{LootTable:"cobblers:portals/<id>"}` in each `cache` room in `cobblers:pocket` | Yes, automatically (ASSUMED). Table already deterministic: `portals.py:311-313` |
| `tools/fossil_dig.py:149-150` | suspicious gravel with a Cobblemon fossil `LootTable` | Not a container Lootr converts (ASSUMED); out of scope |
| `tools/place_donor.py:170-183` | `data remove block ... LootTable` for records with `clear_loot` (4 in `data/placements.json`, measured by grep) | Stripped: never per-player |
| `tools/place_donor.py` records **without** `clear_loot` | the template's own loot tables, kept | **Yes, on install, by accident.** Not counted |
| `tools/place_town.py:96-97, 387-389` | strips every town template's loot tables (ruined copies have no containers, `data/ruins.json:258`) | Stripped |
| `tools/deep_city.py:2334-2336` | strips the Deep city's templates | Stripped |
| `tools/place_donor.py:186-200`, `tools/articuno_tower.py:104-106` (and `tools/new_player_walk.py:1586`, which replays it) | `remove_items`: one item out of a Sophisticated Storage barrel | Not converted (ASSUMED) |
| 39 other generators (152 occurrences of `minecraft:chest`, `barrel`, `trapped_chest`, `gilded_chest` or a shulker box; measured grep count) | container blocks with no `Items` or `LootTable` in the matched string | No: empty scenery stays shared and empty, as ADR-002 decision 2 wants |

`tools/progression_pack.py:374-376` writes empty overrides for upstream loot tables (`empty_loot_tables`); any
Lootr container naming one of those tables would open empty for every player.

### What changes, in order

| # | Step | Agent | Waits on |
|---|---|---|---|
| 1 | The owner's permission to download the Lootr jar | owner | nothing |
| 2 | A lister: every container that will still carry a `LootTable` after our commands, by site (portals; `pack_template` records without `clear_loot`, read with `--server-dir`; adopted legendary sites). Read-only, offline; can run before step 1 | `datapack-content-dev` (lister), `test-author` (its test) | nothing |
| 3 | The owner reads step 2's list and marks each site per-player (our deterministic table), stripped (`clear_loot`), or kept shared (with Lootr in, only by listing its table in Lootr's `loot_table_blacklist`, a key not yet confirmed against the generated config) | owner | 2 |
| 4 | EXP-056 cases 0, A-D on staging | main session (server), `qa-reviewer` (grades) | 1 |
| 5 | Lootr's status in `COBBLEVERSE_COMPATIBILITY.md`; the `overlay.json` `add` entry with measured hashes | `dependency-auditor` | 4 case 0 |
| 6 | A shared helper for a deterministic container table (generalise `portals.py:311-313`), and a data shape for a per-player container: `{id, block, contents: [{item, count, verification}], per_player: true}`, the `verification` convention of ADR-002's `data/rewards.json` | `datapack-content-dev` | 4 A-D |
| 7 | `sea_town.py`'s boat barrels: contents from the rack record into a table `cobblers:containers/<town>/<rack>`; the barrel placed with that `LootTable` (or by `/lootr barrel <table>` if case A shows `setblock` does not convert). Whether a boat rack should be per-player at all is the owner's call (step 3) | `datapack-content-dev` | 6, 3 |
| 8 | Sites the owner marked per-player in step 3: `clear_loot` stays, plus a `data merge block ... {LootTable:"cobblers:containers/..."}` naming our table after the strip | `datapack-content-dev` / `world-content-dev` (data) | 6, 3 |
| 9 | If case D resets: a guard in the re-apply steps that place a Lootr container (R16P and each step 7-8 touches) | `minecraft-systems-dev` | 4 D |
| 10 | Audits and `presence_audit` probes accept the Lootr block id at per-player sites, and check each per-player container names a table that exists and is deterministic | `test-author` | 6 |
| 11 | The `.mrpack` with Lootr to every player; then the live install | owner, main session | all above |

**Why steps 6-10 wait for the experiments.** The emitted command depends on case A (does a `setblock` with a
`LootTable` convert, or must it be `/lootr <block> <table>`?); the boat barrel's look depends on case C (does a barrel
stay a barrel?); the re-apply guard exists only if case D resets, and what it tests for (a block id) is whatever case
A reads back; the audits key on that same id. Built first, each would encode a guess (principle 20). Step 2 does
not wait, because it measures our own data and templates and changes nothing. `tests/test_sea_town.py` has three
known failures from the sea-town migration (`docs/STATE.md:203`, relayed, not re-measured); step 7 lands on top of
that migration, not beside it.

## What must be true before content depends on it

1. The owner has given explicit permission to download the jar (EXP-056 step 0).
2. EXP-056 cases 0 and A-D pass on staging, with the versions recorded.
3. The sha512 and sha1 in `overlay.json` are measured from the downloaded file.
4. The pre-install list of containers that keep a loot table (plan step 2) has been read by the owner.
5. The audits that read container block ids accept the Lootr ids at per-player sites (`test-author`).
6. Every player has the updated client instance before Lootr is on the live server.

## Revisit when

EXP-056 fails any of A-D (fall back to SlashLoot or to ADR-002 only); Lootrmon is verified on Cobblemon 1.8 (gilded
chests); Cobblemon ships a native per-player container; or a Lootr update renames a block.
