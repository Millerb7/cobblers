# Navigation: flag-driven waystones and map markers

**Status: design, for review (2026-09-13).**
- **Built:** the data, the generator and the headless proof.
- **Not placed:** no waystone, because town locations come after the next terrain
  rendition.
- **Vision:** `docs/vision/GAME_VISION.md` records the shift. This is an adventure map with
  speedrun and nuzlocke viability as goals, and navigation is waystone-only.

## At a glance

| Ask | Answer |
| --- | --- |
| **a.** A waystone per gym town, unlocked by that gym, stored in `data/progression.json` | **Built, unplaced.** One flag per gym, `gymN_cleared`, is the badge-ledger entry and the waystone unlock. `tools/progression_pack.py` generates the datapack. Eight towns have `position: null` |
| **b.** Which waystone mod, and can a datapack flag drive it? | **Waystones 21.1.37 (Balm). Yes, through commands, not config.** `waystones activate/forget @s <pos>` compile in a level-2 function (EXP-020 A). Nothing turns off activation by touch, so a one-tick resync undoes it |
| **c.** Hometown waystone; midpoint waystones | Analysed in §3, not decided. Both are one-line data changes |
| **d.** Prestige with other regions' leaders | **Mostly native.** RCT series already handle order, the level-cap reset, per-player eligibility and per-region badges, and the flags are keyed by slot with ids per series. The gap is the trainer spawner, which ignores series. §4 |
| **e.** What obstructs a fast clean run | 14 items in §5. The worst are Cobbleverse's leader chain against our town order, a random spawn roll at spawners, wild and craftable waystones, and uncued Nether/End gyms. Oak's speedrun toggle can run through a Cobblemon dialogue option |
| **f.** Server-pushed Xaero waypoints | **Neither jar has a waypoint packet.** A companion mod would be needed for silent, set-targeted markers. Two built-in routes exist (§6): activated waystones appear on the map automatically, and gym markers can be offered through a chat share the player accepts |

## 1. The model: one flag, three projections

```
RCT defeat of the slot's leader (series-specific id)
        │  advancement cobblers:flag/gymN_cleared   ← the flag (per player)
        ├── badge ledger      the flag is the record; the badge item is RCT loot
        ├── waystone          reconcile: activate if set, forget if not
        └── map               Xaero shows activated waystones (built in);
                              gym markers are offered on grant (§6)
```

### `data/progression.json` (schema `cobblers.progression/1`, validator-clean)

- **Flags:** `gym1_cleared` … `gym8_cleared` and `champion_cleared`.
  - Each flag has `set_by: {kind: "trainer_defeat", trainer_ids: {<series>: [ids]}}`.
  - Every flag carries the ids for kanto, johto, hoenn and sinnoh. They come from Cobbleverse's
    `requiredDefeats` chain in `COBBLEVERSE-RCT-DP-v20`.
  - The other `set_by` kinds are `run_start` (granted on the first tick) and `trigger` (set by
    `/trigger`, e.g. Oak's toggle).
- **Waystone on each gym flag:** `{town, position, dimension}`. The position is null until the
  town exists.
- **Chapters:** `chapter_1` … `chapter_8`, `league` and `postgame`. Each is unlocked by the
  previous flag.
  - They carry no `level_cap`, because RCT computes the cap per player (§4).
- **`active_series`:** `kanto`. `series[]` records RCT's `requiredSeries` order.

### `tools/progression_pack.py` → `build/datapacks/cobblers_progression` (disposable)

| File | Does |
| --- | --- |
| `advancement/flag/<id>` | `rctmod:defeat_count` with the active series' `trainer_ids` (or `minecraft:tick` / `minecraft:impossible`). Reward: `flag/<id>/granted` |
| `function/flag/<id>/granted` | runs `navigation/reconcile` as that player |
| `function/navigation/reconcile` | for each placed waystone: `execute if entity @s[advancements={…=true}] in <dim> run waystones activate @s x y z`, and the `forget` twin for `=false`. Unplaced towns become comments |
| `advancement/navigation/used_waystone` | `any_block_use` on `#waystones:waystones`. It revokes itself, tags the player and schedules `deferred` 1 tick later |
| `function/navigation/deferred` | reconcile for tagged players. **A touch on a locked waystone is undone** |
| `function/tick` / `load` | reconcile for anyone with `cobblers.left ≥ 1` (a `leave_game` stat, so it runs on rejoin); trigger objectives |

**Prestige** is `--series johto`: the same file with other ids (§4).

**Why not the activation stat:** the scoreboard criterion
`minecraft.custom:waystones.waystone_activated` does not exist on this server (EXP-020 C),
so a stat hook is impossible.

**Not verified (EXP-020 F, one player):**
- that the flag activates the waystone;
- that the one-tick resync really removes a touch activation;
- that rejoin reconciles.

## 2. Waystones: what ships and what must change

**Mod:** `waystones-fabric` 21.1.37 on Balm.

**Commands:**
- `waystones activate|forget <targets> <pos>`, `forget … all`, and `place`, `list`, `count`,
  `gui`, `cooldown`, `twinbound`;
- permission nodes `command.waystones.*`.

**Config that matters** (`config/waystones-common.toml`, as shipped):

| Key | Now | For this map | Why |
| --- | --- | --- | --- |
| `chunksBetweenWildWaystones` | 25 | **0** | New Nether and End chunks would grow free, uncued waystones outside the chain |
| `wildWaystonesDimensionAllowList` | end, overworld, nether | irrelevant at 0 | |
| `spawnInVillages` | REGULAR | **DISABLED** | same reason, in any newly generated village |
| `enableCosts` / `enableCooldowns` | false / false | keep | no XP cost and no waiting. The `warpRequirements` list is inert while costs are off |
| `defaultVisibility` / `allowedVisibilities` | ACTIVATION / none | keep | GLOBAL would give every town to everyone |
| `restrictedWaystones` | PLAYER | keep | |
| `inventoryButton` | "" | keep, or "ANY" as a reward decision | an inventory warp menu is fast travel from anywhere |

**Recipes (54 in the jar).** Anything a player can place builds a private network that
bypasses the chain:
- waystones (all variants), sharestones, portstones and warp plates;
- `portal_scroll` and `twinbound_feather`.

**Proposal:** remove those recipes in a datapack.
- **Decide separately:** `warp_stone`, `warp_scroll` and `return_scroll`. They only reach
  waystones the player has already unlocked, which suits speedruns and cuts backtracking. They
  also give a retreat from anywhere, which softens nuzlocke tension and gauntlet restrictions.
- **How to remove a recipe** in 1.21.1 Fabric: an override with a Fabric resource condition
  that never loads. **Not verified.**

## 3. Two open questions

### 3.1 Hometown waystone: given at start, or earned?

| | Given at start (`set_by: run_start`) | Earned |
| --- | --- | --- |
| **Chain** | The ledger gains one entry that is not a badge | Pure: every waystone is a badge. A hometown has no gym, though, so "earned" needs a non-gym flag, such as receiving the Pokédex from Oak or beating the rival |
| **Early game** | A return point from gym-1 town onward. It also teaches the waystone before it matters | No fast travel until gym 1. The first route is a one-way trip |
| **Speedrun** | Neutral. It helps only if the hometown holds something needed later (Oak, a shop, a healer) | Neutral, unless something needed later lives in the hometown. Then it forces a walk back |
| **Nuzlocke** | A free retreat and heal once gym 1 is unlocked. Less tension on routes 1–2 | More tension early, when teams are smallest |
| **Depends on** | Warp items (§2). Without them a waystone is reached only from another waystone, so at start it does nothing until gym 1 | the same |

**Dial:** given = easier early game; earned = harder.

**The deciding fact is what lives in the hometown after the opening.** If nothing later needs
it, the choice is flavour. If Oak's lab, the only healer or a tutor is there, "given" avoids
forced backtracking.

### 3.2 Waystones between gym towns, or only at them?

**Four settings, easiest last.** In the data model, a midpoint is either a flag-driven
waystone (reconciled) or a plain waystone left to discovery (not in `progression.json`).

| Setting | How | Speedrun | Nuzlocke | Pillar 1 ("go find an answer") |
| --- | --- | --- | --- | --- |
| **Gym towns only** | as built | Forward runs are unaffected; every trip back to an earlier route is on foot | Highest tension: routes cannot be skipped or retreated from | Answers must sit ahead of or on the path, or the walk back is the price |
| **Midpoints unlocked behind you** | a midpoint is tied to the flag of the gym *after* its route, so it opens once that route is finished | No forward skip; backtracking is cheap | Forward tension kept; farming earlier routes gets cheaper | Best fit: revisit earlier areas for counters quickly |
| **Midpoints by discovery** | vanilla Waystones behaviour, not reconciled | The first arrival activates one, and then it is a checkpoint | A retreat point inside the current route: lowest tension | Good |
| **Everything by discovery** | no reconcile | Towns reached before their gym become warp targets. Order is still enforced by RCT `requiredDefeats` | Lowest | Good, but route structure weakens |

**Interactions:**
- **Warp items** multiply every row. A warp stone makes each unlocked waystone reachable from
  anywhere.
- **Gauntlets and dungeons** that restrict retreat need warp use blocked inside them. There is
  no Waystones config for "no warping here". Candidates are a region check that clears the
  player's warp items, or no warp items at all. **Not verified.**
- **Route length.** The case for midpoints grows with the distance between towns, which is
  unknown until towns are placed.

## 4. Prestige: same towns, another region's leaders

Sources are jar and zip reads, not tested in game. Full notes: EXP-020 and the research file
the design was built from.

### What RCT already does

| Need | RCT today |
| --- | --- |
| Leader order per region | `requiredDefeats` chains in `mobs/trainers/single/<id>.json`. First leaders have none: `kanto_brock`, `johto_valerio`, `hoenn_petra`, `sinnoh_pedro` |
| Region unlocked after the previous one | `series/<id>.json` `requiredSeries`: johto needs kanto, hoenn needs johto, sinnoh needs hoenn. Switched per player (`rctmod player set series …`, or the Trainer Association) |
| Level cap restarts | Computed per player from the current series and its defeats (`LevelUtils.levelCap`). A series switch clears progress defeats and keeps `completedSeries`. The start is the series' `initialLevelCap`, else config 20. Johto's opener is level 18–20. **Restart not verified in game** |
| Eligibility | Checked per player at interaction: wrong series, missing defeats, over cap. Each has a dialog key (`wrong_series`, `missing_required_trainer_leader`, `over_level_cap`) |
| Badges | Per-region items (`CobbleverseBadges`), given by each leader's RCT loot table on first defeat |

### What the trainer schema supports

A trainer is up to four files sharing one id:
- **team:** `trainers/<id>.json`;
- **spawn and progression:** `mobs/trainers/single/<id>.json`, with `series`,
  `requiredDefeats`, `maxTrainerDefeats`, `battleCooldownTicks` and the rest;
- **rewards:** `loot_table/trainers/single/<id>.json`;
- **dialog:** `dialogs/trainers/single/<id>.json`.

That is fully data-driven, so another region's leader in town *N* is a datapack entry.

### What must be data-driven for a datapack swap, not a map rebuild

1. **Flags keyed by slot, ids per series.** **Done:** `data/progression.json`. The generator
   takes `--series`.
2. **Which trainer the town's spawner produces.** This is the gap: the spawner ignores series.
   `TrainerIds` is a set, but it shuffles and spawns the first id that passes basic checks, with
   no series or `requiredDefeats` check, and the trainer is shared.

   | Option | For | Against |
   | --- | --- | --- |
   | Both leaders in one spawner | nothing to switch | A random one appears. Players in the other series are refused and must wait for a respawn |
   | One spawner per series per gym, powered by a function | deterministic | Mixed-series groups need both powered at once, which is the case above again |
   | `data merge block` on `TrainerIds` when the whole group prestiges | one spawner | Group-wide only. Whether a spawner re-reads changed NBT is **not verified** |

   **Recommendation to test:** one spawner per series, gated by function. If a mixed group is
   real, test whether a spawner with both ids and a quick respawn is tolerable.
3. **Encounter answers per chapter.** Pillar 1 says every boss has answers in the reachable
   region. Johto's slot 1 is Flying (Falkner) where Kanto's is Rock (canonical types; the
   Cobbleverse teams were not checked). Route tables tuned for Kanto may lack Johto's answers.
   - Either chapter tables hold both,
   - or prestige adds spawns. Whether a Cobblemon spawn condition can read player progress is
     **unknown**; that is an experiment.
4. **Gym interiors.** Cobbleverse's regional gyms are whole type-themed buildings, and the only
   identity in their blocks is the spawner id (Brock's also has map-guide command blocks). Our
   towns need either type-neutral arenas or an interior template per series pasted by a
   function (`place template`), which is still a datapack swap.
5. **Cobbleverse's own unlock.** `defeat_champion_blue` runs `datapack enable
   COBBLEVERSE-Johto-DP.zip`, which brings worldgen and gym-map loot and asks for a restart. It
   must be overridden: prestige is a series switch, not a pack enable.
6. **The party.** A series switch resets the cap to 20, but players keep their level-60 teams.
   RCT refuses battles over the cap, so prestige means a new team from the same routes. That is
   a feature, provided the routes still spawn low-level answers (item 3).

**Verdict:** mostly native. The flags are ready. Two pieces are open: the spawner choice
(item 2) and per-series encounter answers (item 3).

## 5. Speedrun implications

**What a fast, clean run hits in the current plan:**
- **B:** blocks or forces a wrong trip;
- **W:** forces waiting;
- **S:** searching without a cue;
- **R:** breaks route structure.

| # | Issue | Kind | Fix |
| --- | --- | --- | --- |
| 1 | **Cobbleverse chains Kanto leaders** (`kanto_misty` needs `kanto_brock`, …). If our town order differs, a leader refuses, with `missing_required_trainer_leader` | B | Our trainer datapack sets `requiredDefeats` to our route order. The flags are slots, so nothing else changes |
| 2 | **Level-cap refusal.** In the EXP-013 session Brock would not battle a party with a level-26 Plusle. RCT has an `over_level_cap` dialog; whether it showed was not recorded | B, cue | Say the cap before the gym (a sign at the gym door, or Oak). Check the dialog text in EXP-020 F6 |
| 3 | **The spawner's spawn roll.** Unless the spawner is "boosted", spawning includes a level-difference chance roll, so a leader may take several attempts to appear | W | Measure time-to-spawn at a gym, and find how boosting is set. **Not verified** |
| 4 | `battleCooldownTicks 240` on leaders | W (after a loss only) | accept (12 s), or lower it in our trainer data |
| 5 | **Wild waystones** in new Nether and End chunks and villages | S, R | config (§2) |
| 6 | **Craftable waystones**, sharestones, warp plates, portal scrolls | R | recipe removal (§2) |
| 7 | **Broken finders:** `gym_map`, cartographer maps, LumyMon locators | S (false cue) | remove (`STRUCTURE_DATA_FALLOUT.md` §3) |
| 8 | **Blaine (Nether) and the League (End)** generate naturally; locators are removed | S | Record their positions from the audit (fixed by the carried seed); add a waystone and a marker in that dimension |
| 9 | **Touching a locked waystone** says "Activated" and then it disappears a tick later | cue | A plaque at each waystone: "opens when this town's gym is beaten" |
| 10 | **Time- or weather-gated species** as a boss's answer (Cobbleverse entries use `timeRange`, `isRaining`, sky light) | W | Rule: every required answer has an ungated source on the path. Check it when encounter tables are written |
| 11 | **Healing** only in some towns | B | a healer in every gym town, before the gym |
| 12 | **Cobbleverse's Blue unlock** enables a datapack and asks for a restart | W, B | override (§4 item 5) |
| 13 | **Riding and flight** (Cobblemon 1.8, patched for Cobbleverse seats) skip route geometry | R | a route-structure decision, not a speed obstruction. Gating flight by badge is possible design space. Mechanism **not researched** |
| 14 | **Town spacing and route length** | slow | cannot be assessed until towns are placed |

### The speedrun toggle: talk to Oak in the starting town

**Cobbleverse ships no Oak NPC.** Only a `lumymon:prof_oak_letter` item exists, and the
starting series comes from `starter_pack.mcfunction`. We author one.

**Mechanism** (bytecode read, not tested):
- A Cobblemon 1.8.0 NPC with `interaction: {type: "dialogue"}`.
- A dialogue page with an `option` input: "Enable speedrun mode?" Yes / No.
- **Yes:** `q.player.run_command('trigger cobblers.speedrun set 1')`.
  - `PlayerMoLangFunctions.run_command` runs with the player's own permission, and `/trigger`
    needs none, so no server-level command is involved.
  - The trigger sets the `speedrun_mode` flag (`set_by: trigger`, already supported by the
    generator).
- **Fallback if dialogue actions cannot run it:** a clickable `tellraw` offering
  `/trigger cobblers.speedrun set 1`.

**What the flag does.** Proposed, not built; `speedrun_mode` stays out of
`progression.json` until Oak exists.

| Rule | Why |
| --- | --- |
| Settable only before `gym1_cleared`, in the starting town: the trigger is enabled only for players without the flag and inside the town extent | a defined start; no mid-run switch |
| Irrevocable for that player | a clean ruleset |
| Start: store game time in a scoreboard on set. End: on `champion_cleared`, print the elapsed time | a defined end, measured in ticks, independent of real-time lag |
| All gym markers are revealed at once (§6) | runners route from knowledge anyway, and it saves eight clicks |
| Nothing else changes | Difficulty stays the same, so a speedrun and a normal run are comparable |

**Multiplayer:** the flag is per player. A co-op run is every player who set it before
leaving town.

## 6. Map markers (Xaero's)

### How server waypoints work in this pack (jar reads, EXP-020 E)

**Packets:**
- Minimap 26.4.2 registers only handshake, rules, tracked player, tracker reset and level map
  properties.
- World Map 1.44.2 registers only handshake, rules, tracked player and tracker reset.
- **Neither has a waypoint packet.** `ServerWaypointManager` is a deprecated client-side
  container with no network feed.

**So a server cannot silently create, update, remove or file a waypoint into a set.** That
would need a new client-and-server companion mod: new code, last on the preference list.

**Two built-in routes do exist:**
1. **Waystones compatibility** (`xaero/hud/compat/mods/SupportWaystones`).
   - Every waystone the player has activated becomes a waypoint automatically, and is removed
     on deactivation.
   - It has its own toggle (`discovered_waystone_waypoints`, on in the Cobbleverse profile).
   - Because activation follows the flag, **this layer is driven by the progression flags
     with no new dependency.**
2. **Chat share** (`WaypointSharingHandler`).
   - A system-chat message containing `xaero-waypoint:<fields>` shows as "Server shared a
     waypoint … [Add]".
   - Clicking opens the Add Waypoint screen, prefilled, with a set dropdown. The player
     confirms.
   - A `tellraw` can therefore **offer** a marker at a chosen moment. It cannot place one
     without the click, and it cannot take one back.
   - The field order, read from `WaypointSharingHandler` in xaerominimap 26.4.2 (2026-09-21):
     `xaero-waypoint:<name>:<initials>:<x>:<y or ~>:<z>:<colour 0-15>:<rotation>:<yaw>:Internal-overworld-waypoints`,
     name 1-32 characters and initials 1-3, with `:`, `-` and `_` rewritten, so our names use
     none. The client finds it anywhere in a system-chat line.
   - **Built:** `tools/progression_pack.py` offers gym *N+1*'s marker from `gymN_cleared`'s reward,
     to that player only (`data/progression.json` `gym_markers`). Cobbleverse's own gym maps
     (exploration maps to naturally generated gyms, which this world does not have) are emptied.

**Considered and rejected:** GLOBAL-visibility waystones as markers. They would show under
Xaero's "other waystones", but everyone can warp to them. The only way to stop that is an
unaffordable warp cost, and they would always show all towns.

### Design

| Layer | Contents | Mechanism | Driven by flags? |
| --- | --- | --- | --- |
| **Unlocked waystones** | every waystone the player has unlocked | built in (route 1); toggled in Xaero's waypoint settings | **yes, both ways** |
| **Gyms** (set "Gyms") | a marker at each gym town, independent of unlock | chat share on reveal (route 2). The player files it into a "Gyms" set; Oak's first-marker message says to create it | **when** it is offered, yes. Once added, the copy is the player's and never changes |
| **Landmarks** | none | not marked | n/a |

### Reveal schedule

**Recommendation: one gym ahead** in a normal run; all eight at once in speedrun mode.
- **One ahead.**
  - Gym 1's marker is offered by Oak at the start; gym *N+1*'s is offered when
    `gymN_cleared` is granted.
  - This keeps route structure readable ("this is where you go next") without laying out the
    whole region.
  - Gyms out of order refuse anyway (`requiredDefeats`), so revealing more invites wasted
    trips, not skips.
- **All at once for speedruns.** Runners plan the whole route, the refusals still enforce
  order, and it avoids a chat prompt at every gym.
- **Nuzlocke:** one ahead is enough. Knowing the next town lets players plan encounters
  without spoiling the region.

**Optional landmarks: leave them unmarked.**
- They are the reward pillar 4 keeps, and a marker turns discovery into a checklist.
- A landmark that has a waystone (a discovery midpoint, §3.2) marks itself once found, through
  route 1. That is exactly the "found it" moment.
- Nothing on the critical path is a landmark, so a speedrun needs no landmark marker.

### One source of truth?

| Marker | Source of truth | Can it drift from the flags? |
| --- | --- | --- |
| Unlocked waystones | the flag → activation → Xaero | no. A revoke forgets the waystone, and Xaero removes it |
| Gym markers | the flag decides when they are offered; the player owns the copy | Only if a town moves after players added markers, or a flag is revoked. Prestige reuses the same towns, so markers stay correct across series |

**Answer:** yes for waystones, which are the travel state. For gym markers the flags are the
single source of what is offered and when; the client's copy is a one-way projection.

## 7. Not verified, and what runs next

| Item | Where |
| --- | --- |
| Flag grants activation; a touch is undone; rejoin reconciles; Xaero draws and removes the waypoint | EXP-020 F1–F4, one player |
| Chat-share payload format | EXP-020 F5 |
| `over_level_cap` dialog text; time-to-spawn with the spawn roll | EXP-020 F6, and a gym timing |
| Cobblemon dialogue `q.player.run_command('trigger …')` | a small Oak NPC probe when Oak is built |
| Removing a recipe with a never-loading resource condition | a headless reload probe, like EXP-020 |
| Spawner re-reading changed `TrainerIds`; the level cap restarting on a series switch | a prestige probe before any prestige content |
| `count` semantics on `rctmod:defeat_count` (the generator omits it) | EXP-020 F3 |
| Whether a spawn condition can read player progress (prestige answers) | a research question, then an experiment |

**Standing rules:**
- Nothing here places a waystone.
- Town positions, and so every `position`, arrive with the town list after the next terrain
  rendition. Then `python tools/progression_pack.py` regenerates the pack.
