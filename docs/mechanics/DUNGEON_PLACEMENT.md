# Where the dungeons sit against the League: before, after, or split

**Status: DESIGN ARGUMENT ONLY (content-architect, 2026-10-08, revised the same day).** Nothing here is built. It
answers the owner's question of 2026-10-08: with eight badges, then a window in which a player builds the team that
takes the Elite Four, do the dungeons sit (a) before the League, inside that window, (b) after it, as postgame, or (c)
split? It takes as settled, and does not reopen, two decisions of the same day:
- **Paradoxes appear only in late dungeons, as threats and rare rewards; the wild stays as it is.** Everything
  paradox-shaped waits on model delivery.
- **The Beast Ball is the key to every dungeon boss, and only dungeon bosses** (Entei today, Heatran and whatever
  follows). Legendaries in the overworld stay catchable with ordinary balls, so a Master Ball keeps its purpose.

The revision folds in the owner's second instruction: **the level cap is the governing constraint**, because a
catchable boss must sit at or under the cap of the player who throws at it. It replaces the first version's argument
for a window paradox reward.

Labels: **VERIFIED** / **ASSUMED** as `.claude/rules/research.md`; *read* = this unit read the value at the cited
line; *relayed* = taken from another document's measurement and not re-run here; **REASONED** = argued from the
standard type chart or design logic, not simulated.

---

## 0. Premises checked

| # | Premise | Finding |
|---|---|---|
| Q1 | "The cap at 80" in the window (repeated in the owner's cap instruction: "bosses at 80 or below") | **Wrong. The cap in the window is 60**, and 62 after Lance. Decided by the owner on 2026-10-02: "After gym 8 the cap stays at 60 ... Capped until Blue (62), and none after him" (`docs/mechanics/LEAGUE_LEVEL_CAP.md:3-6`, *read*). The table at `:50-56` (*read*) gives 25-55 after gyms 1-7, 60 after gym 8 and through Agatha, 62 after Lance, and 100 ("no cap in effect") after Blue. The per-gym caps before that are 20/25/30/35/40/45/50/55 (`docs/mechanics/PROGRESSION_LADDER.md:469-470`, *read*). **Every number below uses these caps.** A cap of 80 would be a new decision, and it would leave the Elite Four 20 levels under it, which `LEAGUE_LEVEL_CAP.md` section 3 argued against. |
| Q2 | "The Entei room exists at badge 8" | **Wrong. Entei is gated at the Champion**, at level 100 (`data/entei_boss.json:13`, `:15`, *read*). What opens at badge 8 is the Nether itself (`data/nether_gate.json:7`, `gym8_cleared`), with its near ring at 54-60 (`docs/mechanics/NETHER_ENCOUNTERS.md:100`). Neither the Entei unit nor the gate has run. |
| Q3 | "Heaven's Arena exists at badge 8" | **Right.** The `league_eve` band (cap 60, ranks 1-3) requires `gym8_cleared` (`data/arena_fights.json:20`). |
| Q4 | "Legendaries catchable" in the window | **Partly.** Groudon and Regigigas are level 60 behind 8 badges (`data/legendaries.json:442-445`, `:491-494`). Both gates are *proposed*, and Regigigas is unreachable until Registeel is sited (`docs/mechanics/LEGENDARIES.md:25-26`). They are overworld legendaries, so under the owner's boss rule they **stay catchable with ordinary balls, the Master Ball included**. |
| Q5 | "The dungeons": one block | **Not one block.** `docs/mechanics/DUNGEONS.md:223-231` sites seven homes. Five are overworld and open before gym 8; the two Nether ones open after the Champion. Every run re-tiers to the cap at entry (`:287-298`), so all five overworld dungeons already run in the window at band 5. **What the window lacks is a dungeon that first opens at badge 8.** |
| Q6 | "Only 7 paradoxes are modelled today" | **Right** (`docs/research/notes/paradox-pokemon-1.8.0.md:24-27`). The 570-590 ones are Walking Wake, Iron Leaves, Iron Boulder (590), Iron Hands and Iron Jugulis (570). Koraidon and Miraidon are 670. |
| Q7 | "The wild stays as it is" | **The wild as it is spawns paradoxes** where suppression does not reach (`paradox-pokemon-1.8.0.md:94-102`), so "only in late dungeons" needs the inherited spawn files switched off (`:309-310`). And the paradox decision is recorded in no document yet (change C1). |
| Q8 | **How the cap refuses a catch, and whether a Beast Ball can override it** | **It cannot.** The level-cap pack's `poke_ball_capture_calculated` callback calls `set_shakes(0)` when the target's level is **strictly greater** than the thrower's RCT cap (`tools/levelcap_pack.py:146-170`, *read*). That callback fires after every ball's maths, the Master Ball's included, and a refusal from any script wins whatever the order (`docs/research/notes/beast-ball-key-1.8.0.md:98`, `:133-136`). The Beast Ball key only *raises the rate and refuses*; it never forces a success (`:133`). So **a key boss above the thrower's cap is uncatchable with every ball**, and the player sees the cap's "Your team isn't strong enough yet" instead of the key's line (`:296-299`). A boss **at** the cap is catchable. Neither the cap pack nor the key callbacks has been thrown at in game (`:142-143`). |
| Q9 | **Which dungeon bosses could be caught at all** | **Only wild ones.** The overworld dungeons' boss is **an NPC by default** with a 3-6 member team; only the Nether dungeons have a wild boss (`DUNGEONS.md:190-193`, *read*). A ball thrown at an NPC's Pokemon is refused at the hit as `not_wild` (`beast-ball-key-1.8.0.md:151-152`, VERIFIED as a refusal Cobblemon has; ASSUMED that an RCT or Cobblemon NPC's battle Pokemon takes that path, not thrown at). So the cap question bites only where a dungeon has a **wild catch-mode boss**: today Entei, then Heatran. Bands 1-5 of the overworld homes have none. |
| Q10 | **Is a level-60 boss cheaper to catch than a level-100 one?** | **No.** The capture formula has no level term above level 13, except a step to x0.1 when the thrower's active battler is 50 or more levels below the target (`beast-ball-key-1.8.0.md:55-66`, VERIFIED in bytecode). At cap, the player's team is at the boss's level, so the step never applies. **A catch-rate-3 boss at 60 costs the same throws as Entei at 100**: about 4 asleep at 1 HP, 19 at full HP, so $21k-$95k at $5,000 a ball (`:207-214`, computed by the note). Paradox catch rates are **not read** anywhere in the repository (no match in `paradox-pokemon-1.8.0.md`). |

---

## 1. What the Elite Four is balanced against today

The Elite Four as authored (`data/trainers.json`, *read* in the first pass): each brings six at 57, 58, 58, 59, 59 and
60, with held items. Lorelei Ice (`:4249-4327`), Bruno Fighting (`:4852-4927`), Agatha Ghost (`:5453-5528`), Lance
Dragon (`:6054-6129`); Blue's six run 58-62 (`:6655-6720`; `data/league_trainers.json:134-136`).

**The levels are pinned by the cap, not by balance** (`LEAGUE_LEVEL_CAP.md:58-63`). No option can retune the Elite Four
by level; only species, sets, held items and order.

**What the player brings is already strong.** Every starter is a mythical line finishing at 45
(`docs/research/notes/larvesta-starter-1.8.0.md:10-11`). Simulated 1v1 against the League, of 30 bouts (*relayed*,
`paradox-pokemon-1.8.0.md:255-266`; battle_sim, IVs 15, no items, no switching): Solgaleo 26, Lunala 24, Silvally 22,
Flutter Mane (TM set, the paradox proxy) 21, Iron Valiant 21, Urshifu 20, Volcarona 14, Naganadel 12, Melmetal 12.
**A 570-590 paradox at cap 60 is a second starter final, not a new class of power.** What it adds is depth, and most
for the Melmetal, Naganadel and Volcarona players.

---

## 2. The three options, with the cap as the constraint

The cap rule for any catchable (key) boss: **its level must be at or under the cap of every player its gate admits**,
read at the throw. Before gym 8 that is the per-gym cap (20-55); in the window 60 (62 after Lance); after the
Champion any level. The cap only rises, since completing the series never resets it (`LEAGUE_LEVEL_CAP.md:31-33`), so a
boss at the entering player's cap stays catchable for the whole run.

All three options keep dungeons optional: a player who ignores them still reaches and can win the League
(`docs/vision/GAME_VISION.md:112-120`, `:158-160`).

### (a) BEFORE: the dungeons are the preparation window, rewards included

- **Catchable where:** a wild paradox boss in each late home, at band 5, spawned at 60.
- **What the cap does:** it allows this (60 is at the window cap), but it does nothing to limit it. A cap-60 paradox
  is a starter final; three of them is unmeasured, and `tools/battle_sim.py` is 1v1 (`paradox-pokemon-1.8.0.md:245`).
- **Worth a Beast Ball?** Yes, which is the problem: three catches at $21k-$95k each is most of the window's spare
  income (by badge 8 a player has earned about $202,835, *relayed* from `beast-ball-key-1.8.0.md:201-203`, with about
  30% unspent by design). The key would become the League's price.
- **Cost:** a wild-boss room added to each overworld home, whose design is an NPC boss (Q9). The Elite Four likely
  needs a retune by sets and items.

### (b) AFTER: every catch is postgame

- **Catchable where:** only after `champion_cleared`, cap 100: the Nether pair, and any band-6 paradox boss.
- **What the cap does:** nothing. At cap 100 every boss level is legal.
- **The window:** keeps its five band-5 runs, NPC bosses, item rewards, but nothing new and no paradox at all.
- **Elite Four:** no change.

### (c) SPLIT: the threat in the window, every catch after the Champion

- **The window (band 5):** paradoxes appear in the late homes **as threats only**: the ace of an NPC boss or trainer,
  uncatchable because it is an NPC's (Q9). Rewards are items. The window gets one dungeon that first opens at
  badge 8 (section 3).
- **Band 6 (cap 100):** every catchable dungeon boss, keyed on the Beast Ball: Entei and Heatran, and the paradox
  rewards as wild bosses in the late homes' band-6 runs.
- **What the cap does:** it stops binding. No key boss sits under a cap below 100, so Q8's wrong-message trap cannot
  happen and no level has to be chosen against it.
- **Elite Four:** no change; the player holds no paradox at Lorelei.

**The variant the first version recommended, (c) with one window catch**, is the only shape under which the cap
matters: a wild 570 paradox at level 60, one per player before the Champion. It is legal under the cap. It is
**rejected below**.

---

## 3. Recommendation: (c), every catch after the Champion; pre-League dungeon bosses are set pieces

**Choose (c) in its revised form.** Pre-League dungeon bosses are fight-only set pieces with item rewards; every
catchable dungeon boss is postgame, behind `champion_cleared`. The reasons, in order:

1. **Before gym 7 there is no key to sell.** The Beast Ball is sold only at Cinderlee, gym 7's town
   (`beast-ball-key-1.8.0.md:225-229`). A catchable boss at bands 1-3 would be a lock whose key cannot be bought.
2. **In the window, the cap permits a catch but does not make it a good one.** A level-60 boss costs as many Beast
   Balls as a level-100 one (Q10). It also needs a wild-boss room in an overworld home designed for an NPC boss (Q9),
   and a "one before the Champion" rule with its own validator.
3. **The window already has its catchable upgrade, and the owner's rule protects it.** Groudon and Regigigas at 60
   (Q4) and the Victory Road prizes at 57 and 60 (`LEAGUE_LEVEL_CAP.md:117`, *relayed*) are overworld catches with
   ordinary balls. The depth a window paradox would have added for a weak-starter player is available there, at no
   key price. Settling those two gates matters more than a window paradox does (U3).
4. **The Elite Four stays at its authored baseline**, so U1 leaves the critical path.
5. **The window still gets something new**: paradox threats at band 5 and a dungeon that opens at badge 8. That is
   the vision's "this next fight looks nasty" (`GAME_VISION.md:57-77`), aimed at the dungeon.

**What this loses, said plainly:** a Beast Ball bought at Cinderlee has no target until the Champion. Buying early is
harmless (`beast-ball-key-1.8.0.md:226-227`), but the ball sits idle through gym 8 and the League. Q12 asks the owner.

**Gate paradoxes by band (the cap at entry), never by home.** The Patriarch opens at gym 6-7 (`DUNGEONS.md:227`), and
a paradox wins 19 of 19 foes at gyms 1-5 (`paradox-pokemon-1.8.0.md:276-277`, *relayed*). The band is already frozen
at entry from `rctmod player get level_cap` (`DUNGEONS.md:287-289`).

| Band | Cap | Paradox as threat (NPC ace, never catchable) | Catchable dungeon boss (wild, Beast Ball key) |
|---|---|---|---|
| 1-4 | 20-55 | none | none |
| 5 (window) | 60, 62 | in the late homes (Patriarch, Cistern, Temple) | **none** |
| 6 (postgame) | 100 | any usable paradox | Entei (100, built), Heatran (designed), one wild paradox boss per late home, catch-once per player per species (`entei_boss.json:22-24`), then `uncatchable` farm mode |

- **The window's new dungeon: the Temple Calendar**, already "~gym 7-8" (`DUNGEONS.md:229`). Its door opens at
  `gym8_cleared`, the Nether gate's flag (`nether_gate.json:7`).
- **Key bosses are never alphas.** Cobblemon re-levels an alpha to the nearest player's highest level +4 to +20, which
  at 100 only clamps but becomes a trap the day a gate moves under the Champion (`entei_boss.json:16`, *read*).
- **The cap rule as a generator check:** a key boss's level must be at or under the lowest cap its gate admits. Under
  this recommendation that is always 100, so it costs nothing to enforce, and it catches the day someone moves a gate.

---

## 4. The options side by side

| | (a) before | (b) after | (c) revised, recommended |
|---|---|---|---|
| Catchable dungeon bosses before the Champion | one per late home, at 60 | none | none |
| Catchable dungeon bosses after | the rest | all | all |
| Where the cap binds | band 5 (60) | nowhere | nowhere |
| New in the window | catches | nothing | paradox threats, the Temple |
| Paradoxes held at Lorelei | unbounded | 0 | 0 |
| Beast Ball's first use | gym 8 | Champion | Champion |
| Elite Four retune | likely, by sets and items | no | no |
| Postgame left | thin | rich | rich |

---

## 5. Changes to `docs/mechanics/DUNGEONS.md` (listed, not made)

- **C1. Section 0:** record the two owner decisions of 2026-10-08, the paradox rule and the boss-key rule (dungeon
  bosses only; overworld legendaries untouched), with the cap as the constraint on any catchable boss. Record that the
  window cap is 60/62, not 80 (Q1).
- **C2. Section 2.3 boss line (`:190-193`):** overworld bosses stay NPCs, never catchable, with no key tag. Every wild
  catch-mode boss is a key boss and is gated at `champion_cleared`. Add a band-6 wild paradox boss to the late homes.
- **C3. Section 3 table (`:223-231`):** a "paradox" column (none for homes 1-2; threat at band 5+ for 3-5; catch at
  band 6 only). Move the Temple Calendar's "First reachable" to `gym8_cleared`.
- **C4. Section 4 rewards (`:248-281`):** paradox rewards are band-6 catches, once per player per species, keyed on
  the catch (Entei's `catch.rule`). Bands 1-5 reward items only. The generator fails closed on:
  - a key boss whose level exceeds the lowest cap its gate admits;
  - a key boss gated below `champion_cleared`;
  - an alpha key boss;
  - any paradox catch below band 6.
- **C5. Section 5 band table (`:291-298`):** add "paradox threat" (bands 5-6) and "catchable boss" (band 6 only)
  columns. The caps there are right; nothing needs 80.
- **C6. Section 7.1 schema:** per band, `paradox.threats` (species list) and `paradox.catch` (species or null, band 6
  only); per boss, `key_boss` (bool) and `gate_flag`.
- **C7. Section 7.2 validation (`test-author`):** every paradox named is in the usable set (today 7), so a doll never
  ships; no paradox appears in bands 1-4; the C4 checks.
- **C8. Cross-reference:** the paradox note's Flutter Mane rite, "move it to a dungeon first clear"
  (`paradox-pokemon-1.8.0.md:305-306`), becomes a band-6 catch, not a second reward.
- **C9. Dependency, outside DUNGEONS.md:** switch off the inherited paradox spawn files (Q7), on
  `datapack-content-dev`'s list, in `data/spawn_suppression.json`.
- **C10. Section 8:** add Q11-Q15 below; drop the old window-reward question.

ADR-008 (Proposed) owns the architecture; this narrows its reward and catch rules, so it is an amendment to propose
there, not a new ADR.

---

## 6. Open questions, each with a recommendation

1. **Q11. Every catch after the Champion, or one window catch (a wild 570 paradox at 60 in the Temple)?**
   *Recommend after* (section 3). The window catch is legal under the cap; it is rejected on cost and Elite Four
   exposure, not on the cap.
2. **Q12. The Beast Ball sits idle from Cinderlee to the Champion.** Keep the sale there (owner-decided, harmless) or
   accept the idle stretch as the price of a clean League? *Recommend keep it*, and let Blaine's optional first-win
   Beast Ball (`beast-ball-key-1.8.0.md:234-235`) introduce it as a promise of the postgame.
3. **Q13. Which home is the window's new dungeon?** *Recommend the Temple Calendar* at `gym8_cleared`.
4. **Q14. Koraidon and Miraidon (670): dungeon bosses (Beast Ball) or overworld legendaries (ordinary balls)?**
   *Recommend dungeon bosses at band 6*, so they fall under the key rule; the owner's rule decides by where they sit.
5. **Q15. Are the Hoopa cradle, the Ursaluna cave, the Gulch Megas and the shrine legendaries dungeon bosses?**
   *Reading: no.* `DUNGEONS.md:216-218` leaves them out of the dungeon homes, so they keep ordinary balls. The owner
   to confirm.
6. **Paradox threats at band 4 (cap 50/55)?** *Recommend no.* A player who sees one at band 4 will expect to get one.

**Unknowns, experiment candidates (the main session runs them; this agent has no shell):**
- **U1.** `battle_sim` per-foe matrix for the paradox *threats* at band 5, so each band-5 boss stays beatable at cap
  60. The boss check `DUNGEONS.md:316` already names covers it. It no longer gates the Elite Four.
- **U2.** Paradox species catch rates: not read anywhere. `cobblemon-researcher`, from the jar's species data. It sets
  the band-6 Beast Ball cost.
- **U3.** Groudon and Regigigas gates (*proposed*; Regigigas unreachable, `LEGENDARIES.md:25-26`). These are now the
  window's catchable upgrade, so they are worth settling first.
- **U4.** In game, staging only: the level-cap refusal (strictly over) and the key callbacks (refuse a non-Beast ball,
  refund it) both work, and an NPC's Pokemon refuses a ball as `not_wild`. None of these has been thrown at
  (`beast-ball-key-1.8.0.md:142-143`, `:323-331`).
- **U5.** Model delivery (ADR-006, Proposed) decides whether the usable paradox set grows past 7.
