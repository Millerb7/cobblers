# EXP-013 D and E: player session on cobblers-10240

About 15 minutes with one player (the server's op). Everything below is already built and
configured on `cobblers-10240`; you only start the server, join, and type commands.

## What D and E test, and why they matter

**The background.** Part A showed that no placement method gives a hand-built structure any
structure data: the game has no record that a village or gym is there. D and E ask what that
costs in the two places it matters most.

**D: do Cobblemon spawns that require a structure work at a hand-built one?**
- **The question.** Cobblemon spawn entries can say "only inside a village", "only inside a
  ruined portal", and so on. 318 entries (89 species) require a village, and more require
  ruins, mansions and shipwrecks. D checks whether those entries fire inside a structure we
  pasted.
- **The prediction.** They do not, because Cobblemon reads the chunk's structure data and
  pasted chunks have none. A natural structure in the Nether is the control that proves the
  test itself works.
- **Why it matters.** If pasted structures cannot host these spawns, a town cannot be "a
  village" to Cobblemon. Its Pokémon have to come from region spawn tables or Habitat Blocks.
  That decides what a town is in the data model (Part 2e).

**E: does a gym's trainer spawner work when the gym is pasted?**
- **The question.** Every Radical Cobblemon Trainers gym leader appears from a trainer
  spawner block inside the gym. E checks that a pasted Brock gym spawns Brock, and that a
  spawner we set ourselves does the same.
- **The prediction.** It does. The spawner needs only its own block data and redstone power,
  not structure data.
- **Why it matters.** If it works, gyms are just builds we paste or author, and the trainer
  system is unaffected. If it fails, every gym needs a different mechanism before any town is
  planned.

## Already done for you

| What | Where | Details |
| --- | --- | --- |
| Test datapack `exp013de` | enabled in the world | three spawn entries, all common bucket, weight 1000, species that never spawn naturally: **Dracozolt** (no condition: proves the datapack works), **Arctozolt** (requires `#minecraft:village`), **Dracovish** (requires `#minecraft:ruined_portal`) |
| D1: pasted village square | 3336, 119, 3323 | `minecraft:village/plains/town_centers/plains_meeting_point_1`, placed with `/place template`; marker post with a sign at 3333, 119, 3320 |
| D2: pasted ruined portal | 3290, 118, 3194 | `minecraft:ruined_portal/portal_1`; marker post at 3287, 118, 3191 |
| D3: natural ruined portal (control) | Nether, 147..152, 51..60, 18..22 | vanilla generated; its chunk holds a `ruined_portal_nether` start (checked in the region file). Stand on soul sand at 150, 55, 20 |
| D4: natural warped village (control) | Nether, bells at −708/−700, 35, −672 | Repurposed Structures `village_warped`, which is in `#minecraft:village` (checked with `/locate`); 36 chunks hold references. Stand at −704, 33, −670 |
| E1: pasted Brock gym | 3553, 130, 3184 | `cobbleverse:brock` via `/place template`; its spawner at 3559, 131, 3196 has `TrainerIds ["kanto_brock"]`, powered by the template's redstone block, 2 air above. Marker post at 3566, 130, 3172 |
| E2: authored spawner | 3191, 116, 3554 | a bare `rctmod:trainer_spawner` set by command with `TrainerIds ["kanto_brock"]` on a redstone block; 520 blocks from E1, so RCT's 151-block uniqueness check cannot block it. Marker post at 3191, 116, 3540 |
| Game rules | world | `doPokemonSpawning false`, `doMobSpawning false`, `doDaylightCycle false`, `doWeatherCycle false`, time noon, clear weather. All four were `true` before; the restore commands are at the end |
| Backup | `cobblers-server-retired/exp013de-site-backup/` | region, entities and poi `r.6.6.mca` from before the builds; all four overworld sites are in that one region |

**Not changed:** `enable-command-block` stays false, so the Brock gym's map-guide command
blocks are inert and cannot fire.

**Checked when prepared:** both spawners report `powered=true, inverted=false`, and all
three sites are `minecraft:plains`.

## Before you start

1. Start the server (or ask me to):
   ```
   cd C:\Users\wnd\Documents\github\cobblers-server
   java -Xms4G -Xmx10G -jar fabric-server-launch.jar nogui
   ```
2. Join `localhost`. You are the server's only op (level 4); every command below needs that.
3. Keep this file open, and have a text file ready to paste results into.

**Reading results:** `/checkspawn common` prints the species that could spawn around you in
the common bucket, with percentages. You only care whether **Dracozolt**, **Arctozolt** and
**Dracovish** appear in the list.

## Part D (about 6 minutes, creative mode)

```
/gamemode creative
```

### D0: prove the test works (at spawn)

**Do:**
```
/tp @s 3400 122 3400
/checkspawn common
```
**Observe:** is Dracozolt in the list?

| Result | Meaning |
| --- | --- |
| Dracozolt listed | the datapack is live; continue |
| Dracozolt missing | **stop.** The test datapack did not load, so nothing below means anything. Tell me |

**Also note:** Arctozolt and Dracovish should be absent here. There is no structure of any
kind at spawn.

### D1: pasted village square

**Do:**
```
/tp @s 3341 126 3328
```
Fly down onto the paved square inside the village centre (next to the marker post that says
"EXP-013 D1"). Standing on the ground, run:
```
/checkspawn common
```

| Result | Meaning |
| --- | --- |
| Dracozolt listed, **Arctozolt absent** | **D1 behaves as predicted:** a pasted village is not a village to Cobblemon |
| Arctozolt listed | **prediction wrong:** a pasted village does count. Big news for Part 2; tell me |
| Dracozolt absent | invalid reading; move a few blocks and retry once |

### D2: pasted ruined portal

**Do:**
```
/tp @s 3293 126 3197
```
Fly down to the ground among the portal blocks (post "EXP-013 D2"). Then:
```
/checkspawn common
```

| Result | Meaning |
| --- | --- |
| Dracozolt listed, **Dracovish absent** | **D2 as predicted** |
| Dracovish listed | prediction wrong; tell me |

### D3: natural ruined portal in the Nether (the control)

**Do:**
```
/execute in minecraft:the_nether run tp @s 150 55 20
/checkspawn common
```
You arrive standing on soul sand next to the obsidian and crying obsidian of a vanilla ruined
portal.

| Result | Meaning |
| --- | --- |
| **Dracovish listed** | **control PASS:** the test detects a real structure, so D2's absence is meaningful |
| Dracovish absent | **control FAIL:** the probe cannot see even a natural structure. D1 and D2 are then inconclusive. Also try one block onto the portal frame and run it again before recording a fail |

### D4: natural warped village in the Nether (the village control)

**Do:**
```
/execute in minecraft:the_nether run tp @s -704 33 -670
/checkspawn common
```
You arrive between the village's two bells.

| Result | Meaning |
| --- | --- |
| **Arctozolt listed** | **control PASS** for the village tag |
| Arctozolt absent | control FAIL for villages; D1 is inconclusive |

### Part D verdict

| D1 and D2 | D3 and D4 | Verdict |
| --- | --- | --- |
| both absent | both listed | **CONFIRMED:** structure-gated spawns do not work at pasted builds |
| either listed | either | **REFUTED:** pasted builds satisfy structure conditions |
| both absent | either absent | **INCONCLUSIVE:** the control failed |

Part E's first command takes you back to the overworld; no separate step is needed.

## Part E (about 7 minutes, survival mode)

### Setup (30 seconds)

```
/execute in minecraft:overworld run tp @s 3566 130 3175
/gamemode survival
/effect give @s minecraft:resistance infinite 4 true
/pokegive geodude level=15
/give @s rctmod:trainer_card
```
- **Survival:** RCT spawners look for the nearest player, and creative players may not count.
- **Geodude:** gives you a party, so RCT sees a player level above 0 and a battle can start.
- **Trainer card:** only matters for RCT's natural spawns, but removes one variable.

### E1: pasted Brock gym

You are 22 blocks from the spawner (range is about 46), just outside the gym next to the
"EXP-013 E1" post. **Wait 60 seconds without moving far.**

Then run:
```
/execute if entity @e[type=rctmod:trainer,distance=..50]
```

| Result | Meaning |
| --- | --- |
| `Test passed, count: 1`, and Brock stands on the spawner inside the gym (3559, 132, 3196) | **E1 PASS** |
| `Test failed` | walk inside to within 10 blocks of the spawner, wait another 60 seconds, run it again. Still failed: **E1 FAIL** |

**Bonus E1+ (1 minute).** Walk up to Brock and right-click him. He may also start the battle
himself if you look at each other.

| Result | Meaning |
| --- | --- |
| The battle screen opens | **E1+ PASS** |
| A chat message refuses the battle | record the exact text |

To end the battle, forfeit from the battle menu, or run `/stopbattle`.

### E2: authored spawner (the way we would build our own gyms)

```
/execute in minecraft:overworld run tp @s 3193 116 3540
```
You are 14 blocks from the bare spawner, next to the "EXP-013 E2" post. **Wait 60 seconds.**
Then:
```
/execute if entity @e[type=rctmod:trainer,distance=..30]
```

| Result | Meaning |
| --- | --- |
| `Test passed, count: 1`, and a Brock trainer stands on the spawner at 3191, 117, 3554 | **E2 PASS** |
| `Test failed` | step onto the spawner's neighbour block, wait 60 seconds, run it again. Still failed: **E2 FAIL** |

### If you need to redo an E attempt

```
/kill @e[type=rctmod:trainer]
```
Walk 60+ blocks away and back, then wait 60 seconds.

### Part E verdict

| E1 | E2 | Verdict |
| --- | --- | --- |
| PASS | PASS | **CONFIRMED:** trainer spawners work in pasted and in authored builds |
| PASS | FAIL | pasted gyms work; our own spawner setup is missing something. Tell me |
| FAIL | any | **REFUTED** for pasted gyms. Every gym needs another mechanism |

## After the session (1 minute)

Restore the game rules and turn the probes off:
```
/kill @e[type=rctmod:trainer]
/gamemode creative
/gamerule doPokemonSpawning true
/gamerule doMobSpawning true
/gamerule doDaylightCycle true
/gamerule doWeatherCycle true
/datapack disable "file/exp013de"
```
Then stop the server (`/stop`, or ask me).

The test builds stay in the world until I restore region `r.6.6` from the backup, which I do
with the server stopped. That only needs doing before any real building happens there. The
two Nether controls are vanilla terrain and stay.

## Report back

Paste this, filled in. Copy each `/checkspawn` list as it appeared, or a screenshot.

```
D0 spawn:        Dracozolt [yes/no]  Arctozolt [yes/no]  Dracovish [yes/no]
D1 village:      Dracozolt [yes/no]  Arctozolt [yes/no]
D2 portal:       Dracozolt [yes/no]  Dracovish [yes/no]
D3 nether portal:Dracozolt [yes/no]  Dracovish [yes/no]
D4 nether village:Dracozolt [yes/no] Arctozolt [yes/no]
E1 pasted gym:   trainer after 60s [yes/no]  after moving closer [yes/no]  battle opened [yes/no/not tried]  message text:
E2 authored:     trainer after 60s [yes/no]  after moving closer [yes/no]
Anything odd:
```
