# Starters: can a mythical be nerfed to starter level, and can starters be found in the world?

**Asked by:** the owner, 2026-10-02 ("STARTERS — design only ... costed before anything is built").
**Answered for:** Cobblemon 1.8.0 on Minecraft 1.21.1 Fabric, this repo at branch `design/2026-10-02-starters`
(from `build/2026-10-02-gates-and-legendaries`, PR #105 head `2de7170`).
**Nothing was built or run in Minecraft.** The design comparison is `docs/mechanics/STARTER_DESIGN_COMPARISON.md`.
The source-level detail behind §2–§4 is `docs/research/notes/starter-stat-mechanics.md`, with file and line citations
into the 1.8.0 source at `https://gitlab.com/cable-mc/cobblemon` (tag `1.8.0`) and the 1.8.0 jar.

Every claim is marked **VERIFIED** (with its source), **MEASURED** (a tool run this session, offline, no game) or
**ASSUMED** (with the experiment that would settle it).

---

## 1. Short answer

1. **Idea 2 (a nerfed mythical from Oak) is possible with data alone, per INSTANCE, without touching the species.**
   The mechanism is a custom *form* of the mythical with its own `baseStats`, added by a `species_additions` file in
   our own namespace and selected by an *aspect* stored on the one Pokemon. Every link is VERIFIED in the 1.8.0
   source; the chain has never been loaded in a game (experiments E1–E6, designed, not run).
2. **It persists** through trading and (by source reading) the PC and a restart, because the aspect is saved with the
   Pokemon and stats are recomputed from the form every time. **It grows** through an "evolution" whose result is
   the same species with the aspect removed, gated on level and on an advancement — and our badge flags are
   advancements. When that evolution check fires is the one real unknown (E3).
3. **A species override is not needed and should not be used.** It would change every Mew in the world, including
   the Long Isle temple's.
4. **IVs, EVs and natures cannot do it.** At their worst they bring a 600-BST mythical to about a fully evolved
   starter, not a level-5 one, and players can undo them (Bottle Caps, mints, EV training).
5. **Idea 1 (starters found in the world) needs no new mechanism.** A per-player gift run as a function is VERIFIED
   (`pokegive` from a function run as the player, EXP-045, owner PASS 2026-09-27) and the per-player
   advancement-keyed find is ADR-002's existing pattern. Its costs are world building and a decision about what
   replaces the opening.
6. **The premise "the starter spread runs 25 leader Pokemon beaten down to 1" is stale.** That was the 36-species
   default list before 2026-09-23. **MEASURED today:** the 27 configured starters beat **27 (Mudkip) down to 9
   (Tepig)** of 35 leader Pokemon across eight gyms. `docs/STATE.md` said 29 to 14 across seven; corrected.

---

## 2. Can stats be altered, and at what granularity?

| Lever | Granularity | Can it make a mythical "starter level"? | Status |
|---|---|---|---|
| Replace `data/<ns>/species/mew.json` | whole species | yes, but every Mew changes | VERIFIED loader; notes §1 |
| `species_additions` patching `baseStats` | whole species | yes, same problem | VERIFIED: `SpeciesAdditions.kt` registers `species_additions` as server data; any mutable field, `baseStats` included; `forms` and `evolutions` are appended, all else replaced (notes §1) |
| `species_additions` adding a **form** with its own `baseStats`, chosen by an **aspect** | **one Pokemon** | **yes** | VERIFIED pattern: Cobblemon's own Bloodmoon Ursaluna (`species/generation8a/ursaluna.json` form with `"aspects": ["bloodmoon"]`, flag feature `species_features/bloodmoon.json`) |
| IVs / EVs / nature | one Pokemon | no: floor ≈ a 496-BST equivalent at L50 (notes §4) | VERIFIED formula; arithmetic in notes §4 |
| Level / RCT level cap | one Pokemon / player | limits level, not stats per level | VERIFIED (`relativeLevelCap` 0, `docs/STATE.md`) |
| Held items | one Pokemon | no stat-lowering hold item fits | ASSUMED (no search beyond notes §4) |
| An addon that scales player stats | — | none in the pack | VERIFIED absent from `base-pack/inventory/mod_inventory.json` descriptions; alpha (`isAlpha`) effect UNKNOWN |

**The form is the answer.** VERIFIED (notes §2):

- `aspect=<x>` and `unaspect=<x>` are registered custom properties (`Cobblemon.kt`: `AspectPropertyType`,
  `UnaspectPropertyType`); they add and remove `pokemon.forcedAspects`. Use `aspect=`, never `form=`: a later aspect
  recalculation can undo a bare `form=`.
- Forced aspects are written to the Pokemon's saved data, and a Cobblemon trade moves the same object, so the aspect
  travels with the trade.
- Stats are **not stored**. They are computed from the current form's `baseStats` each time they are read, so the nerf
  is exactly as durable as the aspect, and removing the aspect ends it at once.
- A form's `labels`, `moves`, `abilities` and `pokedex` fall back to the species unless the form sets them
  (`FormData.labels` is `_labels ?: species.labels`). So the dormant form is still `mythical` unless told otherwise,
  and it can be given **its own, curated level-up movepool** — a balance lever as strong as the stats (see §5).

**Starter config:** VERIFIED that each `starters.json` entry is a full properties string created as written; this
pack's own config already uses that (`"Cyndaquil region_bias=hisui level=5 pokeball=ancient_poke_ball"`,
`modpack/config/cobblemon/starters.json`). So `"mew level=5 aspect=cobblers_dormant"` should work. ASSUMED until E5.

**Battles and clients:** VERIFIED in source that Showdown receives every form's base stats on each reload and that a
battle team names the form, and that species and form data are synced server→client (so players need no datapack).
ASSUMED until E4: that the summary screen, the Pokédex and battle damage all show the dormant numbers.

---

## 3. Does it persist?

| Event | Result | Status |
|---|---|---|
| Trade | aspect travels with the Pokemon | VERIFIED by source (same object moved); E2 confirms |
| PC box and back | aspect saved with the Pokemon | ASSUMED from the save path; E2 |
| Server restart, `/reload` | aspect saved; additions re-applied on reload | ASSUMED; E2 |
| Another player looks at it | stats come from the synced form, so everyone sees the same | VERIFIED sync path; E4 |
| Breeding | Mew is egg group `undiscovered` (jar `mew.json`) | VERIFIED: no copies by breeding |
| Evolution | most mythicals have no evolutions (§4 table) | VERIFIED; growth needs the mechanism below |

**"Growing into itself."** VERIFIED that the code admits an evolution whose `result` is the same species with a
changed aspect (`mew unaspect=cobblers_dormant`), and that 1.8.0 has `level` and `advancement` requirement variants
(`AdvancementRequirement`, `ADAPTER_VARIANT = "advancement"`, field `requiredAdvancement`). VERIFIED that our badge
flags are advancements: the legendary gates test `advancements={cobblers:flag/gymN_cleared=true}`
(`tools/legendaries.py:255, 318`). So "Dormant → Waking at level 20 **and** badge 2" is expressible in data.

**UNKNOWN (E3):** what triggers a `level_up` evolution check. `Pokemon.addExperience` posts the level-up event but
calls no evolution code itself. If the check runs only on level-up, a badge earned after the level is reached waits
for the next level. Fallbacks, all VERIFIED to exist: an item-interaction evolution, a Molang callback on the level-up
or advancement event calling `q.pokemon.apply('unaspect=...')`, or `/pokemonedit` from a function. Also unknown: whether
the evolution is offered as an optional prompt the player can decline, and what message and Pokédex entry a
same-species evolution produces.

---

## 4. What a species override would break (the case for NOT using one)

- **Every Mew changes**: the adopted Long Isle temple's Mew (`data/adopted_legendary_sites.json`, Mew temple at
  (7604, 142, 7082); LumyMon runs its command blocks on `defeat_champion_blue`), any wild, raid or RCT Mew, and the
  Pokédex's base-stat page.
- **A full file replacement freezes Mew at our copy** across Cobblemon updates (moves, fixes).
- **Other addons:** Mega Showdown, LumyMon, Legendary Monuments and the compressed Cobbleverse/RCT datapacks were
  **not** inspected for Mew or `mythical` rules (UNKNOWN; E6). No authored file in this repo selects
  `label=mythical`. Mew has no Mega, so a Mega Showdown collision is unlikely (ASSUMED).
- **Our own data:** `data/legendaries.json` carries no Mew; `celebi_wake` (Celebi L55, gated on `gym8_cleared`)
  would be duplicated if Celebi were also a starter. Hoopa has a shrine in the Deep's city.
- With the **form** approach none of this changes: only aspect-bearing Pokemon are affected.

**Which mythicals the pack can show** (notes §7): Mew and Zarude render; Jirachi, Manaphy, Phione, Pecharunt (no
resolver) and Magearna, Zeraora (mega resolver only) show the placeholder doll until the client fix ships; Celebi,
Darkrai, Shaymin, Victini, Keldeo, Diancie, Hoopa, Volcanion and Meltan are ASSUMED to render via Cobbleverse additions;
Genesect, Meloetta, Marshadow and Melmetal are ASSUMED unimplemented.

---

## 5. Balance: what each does to the measured work (MEASURED, offline)

**The current spread.** `python tools/battle_sim.py` (after `compile_spawns.py` and `availability.py --write` in this
worktree; IVs 15, EVs 0, level-up moves only, no switching, cap offset 0): 8 gyms, 35 leader Pokemon, caps 20–55.
The 27 starters beat **27 (Mudkip), 25 (Turtwig), 24 (Rowlet) ... 13 (Totodile, Sobble), 10 (Snivy), 9 (Tepig)**.

**Mythicals in the same harness** (scratch script, the repo unchanged; each mythical's base stats rescaled keeping its
own distribution). "Grows" = BST set to the median configured starter's form at each gym's cap: 405 for gyms 1–4,
530 for gyms 5–8.

| Mythical | full stats | flat 530 | grows (405 → 530) | renders? |
|---|---|---|---|---|
| Mew | 10 | 6 | **4** | yes |
| Zarude | 18 | 14 | 13 | yes |
| Celebi | 21 | 15 | 11 | assumed |
| Victini | 29 | 25 | 23 | assumed |
| Shaymin | 16 | 14 | 11 | assumed |
| Jirachi | 19 | 17 | 16 | doll |
| Manaphy | 23 | 15 | 15 | doll |
| Meloetta | 27 | 24 | 17 | assumed not |
| Volcanion | **32** | 27 | 23 | assumed |
| Darkrai | 20 | 9 | 6 | assumed |
| Meltan | 2 | 14 | 7 | assumed |

(Full table of 22 in the scratch output; summarised in the comparison doc.)

What it says, and what it cannot say:

- **Base stats are not the big lever at these caps.** By gym 5 the configured starters are 530-BST final forms, so a
  600-BST mythical is only 13% stronger; at gym 1 (cap 20, median 405) it is 48% stronger. Only Volcanion at full
  stats (32) leaves the current band of 9–27. Nerfed to the starter curve, every mythical lands inside it.
- **Movepool dominates, and the simulator cannot see the one that matters.** Mew scores 10 at full stats because its
  level-up list at cap 20 is Pound, Reflect Type, Transform and Mega Punch. In game Mew learns every TM, and this pack
  has TMCraft plus Cobblemon 1.8's native TMs. The sim's Mew is the floor of the real one, not an estimate of it.
  The dormant form's own `moves` list is the lever that would make Mew's strength designable.
- **The stress tests break mechanically on either idea.** `tools/battle_stress.py:330` raises unless exactly 27
  starters; `tests/test_battle_stress.py:82-83` asserts 27 and four profiles each; `build_profiles` needs
  `SAMPLE_SIZE` (108) divisible by the count (`:92`); the starter enters every profile from `pool: "oak"` at level 5
  (`:140-141`).
- **Finding: the sim already drops forms.** `config_starters()` keeps only the first word of each entry
  (`tools/battle_sim.py:991`), so the three Hisuian entries are simulated as the Johto/Unova/Alola forms (Hisuian
  Typhlosion is Fire/Ghost, Samurott Water/Dark, Decidueye Grass/Fighting). An aspect-selected mythical would be
  collapsed to full Mew the same way. Both simulators read species only from the jar, so neither would see our
  `species_additions`.

---

## 6. Idea 1: finding the traditional starters

| Mechanism | Per player? | Status |
|---|---|---|
| Per-player gift from a function: an advancement on reaching the site runs `pokegive <props>` as the earning player (ADR-002) | yes, once each | VERIFIED parts: `pokegive` from a function run as the player (EXP-045 PASS); the advancement-keyed find (ADR-002, `data/rewards.json`; advancements carried across re-exports by `tools/carry_players.py`) |
| Choose one of three at a site, the other two then refuse | yes | ASSUMED: needs a per-player lock (scoreboard or advancement) and a block-use trigger; `any_block_use` with a position filter is a component of EXP-043's proposal, not separately verified here |
| Wild spawn from a Habitat Block or a roster | no: shared, first come; farmable | VERIFIED mechanism (`data/habitat_blocks.json`). Four starters are already wild: Charmander L44–52, Totodile L34–44, Piplup L27–38, Rowlet L25–45 (`data/spawns.json`) |
| An NPC (Cobblemon dialogue or RCT) that hands one over | — | UNKNOWN whether our dialogue system has a give action; not researched |

**Breeding undoes scarcity.** Cobbreeding is in the pack and starters breed, so one found starter becomes as many as the
group wants. "Each player gets one" holds only for the gift itself.

**Interaction with the 27 configured starters.** VERIFIED: the starter screen is Cobblemon's own join prompt
(`allowStarterOnJoin: true`, `promptStarterOnceOnly: true`) — Oak's dialogue says "Your partner is ready"
(`data/dialogue.json`, `dlg_main_pallet_oak`) and gives nothing itself. If the traditional starters are to be found,
the screen must offer something else (idea 2's mythicals, or another set), or be turned off with Oak giving the first
Pokemon from a function. **Players who already chose** keep their starter: the choice is in Cobblemon player data,
which `tools/carry_players.py` carries across re-exports.

---

## 7. Experiments needed before building (designed, not run)

From the notes file (full steps and pass/fail there), plus two for idea 1:

- **E1 Load and create** — a `species_additions` Dormant form loads and `pokegive mew level=5 aspect=cobblers_dormant`
  makes one with the dormant stats while a plain Mew keeps standard stats. *The gate for idea 2.*
- **E2 Persistence** — PC, restart, trade, `/reload`.
- **E3 Growth trigger** — same-species evolution on `level` + `advancement`; when it fires; whether it can be declined;
  the fallbacks.
- **E4 Battle and client** — Showdown damage matches the dormant bases; a client without the datapack shows the same.
- **E5 Starter entry** — the properties string in `starters.json` yields a dormant Mew from the screen.
- **E6 Side effects** — a shrine Mew and a plain spawned Mew stay standard; entry-name grep of Mega Showdown,
  LumyMon, Legendary Monuments and the RCT datapacks for `mew` and `mythical`.
- **E7 Choose-one-of-three** (idea 1) — two players at one site, each claims a different starter, neither can claim a
  second, both keep the claim across a re-export carry.
- **EXP-029** (existing candidate) — count the starter tabs on a fresh join; still unrun.

All but E6's grep need staging with the server lock; E1–E6 fit in one staging session.

---

## 8. Recommendation

**Idea 2 is feasible and cheaper than it sounds — do it with a dormant form, never a species override, and run
E1 + E3 + E4 first**, because those three decide whether the whole chain holds. Choose the mythical by what renders
and by movepool rather than by stats: Mew renders and cannot be bred, but its strength is its TM list, so the dormant
form should carry its own movepool. Idea 1 needs no unknown mechanism, but costs world building, a replacement for the
opening, and a breeding caveat; it pairs naturally with idea 2 rather than standing alone. The costed comparison and the
recommended combination are in `docs/mechanics/STARTER_DESIGN_COMPARISON.md`.
