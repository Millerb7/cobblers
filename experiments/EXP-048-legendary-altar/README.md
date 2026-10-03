# EXP-048 — does a pasted LumyMon altar FUNCTION?

**Status: NOT_EXECUTED — blocked on a permission, 2026-10-01.** Designed and ready to run; nothing has
been placed and nothing has been observed.

## Why it decides more than it looks like it does

`data/adopted_legendary_sites.json` carries **four** adopted Cobbleverse structures — the Mew temple, the
Crown Cemetery, the Zapdos tower and (2026-10-01) the Articuno shrine. Every one of them carries a LumyMon
altar as its payload:

| Site | Template | Altar block |
|---|---|---|
| `adopted_mew_temple` | `cobbleverse:mythical/mew` | — (mythical, see note) |
| `adopted_crown_cemetery` | `cobbleverse:crown_cemetery` | `lumymon:calyrex_statue`, `lumymon:summon_trigger`, `lumymon:summon_anchor` |
| `adopted_zapdos_tower` | `cobbleverse:legendary/zapdos` | `lumymon:zapdos_altar` |
| `adopted_articuno_shrine` | `cobbleverse:legendary/articuno` | `lumymon:articuno_altar` |

**If the altars are silent, all four are scenery**, and the question the owner asked on 2026-10-01 —
whether to import more of Cobbleverse's legendary prebuilds — has a different answer than if they work.
That is the whole reason this runs before any more of the catalogue is adopted.

It does **not** block placing them. `data/adopted_legendary_sites.json` `a_dead_altar_must_not_block`
already states the rule: nothing in the campaign may require any altar to work, and every site is authored
as a place to find with its reward in the template itself. So a silence is a disappointment, not a breakage.

## Method

A disposable world only — the staging universe, never `cobblers-10240`. `enable-command-block=true`.

**1. Place.** The Crown Cemetery first, because its brushable gravel is a reward that does not depend on
the altar, so the paste is worth something either way:

```
forceload add 4118 1982 4162 2028
place template cobbleverse:crown_cemetery 4118 109 1982 none none
```

A failure here is itself the result: it would mean the Cobbleverse datapack is not loaded on the staging
server, which nothing has checked.

**2. Are the blocks present?** Counting over RCON is destructive and then restored — `/fill <volume> air
replace <id>` reports how many it removed, and `/place template` puts the structure back. The volume is
45 x 24 x 47 = 50,760 blocks, over the 32,768 fill limit, so each count splits in z at z2005.

```
fill 4118 109 1982 4162 132 2005 air replace lumymon:summon_trigger
fill 4118 109 2006 4162 132 2028 air replace lumymon:summon_trigger
```

…repeated for `lumymon:calyrex_statue` and `lumymon:summon_anchor`, then:

```
place template cobbleverse:crown_cemetery 4118 109 1982 none none
forceload remove 4118 1982 4162 2028
```

**3. Does it answer?** **This half has always needed a player and cannot be done over RCON at all.** Stand
at the altar and right-click it with an empty hand. Then with a filled hand. Record *any* response: a
sound, a particle, a chat line, a change of block state, an inventory, nothing.

**4. Does a brush on the gravel roll the loot tables?**

**5. Does the chunk log an error?** Read the server console around the placement.

## What counts as a pass

**Placing is not a pass.** Placing already succeeded on this runtime for
`legendarymonuments:firescourge_shrine` (STRUCTURE_WORKFLOW.md:90). The result wanted is a **block
response** or a **confirmed silence** — both are useful and only one of them is good news.

## Then

- **If it is silent:** the four sites stay what they are authored as — places. The catalogue question is
  settled on those terms, and `stark_mountain`, `crown_spire` and the lake trio are judged as scenery
  rather than as encounters.
- **If it answers:** the next question is the activation item, and after that the level cap, and neither
  is settled by this experiment.

## Why it has not run

Two independent reasons, and the second is the binding one:

1. **Step 3 onward needs a player.** Right-click with an empty hand is not something RCON can do, so the
   half that actually answers the question was always the owner's.
2. **Steps 1 and 2 were refused.** On 2026-10-01 the attempt to drive them over RCON was denied by the
   permission classifier as *Remote Shell Writes*. That is a refusal of the outcome, not of the command's
   shape, so the attempt ended there and was not retried by another route. It needs either a Bash
   permission rule for the RCON path or the owner running the commands in-game.

Nothing was placed. Nothing was observed. Every line above is design.

## What the jars say (offline, 2026-10-02)

Read from `LumyMon-0.6.6.jar` and `COBBLEVERSE-DP-v31.zip` with `zipfile` only; detail and sources in
`docs/research/notes/lumymon-altars.md`. Nothing below was run in game.

- **The altars carry no state a paste could miss.** None of `articuno_altar`, `zapdos_altar`, `mew_shrine`,
  `calyrex_statue`, `summon_trigger`, `summon_anchor` is a block entity (VERIFIED, `ModBlockEntities`), and no
  altar class names a structure, biome, advancement, time or weather (VERIFIED as absence of strings). The
  "worldgen-time state" fear has no support in the jar. **The expected answer is that a pasted altar works,
  or fails for one of the reasons it prints.**
- **Activation items** (VERIFIED): Articuno `lumymon:glacier_feather`, Zapdos `lumymon:thunder_feather`,
  Mew `lumymon:origin_fossil` (crafted), Calyrex `lumymon:calyrex_crown`, Spectrier: a `lumymon:shaderoot_carrot`
  **dropped as an item onto `summon_trigger`** (Glastrier: `iceroot_carrot`). The feathers and the crown ship
  **inside the templates' barrels**, and the cemetery's shaderoot crop is pasted at `age=7`.
- **The refusals print in chat**, so the probe distinguishes them: "This altar requires a %s to activate"
  (wrong item), "Summon Anchor not found near the Altar" (no anchor), "You do not have permission to use this
  altar" (`lumymon.altar.use`), and the `pokemon_already_nearby` line. **Articuno, Zapdos and Mew templates
  contain no `summon_anchor`**, and whether those altars require one was not readable: the most likely failure.
- **Levels** (VERIFIED, class strings): Articuno and Zapdos 50-60, Mew 75-90, Calyrex 70, Spectrier 50-70. The
  "70-90" in `data/adopted_legendary_sites.json` is wrong for the birds.
- **Mew's command blocks gate the door, not the shrine**, and `enable-command-block=false` on the server
  (`server.properties:10`), so as things stand the door never opens. No template carries a data marker.
- **There is no fake player** (no Carpet or bot mod among 102 jars). A right-click still needs a human. The one
  exception is the trigger, which may be drivable from the console.

### Probes this implies, in order

1. **No block entity** (RCON; expect "The target block is not a block entity"):
   `data get block <statue x y z>`. If it returns NBT, the note is wrong and everything below needs re-reading.
2. **Statue state** (RCON): `execute if block <x y z> lumymon:calyrex_statue[has_crown=false]` before step 4,
   `[has_crown=true]` after.
3. **Console-only Spectrier** (RCON, no player): with the anchor and trigger pasted,
   `summon minecraft:item <trigger x> <trigger y+1> <trigger z> {Item:{id:"lumymon:shaderoot_carrot",count:1}}`,
   then `execute if entity @e[type=cobblemon:pokemon,x=<x>,y=<y>,z=<z>,distance=..32]` and read the console for
   "Summon Anchor not found near the Altar" or "Error executing pokespawn command". A Spectrier here answers
   "pasted LumyMon blocks function" without a human.
4. **Player, Crown Cemetery:** take the crown from the barrel; right-click the statue empty-handed (expect the
   crown requirement line), then with the crown. Record the exact chat line.
5. **Player, Articuno** (`place template cobbleverse:legendary/articuno ...`): take the feather from the barrel;
   `clear <player> lumymon:glacier_feather 0` (counts, removes nothing) before and after the right-click to see
   whether it is consumed. If chat says "Summon Anchor not found", `setblock` a `lumymon:summon_anchor` beside the
   altar and retry: that separates "pasted altars are dead" from "pasted altars need an anchor the template lacks".
6. **Permission:** repeat 4 or 5 as a non-op. A permission line means the default is `false` and no provider is
   installed to grant it.
7. **Server console** around every click: `Summoning failed: {}` is LumyMon's own log line for a `pokespawnat`
   that Cobblemon 1.8.0 rejected.

## Results, 2026-10-02 (01:53-02:05), the console half

**Runtime:** Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0, LumyMon 0.6.6, COBBLEVERSE-DP-v31,
staging universe `staging-2026-10-01` booted with `--universe` (never `cobblers-10240`), coordination lock held.
Every coordinate below is template position + corner, read from the template files themselves.

| Probe | Result |
|---|---|
| `place template cobbleverse:crown_cemetery 4118 109 1982 none none` | **placed** - so the Cobbleverse datapack IS loaded on staging, which nothing had checked |
| the eight LumyMon blocks at their template positions (statue (4140,112,2005), anchor (4153,112,1999), five triggers round it, carrot crop (4156,111,2009) age 7) | **all eight present** |
| `data get block` on the Calyrex statue | "The target block is not a block entity" - **matches the jar** |
| a shaderoot carrot summoned onto the trigger ring, twice, plus once inside the trigger's own block space | **nothing.** No Spectrier within 48 blocks (selector keyed on SPECIES, not distance, so a wild Pokemon cannot fake a pass), the carrots were NOT consumed, and the console logged nothing from LumyMon about summoning. The carrots rest at y111.875: the trigger has no collision, so they fall through it onto the block below while still overlapping the trigger's space. |
| `place template cobbleverse:legendary/articuno 904 151 320 none none` | **placed**; `lumymon:articuno_altar` present at (914, 153, 331) |

**What this does and does not show.** A console-summoned item entity does not fire the Spectrier trigger.
That is NOT proof the trigger is silent: it may require an item a PLAYER threw (the thrower is part of an
item entity), which RCON cannot fake. The right-click altars cannot be exercised from the console at all.

**The finding that matters more than the probe.** The activation items for three of the four altars do not
exist in obtainable form: across all 102 mod jars and every server datapack, no recipe or loot table makes a
`glacier_feather`, `thunder_feather` or `calyrex_crown`, and the templates' barrels do not hold them
(measured; `docs/research/notes/lumymon-altars.md`, head). So **as the sites stand, Articuno, Zapdos and
Calyrex cannot be summoned in normal play even if their altars work: in practice those three are scenery.**
Mew's `origin_fossil` has a recipe; the cemetery's Spectrier route has its own carrot crop.

## The owner's half - in-game, both sites are now standing in staging

1. **Spectrier**, at the Crown Cemetery (4118-4162, 109-132, 1982-2028): harvest the carrot crop at
   (4156, 111, 2009), then THROW a carrot onto the trigger ring round (4153, 112, 1999). Note any chat line.
2. **Articuno**, at its adopted site, altar at (914, 153, 331): `/give @s lumymon:glacier_feather`, then
   right-click the altar, first empty-handed, then holding the feather. Record the exact chat line. If it says a
   Summon Anchor is missing, `/setblock 915 153 331 lumymon:summon_anchor` and try again.
3. **Calyrex**, at the cemetery statue (4140, 112, 2005): `/give @s lumymon:calyrex_crown`, then right-click it.

Three test carrots tagged `exp048_carrot`, `exp048_carrot2` and `exp048_carrot3` were left by the ring with
pickup disabled. They are evidence, harmless, and despawn on their own.

## Result, the owner's half (reported by the owner in chat, 2026-10-02)

- **Calyrex, at the pasted Crown Cemetery statue (4140, 112, 2005): given the crown, it WORKED** ("i gave the calyrex
  the crown and it worked", the owner, 2026-10-02). So a raw-pasted LumyMon right-click altar functions on Cobblemon
  1.8.0 / LumyMon 0.6.6 in staging. The owner also reports that pasted altars work in general, and that the earlier inert
  results came from our own tooling: `/clone` dropping shrine blocks, a missing ritual block, and a shrine placed 71
  blocks from its record. **Those three are not yet recorded in any file this session could read**; the chat line, the
  item used and whether the crown was consumed should be written here by whoever ran it.
- Still not recorded: the Spectrier thrown carrot (step 1), Articuno's feather (step 2).
- **Consequence for play is unchanged:** the crown has no recipe or loot source, so in normal play Calyrex needs the
  campaign to hand the crown out, as the feathers will be.
