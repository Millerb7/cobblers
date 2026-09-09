# Game Vision

A handcrafted, difficult Pokémon-style region inside Minecraft, played cooperatively
by a small group of friends on a private Cobblemon server.

The difficulty reference points are ROM hacks such as **Run & Bun** and **Pokémon
Imperium**. The Minecraft reference point is the **Cobbleverse** modpack, which one
of the players particularly enjoys and which we keep as our base experience wherever
it remains compatible with our target Cobblemon version.

This is **not** a mandatory Nuzlocke. Difficulty comes from the fights, the level
cap, and the need to build answers, not from permadeath rules.

## What we are building

- A mostly **linear region progression**: routes, towns, gyms, a villain arc, and a
  final challenge, opened chapter by chapter.
- **Routes as explorable biomes/areas**, not corridors. A route is a place with
  side paths, hidden items, caves, ruins, and optional encounters.
- **Curated Pokémon availability.** Every area has an authored encounter table of
  roughly 10 to 20 deliberate species. The generic Cobblemon "everything spawns
  everywhere" feel is the thing we are replacing.
- **Difficult trainers**: Gym Leaders, rivals, villain admins, and boss trainers
  with full teams, real movesets, abilities, natures, held items, and competent AI.
- **Level caps** (or an equivalent mechanism) so that grinding past a wall is not a
  solution. The solution is always team building.
- **Explorable content**: caves, forests, ruins, mines, laboratories, temples,
  facilities, hideouts.
- **Optional dungeons with meaningful rewards**, including strong or unusual Pokémon
  that are earned through an adventure rather than a tiny spawn roll.
- **Puzzle dungeons** with persistent state and sealed final chambers.
- **Villain hideouts** with multi-trainer gauntlets and restrictions on healing,
  PC access, and retreat.
- **Multiplayer exploration** that uses Minecraft's strengths (shared world,
  building, cooperative exploration) instead of literally recreating a ROM.

## The core loop

```text
Explore route / biome
        ↓
Discover Pokémon, items and side areas
        ↓
Optional dungeon / challenge encounter
        ↓
Prepare a team
        ↓
Major trainer / gauntlet
        ↓
Gym / story boss
        ↓
New region opens
```

The feeling we want players to have, repeatedly:

> "This next fight looks nasty. What can we go find that would help?"

## Design pillars

### 1. Difficulty that rewards preparation

Boss fights are designed as problems with solutions. Players are expected to scout
the boss (team, moves, abilities, items), then go find or build an answer. A fight
that can only be beaten by luck or by a single hard counter is a design failure.

**Every difficult boss must have plausible tools available somewhere in the
accessible region.** The trainer designer and the encounter designer work as a pair:
if a Gym Leader runs a sand team with Excadrill, the region before that gym must
contain real counterplay (bulky Water, Grass, Fighting, Intimidate, priority, or a
weather-changing option), findable with normal exploration.

### 2. Team building as the central skill

The level cap removes "grind harder" as an answer. What remains is species choice,
movesets, abilities, natures, held items, and switching. Access to these tools
(TMs, tutors, held items, breeding, nature and ability control) is deliberate reward
placement, not a shop dump.

### 3. Curated encounters

Each route has an authored encounter list. Availability is controlled by area,
progression, and sometimes time or weather. Rare and powerful species are not
buried in random spawn weights; they are placed behind authored content:

- Beldum hidden behind an abandoned observatory puzzle.
- Rotom obtained from a captured power generator in a villain facility.
- Riolu found through a mountain shrine challenge.
- A fossil obtained from an explorable archaeological dungeon.
- A titan-class legendary locked behind a substantial ancient puzzle dungeon.

### 4. Exploration that matters

Side areas hold real rewards: encounter species, held items, TMs, evolution items,
optional trainers, lore, and shortcuts. Exploring should change what teams are
possible. Handcrafted terrain is the medium; world-critical blocks and decoration
are therefore chosen early and rarely changed.

### 5. Dungeons and puzzles

Dungeons combine exploration, puzzle state, optional combat, and a sealed reward
chamber. Example structure:

```text
Ancient Titan Cave

Room 1: exploration / trainer encounter
Room 2: environmental puzzle
Room 3: ancient mechanism puzzle
Room 4: combat or party requirement
Final Chamber: opens only when every required dungeon flag is set
Reward: special encounter
```

Progress persists. Multiplayer state is explicit: some rewards are per player, some
are shared, and each dungeon says which.

### 6. Villain gauntlets

Hideouts are sequences of trainers with restrictions: limited or no healing, no PC,
checkpoints or full resets, and one-time rewards. This is where team depth and
resource management are tested.

### 7. Multiplayer first

Every system must answer: what happens when two players do this at once, when one
player is ahead, when a player joins late, and when a player leaves mid-dungeon.
Progression is player-specific by default; world unlocks are shared where that
makes the game better.

## Difficulty, stated plainly

- Hard, fair, and readable. Bosses telegraph their strategy; scouting is possible.
- Level caps per chapter. Overleveling is prevented, not merely discouraged.
- No mandatory Nuzlocke, no permadeath. Optional self-imposed rules are welcome.
- Healing and PC restrictions apply inside gauntlets and some dungeons only.

## What this is not

- Not a survival-sandbox Cobblemon server with a few gyms attached.
- Not a literal ROM recreation. Minecraft exploration, building, and co-op are
  features, not obstacles.
- Not a giant custom mod. Existing Cobblemon, Cobbleverse, datapack, and scripting
  capabilities are used first; custom code is a last resort proven by experiment.

## Relationship to Cobbleverse

Cobbleverse provides the baseline feel: the full Pokémon roster via model resource
packs, Mega Evolution, trainer NPCs (Radical Cobblemon Trainers), badges, raid
dens, decoration and furniture blocks, waystones, and quality-of-life. We keep what
stays compatible with Cobblemon 1.8.x and what serves the campaign. We override
spawning, trainers, progression, and world design entirely, because those are the
campaign.

See `docs/architecture/TECHNICAL_ARCHITECTURE.md` for the layer model and
`docs/research/EXPERIMENT_BACKLOG.md` for the proofs that must land before serious
content work begins.
