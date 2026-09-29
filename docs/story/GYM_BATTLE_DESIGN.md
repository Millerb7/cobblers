# Challenge-hack battle design research

> **Purpose:** source library and reusable design rules for rewriting Cobblers' eight Gym Leaders, Elite Four, Champion, and route trainers. This is not a roster document.
>
> **Checked:** 2026-09-28. Hack documentation is version-sensitive. Match every trainer sheet and calculator to the exact hack version named by its release page.

## The short recommendation

Build each major fight from the player's availability outward. Give the fight one coherent engine, one deliberate check against the obvious answer, and roles that create a readable sequence. Let route trainers teach those ideas before the leader combines them. Publish enough information that losses improve the player's plan rather than merely revealing a hidden move.

For Cobblers, the default difficulty budget should be:

- **Route trainer:** one lesson, normally two or three Pokemon, no hidden hard counter.
- **Early Gym:** one engine plus one answer-check.
- **Middle Gym:** one engine, one answer-check, and one pace tool such as speed control or hazards.
- **Late Gym:** one engine, one answer-check, and one sequencing twist carried by the ace.
- **Elite Four:** one distinct strategic exam per member; avoid repeating four weather teams.
- **Champion:** synthesis of previously taught ideas, not a new ruleset.

A Focus Sash, immunity ability, resistance berry, unexpected coverage move, and weather setter are each useful. Putting all five on one short team usually deletes the player's informed answer instead of testing it.

## Source library

### Highest-value starting set

| Project | Canonical material | What it contains | Best use |
|---|---|---|---|
| Radical Red 4.1 | [Creator release thread](https://www.pokecommunity.com/threads/pok%C3%A9mon-radical-red-version-4-1-released-gen-9-dlc-pokemon-character-customization-now-available.437688/) · [official documents folder](https://drive.google.com/drive/u/0/folders/1YaYM-8dzRlBRuJm1bmYrjJC6HGwTwl-x) · [official Dex](https://dex.radicalred.net/) · [damage calculator](https://calc.radicalred.net/) | The documents folder contains versioned normal- and Hardcore-mode boss teams, Pokemon and raid locations, and item/TM/tutor locations. The Dex exposes the hack's stats, typings, abilities, evolutions and move access. The calculator carries hack-specific data and boss presets. | Compare the same encounter under several difficulty contracts. Radical Red is especially useful for seeing how field effects, abilities, items and restricted player tools alter a fight. |
| Run & Bun 1.07 | [Creator release thread](https://www.pokecommunity.com/threads/pok%C3%A9mon-run-bun-v1-07.493223/) · [creator-linked documentation folder](https://drive.google.com/drive/folders/1M-PdZrACBkGPpceTanCq_ltbGNT24lR8) · [community calculator](https://rnbcalc.sylmar.dev/) · [calculator source and AI-document link](https://github.com/SynchEleven/rnb-calc-ultimate) | The creator describes almost 500 custom, synergistic trainer battles. The folder covers Pokemon and item locations, trainer battles, mechanical changes and related reference data. The community calculator includes trainer sets and Run & Bun-specific mechanics; its repository links Croven's 1.07 AI notes. | The strongest source here for sequencing, role compression, route-trainer quality, and designing around known AI rather than nominal competitive sets. |
| Pokemon Emerald Imperium | [Creator release thread](https://www.pokecommunity.com/threads/new-release-pokemon-emerald-imperium.534582/) · [official hub](https://emeraldimperium.info/) · [documentation folder](https://drive.google.com/drive/folders/1auRPBg8Ts50NByIskMy6b2XHnmNqIKtV) · [boss battle sheet](https://docs.google.com/spreadsheets/d/1A9iN3N2bZ8-0YCVrhfeZ0qo2runkbHd-HCgaH_TVyr4/edit?gid=769944276) · [official Dex](https://dex.emeraldimperium.net/) · [configured Dynamic Calc](https://hzla.github.io/Dynamic-Calc-Decomps/?data=imp13&dmgGen=8&evs=0&gen=8&noSwitch=1&types=6) | The creator documentation covers boss battles, wild encounters, items, walkthroughs, known bugs and every intentional difference from Radical Red. The boss sheet records the full cap sequence; the configured calculator exposes trainer presets, field states, AI information and save import. | Compare Radical Red-derived balance after transplanting it into Hoenn's geography and availability curve. It is strong evidence for which encounter patterns travel cleanly between regions and which depend on the original game's encounter access. |
| Pokemon Null 1.2.4 | [Official site](https://pokemonnull.com/) · [creator release thread](https://www.pokecommunity.com/threads/pok%C3%A9mon-null-v1-2-3-nuzlocke-romhack.542639/) · [official resources folder](https://drive.google.com/drive/u/0/folders/10H1Pm-1dhEgc0QmjsnA9A9PY6nNRXtoJ) · [official Dex](https://nulldex.pokemon0null.workers.dev/) · [damage calculator](https://nullcalc.pokemon0null.workers.dev/) · [encounter and KO tracker](https://pokemonnull.com/encounter-tracker.html) | The project documents more than 275 hand-crafted singles and doubles fights, trainer sets, encounters and custom field effects. Its calculator includes trainer presets, singles/doubles fields, team import and matchup highlighting; its tracker exports encounter and KO records. | Study deliberate Nuzlocke encounter construction, doubles, unusual field rules and how planning tools support a very dense battle campaign. Null explicitly targets experienced Nuzlockers and pushes difficulty beyond comfort, so use it as an upper-bound stress test rather than Cobblers' baseline. |
| Pokemon Unbound 2.1.1.1 | [Creator release thread and documentation index](https://www.pokecommunity.com/threads/pok%C3%A9mon-unbound-completed.382178/) · [general guide](https://docs.google.com/spreadsheets/d/1LFSBZuPDtJrwAz7t6ZkJ-il4j8M3qCdaKLNe6EZdPmQ/edit) · [location guide](https://docs.google.com/spreadsheets/d/1PyGm-yrit5Ow6cns2tBA9VEMwLVMzn3YhDRipABjLUM/edit) · [trainer teams](https://docs.google.com/spreadsheets/d/1Ha06sD9mKw5yXXT2icVZjVQapcArU5C5gLEvA-hkq9o/edit) | The creator page links separate general, availability and trainer-team sheets plus the underlying level-up, egg-move, evolution and base-stat data. Difficulty modes are explicit; the creator calls Insane intentionally unfair and recommends the Battle Frontier for fair competitive battles. | Study how a fight can be a puzzle with clues, broad team-building access and difficulty modes. Also useful as a warning: an intentionally unfair mode is a different product promise from Cobblers. |
| Inclement Emerald 1.13 | [Creator release thread](https://www.pokecommunity.com/threads/pok%C3%A9mon-inclement-emerald-a-decomp-difficulty-hack-version-1-13.457039/) · [creator-linked community documents](https://drive.google.com/drive/folders/1aajjfQwRdnZczqcVTGoTnBrs6Yq6pBRk) | The download ships Pokemon changes, locations and other reference files; the linked community folder adds trainer teams. Normal, Hard and Challenge explicitly change EVs and battle rules. Challenge removes bag use and Shift style. | Compare difficulty produced by rules and training access against difficulty produced by stronger rosters. Its ordinary trainers intentionally receive weaker EV spreads than specialists so exploration does not become a slog. |
| Renegade Platinum 1.3 | [Drayano's release page](https://projectpokemon.org/home/forums/topic/52294-pok%C3%A9mon-renegade-platinum/) · [creator's online documentation](https://pastebin.com/u/RenegadePlatinum) · [community damage calculator](https://m-row1709.github.io/RenPlat-damage-calc/dist/index.html?gen=4) | The creator's files cover trainer Pokemon, wild encounters, Pokemon and move changes, items, trades and special events. The calculator carries important trainer sets and Renegade-specific changes. | A strong reference for preserving leader identity and signature Pokemon while widening availability and making the whole game self-contained. Its first Elite Four run also demonstrates limited roster variance. |

### Older and harsher references

| Project | Canonical material | What it contains | Caveat and value |
|---|---|---|---|
| Emerald Kaizo | [Creator release thread](https://www.pokecommunity.com/threads/pokemon-emerald-kaizo.395830/) · [community damage calculator](https://calc.anastarawneh.com/hacks) · [Drxx resource/strategy overview](https://www.youtube.com/watch?v=GjjSwzL2avA) | The creator thread gives the intended curve, no-EV rule and major battle formats. The community ecosystem supplies the detailed trainer mastersheet, AI move-choice and switch-in notes, encounter references and calculator presets used by serious runs. | The creator did not publish a modern all-in-one trainer workbook. Treat community sheets as derived material and cross-check against the ROM version. Excellent for studying gauntlets, deterministic planning and attrition; poor as a fairness target if copied whole. |
| Blaze Black / Volt White | [Drayano's release page](https://projectpokemon.org/home/forums/topic/13244-pok%C3%A9mon-blaze-black-pok%C3%A9mon-volt-white/) | The patch package includes regular and important trainer rosters, battle types and rewards, wild encounters, Pokemon changes, movesets, evolution changes and item locations. | Useful for the foundational Drayano model: widen the player's roster and item access, then upgrade every trainer while retaining each leader's theme and signature. |
| Sacred Gold / Storm Silver | [Drayano's release thread and documentation package](https://gbatemp.net/threads/pokemon-sacred-gold-storm-silver.327567/) · [community battle/route reference](https://www.runlocke.com/game/sacred-gold-storm-silver) | The creator package documents locations, Pokemon changes, items, evolutions and events. Detailed trainer sets in modern planners are community-recorded rather than a complete creator-authored roster document. | Useful for level-curve repair, linearizing an open region enough to protect that curve, and making evolution items/TMs available before the League. Cross-check community trainer data before using an exact set. |

### Additional references worth keeping nearby

- [Blaze Black 2 / Volt White 2 Redux documentation site](https://smilingzero.github.io/BlazeBlack2ReduxWiki/) is a useful modern, searchable presentation of trainer, encounter, item and Pokemon changes. It is a separate Redux project, not interchangeable with Drayano's original BB2/VW2 data.
- [Platinum Kaizo calculator and source](https://git.anastarawneh.com/May8th1995/PKCalc) includes all trainer sets, a hack-specific Dex, locations and encounter tracking. It is valuable for studying what complete planning support looks like even if Platinum Kaizo is harsher than Cobblers should be.
- [Dynamic Calc](https://hzla.github.io/Dynamic-Calc-Decomps/) supports several documented hacks and is useful for comparing how trainer sets, save data, switch logic and battle logs can live in one planning surface.

## How to read the material

Do not start by browsing famous rosters. For each hack, read in this order:

1. **Rules:** level caps, Set/Shift, bag use, EVs, healing and battle format.
2. **Availability:** what can actually be caught, evolved, taught and purchased before the fight.
3. **Mechanics:** altered stats, types, abilities, moves and items.
4. **Trainer set:** only now inspect the roster.
5. **Calculator and AI notes:** check the intended lines against the engine that will execute them.

A roster divorced from steps 1–3 is misleading. A Pokemon that is a fair answer in Renegade Platinum may be absent, unable to evolve, or missing its move in Cobblers.

## Reusable patterns

### 1. Availability before pressure

**What it is:** The designer places multiple usable answers before asking the player to solve a matchup. Those answers differ in how they solve it: immunity, resistance, speed, disruption, weather control, priority or raw damage.

**Why it works:** Team building becomes the game. The question is “which answer fits my team?” rather than “did I catch the one intended counter?”

**What it demands:** An availability table including evolutions, moves, items and levels, not just species names. At least two independently obtainable answer families should exist for a major fight; one should come from an ordinary, reliable source.

**How it fails:** A single rare encounter, hidden ability, late evolution item or unproven Habitat Block becomes a fake choice. Conversely, giving six perfect hard counters makes the leader irrelevant.

### 2. One coherent engine

**What it is:** A lead or early member establishes the rule of the fight: rain, sun, sand, snow, Trick Room, Tailwind, terrain, hazards, screens or a status plan. Later members exploit that same rule.

**Why it works:** Every slot contributes to a recognizable identity. Removing the setter or changing the field becomes a meaningful plan.

**What it demands:** The engine must be visible, interruptible and actually supported by the AI. Each member still needs a job when the engine is absent.

**How it fails:** Permanent or repeatedly refreshed field effects turn the whole roster into a stat tax. Reusing weather for several consecutive leaders makes fights blur together.

### 3. Guaranteed action

**What it is:** Focus Sash, Sturdy, a resistance berry, Disguise-like protection, priority or a naturally durable lead ensures that a key Pokemon acts once.

**Why it works:** A fight's central idea cannot be erased by one fast super-effective hit. It also makes a setup lead or warning shot reliable.

**What it demands:** The guaranteed action must be worth noticing: one layer of hazards, one status, one screen, one speed-control move or one meaningful attack.

**How it fails:** Several Sashes turn every encounter into mandatory chip and make speed or good preparation feel pointless. A Sash whose only job is to secure a knockout is often just hidden extra HP.

### 4. Counter inversion

**What it is:** One ability, item or typing interaction reverses the most obvious answer: Lightning Rod against Electric attacks, Levitate or Air Balloon against Ground, Sap Sipper against Grass, Storm Drain against Water, a resistance berry against an expected super-effective hit.

**Why it works:** It teaches that type advantage is the start of planning rather than the whole plan.

**What it demands:** A clue and an alternate line. The player should be able to pop the Balloon, attack from the other category, change weather, use neutral damage, status the target or switch to a second answer.

**How it fails:** If every member invalidates the same counter, the fight deletes an entire answer class. Hidden immunity chains are knowledge checks, not strategy.

### 5. Targeted coverage

**What it is:** A defender carries one coverage move for the Pokemon normally sent into it: Ice coverage for Ground, Grass for Water/Ground, Fighting for Steel, Dark or Ghost for Psychic.

**Why it works:** The player must check damage, speed and bulk instead of clicking a super-effective move automatically.

**What it demands:** Coverage should pressure the intended answer without necessarily deleting it. The player needs another response: outspeed, survive, pivot, use priority or choose a different answer family.

**How it fails:** Four perfect coverage moves make typing meaningless. Surprise coverage on every trainer rewards reading documents more than understanding the game.

### 6. Role compression

**What it is:** A team member performs two related jobs: setter plus pivot, hazard lead plus speed control, wall plus status spreader, breaker plus priority cleaner.

**Why it works:** Four- and five-member teams can still behave like complete teams. Every turn advances the plan.

**What it demands:** The two jobs must fit the Pokemon's stats, ability and likely AI choices. A support move that the AI will never select is not a role.

**How it fails:** Packing setup, recovery, coverage and utility onto every member produces perfect generalists with no readable weakness.

### 7. Invited setup, punished by the ace

**What it is:** Early passive or defensive members tempt the player to boost, stall or lock into a move. The ace carries Unaware, Haze, phazing, priority, a Choice Scarf, a revenge-kill ability, status or coverage that attacks that plan.

**Why it works:** The fight has an arc. The player must think about the last member while exploiting the first.

**What it demands:** The punishment should answer one greedy plan, not every kind of setup. The ace must still be beatable by a team that managed resources well.

**How it fails:** If the ace invalidates all progress automatically, the first half was dead time. An undocumented end-of-fight reversal can make scouting require a loss.

### 8. Speed as a resource

**What it is:** Paralysis, Tailwind, Trick Room, priority, Choice Scarf, weather speed abilities and deliberate speed tiers decide who controls the next turn.

**Why it works:** Speed control creates answers that are not type counters and lets slower species matter.

**What it demands:** Players need access to their own control, priority, bulk or stall tools. The duration and setter need to be readable.

**How it fails:** Stacking Tailwind, weather speed and Scarf users makes every normal-speed Pokemon irrelevant. Constant speed reversals become calculator chores.

### 9. Hazards and switching pressure

**What it is:** Stealth Rock, Spikes, Toxic Spikes, phazing and pivots make team order and repeated switching matter.

**Why it works:** The battle tests the whole six rather than six isolated one-on-ones. A nominal counter can be worn into range before the ace arrives.

**What it demands:** Reliable switching AI, removal or prevention options, and a battle long enough for the investment to matter.

**How it fails:** Hazards are decoration if the AI never switches. Without removal, several layers become unavoidable attrition. Cobblers must not base a leader on this pattern until RCT switching is proven; the current simulator also cannot grade it soundly.

### 10. Anti-setup with a narrow purpose

**What it is:** Taunt, Encore, Haze, Clear Smog, phazing, Unaware, Infiltrator or a timely Choice item stops a single dominant setup line.

**Why it works:** It closes a degenerate strategy while leaving ordinary offensive and defensive play intact.

**What it demands:** Identify the exact setup line being controlled. Use the least broad answer that works.

**How it fails:** Blanket bans plus several anti-setup members remove a whole style of play. The player then solves the fight by raw stats rather than choices.

### 11. Item-defined thresholds

**What it is:** A held item changes one important calculation: a resistance berry buys a turn, Life Orb secures a two-hit knockout, Leftovers changes a stall clock, Choice Scarf changes a speed tier, Eviolite creates an unexpected wall.

**Why it works:** Items give individual members identity and make scouting actionable.

**What it demands:** The item must support the member's role and be legal at the encounter's level. The player should have comparable access where the campaign's rules promise symmetry.

**How it fails:** Six optimized items against a player with no item economy are merely hidden stat boosts. Repeated one-use berries also make rematches feel like memorization.

### 12. Distinct battle format

**What it is:** Doubles, triples, rotation or partner battles make positioning and interaction moves central.

**Why it works:** A format change tests skills that singles cannot: spread damage, protection, redirection, speed support and ally synergy.

**What it demands:** The format must be taught by ordinary trainers first, supported reliably by the runtime, and given enough player move access to be expressive.

**How it fails:** A first-time doubles boss is an interface ambush. A doubles roster run through unreliable partner or switching AI is not difficulty; it is an experiment. This is why Giovanni's format should remain held until RCT doubles behavior is proven.

### 13. Limited roster variance

**What it is:** A boss selects from a small documented set of teams or pools, so rote lead scripting is less reliable while the strategic identity remains stable.

**Why it works:** The player prepares for a concept rather than one exact turn sequence. Renegade Platinum's first Elite Four run uses several possible teams; later Radical Red fights also use variants.

**What it demands:** All variants must obey the same availability and difficulty budget. The player needs a way to scout or know the pool.

**How it fails:** In a Nuzlocke, an unseen random variant can kill a Pokemon through no planning fault. Randomness should change execution, not decide whether the player brought the right type.

### 14. Route trainers as lessons

**What it is:** Ordinary trainers each demonstrate one piece of the upcoming leader: a weather abuser, an immunity, a resistance berry, priority, a setup move or a status plan.

**Why it works:** The route teaches through play. A player who pays attention reaches the Gym with a mental model, not just a warning sign.

**What it demands:** Short fights, clear identities and dialogue that points at the lesson without explaining the solution. Their Pokemon must come from the same local ecology available to the player.

**How it fails:** Giving every route trainer a complete competitive core makes exploration exhausting. Repeating the leader's whole gimmick turns the Gym into a rerun.

### 15. Resource normalization

**What it is:** Level caps, easy relearning, cheap or infinite leveling resources, controlled EV rules and clear item access remove grinding as the answer.

**Why it works:** Losses point back to team construction and lines of play. Run & Bun removes EVs and supplies endless leveling; Radical Red and Inclement Emerald expose modes that control grinding and bag use.

**What it demands:** The campaign must give players practical access to the moves, items, evolutions and replacement Pokemon its battles expect.

**How it fails:** A cap without replacement training or move access turns experimentation into chores. Removing resources while optimizing every opponent creates difficulty by asymmetry.

### 16. Documentation as part of the rules

**What it is:** Trainer sheets, encounter tables, calculators and AI notes are treated as supported planning tools.

**Why it works:** The hard part becomes building and executing a plan. This is central to serious Run & Bun and Emerald Kaizo play.

**What it demands:** Versioned, accurate exports from the same source data that builds the game. A roster change and its published reference must happen together.

**How it fails:** Hidden sets plus lethal stakes force sacrificial scouting. Stale documents are worse than no documents because they punish correct preparation.

## Pattern combinations

These combinations usually create a fair, memorable fight:

- **Weather setter + two beneficiaries + ace that works outside weather.** The player can fight over weather without making the last member collapse when it ends.
- **Guaranteed-action lead + one visible consequence.** A Sash lead gets one layer or one status, then the battle moves on.
- **Obvious weakness + one counter-inverter + alternate answer.** One Air Balloon asks the player to break it; four Ground immunities delete Ground.
- **Defensive opener + breaker + cleaner.** The team has a beginning, middle and end.
- **Route lesson + Gym exam.** A route trainer demonstrates Lightning Rod; the leader later combines it with screen support or speed pressure.
- **Elite Four specialization + Champion synthesis.** Each member isolates one learned skill; the Champion asks the player to preserve enough options to combine them.

These combinations tend to feel arbitrary:

- weather + hazards + sleep + speed doubling + resistance berry on a four-member early team;
- every intended counter hit by super-effective coverage;
- several Focus Sashes before the player has reliable chip or hazards;
- a boss format never seen before;
- mandatory switching against an AI/runtime whose switching is not proven;
- one viable answer tied to a rare spawn, hidden ability or consumable evolution item;
- random team selection with no disclosed pool in a permanent-death mode.

## Applying this to Cobblers

### Constraints the rewrite must respect

- The player-facing ace curve is **20 / 25 / 30 / 35 / 40 / 45 / 50 / 55**, and RCT's relative cap is **0**.
- `docs/story/AVAILABILITY.md` is the roster boundary. Species alone are insufficient; check actual evolution level, legal moves and obtainable items.
- This campaign supports ordinary play and optional Nuzlocke rules. A major fight should not require a sacrifice or a one-turn blind guess.
- RCT switching, doubles behavior, item use and several AI details remain runtime concerns. The local simulator explicitly cannot validate switching, hazards, pivot loops or doubles soundly.
- Major fights should be scoutable. The final implementation should generate player-facing team sheets from the same source that generates RCT data.

### Current leaders: what to preserve or trim during the rewrite

| Leader | Pattern worth preserving | Main risk to remove |
|---|---|---|
| Brock | Sturdy or another single guaranteed action on the ace makes the first super-effective hit start a damage race. | Do not add a second survival trick or perfect coverage to every Rock member. One lesson is enough at Gym 1. |
| Misty | Rain gives the whole team an identity; one Lightning Rod member checks an Electric-only plan. | Do not also make every member punish Grass. Preserve at least two distinct answer classes. |
| Surge | One Air Balloon or Levitate member can test whether the player has a second line after finding Ground types. | The current data also gives Lightning Rod to most of the team. Repeated immunity is answer deletion, and current availability already has three Ground families. |
| Erika | Sun can turn a nominally defensive type into speed and damage pressure. | The current plan stacks sun, sleep, hazards, Chlorophyll, Focus Sash and a Coba ace. Choose the engine and one check; cut the rest until the fight reads cleanly. |
| Koga | Tinted Lens on the ace is a strong way to punish relying only on Bug resistance. | Sash Tailwind, Levitate, Shuca, Toxic Spikes, Throat Spray and Quiver Dance is the highest overstack risk among the authored teams. Build one poison-control sequence. |
| Sabrina | Trick Room gives slow Psychic partners a distinct tempo and makes speed control matter. | Do not depend on the mansion's unplaced Habitat pool as the only source of Dark/Ghost answers. Avoid making the ace simultaneously Sashed, recoil-free and impossible to revenge. |
| Blaine | Drought is a clear engine that meaningfully changes Water damage and Fire thresholds. | The current simulation shows Drought already changes the result. Solar Beam/Power Herb, hazards, several premium items and six attackers can tax every answer at once. Let sun carry more of the difficulty. |
| Giovanni | Ground-centered team with one learned format or positioning test. | Roster and singles/doubles decision are still held. Do not use doubles until ordinary trainers teach it and RCT proves it. |

### Nuzlocke-compatible minimum for each major fight

- Two independently catchable answer families before the fight.
- One answer available from a normal route or guaranteed event, independent of an unproven Habitat Block.
- No answer that requires an unavailable move, illegal evolution, hidden ability, or unplanned shop item.
- The lead and core engine are telegraphed by route trainers, environment or dialogue.
- No mandatory one-turn guess and no expected sacrifice.
- One countermeasure per answer class at most.
- A plausible win through managed attrition; zero deaths need not be guaranteed.

### Unfairness checks

Reject or revise a roster if any answer is yes:

1. Is the only clean answer unavailable, rare, unproven or missable?
2. Does the plan rely on an illegal move, evolution, ability, item or level?
3. Does a normal win require sacrificing a Pokemon?
4. Does turn one require a blind guess whose wrong branch loses a Pokemon?
5. Has the team hard-countered every reasonable answer class?
6. Is the boss the player's first exposure to its format or central mechanic?
7. Is crucial coverage or an item hidden with no scouting path?
8. Does the opponent get an asymmetric rule the player cannot interact with?
9. Is a simulator verdict being quoted for switching, hazards, pivots or doubles it cannot model?
10. Does a retry teach only a hidden roster fact rather than a reusable battle lesson?

## Rewrite workflow

1. Freeze the leader's strategic lesson in one sentence.
2. Pull the pre-fight availability slice, including move and item access.
3. Name at least two answer families and one backup line.
4. Choose one engine.
5. Choose one answer-check that pressures, but does not delete, the obvious answer.
6. Assign lead, support, breaker and ace roles; combine roles only where the AI can execute them.
7. Give the ace one math-changing property.
8. Write two route-trainer lessons that foreshadow the engine and answer-check separately.
9. Validate legality and RCT format.
10. Run deterministic damage checks, then in-game AI tests for anything involving switching, support moves, items or doubles.
11. Generate the player-facing reference from the same rules.
12. Re-test with an informed team and a plausible walked team; for Nuzlocke review, examine deaths and forced lines, not only win rate.

## What to borrow, and what to leave behind

Borrow the documentation discipline of Run & Bun and Emerald Kaizo, Radical Red's explicit difficulty contracts, Drayano's combination of broad availability with preserved leader identity, Inclement Emerald's separation between ordinary-trainer and boss pressure, and Unbound's use of clues before a tactical puzzle.

Leave behind modes their own creators describe as unfair, permanent field rules the player cannot contest, hidden random roster variants, and gauntlet attrition calibrated for mandatory Nuzlockes. Cobblers should be hard because the next fight creates a team-building problem whose answers exist in the world, not because the player needed an external script or a sacrificial first attempt.
