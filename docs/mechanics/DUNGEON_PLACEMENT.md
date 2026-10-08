# Where the dungeons sit against the League: before, after, or split

**Status: DESIGN ARGUMENT ONLY (content-architect, 2026-10-08).** Nothing here is built. It answers the owner's
question of 2026-10-08: with eight badges, then a window in which a player builds the team that takes the Elite Four,
do the dungeons sit (a) before the League, inside that window, (b) after it, as postgame, or (c) split? It takes as
settled, and does not reopen, the owner's decision of the same day: **paradoxes appear only in late dungeons, as
threats and rare rewards; the wild stays as it is.** Everything paradox-shaped waits on model delivery.

Labels: **VERIFIED** / **ASSUMED** as `.claude/rules/research.md`; *read* = this unit read the value at the cited
line; *relayed* = taken from another document's measurement and not re-run here; **REASONED** = argued from the
standard type chart or design logic, not simulated.

---

## 0. Premises checked

| # | Premise (the owner's framing) | Finding |
|---|---|---|
| Q1 | "The cap at 80" in the window | **Wrong. The cap in the window is 60**, and 62 after Lance. The owner decided on 2026-10-02 to keep it there: "After gym 8 the cap stays at 60 ... Capped until Blue (62), and none after him" (`docs/mechanics/LEAGUE_LEVEL_CAP.md:3-6`, *read*; the table `:50-56`, *relayed* from that document's walk through rctmod's `LevelUtils`). After Blue it is 100. The only "80" in the docs is a passing remark that a cap "passes 80" only after the League (`docs/world-building/SOUTHERN_RIFT_MEGA.md:679`). Nothing records a plan for 80. **Every number below uses 60.** If the owner wants 80, that is a new decision with its own consequences: the Elite Four would sit 20 levels under the cap, which `LEAGUE_LEVEL_CAP.md` section 3 already argued against. |
| Q2 | "The Entei room exists at badge 8" | **Wrong. Entei is gated at the Champion.** `data/entei_boss.json:13` `gate_flag` is `cobblers:flag/champion_cleared`, at level 100 (`:15-16`). What opens at badge 8 is **the Nether itself** (`data/nether_gate.json:7`, `gym8_cleared`) with its near ring at 54-60 (`docs/mechanics/NETHER_ENCOUNTERS.md:100`). The deep ring (65-75) is postgame (`:101`). Also built and not run: Entei (`entei_boss.json:4`) and the gate (`nether_gate.json:4`). |
| Q3 | "Heaven's Arena exists at badge 8" | **Right.** The `league_eve` band, cap 60, ranks 1-3, requires `gym8_cleared` (`data/arena_fights.json:20`). Rank 3 is two three-member legs with no heal, "the Elite Four's own member count" (`:52-56`). `champion_door` (cap 62) needs Lance beaten (`:21`). |
| Q4 | "Legendaries catchable" in the window | **Partly.** Groudon and Regigigas are level 60 behind 8 badges (`data/legendaries.json:442-445`, `:491-494`, *read*). Both gates are "*proposed*", and Regigigas is "UNREACHABLE until Registeel is sited" (`docs/mechanics/LEGENDARIES.md:25-26`). Celebi's gate is built and its trigger is open (`:28`). Lugia is Champion-gated (`:27`). So the window already contains, on paper, **legendaries at the Elite Four's own level.** |
| Q5 | "The dungeons": one block, before or after | **The dungeon design is not one block.** `docs/mechanics/DUNGEONS.md:223-231` sites seven homes. Five are overworld and open **before** gym 8: the Night Shift at 0 badges, the Street at gyms 2-3, the Patriarch at 6-7, the Cistern at 7 and the Temple at 7-8. The two Nether ones open **after** the Champion. Every run re-tiers to the cap at entry (`:287-298`), so **all five overworld dungeons already run in the window**, at band 5 (cap 60/62, `:297`). Under the current design the window has dungeon *runs*. What it lacks is a dungeon that is **new** at badge 8: none first opens there. That is the real gap the owner's question points at. |
| Q6 | "Only 7 paradoxes are modelled today" | **Right**, and the seven are not all at 570-590 (`docs/research/notes/paradox-pokemon-1.8.0.md:24-27`, `:45-66`, *read*). The 570-590 ones are Walking Wake (590), Iron Leaves (590), Iron Hands (570), Iron Jugulis (570) and Iron Boulder (590). **Koraidon and Miraidon are 670.** Flutter Mane, the only paradox the simulator ran in full, is **not** among the seven (`:14-21`). |
| Q7 | "The wild stays as it is" | **The wild as it is already spawns paradoxes**: the datapack's inherited spawn files are live wherever suppression does not reach, which includes a rare 45-60 Flutter Mane in the Wedge's unsuppressed dark forest (`paradox-pokemon-1.8.0.md:94-102`). Our pools exclude paradoxes (`data/encounter_design.json:71`, *relayed* via the note). "Only in late dungeons" therefore **needs** the inherited spawns switched off, as the note recommends (`:309-310`). This applies the owner's decision; it does not reopen it. And **the decision itself is in no document**: no file under `docs/STATE.md`, `docs/mechanics/` or `docs/decisions/` mentions paradoxes. Record it (section 5, change C1). |

---

## 1. What the Elite Four is balanced against today

The Elite Four as authored (`data/trainers.json`, *read*): each brings six, at 57, 58, 58, 59, 59 and 60, and holds
items.
- **Lorelei**: Froslass, Mamoswine, Jynx, Weavile, Walrein, Lapras (`:4249-4327`).
- **Bruno**: Hitmontop, Machamp, Hariyama, Lucario, Heracross, Hitmonlee (`:4852-4927`).
- **Agatha**: Mismagius, Spiritomb, Banette, Dusknoir, Chandelure, Gengar (`:5453-5528`).
- **Lance**: Aerodactyl, Gyarados, Flygon, Baxcalibur, Dragalge, Dragonite (`:6054-6129`).
- **Blue**: Pidgeot 58, Exeggutor 59, Rhydon 60, Arcanine 60, Alakazam 61, Blastoise 62 (`:6655-6720`;
  `data/league_trainers.json:134-136`).

**The levels are pinned by the cap, not by balance.** The aces sit at 60 because the window's cap is 60, and the cap is
60 because it is the next trainer's ace (`LEAGUE_LEVEL_CAP.md:58-63`). **So no option below can retune the Elite Four
by level.** The only levers are species, sets, held items and member order. Challenge mode's mirror is the same
(`data/challenge_mode.json:13`).

**What the player brings is already strong.** Every player's starter is a mythical line finishing at 45
(`docs/research/notes/larvesta-starter-1.8.0.md:10-11`). The finals are Urshifu 550, Silvally 570, Solgaleo and Lunala
680, Naganadel 540 and Melmetal 600, all VERIFIED in the jar (`:63`). Volcarona (550) is the sixth (the commit at HEAD
`9646e60`). Their simulated record against the League, 1v1, of 30 bouts (*relayed*,
`paradox-pokemon-1.8.0.md:255-266`; battle_sim, IVs 15, no items, no switching):

| Pokemon | BST | E4 (of 24) | Blue (of 6) | League (of 30) |
|---|---|---|---|---|
| Solgaleo (starter) | 680 | 21 | 5 | 26 |
| Lunala (starter) | 680 | 19 | 5 | 24 |
| Silvally (starter) | 570 | 18 | 4 | 22 |
| **Flutter Mane, TM set** | 570 | **17** | **4** | **21** |
| Iron Valiant | 590 | 18 | 3 | 21 |
| Urshifu (starter) | 550 | 17 | 3 | 20 |
| Mismagius, same set | 495 | 12 | 3 | 15 |
| Volcarona (starter) | 550 | 11 | 3 | 14 |
| Naganadel (starter) | 540 | 10 | 2 | 12 |
| Melmetal (starter) | 600 | 8 | 4 | 12 |

The note's own reading: "From 45 on, Flutter Mane is a starter final, not above one" (`:273-275`). Its blind spots all
point upward: no set-up moves, no Protosynthesis, no crits (`:281-290`).

**The finding that decides most of this argument:** a 570-590 paradox at cap 60 is **not a new class of power at the
League.** It is a second starter final. The Elite Four already has to survive one per player, and on paper one Groudon
too (Q4). **What a paradox before the League changes is depth, not peak.** For a player whose starter is Melmetal,
Naganadel or Volcarona (12-14 of 30), a paradox nearly doubles the team's 1v1 answers. For a Solgaleo player (26) it
adds little.

---

## 2. The three options

All three share the same rule: dungeons stay optional. A player who ignores every dungeon still reaches and can win the
League (`docs/vision/GAME_VISION.md:112-120`, `:158-160`). That rule is what keeps speedrun viability.

### (a) BEFORE: the dungeons are the preparation window

**What it means here.** Paradox threats and paradox rewards come up in the window, at band 5 (cap 60/62), in every
late home.

**For it.**
- The vision's core loop puts the optional dungeon **before** the boss, as the thing you go and do to answer it:
  "Optional dungeon / challenge encounter -> Prepare a team -> Major trainer" (`GAME_VISION.md:57-77`), and "This next
  fight looks nasty. What can we go find that would help?" (`:77`). The League is the nastiest fight in the game.
- It fills the window with something new instead of re-tiered repeats (Q5).

**Against it.**
- A paradox becomes **the** answer to the League: the item every informed player farms before Lorelei. That is the
  shape `NETHER_DUNGEON_SCOPE.md:103-104` warns against, one activity becoming dominant (*relayed* via
  `DUNGEONS.md:335`).
- With several homes each giving a paradox, a player could reach Lorelei with three. Three starter-final-class members
  plus Groudon is unmeasured, and nothing in the repository can measure it: `tools/battle_sim.py` is 1v1
  (`paradox-pokemon-1.8.0.md:245`).
- It leaves the postgame with only Entei, Heatran, the arena's upper ranks and the deep Nether ring. After the
  Champion the cap is 100, and band 6 has nothing new to give.

**Effect on the Elite Four.** The level is unchanged (pinned at 60). The pressure is **likely to need retuning**,
because the player's ceiling moves from "starter final plus one window legendary" to "starter final plus N paradoxes".

REASONED from the standard type chart (ASSUMED, not simulated), each usable 570-590 paradox has an Elite Four member it
lines up against:
- Iron Hands (Fighting/Electric) into Lorelei's four Ice types, Weavile at 4x;
- Iron Jugulis (Dark/Flying) into Agatha's Ghosts, and Flying into Bruno;
- Iron Boulder and Iron Leaves (Psychic) into Bruno;
- Walking Wake (Water/Dragon) into Lance's four Dragons, a mutual weakness.

A team of three paradoxes covers every member. The retune would be by **sets and items**: coverage moves on each Elite
Four ace, and Focus Sash or Assault Vest on more members. It would not be by level, which the cap forbids.

### (b) AFTER: dungeons are postgame, the League is the climax

**What it means here.** Paradoxes only at band 6 (cap 100, after `champion_cleared`), and the five overworld homes'
band-5 runs stay as they are.

**For it.**
- The Elite Four stays balanced against what it was authored against, and needs no retune.
- The League is the clean climax, and postgame gets a reason to exist: band 6, the Nether pair and the full paradox
  collection. That is where Entei already is, and the paradox note's alternative gate (`:302-303`, "At cap 100 it is a
  postgame trophy").

**Against it.**
- It answers the owner's own worry least. The window keeps runs, but nothing new to find. The owner's fear is
  "a preparation window with nothing new in it is just grinding".
- A paradox at cap 100 sits beside 680 legendaries (Lugia, the Nether pair, Giratina and others). It is a collection
  piece, not a team-building decision, which is the thing pillar 2 values (`GAME_VISION.md:93-98`).

**Effect on the Elite Four.** **None.** The ceiling stays "starter final plus Groudon/Regigigas at 60 plus window
catches".

**Correction to the framing.** The window is not empty under (b). It holds:
- the whole Rift finale, which is on the critical path: `rift_crisis_resolved` admits a player to the League's
  precinct (`docs/world-building/RIFT_FINALE_CHAIN.md:35-36`);
- Victory Road, whose prizes are at 57 and 60 (`LEAGUE_LEVEL_CAP.md:117`, *relayed*);
- arena ranks 1-3;
- the near Nether ring;
- the two window legendaries;
- five dungeons at band 5.

"Nothing new" is about dungeons only, not about the window.

### (c) SPLIT: the threat and one bounded reward in the window, the collection after

**What it means here.**
- **The window (band 5)** brings paradoxes into the late dungeons **as threats**: a boss or a trainer's ace, never
  catchable.
- **Each player gets at most one paradox reward before the Champion**, from the 570 tier.
- **Band 6** has everything else: the 590s, Koraidon and Miraidon (670), repeat paradox bosses and the collection.

**For it.**
- It gives the window the thing it lacks, something new to meet, and the vision's "what can we go find" (`:77`).
- It bounds the Elite Four exposure to a figure that has been simulated: one starter-final-class member.
- It keeps postgame worth having.
- It matches the paradox note's own recommendation: gate at gym 8 or the Champion, one key per player (`:302-306`).
- Seeing a paradox as a threat at 60 before you can own one is the "this next fight looks nasty" feeling, aimed at the
  dungeon instead of the League.

**Against it.**
- It is the most rules to build: a per-band reward table, a "one before Champion" limit per player, and a validator for
  both.
- It also has to answer co-op: a badge-8 player and a Champion-cleared player are in different bands. With solo
  instances (`DUNGEONS.md:461-462`, Q7 there) this resolves per player, as the cap does (`GAME_VISION.md:149-152`).

**Effect on the Elite Four.**
- **Small and bounded. Expect no retune, but confirm it**: the U1 check in section 6 runs before content.
- The worst case is a Melmetal-starter player who adds the one paradox best matched to a member. For example, Iron
  Hands into Lorelei, REASONED: that one member's fight gets much easier, and the other three are unchanged.
- That is the same size of effect as the starter choice already has: 12 to 26 of 30 across the six lines.

---

## 3. Recommendation: (c), with the gate keyed on the band, not the home

**Choose (c).** It is the only option that gives the window new content and keeps the Elite Four's exposure inside a
measured range. The reasons to prefer it, in order:
1. **The level cap already makes (a)'s peak harmless and its depth dangerous.** One paradox is a measured quantity:
   21/30, starter-final class. Three is not measured. So limit the count, not the timing.
2. **(b)'s safety is real but buys too little.** The Elite Four needs no protection from a single 570 at cap 60. It
   already faces starter finals at 680.
3. **The vision's loop wants something to find before the hardest fight** (`GAME_VISION.md:57-77`).

**The rule that makes (c) correct: gate paradoxes by band (the cap at entry), never by home.**
- The Patriarch opens at gym 6-7 (`DUNGEONS.md:227`), and a paradox wins **19 of 19** foes at gyms 1-5
  (`paradox-pokemon-1.8.0.md:276-277`, *relayed*).
- "Late dungeons" read as "late homes" would therefore leak a paradox to a cap-50 player. Read as "band 5 and 6", it
  cannot.
- The band is already frozen at entry from `rctmod player get level_cap` (`DUNGEONS.md:287-289`).

**Concretely:**

| Band | Cap | Paradox as threat | Paradox as reward |
|---|---|---|---|
| 1-4 | 20-55 | none | none |
| 5 (window) | 60, 62 | boss or trainer ace in the late homes, uncatchable (`uncatchable` is VERIFIED, `entei_boss.json:20`) | **one per player before `champion_cleared`**, from the 570-tier usable set (today: Iron Hands, Iron Jugulis), caught once (the Entei catch-once pattern, `entei_boss.json:22-25`) |
| 6 (postgame) | 100 | any usable paradox | the rest, including the 590s; Koraidon and Miraidon only here |

- **The window needs a dungeon that first opens at badge 8.** Recommend the Temple Calendar, already "~gym 7-8"
  (`DUNGEONS.md:229`). Its door opens at `gym8_cleared`, the Nether gate's flag (`nether_gate.json:7`). It becomes the
  window's new place, and the home of the band-5 paradox reward. The other late homes carry band-5 paradox *threats*
  only.
- **The Nether pair stay postgame**, as built (`entei_boss.json:13-14`).
- **Why 570-only in the window.** The 590s (Walking Wake, Iron Leaves, Iron Boulder) have no row in the simulator yet,
  and Iron Valiant at 590 matched Flutter Mane's League total (21) with a worse gym record (`:267`). Allowing 590 in
  the window is cheap to decide later, once U1 runs.

---

## 4. What each option does to the Elite Four, in one place

| | (a) before | (b) after | (c) split, as recommended |
|---|---|---|---|
| Paradoxes a player can hold at Lorelei | unbounded (one per late home; up to 5 usable at 570-590 today) | 0 | at most 1, a 570 |
| Measured basis | none: no team simulator | the authored baseline | one member at 17/24 Elite Four bouts (Flutter Mane, the proxy) |
| Elite Four members out-classed (REASONED) | all four, by a three-paradox team | none new | at most one per player (whichever member the chosen paradox lines up against) |
| Retune needed | **likely**, by sets and items (levels pinned at 60) | **no** | **expected no**; U1 decides |
| Postgame left | thin | rich | rich |

---

## 5. Changes to `docs/mechanics/DUNGEONS.md` (listed, not made)

- **C1. Section 0:** add the owner's paradox decision (2026-10-08) as a premise with its date. It is recorded nowhere
  (Q7). Add that the window's cap is 60/62, not 80 (Q1).
- **C2. Section 3 table (`:223-231`):** add a "paradox" column per home: none for 1-2, threat at band 5+ for 3-5, the
  band-5 reward at the Temple, any at band 6. Move the Temple Calendar's "First reachable" from "~gym 7-8" to
  "`gym8_cleared`", the window's dungeon.
- **C3. Section 4 rewards (`:248-281`):** add the paradox reward rule. It is catch-once per player, keyed on the catch
  (Entei's `catch.rule`). The band-5 reward is limited to one per player before `champion_cleared`, from the 570 tier.
  The generator fails closed on any paradox reward in bands 1-4, on a 590 or 670 at band 5, and on a second band-5
  paradox for one player.
- **C4. Section 5 band table (`:291-298`):** add a "paradox threat" column (bands 5-6 only). The caps in the table are
  already right (60, 62, 100). Nothing there needs the owner's 80.
- **C5. Section 7.1 schema:** per band, `paradox.threats` (species list), `paradox.reward` (species, or null) and
  `paradox.reward_scope` (`per_player_before_champion` | `per_player`).
- **C6. Section 7.2 validation (`test-author`):**
  - every paradox named must be in the **usable set**, meaning species data, resolver and model installed and enabled
    (today 7, `paradox-pokemon-1.8.0.md:24-27`); fail closed otherwise, so a doll can never ship (`ENCOUNTER_DESIGN.md:207`,
    *relayed*);
  - paradox species must not appear in bands 1-4;
  - a band-5 reward must be 570 BST, read from the jar's species data, not typed into the record.
- **C7. Section 8:** add Q10-Q13 below.
- **C8. Cross-reference:** the paradox note's Flutter Mane rite says "move it to a dungeon first clear when dungeons
  exist" (`paradox-pokemon-1.8.0.md:305-306`). That key is the band-5 reward under this design, so the two must not
  become two rewards.
- **C9. Dependency, outside DUNGEONS.md:** switching off the inherited paradox spawn files is a precondition of "only
  in late dungeons" (Q7). It goes on `datapack-content-dev`'s list, with `data/spawn_suppression.json` as its home.

The architectural choice is ADR-008's (Proposed). This placement only narrows its reward rules, so it is an amendment
to propose there, not a new ADR.

---

## 6. Open questions, each with a recommendation

1. **Q10. Is the cap in the window 60, as decided on 2026-10-02, or does the owner now want 80?** *Recommend 60.* The
   whole League levelling, the arena's bands (`arena_fights.json:15`, `:20`) and Groudon and Regigigas at 60 rest on it.
2. **Q11. One paradox per player before the Champion, or none (b)?** *Recommend one, the 570 tier*, subject to U1.
3. **Q12. Which home is the window's new dungeon?** *Recommend the Temple Calendar*, opened at `gym8_cleared`. The
   alternative is a sixth overworld home first opened at badge 8, which costs a whole new dungeon.
4. **Q13. Paradox threats at band 4 (cap 50/55) as uncatchable bosses?** *Recommend no.* A 570-590 boss at 55 is
   legal, but "paradoxes are what the late world holds" reads cleaner from badge 8. The 19-of-19 early-strength figure
   means a player who sees one at band 4 will expect to be able to get one.
5. **Q14. Koraidon and Miraidon (670): paradox rewards or legendaries?** *Recommend band 6 only, treated as legendaries*,
   gated at the Champion with the others (`entei_boss.json:14`).

**Unknowns, to run before any paradox content.** These are experiment candidates. The main session runs them, since
this agent has no shell.
- **U1.** Run the `battle_sim` per-foe matrix for the five usable 570-590 paradoxes against each Elite Four member at
  60 and Blue at 62, the same rig as `paradox-pokemon-1.8.0.md` section 4. It settles 570-only and confirms "no
  retune".
- **U2.** There is no team-against-team check: `battle_sim` is 1v1. Either accept the 1v1 proxy, or make the first
  staging League run with a starter-plus-paradox team an `experiments/` record.
- **U3.** Model delivery (ADR-006, Proposed) decides whether the usable set grows past 7. Every paradox row waits on it.
- **U4.** Groudon and Regigigas at 60 are the window's other upgrade. Their gates are *proposed* and Regigigas is
  unreachable (`LEGENDARIES.md:25-26`). The Elite Four baseline in section 1 assumes the owner settles them; neither is
  simulated against the League. Add both to U1's matrix.
