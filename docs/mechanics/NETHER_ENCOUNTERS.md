# The Nether's encounters: five biomes, three dungeons, and Poipole's home

**Status: DESIGN DRAFT (trainer-balance-designer).** Nothing here is built, compiled, installed or seen in game.
It answers the owner's decision of 2026-10-10 (`docs/STATE.md:149` items 6 and 7): "the Nether gets its own
encounter design by biome, NOT all fire, dungeons themed rather than typed, late-game levels and gating, designed
before it is built", and "Poipole gets a natural home (it is a starter)". The environment clock reads 2026-10-08,
while the newest repository records are dated 2026-10-11; dates below are the records' own.

Every foundational mechanic this design rests on in the Nether is unproven: Nether spawning under our compiler, the
gate, the inherited-pool replacement. By the agent's own rule the whole document is therefore a **draft**. Section 6
lists the experiments that turn it into content.

Labels: **VERIFIED** = read in a file, a jar listing recorded in `docs/research/`, or a run, with the citation;
**ASSUMED** = inferred and not checked; **INFERRED** = reasoned from read code, not run; *relayed* = a number taken
from another document and not re-measured here.

---

## 0. Premises checked (four are wrong or incomplete)

| # | Premise (from the brief) | Finding |
|---|---|---|
| P1 | "The Nether is late-game" | **Wrong today.** Nothing gates it. It opens with the first obsidian: "Nether: after badge 6. They need obsidian ... Nothing stops an earlier trip" (`docs/world-building/DIMENSIONS_AND_BORDERS.md:279-281`), and the standing recommendation is "optional exploration opened by obsidian, which fits **mid-game**" (`:241-242`). Section 1 proposes the gate. |
| P2 | "The Nether override removed Poipole's only natural spawn" | **Half right, wrong dimension.** Poipole's one spawn file, `cobblemon:0803_poipole`, spawns via the **End's** Dawn and Dusk towers (`data/structures.json:5264-5297`, `spawn_via cobbleverse:dawn_tower`; the Dusk record at `:5336-5347`). The END half of the override zeroes those two sets (`data/dimension_overrides.json:50-69`). The spawn was already dead before that: no player can reach the End (`data/adopted_legendary_sites.json:520`), and our pasted overworld copies are templates, not structures, so "Pasted, no Poipole spawns there" (`:531`, `:597`). |
| P3 | "`dimension_overrides.json`'s `not_covered` names Poipole" | **Not in this checkout.** `not_covered` lists `cobbleverse:sandra`, `cobbleverse:johto_league` and `cobbleverse:mythical/deoxys` only (`data/dimension_overrides.json:101-123`). Poipole is named in the morning report (`docs/MORNING_REPORT_2026-10-11.md:39`, N141). |
| P4 | "Entei's room should read as something other than a fire room" | **The built room is a fire room.** Nether-brick walls and ceiling, polished blackstone floor, a crying-obsidian frame, shroomlight lamps (`data/entei_boss.json:71-79`). The key is "Ember Sigil": "Eat it in the Nether, and the heat answers" (`:32-33`). The text is fire throughout: "the heat takes you", "Entei rises out of the embers" (`:142-152`). The drop table is "fire-themed battle items" (`:110`). **The machinery is theme-neutral**: pocket slots, the keeper, the lockout, the catch key. Only the palette, the text and the drop table need to change (section 3.1). |

Two findings from reading the spawn tools. They decide how a builder must do this (section 7).

- **F1. The suppression already strips inherited Nether spawns, but only where the overworld's boxes lie (INFERRED,
  not run).** `tools/suppress_inherited_spawns.py` re-emits **every** inherited `spawn_pool_world` file. On each
  spawn detail it sets anticonditions that are plain `minX/maxX/minZ/maxZ` boxes with no dimension
  (`:198`). It runs with `--subregions`, so the boxes are the route corridors plus every sub-region polygon
  (`tools/reapply.py:1340-1341`). Cobblemon compares coordinates against the spawn position, whatever the dimension
  (`docs/research/notes/underground-biomes.md:103-110`; `dimensions` is a separate field). So every inherited Nether
  spawn is suppressed at any Nether x/z that an overworld sub-region covers. That includes Nether x/z 0..1024, the
  part a portal from the landmass reaches (*relayed*, `DIMENSIONS_AND_BORDERS.md:102-103`). Inherited Nether spawns
  survive only further out. Nobody chose this. How much of that square the merged boxes actually cover is not
  measured.
- **F2. Our compiler would empty a Nether table.** `tools/compile_spawns.py` `box_condition` forces
  `canSeeSky: true` on every grounded entry (`:84-86`). Below the Nether's roof a column cannot see the sky
  (INFERRED from vanilla's heightmap rule, not run). The Nether tables need their own condition shape.

---

## 1. Gating and the level band

### The caps (read)

| Beaten | Cap | Source |
|---|---|---|
| nothing ... gym 7 | 20, 25, 30, 35, 40, 45, 50, 55 (next leader's ace) | `data/trainers.json:14-23` `gym_ace_levels`; `docs/mechanics/LEAGUE_LEVEL_CAP.md:50-52` |
| gym 8 (Giovanni), and Lorelei, Bruno, Agatha | **60** | `LEAGUE_LEVEL_CAP.md:53-54` |
| Lance | **62** | `:55` |
| Blue (Champion) | **100**, no cap | `:56` |

The overworld's top wild band is tier 9 (Victory Road and the Rift): **52-60**, with heart presences up to **62**
(`docs/mechanics/ENCOUNTER_DESIGN.md:36-41`, `:273`). **Measured here: no entry in `data/spawns.json` starts or
ends above level 62** (grep for `"level": "6[3-9]..."`, `"level": "...-6[3-9]|7x..100"`: 0 matches), and no
`data/encounter_design.json` table's `levels` starts above 62. **Nothing wild exists for a post-Champion player
(cap 100).**

### The gate (proposed)

**G1. Entry needs `cobblers:flag/gym8_cleared`.** That is the flag the finale gate already uses (`docs/STATE.md:142`
item 1).
- **Mechanism:** a vanilla advancement on `minecraft:changed_dimension` (to `minecraft:the_nether`) runs a function
  as the player. Without the gym-8 flag, the player is returned to the overworld with one line ("The heat turns you
  back. Eight badges first."), and the advancement is revoked so it fires again next time.
- **Where the player is returned to:** their blackout checkpoint, falling back to `data/blackout.json`
  `pallet.position`, the fallback `data/entei_boss.json:140` already uses.
- **Status:** ASSUMED. The trigger is vanilla, but it is not in `docs/research/`, and the return needs the
  dimension-safe selector pattern that `data/entei_boss.json:51` records from EXP-047. Experiment N5.
- **Why gym 8:** it makes the Nether the leg after the gyms, beside Victory Road, and it prepares the Elite Four.
  The cap on arrival is 60 for every player who can enter. Gym 7 (cap 55) would make the Nether a side trip of the
  same leg as the Craters.
- **What it gates, and what that costs** (cross-system, each checked):
  - **Fire Stones.** The Nether holds the game's only stone ore (`STATE.md:347`). The same line records **0 Fire
    Stone uses** among the catchable overworld families, so gating it breaks no family.
  - **Netherite.** It is the Entei key (`data/entei_boss.json:41`, post-Champion anyway) and the currency of the
    late barter lines (`data/direct_trades.json:109-114`, a Master Ball for netherite). Gating the Nether makes them
    late in fact, which is what "late-game items by direct trade" asked for (`STATE.md:141` item 5).
  - **Blaze rods for eyes of ender.** End access is post-game by decision (`DIMENSIONS_AND_BORDERS.md:338`), so
    this is unaffected. The "gym-7 Nether trip" in `:294-296` is superseded.
  - **The Ruinous shrines** move behind badge 8 with everything else. That is wanted: a free Chi-Yu at badge 6 is
    the "unearned legendary" the override was built to stop (`data/dimension_overrides.json:5`).
- **Multiplayer:** the gate is per player, like the cap. A friend without the eighth badge cannot follow through a
  shared portal. That is consistent with per-player RCT caps; the owner should know it before a co-op night.

**Fallback if N5 fails:** a soft gate by levels alone. The bands below hit a gym-6 party hard, but nothing stops a
player mining netherite at badge 4. That fallback does not make the Nether late-game, only dangerous.

### Two rings, two bands (proposed)

The Nether has no heightmap, no routes and no sub-regions, so its only spatial handles are dimension, biome, Y, light,
nearby blocks and coordinates. Coordinates give it a shape: **the part under the landmass, and the rest.**

| Ring | Nether x/z | Tier | Base band | Heart presences | Who catches |
|---|---|---|---|---|---|
| **Near Nether** | -128..1152 (the landmass /8 with its margin, *relayed* `DIMENSIONS_AND_BORDERS.md:102-103`) | **10** | **54-60** | the band's top to **62** | everyone the gate admits (cap 60; 62 after Lance) |
| **Deep Nether** | everything else inside the border (-1024..9215, `data/dimension_overrides.json:126-128`; the centre/8 reading is INFERRED there) | **11** (postgame) | **65-75** | 75-**85** | after the Champion only (cap 100) |

- **Why 54-60 near:** it is level with Victory Road's top, two levels above its floor. The Nether is entered at the
  same cap as Victory Road, so it cannot honestly go higher and stay catchable. It feels later because every family
  is mature: maturity **0.9** at tier 10, against 0.85 at tier 9 (`ENCOUNTER_DESIGN.md:63-65`).
- **Why a postgame ring:** it fills a measured gap (above: nothing wild over 62). The deep Nether is already where
  "a portal ... exits at an overworld position the border clamps to its edge" (`DIMENSIONS_AND_BORDERS.md:103-105`),
  so nobody plans a journey through it.
- **The cost of the ring, plainly.** Before the Champion, everything in the deep ring is above the cap and breaks
  free of any ball. The owner's rule is that above-cap Pokemon are "the exception at a heart, never the texture of a
  place" (`ENCOUNTER_DESIGN.md:230-231`). The deep ring breaks that rule on purpose, as postgame country "by level,
  not by lock". Owner question Q2.
- **Alphas re-level.** Every heart entry is a native alpha (`ENCOUNTER_DESIGN.md:328-335`). The jar re-levels an
  alpha to the nearest player's highest party level +16 for parties at 46-65 and +20 above that, capped at 100
  (`:344-353`; the owner kept this, `:360`). A cap-60 party meets near-ring heart alphas at about 76. The authored
  62 ceiling is therefore the spawn level, not the level fought.
- **Inherited pools: REPLACE, not layer.** The spawn philosophy keeps default pools open "in wilderness and
  postgame areas" (`STATE.md:148`; `data/spawns.json:7`). The Nether is wilderness, but layering fails the owner's
  brief. The pack's Nether pools are mostly fire:
  - the upstream Nether species found in the roster audit are Magby, Magmar, Magmortar, Numel, Camerupt,
    Charmander, Sizzlipede, Centiskorch, Salandit, Heatmor, Turtonator, Larvesta, Volcarona, Litleo and Pyroar,
    with Gligar, Cubone and Nacli the exceptions (`docs/world-building/ROSTER_AUDIT.md:288-506`, `:932-1059`,
    upstream biome columns);
  - the pack tags hold about 33 `#minecraft:is_nether` entries over 18 species, plus per-biome tags (*relayed*,
    superseded generation, `docs/world-building/BIOME_COVERAGE_MATRIX.md:96-156`).

  Layered, that fire would sit in every biome and undo the identities below. F1 also means the inherited pools are
  already half-suppressed by accident. **Recommendation: suppress every inherited spawn in `minecraft:the_nether`
  and author the five tables below as the Nether's only wild spawns.** The mechanism and its experiment are section
  7, N3.

---

## 2. The five biomes

Shape, as the overworld's (`ENCOUNTER_DESIGN.md:75-86`): roles anchor 24, common 12, uncommon 6, rare 2 (family
weight), buckets by role. Families are named by the species first met, and the generator walks the stages. "Spawns
as" is what survives a 54-60 band: a stage spawns from its evolution level to four past its next one
(`ENCOUNTER_DESIGN.md:60-62`). Evolutions not by level are allowed at this tier, trades included, in the upper half
of the band (`:66-69`). The deep ring uses the same tables at 65-75, so nearly every family shows its final stage
there. **Evolution levels quoted in "Spawns as" (Volcarona 59, Hatterene 42, Dragapult 60, Carkol 34) are mainline
figures, ASSUMED. The generator takes the real ones from the jar.**

**The fire rule, as a test can read it:** no species with Fire as either type is in any table except the nether
wastes and the crimson forest. The dungeons are not biomes and follow their themes (section 3).

**Hearts without a map.** An overworld heart is a focus point or a height line measured on the heightmap
(`ENCOUNTER_DESIGN.md:242-265`). The Nether has neither, and positions may not be read from a world (CLAUDE.md,
"Ground comes from the heightmap"). Each Nether heart is therefore a **feature condition**: `neededNearbyBlocks`, or
a Y line, both VERIFIED Cobblemon 1.8.0 condition fields (`docs/research/notes/underground-biomes.md:103-113`).
Their behaviour, including the radius of "nearby", is ASSUMED (experiment N2).
- The 1/9-of-area cap (`ENCOUNTER_DESIGN.md:271`) cannot be measured without a pregenerated Nether. It is checked
  on the first pregen, or the owner accepts it unmeasured (Q4).
- The 128-blocks-from-a-path rule has no path to measure from. A portal is the Nether's path, and portals are
  wherever players build them.

**Evidence for species.** Every species below is in this pack's species data. The evidence column says how that is
known:
- **E1:** it is in a compiled overworld table (`data/encounter_design.json` or `data/spawns.json`), which
  `tools/build_encounters.py` builds by walking the Cobblemon 1.8.0 jar's evolutions.
- **E2:** it has been seen spawning in game (EXP-012).
- **E3:** it appears only in a trainer team or an ambient list. Its species file exists, but implementation was not
  separately read.

Species with no evidence are listed as UNCONFIRMED and kept out of every table. Excluded throughout:
- the 40 substitute-doll species (`docs/research/COBBLEVERSE_COMPATIBILITY.md:108-109`): Greavard, Houndstone and
  Mandibuzz are the obvious Nether picks lost to it;
- final forms with a mis-assembled 1.8 model (`:136-148`): Tyranitar, Cofagrigus, Turtonator and Talonflame.

### 2.1 Nether wastes: the furnace floor

**Identity:** the Nether as the overworld imagines it: open heat, lava shores, quartz and slag, and the things that
live on heat itself.

| Family | Role | Spawns as (54-60) | Evidence |
|---|---|---|---|
| Magby | anchor | Magmar; Magmortar in the upper band (trade with item) | E1 (`encounter_design.json`; Magmortar `spawns.json`) |
| Numel | anchor | Camerupt | E1 |
| Slugma | common | Magcargo | E1 |
| Sizzlipede | common | Centiskorch | E1 |
| Rolycoly | common | Coalossal (Carkol 18-38 falls below the band) | E1 (Coalossal `spawns.json`) |
| Nacli | common | Garganacl | E1. **Model defect:** Garganacl's 1.8 texture was widened (`COBBLEVERSE_COMPATIBILITY.md:144`); it is already on the overworld tables, so this adds nothing new |
| Torkoal | uncommon | Torkoal | E1 |
| Heatmor | uncommon | Heatmor | E1 |
| Salandit | uncommon | Salandit; Salazzle (female-only evolution) | E1 |
| Charcadet | rare | Armarouge / Ceruledge (item evolutions) | E1 (both in `spawns.json`) |

**Heart, "the lava shore":** grounded, `maxY` 40, near `minecraft:lava` (the wastes' lava sea sits low, ASSUMED
until pregen).
- Families: Camerupt, Coalossal.
- Presences (alpha): **Magmortar**, **Centiskorch**.

**Deliberately absent:**
- ghosts: the dead belong to the valley;
- the overworld's fire mammals (Growlithe, Ponyta, Vulpix): they are stone or meadow Pokemon, and the Craters own
  them;
- every mainline starter: each has one overworld home by decision (`ENCOUNTER_DESIGN.md:401-422`);
- water of any kind: the Nether boils it;
- no lava-submerged table: the `fluid` key exists (`underground-biomes.md:113`), but lava spawning is unproven.

### 2.2 Crimson forest: the hunting wood

**Identity:** a hot red forest where things hunt. Hoglins and piglins already prowl it, so its Pokemon are predators
and the prey that hides under the weeping vines.

| Family | Role | Spawns as | Evidence |
|---|---|---|---|
| Houndour | anchor | Houndoom | E1 |
| Litleo | common | Pyroar | E1 |
| Spinarak | common | Ariados | E1 |
| Paras | common | Parasect (the fungus that drives the bug) | E1 |
| Mankey | uncommon | Primeape; Annihilape (by move, upper band) | E1 (Annihilape `spawns.json`) |
| Larvesta | rare | Larvesta; Volcarona from 59 | E1 |

**Heart, "the hanging canopy":** near `minecraft:weeping_vines`.
- Families: Houndoom, Ariados.
- Presences (alpha): **Volcarona**, **Pyroar**.

**Deliberately absent:**
- anything psychic or strange: that is the warped forest's, and the two forests must not read alike;
- ghosts;
- Capsakid / Scovillain, the ideal crimson pick (a pepper whose Fire Stone is mined in the Nether): **UNCONFIRMED**.
  There is no evidence of it anywhere in the repository. Add it only after a jar read.

### 2.3 Warped forest: the alien wood

**Identity:** the one place in the Nether that is not hot and not dead. It is wrong-coloured, quiet, lit by fungus,
walked by endermen, and full of things that do not look like they evolved on this world.

| Family | Role | Spawns as | Evidence |
|---|---|---|---|
| Elgyem | anchor | Beheeyem | E1 |
| Morelull | anchor | Shiinotic (the glowing mushroom) | E1 |
| Toedscool | common | Toedscruel | E1 |
| Foongus | common | Amoonguss | E1 |
| Inkay | common | Malamar (inverted evolution, upper band) | E1 (Malamar `spawns.json`). Whether the "held upside down" method is implemented is NOT READ; failing it, Inkay alone spawns |
| Hatenna | uncommon | Hattrem; Hatterene from 42, so Hatterene at this band | E1 (Hattrem `spawns.json`); Hatterene E3 (trainer teams) |
| Solosis | uncommon | Reuniclus (cells from somewhere else) | E3 (`data/ambient.json:176`; Reuniclus in trainer teams) |
| Blipbug | uncommon | Orbeetle | E2 (seen spawning, `experiments/EXP-012-bounded-default-suppression/README.md:85`); Orbeetle not read |
| Beldum | rare | Metagross | E1 (Metagross `spawns.json`) |
| Minior | rare | Minior (fallen from the sky) | E3 (`data/ambient_towns/gym1_town.json:177`). Its shell forms are not read |

**Heart, "under the lamps":** near `minecraft:shroomlight`.
- Families: Beheeyem, Shiinotic.
- Presences (alpha): **Metagross**, **Malamar**.

**Deliberately absent:**
- **every Fire type**: this is the forest the heat forgot;
- beasts and hunters: the crimson forest's;
- Ultra Beasts: tempting for "alien", but the only one that renders and suits an ambient table is Poipole, and
  Poipole's home is decided in section 4 (most UBs are dolls, `docs/research/notes/legendary-species-1.8.0.md:76-78`).

### 2.4 Soul sand valley: the boneyard

**Identity:** where the Nether keeps its dead. Blue soul fire that gives no warmth, giant fossil ribs, ghasts
drifting, and the sand itself made of souls.

| Family | Role | Spawns as | Evidence |
|---|---|---|---|
| Gastly | anchor | Haunter; Gengar (trade, upper band) | E1 |
| Sandygast | anchor | Palossand (a castle built of soul sand) | E1 |
| Duskull | common | Dusclops; Dusknoir (trade with item, upper band) | E1 |
| Shuppet | common | Banette | E1 |
| Cubone | common | Marowak (the bone it wears) | E1 |
| Drifloon | uncommon | Drifblim | E1 |
| Spiritomb | rare | Spiritomb (108 souls in a stone) | E1 |
| Dreepy | rare | Drakloak; Dragapult from 60 (the ghosts of an ancient dragon) | E1 (Dreepy `spawns.json:53466`; Dragapult `spawns.json`) |

**Heart, "the fossil ribs":** near `minecraft:bone_block`, which the valley's generated fossils are made of
(ASSUMED until pregen).
- Families: Gengar, Palossand.
- Presences (alpha): **Dusknoir**, **Dragapult**.

**Deliberately absent:**
- **Litwick / Chandelure, the obvious pick and deliberately left out.** They are Fire, and the valley's fire is soul
  fire: the cold kind, the dead's. Putting the candle ghost here would make the valley a fire biome by the back door;
- Alolan Marowak, for the same reason;
- Greavard and Houndstone: dolls (`COBBLEVERSE_COMPATIBILITY.md:109`).

### 2.5 Basalt deltas: rock and ash

**Identity:** grey columns, black stone and falling ash; no forest, no fire you can live beside. Things that are
stone, or eat stone, or breathe the ash.

| Family | Role | Spawns as | Evidence |
|---|---|---|---|
| Roggenrola | anchor | Boldore; Gigalith (trade, upper band) | E1 |
| Rhyhorn | anchor | Rhydon; Rhyperior (trade with item, upper band) | E1 |
| Onix | common | Onix (the basalt serpent) | E1 |
| Gligar | common | Gligar; Gliscor (held item at night) | E1 |
| Klawf | common | Klawf (cliff crab) | E1 |
| Koffing | uncommon | Weezing (the ash cloud) | E1 |
| Glimmet | uncommon | Glimmora (crystal grown on toxic ash) | E1 |
| Carbink | rare | Carbink (a gem pressed out of the columns) | E1 |

**Heart, "the vents":** near `minecraft:magma_block`.
- Families: Rhyperior, Gigalith.
- Presences (alpha): **Gliscor**, **Glimmora**.

**Deliberately absent:**
- **Magcargo and Coalossal**, the obvious lava-and-rock picks: they are Fire, and they live in the wastes;
- Larvitar's line: Tyranitar's 1.8 model is mis-assembled (`COBBLEVERSE_COMPATIBILITY.md:143`), and at 54-60 the
  line is mostly Tyranitar;
- ghosts.

**Stonjourner** (a basalt henge) would suit this biome and is **UNCONFIRMED**: there is no repository evidence for
it.

### 2.6 Two set pieces the Nether already generates

Fortresses and bastions generate normally (`DIMENSIONS_AND_BORDERS.md:295`). `structures` is a VERIFIED condition
field ("IDs or tags", `underground-biomes.md:107`), so each can carry a small roster of its own without placing
anything. Behaviour is ASSUMED (experiment N4).

- **The Fortress, "the garrison"** (`minecraft:fortress`): the soldiers who held the halls, and what is left of
  them.
  - Honedge, which spawns as Doublade and as Aegislash (item): the swords. E1 (Doublade and Aegislash in
    `spawns.json`).
  - Pawniard, which spawns as Bisharp: the ranks. E1.
  - Golett, which spawns as Golurk: the guardians built to outlast their builders. E1.
  - No Fire, though the halls are full of blazes: the garrison is steel and ghost.
- **The Bastion, "the hoard"** (`minecraft:bastion_remnant`): the piglins' gold, and everything that wants it.
  - Gimmighoul: E1, with Gholdengo in `spawns.json`. Its coin evolution is outside this design.
  - Sableye: E1.
  - Murkrow, which spawns as Honchkrow (Dusk Stone): E1.
  - Meowth, which spawns as Persian: E3 (`data/ambient.json:176`, `data/ambient_towns/gym8_town.json:559`).

---

## 3. The dungeons: a theme each, the roster after it

The built machinery is one boss room per player in `cobblers:pocket`. It is entered by eating a crafted key anywhere
in the Nether, gated at `champion_cleared`, with the boss at level 100: catchable the first time, then `uncatchable`
with one drop roll (`data/entei_boss.json:13-16`, `:22-26`, `:47-52`, `:96-111`). That is the scope's option B
(`docs/mechanics/NETHER_DUNGEON_SCOPE.md:269-285`). **A roster beyond the boss needs rooms, which is option A and
not built.**

Each dungeon below is therefore given in two layers:
1. what the built room can carry now: palette, text, key, boss set, drops;
2. the roster for the gauntlet rooms, when option A is approved. These use Heaven's Arena's pool machinery
   (`NETHER_DUNGEON_SCOPE.md:116-118`); its per-player NPC loop is proven for one player.

### 3.1 Entei: "The Tower After the Fire"

**Theme.** A bell tower burned for three days. Three nameless Pokemon died in it, and something raised them. The fire
has been out for a hundred years. What remains:
- charred timber gone silver;
- a cracked bell on the floor;
- rain that comes through the open roof, the rain that put the fire out;
- a ring of cold ash where one of the three still will not leave.

This is a ruin and a vigil. **Entei is the grief of the place, not its heat.** The room reads as aftermath: wet,
grey, quiet.

**Changes to the built room** (owner Q5; `data/entei_boss.json` fields, world-content-dev for the palette, this
agent for the drops):

| Field | Built | Proposed |
|---|---|---|
| `room.palette` | nether bricks, polished blackstone, crying obsidian, shroomlight (`:71-79`) | charred-timber walls (stripped dark oak, a dark-oak log frame), a cracked-stone floor, a broken ceiling with daylight-coloured lamps, a fallen `minecraft:bell` at the boss spot, an unlit campfire ring. Palette ids for world-content-dev to choose; the sealed bedrock shell and the Mining Fatigue ward are unchanged (`:80`) |
| `key` name and lore | "Ember Sigil", "the heat answers" (`:32-33`) | "Tower Ash", "Eat it in the Nether, and the tower remembers you." Same item, components and recipe |
| `message.*` | heat and embers (`:142-152`) | e.g. `appear`: "Something rises from the ash ring. It has been waiting." `out`: "The rain lets you go." |
| `drops` | Fire Gem, Heat Rock, Red Mint Seeds, Flame Orb, Magmarizer, Life Orb, "fire-themed" (`:100-110`) | the tower's things. **Candidate ids, UNVERIFIED in the jar:** Sacred Ash, Smoke Ball, Spell Tag, Damp Rock, Charcoal, Life Orb (kept: it is VERIFIED). The bank check and the no-plate check (`:109`) stay fail-closed. Weights flat, as now |

**The boss** stays as built: Entei, level 100. Catch set: Sacred Fire, Extreme Speed, Crunch, Stomping Tantrum,
Sitrus Berry. Farm set: Sacred Fire, Extreme Speed, Stone Edge, Crunch, Life Orb, Inner Focus, 252 Atk/Spe, six
perfect IVs (`data/entei_boss.json:17-21`). Entei is VERIFIED to exist and render, through Mega Showdown
(`legendary-species-1.8.0.md:38`).

**Gauntlet roster (option A, draft):** the things that live in a burned building.
- Koffing, as Weezing: the smoke that never cleared. E1.
- Murkrow, as Honchkrow: the crows on the beams. E1.
- Misdreavus, as Mismagius: the unsettled. E1.
- Rattata, as Raticate: the cellar. E1.
- One Magmar, the tower's own resident in the old story: the only Fire in the run. E1.

Trainer classes would be "Tower Keeper" and "Bell Ringer" (the people who stayed). That is three trainers, no heal
between, before the ash ring, the arena's gauntlet format (`NETHER_DUNGEON_SCOPE.md:138-139`).

**Answer check (Entei, level 100, post-Champion, cap 100).** Everything below is from the overworld tables a
Champion has walked:

1. **Bulky Water/Ground: Swampert.** Mudkip is at Marshy Marsh, with Swampert in its heart (`ENCOUNTER_DESIGN.md:419`).
   It is neutral to Stomping Tantrum, Crunch and Extreme Speed, resists Fire and Stone Edge, and Earthquake and
   Waterfall are both super effective.
2. **Rock walls that ignore the burn: Garganacl or Rhyperior** (Nacli and Rhyhorn, E1).
   - Garganacl's Purifying Salt blocks Sacred Fire's burn, and Rock resists Fire and Extreme Speed. Its weakness is
     Stomping Tantrum. *Ability effects are mainline knowledge, not read from the jar.*
   - Rhyperior resists Fire and Normal at 0.5x.
3. **Cut its Attack: Intimidate Gyarados** (Magikarp and Gyarados, E1). Water resists Fire. Entei's whole set is
   physical.
4. **For the catch (catch rate 3):** a False Swipe user plus sleep (Amoonguss's Spore; Foongus E1) keeps it in the
   ball's window. Fire's burn immunity does not protect it from sleep.

The open problem is the scope's own: one level-100 Pokemon against six loses fast (`legendary-species-1.8.0.md:144-146`).
The gauntlet is the difficulty, and the room alone is a farm.

### 3.2 Heatran: "The Crucible"

**Theme.** Under the Nether's floor there is a foundry older than the piglins, where netherite was first smelted.
Nobody works it now. The bellows still breathe, the gears still turn, and the metal still moves.
- The run is a **forge**, not a volcano: anvils, chains, cooled slag, an orange glow from far below.
- Heatran is the crucible's heart: a body of molten steel that was the furnace all along.
- The key fits the theme: **you bring ore to the forge.**

**Changes from the Entei room** (a second record, `data/heatran_boss.json`, on the same machinery):
- **Key:** "Crucible Ore", crafted from **raw ancient debris** rather than ingots. "You bring the ore; the crucible
  does the smelting." The exact count is the economy's (Q6). Entei's price is 2 netherite ingots = 8 debris + 8 gold
  at the bank's values (`data/entei_boss.json:43`).
- **Gate:** `champion_cleared`, level 100, as Entei.
- **Slots:** a separate pocket band so the two never share a slot. Entei holds z = -768 from x = -768 at spacing 128
  (`data/entei_boss.json:58-60`). Heatran's would be a second row at z = -896, inside the border margin
  (-1024 + 32). **This is a proposal; the builder re-derives the bounds** (border, portal rescue box `:60`).
- **Boss set: NOT DESIGNED until the learnset is read.** Heatran is VERIFIED to exist and render (fire/steel,
  91/90/106/130/106/77, Flash Fire, hidden Flame Body, catch rate 3; `legendary-species-1.8.0.md:41`), but
  `data/cobblemon/species/generation4/heatran.json` was not read by anyone. A special set is the shape (SpA 130):
  a Fire STAB, a Steel STAB, Earth Power for coverage, and Leftovers. Every move id is to be checked against the jar
  before it is written.
- **Drops (candidates, UNVERIFIED ids):** Metal Coat, Iron Ball, Magnet, Hard Stone, Leftovers. The bank check
  applies.
- **Stark Mountain stays suppressed** (`data/dimension_overrides.json:80-88`, "The owner may move it to kept"). This
  design answers that: Heatran's home is the Crucible, not the volcano.

**Gauntlet roster (option A, draft):** the machinery and the metal that lives on it. None is Fire.
- Klink, as Klinklang: the gears. E1.
- Magnemite, as Magnezone: the current. E1. Its evolution method in 1.8 is not read.
- Bronzor, as Bronzong: the temple bells cast here. E1.
- Tinkatink, as Tinkaton: the smith who steals metal with a hammer. E1.
- Durant: iron ants in the slag. E1.
- Varoom, as Revavroom: the engines. E1.
- Cufant, as Copperajah: the hauler. E1.
- Orthworm: the worm in the ore seam. E1.

Trainer classes would be "Smelter" and "Foreman".

**Answer check (Heatran, fire/steel, post-Champion).** Its 4x weakness is Ground; it is also weak to Water and
Fighting. All are from the overworld tables:

1. **Ground: Krookodile, Hippowdon or Excadrill** (Sandile, Hippopotas, Excadrill: E1). Earthquake is 4x.
2. **Water: Swampert or Gyarados** (E1). Swampert covers both weaknesses at once.
3. **Fighting: Machamp, Conkeldurr or Lucario** (Machop, Timburr, Riolu: E1).
4. **Never Fire:** Flash Fire. The run's text should say so once, before the room.

### 3.3 The Ruinous shrines: "The Broken Seal"

**Theme.** Four treasures (a sword, a vessel, tablets and beads) once sealed a king's grudge. The seal's pins are the
stakes driven through the Nether. A player who pulls them is not finding a legendary; **they are unsealing a
calamity**, one colour at a time, and the shrine is where it gets out.

**What we can and cannot author.** The stakes are a worldgen feature in every `#minecraft:is_nether` biome, and the
shrine's spawn is LegendaryMonuments bytecode. Progress is kept per player in `minecraft-shrine-data`, outside the
world save (`docs/research/notes/legendary-catalogue-reopened.md:55-70`). The stake count and **the levels are
bytecode constants, never read** (`:64-65`). So:
- **We cannot set their levels, sets or rosters.** If a shrine spawns above a player's cap, the catch block refuses
  the ball until the cap rises. Experiment N6 reads the level.
- **What we can add** is a ring roster at each shrine (the `structures` condition, N4): local Pokemon bent by the
  calamity they sit beside.
  - Grasswither (Wo-Chien): Foongus and Paras, as blight.
  - Groundblight (Ting-Lu): Cubone and Rhyhorn, as cracked earth.
  - Icerend (Chien-Pao): the one cold thing in the Nether. Which ice family renders here is to be chosen from the
    overworld's E1 ice species (Sneasel is E1).
  - Firescourge (Chi-Yu): Houndour, as the fire it lets loose.
  - Which biome each shrine generates in is not read (`DIMENSIONS_AND_BORDERS.md:83-84`: "one of four Nether
    biomes"). A shrine that sits in the warped forest would bring its calamity's types into the wrong biome. That
    is the theme (a calamity is out of place), but the fire rule would then need a written exception for the
    Firescourge ring. Q7.

**Answer check (all four are Dark plus one type):**
1. **Fighting** hits all four: Machamp, Conkeldurr, Lucario (E1).
2. **Fairy** beats Dark: Hatterene (Hatenna E1; Hatterene E3).
3. **Per shrine:** Water and Rock for Chi-Yu (dark/fire); Fire, Fighting and Steel for Chien-Pao (dark/ice).

Levels unread, so this is an answer by type only.

### 3.4 Not proposed

- Raikou and Suicune as further rotation bosses: the scope's option A. Each would get a theme first, for example
  Suicune as "the spring under the ash", the rain from 3.1 found at its source.
- Ho-Oh (Cobblemon-native, `legendary-species-1.8.0.md:42`) belongs to the Burned Tower story. It is left for the
  owner, because it would be the bell's other half.
- Mewtwo stays on the fossil route, and there are no Arceus plates (the owner, `data/entei_boss.json:5`).

---

## 4. Poipole's home

**Facts.**
- Poipole is native to Cobblemon 1.8.0 with its own model, the only one of the five starters that is
  (`docs/research/NATIVE_STARTERS_1_8_0.md:39`).
- Catch rate 45; egg group undiscovered, so it cannot breed (`:45-46`). A wild spawn is the only second source of
  Poipole or Naganadel.
- It evolves on level-up while knowing Dragon Pulse, which is one of its level-1 moves (`:39`, `:59-60`).
- Its one upstream spawn rides the End towers (P2).

**Proposal: Poipole lives at our two pasted Ultra Space towers, in the overworld.**

| Tower | Where (read from `data/adopted_legendary_sites.json`) | Tier, band |
|---|---|---|
| Dawn tower | north_pine_isle, corner (7480, 316), y99, footprint 45x46 (`:486`, `:496`, `:505-510`) | tier 6, 33-43 (`data/encounter_design.json:325`; `ENCOUNTER_DESIGN.md:38`) |
| Dusk tower | sunset_west, corner (1156, 7216), y146, footprint 46x45 (`:552`, `:562`) | tier 5, 28-38 (`encounter_design.json:250`; `ENCOUNTER_DESIGN.md:38`) |

- **Shape:** one rare-bucket entry per tower, family weight 2, the "find" role (`ENCOUNTER_DESIGN.md:81`), compiled
  over the tower's footprint box at any height. Levels come from the place's band. Poipole only: Naganadel would
  appear on its own, since a wild Poipole may already know Dragon Pulse. *Whether a wild spawn's moveset includes
  it is not read.*
- **Why there:**
  1. It is where the pack's own author put Poipole: beside Necrozma's towers, both from Ultra Space.
  2. The towers already stand in our world and are "findable by eye" (`:560`).
  3. Both are reachable well before badge 8 (the Dusk tower by the Sunset Isle charter, `:560`). A starter's second
     copy should not wait behind the Nether gate.
  4. The towers can be climbed before the Champion; only Necrozma is gated (`:528`). So the spawn needs no gate of
     its own.
- **Why not the warped forest:** it suits "alien" and would be easy to write. But it would put a starter's only
  second source behind the eighth badge, in a biome that no tool can position. It would also make the warped forest
  about a Pokemon one player already owns.
- **Mechanism, two choices:**
  - a compiled coordinate-box entry in `data/spawns.json` through `tools/compile_spawns.py`. That needs the compiler
    to stop forcing `canSeeSky` for this entry if the spawn is to reach the tower's interior (F2's code, `:84-86`);
  - or a Habitat Block, which the record already names as the fix (`adopted_legendary_sites.json:531`) and which the
    owner places by hand (`STATE.md:147`).

  Recommendation: compiled, so a re-export restores it.

---

## 5. Open questions for the owner

1. **The gate: badge 8 (`gym8_cleared`), by bouncing the player out on arrival?** *Recommend yes.* It is the only
   reading of "late-game" that holds, and it gates Fire Stones, netherite and the Ruinous shrines together, at a
   cost of 0 families (section 1).
2. **A postgame deep ring (65-75, presences to 85), uncatchable before the Champion?** *Recommend yes.* It is the
   game's only wild country above 62, and its levels say plainly that it is for after.
3. **Replace the inherited Nether pools rather than layer over them?** *Recommend replace.* Layered, the pack's fire
   undoes every biome's identity, and the suppression is already stripping them at random by coordinate (F1).
4. **Hearts by feature (near shroomlight, bone blocks, magma, weeping vines, the lava shore), with the 1/9 area cap
   unmeasured until a pregen?** *Recommend yes, measured at the first Nether pregen.*
5. **Re-theme the built Entei room ("The Tower After the Fire": palette, key text, messages, drops)?** *Recommend
   yes.* The machinery is untouched, and the built room is the fire room the brief rejects (P4).
6. **Heatran's key from raw ancient debris, and at what count?** *Recommend debris* (the theme: ore to the forge),
   with the count set by the economy design against Entei's 2 ingots.
7. **The Ruinous rings: allowed to put a calamity's types into whatever biome its shrine landed in (Fire included
   for Firescourge)?** *Recommend yes, as the one written exception to the fire rule.* A calamity is meant to be out
   of place.
8. **Poipole at both towers or one?** *Recommend both.* Two isles and two tiers, so a Poipole player on either side
   of the map has one within reach.
9. **Capsakid and Stonjourner**, if a jar read confirms them: *recommend adding them* (to the crimson forest and the
   basalt deltas). Until then they stay out.

---

## 6. Experiments before any of it is content

| Id | Question | Where |
|---|---|---|
| **N1** | Does a grounded Cobblemon spawn in the Nether pass with `canSeeSky` omitted, and fail with it forced true (F2)? | disposable world |
| **N2** | `neededNearbyBlocks` in 1.8.0: does it select by the named block, and over what radius? | disposable world |
| **N3** | Does an anticondition `{"dimensions": ["minecraft:the_nether"]}` on an inherited detail remove it in the Nether and nowhere else? And, read now, does today's suppression strip inherited Nether spawns at overworld box coordinates (F1)? | disposable world, `/checkspawn` |
| **N4** | Does the `structures` condition match inside `minecraft:fortress` and `minecraft:bastion_remnant` (and a LegendaryMonuments shrine)? | disposable world |
| **N5** | Does `minecraft:changed_dimension` fire on a portal arrival, and can its function return a player without the flag to their checkpoint and revoke itself, for two players at once? | staging, two accounts for the second half (`STATE.md:177`) |
| **N6** | What level do the four Ruinous shrines spawn at, and how many stakes does each need? | disposable world, one shrine |
| **N7** | Species reads in the jar: Capsakid, Scovillain, Stonjourner; Heatran's learnset; Inkay's and Magnemite's evolution methods; the drop candidates' item ids | `cobblemon-researcher`, jar read |

---

## 7. What a builder would need (not built)

**Data (this agent and datapack-content-dev):**
- `data/encounter_design.json`:
  - five tables `nether_wastes`, `crimson_forest`, `warped_forest`, `soul_sand_valley`, `basalt_deltas`, each with
    `placement: "nether"`, its `biomes`, tier 10, levels [54, 60], the families of section 2, and a feature `heart`;
  - a deep variant (tier 11, [65, 75]) keyed on the ring;
  - two structure tables (fortress, bastion);
  - the Poipole find at the two towers;
  - `rules` gains tiers 10 and 11 (caps 60 and 100, maturity 0.9 and 1.0, next cap 62 and 85).
- `data/spawns.json`: the generated entries (by `tools/build_encounters.py`, never by hand).
- `data/entei_boss.json`: `room.palette`, `key` text, `message`, `drops` re-themed (section 3.1; palette ids from
  world-content-dev, drop ids after N7).
- `data/heatran_boss.json`: new, the Entei record's shape with section 3.2's values.
- `data/progression.json`: the Nether gate as a record (flag, trigger, return point, message, why).

**Generators and packs (datapack-content-dev / minecraft-systems-dev):**
- `tools/build_encounters.py`:
  - tiers 10 and 11;
  - heart kinds `nearby` (block list) and `y_line` that need no position;
  - a fire-confinement check, failing closed on any Fire type outside `nether_wastes` and `crimson_forest`, read
    from the jar's types.
- `tools/compile_spawns.py`:
  - a Nether condition shape: `dimensions: ["minecraft:the_nether"]`, the biome, ring boxes, the feature condition,
    and **no forced `canSeeSky`**;
  - the `structures` condition;
  - hygiene: `dimensions: ["minecraft:overworld"]` on every overworld pool. Today a grounded overworld box entry has
    no dimension (`:84-90`), and nothing keeps it off the Nether roof at the same x/z (INFERRED).
- `tools/suppress_inherited_spawns.py`:
  - one Nether-dimension anticondition on every inherited detail (replace, Q3);
  - the overworld boxes made dimension-bound, so they stop reaching into the Nether by accident (F1).
- `tools/entei_boss.py`: generalised to a boss record, or a second instance for Heatran, with the reapply step that
  builds its rooms (Entei's is R16Q, `data/entei_boss.json:4`).
- **The Nether gate:** a new small generator (advancement on `changed_dimension`, the return function, the
  self-revoke) and a reapply install step. It must land **with or before** `cobblers_dimension_overrides` on the
  live world, before anyone enters the Nether (`data/dimension_overrides.json:17`).

**Tests (test-author, not the builder):**
- every Nether pool carries `dimensions`;
- no Nether pool forces `canSeeSky`;
- the fire rule;
- no doll species and no mis-modelled final form;
- every species implemented in the jar;
- the ring boxes inside the border;
- the base bands under the caps of section 1;
- the Entei and Heatran slot bands disjoint and inside the border;
- `tests/test_system_contracts.py`: a new contract, "the Nether gate admits only `gym8_cleared`", consumed by the
  economy (netherite, Fire Stones) and the Ruinous shrines.

**Not touched:** `data/dimension_overrides.json` keeps its seven suppressions, Stark Mountain included, and its
kept shrines.
