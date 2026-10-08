# The Nether dungeon: a repeatable legendary run, scoped and costed

**Status: SCOPE ONLY (content-architect, 2026-10-08).** Nothing here is designed in full, built, placed or run.
It answers the owner's ask of 2026-10-09 and says what must be proven first. No ADR yet: the choices that would
constrain later work (the dimension, the entry key) each wait on an experiment in section 12.

**The ask (paraphrased closely):** the Nether becomes a repeatable run. A team fights through to a final boss and
earns rewards, and can farm it on a loop: "the late-game money sink the economy design needs". The boss is a
legendary: the roaming beasts (Raikou, Entei, Suicune) and anything else with no home. "Moltres is in the overworld
now, so the Nether is clear." The owner thinks everything built so far is once-per-player.

Labels: **VERIFIED** = seen in source, a jar read, or a run, with the citation; **ASSUMED** = inferred or relayed and
not checked. A number marked *relayed* was not measured by this unit.

---

## 0. The premises, checked (three are wrong or incomplete)

| # | Premise | Finding |
|---|---|---|
| P1 | "Moltres is in the overworld now, so the Nether is clear" | **Half true.** Moltres's adopted copy stands in the Craters (`docs/STATE.md:137`, `:221`; pasted at 6252,168,5344, `:55`). But **the Nether copies still generate.** Adopting a template does not switch off its structure set. `data/adopted_legendary_sites.json:664`: "Its Nether copies still generate; if the feather ever reaches a player who goes to the Nether, those altars answer too (one per copy)". The feathers now have a source: Shrew Station's dialogue at `gym8_cleared`, with issuing on (`STATE.md:137`). So **once a player holds an Ember Feather, each Nether Moltres copy is a live altar.** The shared border holds **16 Moltres attempts, 67 Ruinous-shrine attempts and 643 Blaine-gym attempts** (`docs/world-building/DIMENSIONS_AND_BORDERS.md:65-67`, *relayed* counts of attempts, not structures). Each Blaine copy carries a `kanto_blaine` spawner and a healer (`:228-232`). Suppressing those copies is **blocked on an unproven override** (`STATE.md:370`). The Nether is not clear. |
| P2 | "Moltres, the shrines and the legendary structures are there" (the Nether) | **Only the Ruinous four belong there by design.** Chi-Yu, Wo-Chien, Ting-Lu and Chien-Pao stay Nether-generated because their stakes are a Nether worldgen feature (VERIFIED, jar strings: `docs/research/notes/legendary-catalogue-reopened.md:55-70`; `adopted_legendary_sites.json:999-1002`). Their progress is kept **outside the world save**, in `minecraft-shrine-data`, keyed partly on the spawn point. A re-export may reset it (INFERRED, `:69-70`). **Nothing authored by this repository is in the Nether**: no `data/` record places anything there (grep `the_nether` in `data/`: only biome blacklists and the Moltres re-home note). The Nether also holds the game's only stone ore, `nether_fire_stone_ore` (`STATE.md:345`). **The live world has never generated a Nether chunk** (`DIMENSIONS_AND_BORDERS.md:195-196`). That matters for timing (section 5). |
| P3 | "Everything built so far is once-per-player" | **Wrong.** At least four repeatable mechanisms exist, two of them with repeating rewards. (a) **Heaven's Arena**: endless pool bouts, a fresh draw each time, a purse on every win, rank-up fights paid again on each repeat (`data/arena_fights.json:140-145`). Its core loop is PROVEN in game for one player: spawn, start, win/loss callback, re-roll, remove (`docs/research/notes/arena-per-player-opponents.md:354-371`). (b) **The Mega field.** Uncatchable Megas respawn on a per-den clock (10/15 min) and drop an owner-only raw stone on defeat at 15-30% (`data/gulch_mine.json:3152-3158`, `:3216-3233`; built and applied, never seen in game, `STATE.md:219`). (c) **rctmod placed trainers never refuse a rematch** (`STATE.md:84`). This is a defect we hold off, not a feature. (d) The **Hoopa cradle keeper** respawns a lost per-player legendary every 1,200 ticks until it is caught (`docs/world-building/LEGENDARY_SWEEP.md:98-106`; built, not run). |
| P4 | "Money sink" and "earn rewards, farmable" | **These pull opposite ways.** A run that pays out is a **source**. It is a sink only if entry costs more, in money or materials, than the payout is worth in money. And the payout must not be resellable at the bank (the bank "may pay for anything", `STATE.md:140` item 2). **The postgame already has an uncapped CobbleDollars faucet:** the arena pays about $1,700-$3,150 per bout, endlessly (`arena_fights.json:38-111`, typical purses). Whether CobbleDollars actually pays on a `cobblemon:npc` win is ASSUMED, not run (`arena-per-player-opponents.md:198-199`). A dungeon that also paid cash would double that faucet. Section 3 shows how the dungeon becomes a sink. |

Two disagreements found while reading, not chased:

- `data/markets.json:22` says "The blackout is a flat $600"; `STATE.md:107` says **20% rounded up**.
- `STATE.md:54` puts Zapdos at 881,67,5569 (moved 2026-10-03); `STATE.md:221` still says (562, 74, 2614).

---

## 1. What a farmable run needs, and what exists

| Need | What exists | Status |
|---|---|---|
| **A boss that comes back** | Hoopa cradle keeper: a per-player owned legendary, respawned after loss, only the owner's ball holds (`LEGENDARY_SWEEP.md:98-106`). The Mega keeper: a respawn clock per den, macro spawn, claimed at once (`gulch_mine.json:3158`). | Both built, neither run. The macro-spawn rule is VERIFIED (EXP-046, `STATE.md:83`). |
| **A per-player opponent** | Arena: `spawnnpcat` at absolute coordinates, then `runmolang ... q.npc.start_battle(...)` (VERIFIED, one player, `arena-per-player-opponents.md:357-363`). Wild: a per-player owned spawn keyed on a score (`hp.own`, Hoopa). | NPC: proven for one player. Wild per-player: built, not run. Two players: **never run anywhere** (needs a second account, `STATE.md:177`). |
| **A reward that repeats** | Mega field drop: one owner-only item entity per defeat, matched by Pokemon UUID through the `battle_fainted` callback (`gulch_mine.json:3220`). Arena purses. | Built; the drop is unseen. |
| **A once-only first reward** | Spectrier cap: judges the spawn, grants a per-player advancement (`tools/spectrier_cap.py:2-29`). Hoopa: the `caught` advancement, granted on a catch within 40 blocks. Arena first-clear prizes (`arena_fights.json:142`). Kyogre design: once per player, keyed on the catch (`docs/world-building/KYOGRE_CAVE.md:41-44`). | Built (Spectrier, Hoopa) or designed (Kyogre); none run. |
| **Reset** | Nothing resets a space. The arena needs none: it spawns and kills per bout. | **Missing.** A dungeon with doors or spent rooms needs one. |
| **Instancing** | The pocket dimension works (EXP-047, `STATE.md:234`). ADR-004 reserves it for spaces "instanced per player" (`docs/decisions/ADR-004-pocket-spaces.md:32`), which "needs per-player coordinates inside it" (`:56`). | The dimension is VERIFIED. **Per-player slots inside it: never built.** |
| **Failure handling** | The arena's loss skips the blackout (`STATE.md:214`). The Megas' `claims.exempt_tag`: a Mega that blacks a player out makes no item claim (`gulch_mine.json:3158`). The NPC cleanup must run while the player is near, because the NPC unloads with its chunk (`arena-per-player-opponents.md:369-370`). | Patterns exist. A flee, forfeit or logout mid-battle is **unknown** (`:194-197`, `:371`). |
| **An entry cost** | The ferry's checked-payment sequence (`STATE.md:217`, "the ferry's proven checked-payment sequence"). The direct-trade villager for item barter (EXP-055, `STATE.md:140` items 5 and 6). | Ferry played and approved (`STATE.md:236`). Barter held, `approved: false`. |
| **A lockout / diminishing return** | Nothing. The respawn clocks use game time (`gulch_mine.json:3158`). | **Missing.** A per-player score is trivial vanilla work, but "daily" means 24 hours of **server uptime**: game time stops when the server stops (ASSUMED, vanilla behaviour, not researched here). |
| **A team** | Nothing. "There is no shared-party quest state" (`STATE.md:170`). Two players battling one wild Pokemon together is **unknown**. | **Missing; experiment.** |

**Verdict: about 70% of a farmable boss exists as built-but-unrun parts.** The missing 30% is reset, instancing, a
lockout and a team. The parts that exist are mostly unproven in game, so the first cost is experiments, not building.

---

## 2. How a run resets, and whether two groups interfere

Three shapes:

1. **The Nether's own terrain** (fight through to a fortress, say). **Rejected.**
   - Nothing resets: terrain gets mined, and loot is first-come.
   - No tool of ours knows where the ground is. The heightmap covers the overworld only, and the rule forbids
     reading a world to decide a position (CLAUDE.md, "Ground comes from the heightmap").
   - Two groups share everything.
2. **A built space at a fixed Nether coordinate.** Per-player spawns (the arena and Hoopa shape) keep fights apart,
   so a **boss room alone needs no instancing**. A room chain with doors does, because a door opened by one group is
   open for the other.
   - Placing it means generating those Nether chunks and building blind into unknown terrain. Lava seas and
     fortresses are possible. A sealed shell can make the box safe ("solid first, then the void",
     `docs/mechanics/LEGENDARIES.md:62-69`), but **the entrance has to meet terrain we cannot see.**
3. **A pocket dimension** (EXP-047), with one slot per group at per-slot coordinates.
   - **It is flat and deterministic**, so the ground rule is satisfied by construction.
   - **Global selectors reach it** and positional ones are confined to it, so the blackout, the level cap and the
     keepers work there unchanged (EXP-047 README:29-42).
   - Reset is a function per slot: kill the slot's tagged entities, re-close its doors, zero its scores.
     **Nothing is consumed**, so no block rebuild is needed, as long as walls cannot be broken. That needs a ward or
     a solid shell; the gulch's Mining Fatigue ward is the built pattern (`gulch_mine.json:3149`).
   - Players in different slots cannot see each other (ADR-004:57-63). That is wanted.

**Recommendation: shape 3 for any multi-room run; shape 2 or 3 for a boss room alone.** The Nether fiction survives
if the door is in the Nether. One way: a **key item used anywhere in `minecraft:the_nether`** carries its holder
into the pocket's slot. That needs no Nether ground at all.
- This is ASSUMED to be expressible in vanilla, through an advancement trigger on using or consuming an item with a
  dimension condition. **It is not in `docs/research/`: experiment X3.**
- The portal precedent is a click into `cobblers:pocket` (`data/portals.json:4-5`, unrun).

---

## 3. Rewards, the economy, and what stops it being the only thing anyone does

**Make it a sink by charging materials and paying in things money cannot buy.**

- **Entry:** a consumed key, crafted or bartered from **Nether materials a player must go and get.**
  - Ancient debris or netherite scrap is effort-limited; gold, which piglin farms make AFK-farmable, is not. That
    is exactly the distinction `STATE.md:143` asks the economy redesign to draw.
  - The key also fits the owner's barter rule ("4 netherite ingots for a master ball", `STATE.md:140` item 5).
  - An optional cash fee on top is a pure sink. The ferry's payment sequence is the mechanism.
- **Payout: items, never CobbleDollars.** The arena already owns the cash faucet (P4).
  - Every dungeon reward must be **excluded from the bank's buy list**, so it cannot launder back into cash.
  - It must pass `tools/economy_audit.py`'s arbitrage check (0 today, `STATE.md:130`).
- **Diminishing returns, three levers** (recommend all three, owner to tune):
  - A **collection table** per boss: repeat clears draw without repeats until the set is complete, then fall to a
    flat consolation.
  - A **per-player lockout per boss**, counted in game time (section 1, last-but-one row).
  - **The key cost itself.**
- **Flat versus scaling:** flat per clear, with a harder tier optional (section 9). Do not raise payouts with
  repetition; that is the shape that makes one activity dominant.
- **Challenge mode:** a voucher player (about $100k, `STATE.md:144`) is "not concerned with Minecraft". A material
  key would lock them out of the dungeon. **Owner question:** a cash-only key for Challenge players, at a price that
  dents the voucher, or no dungeon for them.
- **The blackout is itself a sink:** 20% on a loss (`STATE.md:107`). The arena exempts its losses. **Owner
  question:** does losing to the boss black out? The recommendation is yes, with no item claim, because the run is
  the risk. The claim must be exempt, as the Megas' is.

---

## 4. Heaven's Arena as the model, and the boss's machinery

**The arena is the model for everything except the boss.** Its per-player NPC spawn, start, callback and kill loop is
the only proven per-player combat loop we have. Room fights before the boss should reuse `tools/arena_runtime.py`'s
machinery: classes, pool parties re-rolled per challenge, our `battle_victory` callback, the loss path.

**The boss should be a wild legendary spawned per player, not an NPC.**

- **The catch.** A first clear that "gives the encounter" means a catchable Pokemon. An NPC's party cannot be caught.
- **The drop.** The Mega field's drop is keyed on a wild Pokemon's UUID through `battle_fainted`
  (`gulch_mine.json:3220`), and that is the repeat reward's mechanism.
- **Precedent.** The Hoopa keeper already spawns a per-player owned legendary, refuses other players' balls
  (`ball_check`, `set_shakes(0)`) and grants `caught` (`LEGENDARY_SWEEP.md:100-106`).
- **The repeat form.** After the catch, the same spawn adds the `uncatchable` property (VERIFIED, Cobblemon 1.8.0
  `UncatchableProperty.kt`, `docs/research/notes/wild-mega-pokemon.md:97-101`).

**The hard part is difficulty.** A wild legendary is one Pokemon against six.
- Levels well over the party help, and the Mega field's rule is cap +10 to +17 (`gulch_mine.json:3244`). Fixed
  IVs and moves help too: Necrozma's tower spawns with all IVs 30 and four set moves (`legendary-catalogue-reopened.md:37`).
- After the Champion the cap is 100 (`STATE.md:344`). So a level-90-plus boss is catchable under the catch block
  (`STATE.md:244`, installed and unrun), and "cap + 10" stops meaning anything.
- **Whether Cobblemon 1.8.0 offers any boss modifier** (HP scaling, alpha behaviour in battle, multiple actions)
  **is not recorded.** The spawn overhaul's "bosses are native alphas" (`STATE.md:25`) does not say what an alpha
  does in a fight. **Research R1.**
- If nothing exists, the honest fallback is a **gauntlet**: room fights with no heal between (the arena's gauntlet
  format, `arena_fights.json:27`) wear the team down before a strong wild boss.

---

## 5. The Nether's existing content, and what the dungeon does to it

- **The Ruinous shrines and stakes:** leave untouched. A pocket-dimension dungeon touches no Nether chunk, which is
  one more reason for it.
- **The Moltres copies:** become live altars once feathers circulate (P1). Either accept one extra Moltres per
  feather-holder per copy, or prove a structure-set override.
- **The Blaine copies:** clutter after badge 7, and a skip route before it (`DIMENSIONS_AND_BORDERS.md:228-232`).
- **Timing.** A worldgen override only affects chunks generated after it. **The live world has none yet**, so the
  override experiment (X1) should land **before any player enters the live Nether.**
  - The dungeon raises this: it is a reason to go to the Nether, at exactly the point where players have the
    feathers.
- **Fire stones:** the Nether is the only stone ore (`STATE.md:345`), so players already have one reason to visit.
  The dungeon adds a second.

---

## 6. The Nether's terrain against a built space: re-export consequences

- **The Nether is in the world folder** (`DIM-1`), like the pocket dimension (EXP-047 README:52-57).
- **A re-export makes a new world folder and carries players only** (`STATE.md:126`). So:
  - **Built inside the Nether:** lost on re-export. Rebuilt by a re-application step, if the regenerated Nether
    matches the old one. The same seed is carried (`STATE.md:67`); identical generation is ASSUMED.
    LegendaryMonuments' stake progress may reset as well (P2).
  - **Built in a pocket:** also lost, but rebuilt **exactly** from data, because its ground is flat and ours.
    `reapply.py carry` could also copy `dimensions/` (EXP-047 README:63-65, not built).
- **Per-player progress** (caught, cleared, collection, lockout) belongs in **advancements**, which `reapply.py carry`
  already moves (`docs/mechanics/LEGENDARIES.md:138-143`). Keep scores for transient run state only.
- **Entities (the boss, NPCs) are always erased by a re-export** (`LEGENDARIES.md:149-150`). Spawning on demand
  means there is nothing to restore.

---

## 7. The legendary list: who has no home, and who suits a boss

Sources: the catalogue in `adopted_legendary_sites.json:984-1013`, `LEGENDARY_SWEEP.md:38-60`, `data/legendaries.json`,
and `docs/world-building/STRUCTURE_DECISIONS.md:85`. **Whether each species, and its model, exists in Cobblemon 1.8.0
was NOT checked for any row below.** That check is research R1, and Hoopa is the only one recorded as present
(`STATE.md:226`). Being "in the arena audit's legendary list" (`tools/arena_runtime_audit.py:58-67`) is a games list
typed by hand, not evidence of the jar.

| Species | Current status (source) | Boss fit |
|---|---|---|
| **Entei** | No home: `burned_tower` is in the disabled Johto pack; "no structure anywhere" (`STRUCTURE_DECISIONS.md:85`) | **Best Nether fit**: a fire beast, the owner's named case |
| **Raikou** | As Entei | Good. The owner named it; no Nether theme needed |
| **Suicune** | As Entei; also "stay unplaced" (`docs/mechanics/WATER_MAP.md:239`) | Good, the owner named it. Water in the Nether is a fiction stretch, which a pocket room can dress away |
| **Heatran** | Unplaced, "an owner's call": a 120x90x137 volcano, two Sinnoh spawners to empty, a Magma Stone chain (`adopted_legendary_sites.json:1004`) | **Excellent**: fire/steel, Nether-native in the games. The dungeon is a home for it that needs no volcano landmark. The Magma Stone can be its first-clear item |
| **Ho-Oh** | Not loaded (Johto `bell_tower`, `LEGENDARY_SWEEP.md:57`) | Good, fire. A rotation slot |
| **Mewtwo** | No structure. A fossil route via the DNA and the catalyst is **proposed, waiting on the owner** (`docs/mechanics/ITEM_ROUTES.md:110-132`, Q3) | A classic final boss, but it would be **two authors for one legendary** if the fossil route is chosen. Pick one |
| **Cresselia, Shaymin, Dialga, Palkia, Regieleki, Regidrago, Deoxys, Jirachi** | Not loaded: their pack is disabled (`LEGENDARY_SWEEP.md:56-60`) | Possible rotation slots. **A spawn needs only the species, not the pack's structure** (ASSUMED: R1 confirms the species ship in Cobblemon itself) |
| **Arceus** | Unplaced: 18 pedestals want a plate each, and nothing makes a plate (`adopted_legendary_sites.json:1005`) | **Not a boss. A capstone:** plates as the dungeon's repeat drops would open the Arceus temple. Section 9 |
| Chi-Yu, Wo-Chien, Ting-Lu, Chien-Pao | Have a home: the Nether shrines (P2) | **No.** That would be a second author |
| Moltres | Adopted in the Craters, plus live Nether copies (P1) | No |
| Kyogre, Rayquaza / Groudon | Planned (`KYOGRE_CAVE.md`) / authored (`data/legendaries.json`) | No |
| Giratina, Darkrai, Necrozma x2, Mew, Hoopa, Spectrier, Glastrier, Calyrex, the birds, the Regis, the lake trio, Lugia, Celebi, Latias, Latios | All homed (`LEGENDARY_SWEEP.md:38-58`, `STATE.md:139`) | No |
| Eternatus | Out by the owner until a Galar Particle supply exists (`STATE.md:137`) | No |
| Everything else (the Kalos, Alola, Galar and Paldea legendaries, the Ultra Beasts, the Paradox legendaries) | No catalogue entry, so no home | Unchecked. R1 lists which exist in 1.8.0 |

**Shortlist for a first boss: Entei, then Heatran.** Entei is the owner's named case. Heatran turns an awkward
"owner's call" into a home.

---

## 8. Catchable: first clear gives the encounter, later clears give items

**The model works here, keyed on the catch, not the clear** (the Kyogre design's rule, `KYOGRE_CAVE.md:256-266`):

- **Until the catch:** each clear spawns the player's own catchable boss. It is owned by a per-player score, and
  only that player's ball holds (Hoopa's `ball_check`). Fainting or fleeing it costs a run, not the Pokemon forever.
- **The catch** grants a per-player, per-species advancement, like Spectrier's (`tools/spectrier_cap.py:16-20`).
  The keeper reads it on the next run.
- **After the catch:** the boss spawns `uncatchable`. A defeat rolls the item table through the Mega field's
  owner-only drop.
- **The level-cap catch block** (`STATE.md:244`, unrun) is no obstacle after the Champion (cap 100). Gate the
  dungeon at `champion_cleared`, as every other postgame legendary is gated (Giratina, Darkrai, Necrozma, Mew).
- **Risk:** the wild-victor claim system would treat a boss that beats a player as a guardian and take their items
  (`STATE.md:107`). The boss needs the Megas' exempt tag.

**Repeat rewards, from items with no route today** (`ITEM_ROUTES.md`):

- **The 17 Arceus plates**, which have "none recommended" today (`:143`, Q4). With them the temple's 18 pedestals
  become a long goal. The 17-against-18 count and the temple's "locked" state (INFERRED Azure Flute,
  `adopted_legendary_sites.json:1005`) are unread.
- **Mint seeds** (`:176`).
- **PP Up and PP Max, and the plain bottle cap** (`:180`, `:184`).
- **Rare and Exp. Candies**, "cut by design" today (`:179`): the owner's call.
- **The 14 ancient balls** (`:182`).
- **The Dynamax band**, if Dynamax is kept (`:177`, Q6).
- **Each boss's own form item:** Heatran's Magma Stone.

Do **not** put arena trophies or the Ability Patch here. Arena trophies stay once-per-player prizes (`STATE.md:142`
item 3), and the Ability Patch is already an arena prize (`ITEM_ROUTES.md:181`).

---

## 9. Rotation or one dungeon per boss, and the tenth run

- **One dungeon, rotating bosses**, not one build per boss. Geometry is the expensive part (builders), and a boss
  is a data record.
  - Rotation by game-time week, or player's choice among unlocked bosses.
  - Each boss's collection table is separate, so a player chooses what they farm.
- **Why someone runs it a tenth time:**
  1. A collection that is not finished yet: plates towards Arceus is the strongest, because it ends in a
     legendary.
  2. A best-clear record per player, as the arena's streak is (`arena_fights.json:117`).
  3. A harder tier that unlocks after N clears: a higher level, a longer gauntlet.
  4. The next boss in the rotation.
  - A shiny chance per run is ASSUMED to be a spawn property; not in `docs/research/`.
- **What must not drive it:** cash. Section 3.

---

## 10. Cost, in the repository's measured units

Measured rates: a builder **3.4-4.6M** (CLAUDE.md, measured 2026-10-02); research **0.57-0.66M** per settled question
(CLAUDE.md); an independent audit **0.59M-2.99M** (`docs/REPORT_2026-09-30_DAY.md:160`,
`docs/MORNING_REPORT_2026-09-30.md:112`), quoted here as 2M with an Opus escalation for softlock and economy audits
(CLAUDE.md rule 1). Prepare is ~35 min (*relayed* from the brief; `STATE.md:122` records 169 jobs and no current
time).

**Scale reference.** **The Rift has no single recorded cost.** It was built across many sessions: sculpt, skin, the
Deep, the Deep's city, Victory Road, the zones (0.94M + 1.07M), the Mega field, the arena, the HQ. Fifteen or more
units, so "compare to the Rift" cannot be done in tokens. The closer reference is **Heaven's Arena: six units**
(research note, fight list, dome builder, dome audit, runtime builder, runtime audit; `STATE.md:214`). The full dungeon
is about one and a half arenas. For a night's scale: 15.8M across 14 agents (`docs/HANDOVER_SESSION.md:45-46`);
44.4M of agents in the 2026-10-09 session (`docs/REPORT_2026-10-09.md:69`).

| | **A. Full dungeon** | **B. One repeatable boss** |
|---|---|---|
| What it is | Pocket dimension, 4 group slots, 3 rooms (arena-NPC gauntlet, a guardian room, a gate) then a boss room; 4-6 rotating bosses; per-player collection tables; key entry from the Nether; lockout; best-clear record | One pocket room (or a sealed Nether chamber) reached by the key; one boss (Entei); first clear catchable, then `uncatchable` with one drop table; key entry; lockout |
| Research | R1 species, models, boss modifiers and the key trigger (1M); R2 multi-player wild battle (0.6M) | R1 trimmed to one species and the trigger (0.6M) |
| Design | Run design: rooms, state, reset (content-architect, 1M); bosses, gauntlet, tables (trainer-balance-designer, 1M) | Boss and table (trainer-balance-designer, 0.6-1M); this document is the rest |
| Builders | Dimension, slots, geometry and reapply step (4M); run runtime: entry, rooms, reset, sweep, lockout, exemptions (4M); boss keeper: catch key, drops, rotation (4M); Nether overrides, key item, rewards and bank wiring (3-4M) = **15-16M** | One builder: room, keeper, key, drop and wiring, reusing the `hoopa_cradle` and gulch keeper patterns (**4M**) |
| Audits | Softlock and escape (Opus, 2M); economy arbitrage (Opus, 2M); instance isolation and geometry (2M) = **6M** | One audit, softlock plus economy (Opus, **2M**) |
| Integration and experiments (main session; cannot delegate) | X1-X6 on staging, 2-3 full prepares, a second account for X5: **4-6M** | X2-X4 and X6, 1-2 prepares: **2-3M** |
| **Total** | **~28-32M** | **~9-11M** |
| What it gets | The owner's whole ask: a team run, rotation, a long tail (plates), a real sink | A farmable legendary with a catch, a sink through the key, and every mechanism A needs, proven once |
| What it leaves out | Nothing asked for | Rooms, teams (each player fights their own copy), rotation, plates as a long goal, and the Arceus capstone |

---

## 11. Recommendation

**Build B first, designed as A's first slice. Decide A after B is played.**

- **Every mechanism under A is built-but-unrun.** That covers per-player wild spawns, owner-only balls, owner-only
  drops, NPC gauntlets and the pocket dimension's spawning. **Nothing has run with two players**
  (principles 15 and 20).
- **B proves the boss keeper, the catch key, the drop table, the key entry and the economy exemption on one boss for
  about a third of A's cost.** Each of those carries straight into A; nothing in B is thrown away.
- **A's extra cost is mostly rooms, instancing and teams**, and the team question cannot be answered without X5. If
  two players cannot share a wild battle, A's "team fights through" becomes "a team walks through together and each
  fights their own boss". The owner may not think that worth 20M more.
- **Separately, and whichever is chosen:** run X1 (the Nether copy override) **before anyone generates the live
  Nether**. It closes the live Moltres altars and the Blaine copies. It is cheap now and impossible to undo later.

---

## 12. Experiments that must run first

| Id | Question | Why it gates | Where |
|---|---|---|---|
| **X1** | Does an overlay datapack override of the Blaine and Moltres structure sets (or their biome lists) suppress Nether copies without a worldgen error on 1.21.1? | P1; timing (section 5). Already an open item (`STATE.md:370`, `DIMENSIONS_AND_BORDERS.md:233-237`) | A disposable generated world: no export needed (`STATE.md:66`) |
| **X2** | Per-player wild boss: spawn an owned legendary per player, refuse others' balls, grant `caught` on a catch, then spawn `uncatchable` and roll an owner-only drop on defeat | The core of B. Runs the Hoopa keeper (`data/hoopa_cradle.json` runtime_checks) and the Mega drop (EXP-054) on one target | Staging, one player |
| **X3** | Can a key item used in `minecraft:the_nether` trigger a function (advancement on using or consuming an item, with a dimension condition), and does the crossing into `cobblers:pocket` arrive cleanly? | The entry, with no Nether ground needed. ASSUMED today | A disposable world, then staging |
| **X4** | A loss to the boss: blackout yes or no, no item claim (exempt tag), and a flee, forfeit or logout mid-battle | Failure handling. The forfeit question is still open from the arena (`arena-per-player-opponents.md:371`) | Staging, one player |
| **X5** | Can two players battle one wild Pokemon together in Cobblemon 1.8.0, and what happens to two per-player bosses in one room? | A's "team". Needs the second account (`STATE.md:177`) | Staging, two accounts |
| **X6** | Research R1: which candidate species, and models, exist in 1.8.0; any boss modifier (HP, alpha in battle); the plate count and the Arceus temple's lock | Section 7's table and section 4's difficulty | `cobblemon-researcher`, jar reads |

**Owner questions:**

1. **Team, or each player their own boss?** X5 decides whether a real team is possible.
2. **Does losing to the boss black out?**
3. **What does entry cost: materials, cash, or both?** And what about a Challenge-mode player?
4. **Do the plates go in the drop table**, which opens Arceus, or stay unrouted (`ITEM_ROUTES.md` Q4)?
5. **Mewtwo:** the dungeon or the fossil route, never both.
6. **First boss: Entei or Heatran?**
