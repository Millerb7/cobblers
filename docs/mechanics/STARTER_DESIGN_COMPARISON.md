# Starters: found in the world, or a nerfed mythical from Oak — a costed comparison

**Status:** PROPOSAL, design only (2026-10-02). Nothing here is built. The owner decides.
**Evidence:** `docs/research/STARTER_OPTIONS.md` (verified vs assumed, with sources) and
`docs/research/notes/starter-stat-mechanics.md` (the 1.8.0 source reading). Numbers marked MEASURED come from
`tools/battle_sim.py` run offline on this branch, plus a scratch script that did not change the repo.

## The owner's two ideas

1. **Real starters found in the world** — the traditional starters are discovered somewhere specific, earned,
   probably not early.
2. **Nerfed mythicals as the starting choice** — Oak offers a mythical with its stats brought down to starter level,
   growing into itself as the player progresses.

## What is true today

- The starter is Cobblemon's own join screen, offering **27 species in 10 categories at level 5**
  (`modpack/config/cobblemon/starters.json`). Oak gives nothing; his dialogue assumes the partner is already chosen.
- **The spread is 27 to 9, not 25 to 1** (MEASURED: of 35 leader Pokemon across eight gyms, Mudkip beats 27 and Tepig
  9). "25 to 1" was the 36-species default list retired on 2026-09-23.
- `tools/battle_stress.py` and `tests/test_battle_stress.py` hard-require exactly 27 starters, four profiles each
  (108), each starting with a level-5 starter from `pool: "oak"`.

---

## Idea 2: the dormant mythical

### How it would work (data only)

- A `species_additions` file in our namespace adds **forms** to the chosen mythical, each with its own `baseStats`
  and selected by an aspect. For example: `cobblers_dormant` (≈ 320 BST, a starter's base stage) until level 16, then
  `cobblers_waking` (≈ 405, the middle stage), then `cobblers_risen` (≈ 530) at level 36 and badge 4. The aspect
  comes off (the real 600) only after the League. This follows the curve the starters actually walk: the sim
  measures their median form at 405 for gyms 1–4 (caps 20–35) and 530 for gyms 5–8 (caps 40–55).
- **Only Pokemon carrying the aspect change.** The temple's Mew, wild Mews and the Pokédex's species page keep
  standard stats. **No species override.**
- Oak's offer is a starter-screen category: `"mew level=5 aspect=cobblers_dormant"`. The screen already gives each
  player exactly one choice, once (`promptStarterOnceOnly`). Multiplayer fairness comes free.
- **Growth** is a same-species evolution: `result: "mew unaspect=cobblers_dormant aspect=cobblers_waking"`, with
  requirements `level` (16), and for the later stage `level` 36 **and** `advancement: cobblers:flag/gym4_cleared`.
  Our badge flags are already advancements (`tools/legendaries.py:255`).
  Fallbacks if the evolution check misfires (E3): an item-interaction evolution (a "key" from the gym), or a function
  that runs `pokemonedit` when the badge is granted.
- Each dormant form can carry **its own level-up movepool**, so the mythical's strength is authored rather than
  inherited. That matters more than the stats (below).

### Persistence (from the research)

The aspect is saved on the Pokemon, and stats are computed from the form on every read. So the nerf follows that one
Pokemon through trade (VERIFIED by source), and through the PC and a restart (ASSUMED, E2). Every player sees the same
numbers (VERIFIED sync path, E4). Mew cannot breed (egg group `undiscovered`), so there are no un-nerfed copies.

### Which mythical

| Candidate | Renders now | Grows-curve score (band 9–27) | Note |
|---|---|---|---|
| **Mew** | yes | 4 (level-up moves only) | the sim's floor. Real Mew learns every TM; the dormant movepool must carry it |
| **Zarude** | yes | 13 | Dark/Grass; mid-band |
| Celebi | assumed | 11 | collides with the authored Celebi wake (L55, after badge 8) |
| Victini | assumed | 23 | strong early; near the top of the band |
| Shaymin | assumed | 11 | Grass, so it inherits Grass's hole in the gym order like the Grass starters |
| Jirachi / Manaphy | **doll** until the client fix | 16 / 15 | not usable until it renders |
| Volcanion | assumed | 23 (32 at full stats, the only one above the band) | |

**One mythical or a category of several?** A category of three (one per player, the same screen) keeps the
opening's choice. It also widens the band again: Mew 4 next to Victini 23. One mythical makes every player's
partner the same species.

### What it does to the balance work

- **The spread metric survives.** Nerfed to the starter curve, every mythical tested lands inside today's 9–27
  band (MEASURED). The tooling must learn about forms first, though. `config_starters()` keeps only the first word
  of each entry, so it already simulates the Hisuian starters as their ordinary forms (a standing bug). Neither
  simulator reads our `species_additions`.
- **The stress tests need a rewrite of their starter model.** It has to cover the count, the sample divisibility,
  and a starter whose stats change at a badge. The profiles currently treat the starter as a fixed species evolving
  by level.
- **The real risk is the TM list, not the base stats.** No tool here models TMs. A dormant Mew with Mew's TM list
  is a different Pokemon from the one the sim scores.

### Cost

| Kind | Items |
|---|---|
| New data | `species_additions/<mythical>.json` per offered mythical (forms, aspects, evolutions, movepool); an advancement per growth gate if not reusing `cobblers:flag/gymN_cleared` |
| Generator | a small emitter (say `tools/mythical_starters.py`) from one authored record to the additions file and the `starters.json` category; or hand-authored if one species |
| Config | `modpack/config/cobblemon/starters.json` (a new category; keep or drop the 27) |
| Install path | the datapack must reach the server and `tools/install_check.py` must see it. Four times now, repo work never reached the game |
| Tools | `tools/battle_sim.py`: form/aspect-aware starters, read our additions, growth schedule. `tools/battle_stress.py`: starter count, sample size, the growing starter |
| Tests | `tests/test_battle_stress.py` (27, 108); a new independent audit: each dormant stage's BST ≤ the configured starters' form BST at that gym's cap, the expectation taken from the jar's starter lines, never from our additions |
| Story | Oak's dialogue (`data/dialogue.json`), `docs/story/ARC.md`'s opening ("Oak offers the starter") |
| Experiments | E1–E6 (one staging session) |
| **Effort** | **about 3 sessions**: experiments (1), build + tooling + tests (1), balance pass on movepool and stage BSTs (1) |

---

## Idea 1: traditional starters found in the world

### How it would work

- **A sanctuary per regional trio**: nine trios (Kanto ... Paldea, plus Hisui as a twist on three of them), each at
  a site with a badge gate. A player claims **one of the three** at each sanctuary they reach.
- **Mechanism:** ADR-002's per-player find. An advancement fires on reaching the site; the claim runs
  `pokegive <species> level=<L>` as the earning player. That is VERIFIED from a function (EXP-045). A per-player lock
  stops a second claim (E7). Habitat Blocks are the wrong tool: a wild spawn is shared, first-come and farmable.
- **Level on gift:** at the site's cap minus a margin. A level-5 starter at badge 4 is a nursery project the caps make
  pointless. Above the second evolution level it arrives fully evolved, which loses the charm. A middle path: give
  the base stage at the cap and let it evolve on its next level.
- **Fairness:** every player gets one per sanctuary, and advancements carry across re-exports. **Breeding undoes
  scarcity:** Cobbreeding is in the pack, so one found starter becomes as many as the group wants.

### The open problem it creates

**Idea 1 removes the opening.** If the traditional starters are found, the join screen must offer something else (idea
2, or a set of non-traditional partners), or be turned off with Oak giving the first Pokemon from a function. Players
who already chose keep their starter: it is in their player data, which `tools/carry_players.py` carries.

Note that four starters are already wild at mid-levels: Charmander, Totodile, Piplup and Rowlet (`data/spawns.json`).

### What it does to the balance work

- The **25-to-1 / 27-to-9 spread stops being the opening's measure**: the starter no longer carries gyms 1–N. Gyms
  before the first sanctuary must be winnable on route catches plus whatever the opening gives. That is the
  early-route availability work the owner already named as the lever (2026-09-23), now load-bearing.
- **The stress tests' acquisition model changes.** A starter is acquired at the gym index of its sanctuary, at its gift
  level, not from Oak at level 5. Every archetype ("critical path only", "nuzlocke") must be re-run, and a sanctuary off
  the critical path is invisible to the critical-path archetype.

### Cost

| Kind | Items |
|---|---|
| World | up to nine sites: placements in `data/placements.json`, a structure each in `kits/`, apply steps, floor verifies |
| Data | a gift kind in `data/rewards.json` (choose one of three, per-player lock); advancements; dialogue for each site |
| Generator | the reward emitter gains a gift-with-choice kind; the placement and apply chain gains the sites |
| Config | `starters.json`: replace or remove the 27 (a decision, above) |
| Tools / tests | `battle_stress.py`: acquisition at a gym index; `battle_sim.py` per-sanctuary assessment; tests for the lock and the gift levels |
| Experiments | E7 (choose one of three, two players, re-export carry); EXP-029 still open |
| **Effort** | **about 4–6 sessions**: mechanism proof (1), sites and structures (2–3, depending on how many sanctuaries), reward and gift generator (1), balance re-run (1) |

---

## The two together

They solve each other's open problem. **Idea 2 is the opening; idea 1 is the mid-game.** Oak offers the dormant
mythical, the partner that grows with the badges. The traditional trios become the region's discoveries: a sanctuary
per few badges, each a real choice of three. The story fits as well: the world is an exchange of displaced places,
so starters scattered from their home regions belong to it.

Combined cost is roughly the sum, about **7–9 sessions**. Idea 2's three sessions come first, because they settle
whether the opening works at all.

## Decisions for the owner

1. **Idea 2 at all?** If yes: one mythical for everyone, or a category of three?
2. **Which mythical(s)?** Recommended: Mew (renders, cannot breed, fits Oak). Its strength would be an authored dormant
   movepool rather than its TM list. Zarude is the second that renders today.
3. **How many growth stages, gated on which badges,** and does it reach full 600 BST before or after the League?
4. **Idea 1: how many sanctuaries** (nine trios, or three type sanctuaries), at which badges, and at what gift level?
5. **The 27 on the screen:** dropped (idea 1 or both), or kept alongside the mythical (idea 2 alone)?

## Recommendation

**Run E1, E3 and E4 before deciding anything else.** They are one staging session and settle whether the dormant
form loads, grows on a badge, and fights at the dormant stats. If they pass, **adopt idea 2 with a single dormant Mew
and its own movepool**, three dormant stages on the starter curve (320 → 405 at L16 → 530 at L36 + badge 4), and the
full Mew after the League. Then **adopt idea 1 as the mid-game layer**, starting with three sanctuaries rather than
nine, so the world-building cost is proved small before it is multiplied.

If E1 or E4 fails (the form does not load, or Showdown fights with standard Mew stats), idea 2's only remaining route
is a species override. Do not take it: it changes every Mew in the world. In that case keep today's screen of 27.
Idea 1 then works only as extra finds, not as the place the starters come from, unless a separate design gives the
opening its own partners.
