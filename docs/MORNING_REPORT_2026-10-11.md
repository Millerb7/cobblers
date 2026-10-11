# Morning report, 2026-10-11 (the night after "finish all dungeon work")

Branch `build/2026-10-09-dungeon-playtest` (local; not pushed). Nothing below has been run in Minecraft unless it says so.

## 1. Cost (measured, `python tools/session_cost.py`) — read this first
- **This session's agents: 422.4M weighted in all; about 223M of it since the 2026-10-10 pass-2 measurement (199.1M).**
  The overnight estimate was 40-60M. The overrun has three causes: 11 dungeon authors on Opus at 0.3-0.42M final context
  each over long runs, a long engine fix (ENGINE-SCALE), and the integrator merging 10 branches. The main session is at
  82.6M weighted and **925k of context per turn**: far past the hand-over line. A cold session should take the next job.

## 2. What got built (all merged on the branch unless noted)
- **11 new dungeons, 14 in all** (the pocket holds 16): nether — the Crucible (basalt), Ash Bell (wastes), Moth
  Cathedral (crimson), Warped Laboratory (warped), Soul Ossuary (soul sand); overworld — the Street (city), the Patriarch
  (great tree), Dragonspiral (ice spire), Field of Swords (hill keep), Zero Dig (desert dig), Starfall (night crater).
  Each: visible forks (one three-way), an optional wing with the hidden prize, two parkours, a set piece, three to five
  of the six new rooms, relics, a shortcut, four variants, rotating trainers/mini-boss/boss crews, a two-stage boss with
  a heal, ~31-33 min required at band 1. Simulated wins at the lower cap, bands 1-4: 61-89% everywhere; bands 5-6
  untuned (the simulator has no Pokemon past gym 8).
- **Six new themes** (city, great tree, ice spire, hill keep, desert excavation, night crater) and five nether themes.
- **Legendary coverage:** 125 legendary/mythical/UB/paradox species from the jar: 43 already placed, 67 assigned to
  dungeon prize pools (`data/dungeon_prize_roster.json`, `docs/mechanics/LEGENDARY_COVERAGE.md`), 7 proposed for the
  world (Forces of Nature on the Tri Peaks, three Tapus on the isles — designed, not built), 7 power lines with no early
  wild home placed in rare pools.
- **Prize pools and rotation**; **the Ultra Beast x25 fixed to x5** (Beast Ball + key ball no longer stack).
- **Engine scaling:** the keeper now runs one command chain per live slot: longest chain ~5,900 with 16 dungeons
  (was 54,739 with 3 and over the 65,536 limit with 4).
- **The Scar Tarn** (Mt Vessu's NNW hollow): a terrain-held pond, 190 trees, alpha Pokemon (Quagsire, Lanturn, Gyarados;
  Lycanroc, Gabite, Haunter); independently audited, 0 findings.
- **The Haven Compact:** 14 story points (CP-01..14), 26 trainers, Varga four times; the three missing ARC beats now
  in play (CP-04 records, CP-12 crater shutdown, CP-14 public split). Design: `docs/story/HAVEN_COMPACT_PASS.md`.
- **Staging** runs pass 3 + the six new rooms + the two-stage bosses (installed 02:45). **The new dungeons, the Scar
  Tarn and the Compact are NOT installed yet**: the integrator is finishing its checks; then build (~50 min) and install.

## 3. Decisions waiting on you
1. **Early prizes:** the roster gives Ash Bell, Soul Ossuary, Moth Cathedral, Dragonspiral, Field of Swords, Warped Lab,
   Starfall and Zero Dig no prize before band 4/5, so their wings hold only a relic at low bands. Add rare early pools
   everywhere (the Crucible's author did, Metang/Pupitar/Duraludon), or gate those dungeons to open late?
2. **Model pack:** 29 prize species (and Blacephalon as a boss ace) need the AllTheMons subset; until it is delivered
   they are dropped from pools or show as the doll.
3. **Nether rips:** placed on the test trail for now, marked `siting_pending`. A throwaway world to find each biome, or
   one nether hub?
4. **Zero Dig copies the Night Shift's layout room for room** (its own theme and fights): give it its own layout?
5. **The Haven Compact framing:** "evil faction" vs your 2026-09-22 note "not evil" (ARC rules 3-5). Built as: secretive
   until the Craters, open enemies only after. Also O2-O10 in the design doc.
6. **Eternatus** (out since 10-02), **Koraidon/Miraidon**, **Lugia/Registeel** homes, **Cistern/Temple Calendar** vs the
   jungle/ruin, and switching off old wild spawns of species that now have a dungeon home.
7. **The Scar Tarn's alphas** respawn (a repeatable alpha source) and sit at 29-33 over the leg's cap of 30.
8. Still open from before: Giratina fight-only or catchable once; the boss band 5-6 tuning; nether gate at badge 8.

## 4. Not verified anywhere
Everything new tonight is checked by tools and simulators only. In-game checks owed: the dungeons' chain split and
one-tick delay, prize rolls, Beast Ball keying, the six rooms (EXP-090), the Compact's talk-then-battle route
(EXP-091/097), the tarn's alpha flag and water, the bank-vault sign.
