# Disabling Xaero's minimap and world map: inside `cobblers:pocket`, and everywhere

Asked 2026-10-10 (unit XAERO, dungeons pass 2; the owner: "Xaero's map should be off", inside the dungeons, everywhere
unconfirmed). Answered for Minecraft 1.21.1 Fabric, Xaero's Minimap 26.4.2, Xaero's World Map 1.44.2.
Research only: no jar was opened this session (no code execution); jar facts are carried from
`xaero-map-effects.md` (javap, 2026-09-26) and cited as such. Nothing was changed.

## Versions shipped (VERIFIED)

- `xaerominimap-fabric-1.21.1-26.4.2.jar` (bundles xaerolib 1.7.1) and `xaeroworldmap-fabric-1.21.1-1.44.2.jar`:
  `base-pack/inventory/mod_inventory.json:11190,11277`.
- The server snapshot (`server-snapshot-2026-10-05/mods/`) and the client profile (`ModrinthApp/profiles/yordymon 1.0.0/mods/`)
  carry the same two file names (globbed this session). Byte identity with the staging client was `cmp`-checked on 2026-09-26.
- The minimap is `env=*` with a server entrypoint (`mod_inventory.json`, notes at ~11274): the server runs it, so its
  server-side features (effects, enforced profiles) are live.
- No Xaero config exists in the repo or snapshot except `xaerohud.txt` (HUD position only).

## What documentation offers

All from the official CurseForge pages (Xaero's Minimap, World Map; fetched 2026-10-10, current text, not version-pinned
beyond the notes) unless marked.

| Mechanism | Scope | Covers | Source |
|---|---|---|---|
| Status effects `xaerominimap:no_minimap`, `no_entity_radar`, `no_waypoints`, `no_cave_maps`; `xaeroworldmap:no_world_map`, `no_cave_maps` (`_harmful` suffix = harmful type) | per player, any duration | hides minimap HUD and toggle; blanks the world map screen | CurseForge pages; bytecode in `xaero-map-effects.md`; `effect give` accepted on staging |
| System-message code `§f§a§i§r§x§a§e§r§o` (login message) | per player, until reset | cave mode (minimap and world map) + entity radar only | CurseForge FAQ |
| `§n§o§m§i§n§i§m§a§p` | per player | minimap completely; the page names no world-map equivalent | CurseForge Minimap FAQ |
| `§r§e§s§e§t§x§a§e§r§o` | reset flags | | both FAQs |
| Server "Minimap Server Settings" (25.3.0+) / World Map "Open Server Settings" (1.40.0+) UI, enforced profiles by permission (`xaero.minimap.enforced_server_profile`, `xaero.world_map.enforced_server_profile`) | global or per rank/permission | "almost any option" (exact option list not on the page) | CurseForge pages |
| `minimapItemId` in the common config | per player | minimap shows only with that item in hotbar | Minimap page |
| Third party, not by Xaero: datapack *Xaero's Map Server Utils* (`/function xaero:fairxaero`, `nominimap`, `autorun`), mod *Fair Play for Xaero's Maps*, mod *XaeroNuhUh* (gamerules `disableminimap`, `enablefairmode`; MIT; lists 1.21.1 Fabric) | global | minimap off or fair play | their Modrinth/CurseForge pages |

## Verified limits (VERIFIED, `xaero-map-effects.md`)

- No effect, code or option is keyed on coordinates. The only per-dimension option is `CAVE_MODE_ALLOWED_DIMENSIONS`
  (cave mode only). So "pocket only" cannot be a Xaero setting; it has to be driven by us.
- The effects blank the display only. The map writer keeps recording (cache test, staging, 2026-09-26): pocket regions
  land in the pocket's own per-dimension cache folder and are visible later from the world map's dimension switcher.
  Nothing on the server can stop that or delete a client cache.
- Only the effect `no_world_map` hides the world map screen. The login codes and Server Utils/Fair Play functions
  touch cave mode, radar and the minimap, not the world map screen (CurseForge pages; third-party pages say fair play
  "only disables its cave mode").
- Not observed in game: that the screen actually blanks. The 2026-09-26 test looked at the cache after the effects ended.

## Proposal

**Pocket only (smallest, uses what exists).** In the keeper (`tools/dungeon.py` ~780-805, every `period_ticks` = 20,
already tags players in the pocket `dg.pk`), add one line per effect, for example
`execute as @a[tag=<pk>] run effect give @s xaerominimap:no_minimap 3 0 true`, and the same for
`xaeroworldmap:no_world_map`, `xaerominimap:no_waypoints`, `xaerominimap:no_entity_radar`, both `no_cave_maps`. A
3 s refresh needs no clear step: leaving by exit, death, logout, `/tp` or milk all end it within 3 s. Also give it in the
entry function so there is no up-to-1 s gap. Cost: six `effect give` per member per second. ASSUMED: the `effect give`
duration/hide-particles syntax (`<seconds> <amplifier> true`) is standard vanilla and worked for the staging test;
the visible result is unproven.

**Everywhere.** (a) Same effects from a tick/second function over all `@a` (re-applied, or "infinite" duration, ASSUMED
supported in 1.21.1, then cleared on demand): the only route that also blanks the world map. (b) Minimap alone:
Server Settings enforced profile, or the `§n§o§m§i§n§i§m§a§p` message on login. Third-party mods add a dependency
(CLAUDE.md principle 9) and none documents the world map; skip them.

## Unknown / experiment candidates

1. Does `no_world_map` plus `no_minimap` visibly blank both screens in the pocket (owner's client, one screenshot)?
2. Does the 3 s refresh flicker the minimap? (assumed no)
3. Do the login codes still work on Minimap 26.4.2? (docs are unversioned; grep the jar for the code string.)
4. Which options the enforced server profile can force (a jar read of the profile schema).
5. Whether the pocket's cached map leaks layout to a player after leaving (cache test already says it is written).
