# Oak's lab scene and Challenge mode

**The owner, 2026-10-06:** "Finish both. Oak offering the starters in the lab as a scene rather than a menu on join,
and Oak offering the mode choice -- the difference explained without the words easy and hard. Codex wrote his
dialogue. Build it."

**Status: built as data and generators, tested offline, NOT run in game.** The mechanism research is
`docs/research/RCT_PER_PLAYER_MODE.md` (rctmod 0.19.0-beta / rctapi 0.16.1-beta source); its section 7 (E1-E8) is the
in-game proof list and none of it has been run.

## 1. What a new player sees

1. **Join.** `modpack/config/cobblemon/starters.json` `allowStarterOnJoin: false`: no menu; Cobblemon marks the player
   starter-locked (`starterLocked = !allowStarterOnJoin`, `docs/research/notes/starter-selection.md:246`).
2. **Spawn to the lab.** World spawn (1461, 118, 5306) is about 34 blocks from Oak (1493, 118, 5317). Inside the scene
   area (`data/scenes.json` `oak_lab`, x1440-1510 z5290-5335) a player without a starter sees the hotbar line
   "Professor Oak is waiting for you in his lab." (effect `oak_is_waiting`, kind `actionbar`, new in
   `tools/scenes_pack.py`).
3. **The lab.** Five Pokemon stand in a row along the lab's north wall at y118, z5313, x1493/1495/1497/1499/1501:
   Cosmog, Kubfu, Type: Null, Poipole, Meltan (the five the config offers). Each is the player's own scene actor
   (uncatchable, no AI, unbattleable), present only while the player has not chosen (`not starter_chosen`). Clicking
   one opens `dlg_main_pallet_lab_starter`: one narration line pointing at Oak.
4. **Oak greets.** The first step into the main room (zone `lab_floor`, x1491-1502 y118-120 z5312-5318) runs
   `greet_in_lab`: once per player (`quest.main_worldshift_reveal.oak_greeted`), and only before the send-off, it opens
   Oak's conversation with no click (`opendialogue`, effect `open_dialogue` in `tools/compile_dialogue.py`).
5. **The offer** (unchanged lines): "There you are. Nobody walks out of Pallet without a partner..." then "Five are
   waiting in the lab. Choose one, and look after it. You only get the one." -- "Let me see them." runs
   `openstarterscreen` for the player: **Cobblemon's own chooser**, opened by Oak; "Not yet." leaves the offer standing.
6. **The pick.** The `starter_chosen` callback tags the player; the five actors vanish on the next scene cycle.
7. **The League rules** (next talk; Oak is clicked from here on), then the old send-off `oak_001`-`oak_003`.

## 2. The mode choice, in Oak's words

Codex's lines are `docs/story/CHALLENGE_GYM_DESIGN.md` "Oak's world-wide choice". They were written for ONE choice for
the whole world; rctmod's series is per player, so the choice is per player and three phrases changed ("this
campaign" -> "your journey", "for this world" -> "for your journey", "belongs to the whole campaign ... everyone uses
it" -> "is yours alone"). Nothing else is changed. Standard = Normal, Full-Team = Challenge.

- `oak_mode_001` "Before I send you out, we need to record the League rules your journey will follow."
- `oak_mode_002` "Under Standard rules, Gym Leaders use focused teams. Their plans are clear, and their held items
  support the lesson without filling every slot."
- `oak_mode_003` "Under Full-Team rules, every Gym Leader brings six. Their combinations are tighter, their held items
  matter, and a prepared answer may need help from the rest of your party."
- `oak_mode_004` "The level limits are identical. This changes what each battle asks of you, not how far you may train."
- `oak_mode_005` "This record is yours alone. Once I enter it, it cannot be changed. Which rules should I enter?"
  - "Use Standard rules." -> "Record Standard rules for your journey? This cannot be changed later." -> "Record them." /
    "Let me think."
  - "Use Full-Team rules." (hidden from a player holding `gym1_cleared`) -> the same confirmation for Full-Team
  - "Let me think." closes; the next talk starts again at `oak_mode_001`
- Recorded: "Your League rules are recorded: Standard rules." / "... Full-Team rules." then `oak_001`.

**Written once.** `data/quests.json` `record_trainer_mode_normal` / `record_trainer_mode_challenge` require
`quest.main_worldshift_reveal.trainer_mode == unset`. The Challenge one also requires no `gym1_cleared` and, in one
action: sets the field, runs `execute as <player> run rctmod player set series cobblers_challenge @s` (effect
`rctmod_series`) and `tag @s add cobblers_mode_challenge` (effect `tag_player`). The compiler refuses `rctmod_series`
in any transition that does not require an enum field at its initial value and set it away from it
(`check_series_guard`): every call of that command wipes the player's rctmod progress. Standard runs no command: the
player stays in rctmod's initial series `kanto`. A player who never chooses is Normal.

**Who never sees it:** anyone already past `oak_001` (sent off before this shipped). They are Normal.

## 3. What Challenge adds (all in `build/datapacks/cobblers_trainers`, by `tools/route_trainers.py` + `tools/challenge_mode.py`)

Data: `data/challenge_mode.json` (hand) and each record's `modes.challenge.rct` in `data/trainers.json`
(`docs/story/generate_trainers.py`, which now gives every Challenge payload `identity` = `<record id>_challenge`).

- **Series** `data/rctmod/series/cobblers_challenge.json`: title, description, difficulty 7 (Kanto's own number; the
  card must not rank the modes). No caps: the config's initialLevelCap 20 and relativeLevelCap 0 apply as for Kanto.
- **13 boss ids** `<upstream>_challenge`: kanto_brock, kanto_misty, kanto_ltsurge, kanto_erika, kanto_koga,
  kanto_sabrina, kanto_blaine, kanto_giovanni, kanto_league_lorelei/_bruno/_agatha/_lance, kanto_champion_blue.
  Per id: `trainers/` (Challenge team, battleFormat, own identity), `mobs/trainers/single/` (upstream's mob fields as
  read from COBBLEVERSE-RCT-DP-v20, `series: [cobblers_challenge]`, `requiredDefeats` the upstream chain suffixed),
  `dialogs/trainers/single/` (every refusal from `data/trainer_refusals.json` incl. `wrong_series`; battle lines are
  upstream's translatable keys for a leader, our authored League lines for the Elite Four and Champion),
  an empty loot table, and `cobblers:trainer/<id>` whose reward grants upstream's own defeat advancement
  (`cobbleverse:trainer/kanto/defeat_*`) -- the League elevator, the League hold-off and the Champion's door key on it.
  Every Challenge team tops out at its record's `ace_level`, so the cap curve is the Normal one (asserted).
- **Badge flags:** `data/progression.json` gym1-8_cleared and champion_cleared list `<id>_challenge` beside the Normal
  id. The first-win reward is keyed on the flag, so it pays once whichever leader was beaten.
- **13 second spawners**, set into the floor and powered from below, 2-5 blocks from the Normal one:
  Brock (1830, 155, 3696), Misty (1602, 132, 2874), Surge (1747, 190, 1412), Erika (4306, 110, 1480),
  Koga (4592, 131, 2487), Sabrina (6194, 111, 3312), Blaine (6178, 106, 5004), Giovanni (3565, 120, 6418),
  Lorelei (3696, 110, 2428), Bruno (3695, 127, 2438), Agatha (3695, 138, 2419), Lance (3695, 148, 2423),
  Blue (3695, 171, 2432). **Self-placing:** `cobblers:trainers/challenge/cycle` (every 10 ticks, before the trainers
  cycle) runs `place_<id>` when a player is within 48, the chunk is loaded, the spawner is missing and the two cells
  over it are air. Gyms 1 and 3-8 are checked against `tools/gym_buildings.py`'s model with the shared floor rule;
  Misty's and the League's five were measured from the templates (COBBLEVERSE-DP-v31) on 2026-10-06 and nothing
  re-checks them at build time.
- **Hold-off** for each Challenge leader at its own spawner on the same badge flag, and for the Challenge League on
  upstream's advancement, in the Challenge cycle.
- **51 route copies** `<id>_challenge` (Routes 1-8 and Victory Road's ten; not the mansion guardians, HQ or arena,
  which have no modes): same mob, lines and skin, Challenge team, `series: [cobblers_challenge]`, optional, no
  requiredDefeats (never a cap). The Normal ids stay seriesless. **One entity per seat:** the Challenge cycle merges the
  entity's `TrainerId` to the Challenge id while the nearest player within its reach carries `cobblers_mode_challenge`,
  and back when the nearest is not or nobody is near, never `InBattle`. **ASSUMED (E7)**: that a TrainerId merge swaps
  the team. If it does not, a Challenge player meets Normal route teams and nothing else breaks. Each seat's defeat
  advancement lists both ids.

## 4. Owner decision to confirm

**Two leaders stand in every gym and on every League floor**, each refusing the other mode's players with rctmod's
`wrong_series` line (a spawner block cannot choose per player). Built that way as briefed; whether that is acceptable,
or the second spawner should appear only for a Challenge player, is the owner's call.

## 5. Installing it

Packs to rebuild and install (all by existing prepare jobs): `cobblers_trainers`, `cobblers_dialogue`,
`cobblers_scenes`, `cobblers_progression`; the client/server config `modpack/config/cobblemon/starters.json`.
**Restart** after install: rctmod loads series and trainer data at boot and its trainer-level cache is not cleared on
`/reload`. **No new re-apply step and no edit to `tools/reapply.py`:** the spawners self-place, the scene's actors and
zone run from the scenes cycle, and Oak is already seated (R17N). Seated route trainers keep their entities.

## 6. What an audit must check

Expectations come from the sources named, never from these generators.

1. **Config:** `allowStarterOnJoin` is false and the five entries unchanged (`tools/oak_starter_audit.py` P4, already
   switched; re-confirm its P1/P3/P6 on the new pages).
2. **Starter gate:** no path from a fresh player to the send-off without the starter tag; the greet zone never opens
   Oak for a player past `not_started` and only once; the lab actors show only before the pick.
3. **The series command** appears exactly once in all compiled output, only behind `trainer_mode == unset`, only on a
   path after the starter, never reachable for a `gym1_cleared` player, and never twice for one player over any
   sequence of talks (each call wipes rctmod progress, RCT_PER_PLAYER_MODE.md section 1).
4. **Text:** no "easy"/"hard" (or comparatives) in Oak's rules pages; the lines match Codex's except the three named
   phrases.
5. **Series and chain:** `cobblers_challenge` exists with no cap fields; the 13 Challenge mob files form one chain in
   Kanto's order from the upstream zip's `requiredDefeats` (read the zip, not `data/challenge_mode.json`); each Challenge
   team's maximum level equals the Normal ace for that slot (`data/trainers.json` `generation_contract.gym_ace_levels`,
   League 60/62).
6. **Identity:** every Challenge trainer file's `identity` differs from the Normal one's effective identity (upstream
   falls back to the name), so both may spawn within `uniqueTrainerRadius` 151.
7. **Flags and doors:** each of the nine Kanto flags lists both ids; each Challenge win grants upstream's own
   defeat advancement for its slot (match against COBBLEVERSE-DP-v31's advancement criteria, not our data).
8. **Spawners, from the world shape:** replay `tools/gym_buildings.py` and the two templates independently and check
   each Challenge spawner is flush in the floor, powered, two air over it, inside the same room as the Normal
   leader, and not on a chest, door or puzzle block. This audit must re-derive the template transform for Misty
   (placement gym2_misty_gym) and the League (league_building, clockwise_90).
9. **Our list is not the world:** every system keyed on a leader id that must learn the Challenge id --
   `tools/trainer_world_audit.py` (spawner presence), `tools/challenge_guide.py`, `tools/battle_sim.py`,
   `tools/legendaries_audit.py` `rct_caps`, `data/arena_fights.json` (`rct_defeated:kanto_league_lance`). None was
   changed here.
10. **Route swap:** for every seat with a copy, the swap lines match the seat, never act `InBattle`, return to the
    Normal id when no player is near (so `tools/reapply.py` R17's Normal-id check still finds the entity), and the
    Challenge copy's mob equals the Normal mob except `series`. KNOWN gap: R17 run while a Challenge player stands
    at a seat finds no Normal-id entity there and summons a second trainer; run R17 with nobody near the routes.
11. **In game (EXP, staging only):** RCT_PER_PLAYER_MODE.md E1-E8, plus: the lab hint, actors, greet and chooser for a
    fresh account; `q.player.has_tag` inside `runmolang` (the actors' and hint's condition) -- used by the dialogues,
    not yet seen in a scene beat.
