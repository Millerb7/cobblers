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
