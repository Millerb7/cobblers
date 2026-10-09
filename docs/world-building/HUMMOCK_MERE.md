# Hummock Mere: the swamp monster's nest

**Status (2026-10-09): built and audited offline, NOT applied to any world, never seen in game.** Data
`data/hummock_mere.json`; generator `tools/hummock_mere.py` (pack `cobblers_hummock_mere`); independent audit
`tools/hummock_mere_audit.py`; steps R9HM (blocks, before R9E) and R18HM (the resident, after R18FS); probes
`data/world_probes.json` `places.hummock_mere`; tests `tests/test_hummock_mere.py`.

The owner (2026-10-09): "a large swamp monster in a den", on the model of the Ursaluna den. The den's MECHANISM is
copied; its form is not.

## What a player finds

The Marshy Marsh's lake spreads over a flat a block deep on its east shore. Thirteen blocks from the flat's middle eight
mangroves stand in a ring, leaning in; their crowns close over a round mud island, and a green froglight hangs under
each crown. On the island lies **the Hummock**, a Clodsire at scale 2.2, level 52. A furrow of dark mud runs from the dry
spit, where a punt rots beside a warning sign, to the island's foot: three blocks wide, wading depth the whole way.
The lure is a second sign on Route 6, 80 blocks outside Fenhide: "WARNING / Something huge / sleeps in the / east mere."

Nothing here is a cave. It is a drowned grove: the "den" is the canopy over the water.

## The mechanism, rung by rung (CLAUDE.md principle 6)

| Need | Rung | Why the earlier rungs do not suffice |
|---|---|---|
| A named, sized creature that stays put | Cobblemon native: `spawnpokemonat ... scale_modifier=2.2` (the Ursaluna den's property; `PokemonProperties` in the 1.8.0 jar carries the string) | nothing earlier gives a placed resident |
| Dormant, wakes near, respawns, blackout-safe | functions: `tools/resident_encounters.py`'s keeper, CALLED (through `southern_residents.shim`), the northern/far-south residents' shape | it is the proven keeper; the Ursaluna den's own boss wake (EXP-053) is unproven and is NOT used |
| Catchable only late | configuration already built: the level-cap refusal (`data/level_cap.json`, `tools/levelcap_pack.py`) | the level IS the gate: nothing is built for it |
| The place | functions (`fill`/`setblock`) from a generator, every Y from `tools/ground.py` | no structure kit has a mangrove grove on a flooded flat |
| The rumour | a sign block | a dialogue NPC would need a quest, progression fields and a class; the brief allows "a sign" |

No Fabric mod, no scripting layer, no new dependency.

## Why this creature

Clodsire (Poison/Ground, 130 HP, 100 Sp.Def, the Paldean Wooper's last form). `data/spawns.json` names it nowhere, so this
is the only Clodsire a player can meet and catching it is the only way to own one. Swampert is the Marshy Marsh heart's
"presence" roll and Toxicroak its common one (`data/encounter_design.json`), so neither could be a named find; Goodra and
Dhelmise spawn elsewhere. Read from the Cobblemon 1.8.0 jar: species `generation9/clodsire.json`, model
`0980_clodsire/clodsire.geo.json` (cubes span 1.88 x 1.75 x 2.88 blocks, species baseScale 1.15, hitbox 1.4 x 1.0); it
swims and breathes underwater.

## The level and the gate (measured, not relayed)

- The place is `marshy_marsh`, tier 5: cap 40, band 28-38, ceiling 45 (`data/encounter_design.json`). A player reaches
  it holding four badges (cap 40).
- **L52** is 12 over the cap a player arrives with. It is over the place's *ceiling* on purpose, as Split-Bark is, by the
  owner's brief ("well above the local cap"). `tests/test_resident_siting.py` does not read this file, so there is no
  xfail; `tests/test_hummock_mere.py` holds the decision instead.
- The cap after n badges is `gym_ace_levels[n]` = 20, 25, 30, 35, 40, 45, 50, 55 (`data/trainers.json`
  `generation_contract`). A catch above the thrower's cap is refused, so **the catch gate is gym 7**: with six badges a
  player holds 50 and cannot catch a 52; with seven, 55, and can. `appears_after` is null: it is there from the start.

## The site (measured on `tools/ground.py` and `tools/water_mask.py`)

Centre (5240, 1924), cell B6, sub-region `marshy_marsh`. Lake level y100; bed y99 (water one deep) across the flat,
falling to y96-98 in a pool 25 blocks west; the spit east of x5268 is dry at y100. The island's crest is y102, the
creature's feet y103, the lowest leaf y109 (six blocks of air over it). The audit measured: nearest route path 766 blocks
(Route 6), nearest town footprint 617 (Fenhide), nearest other authored point 139 (the marsh's own neighbours in
`landmarks.json`; the lake's own outline is skipped by id, `rules.skip_records`). The nearest activated Habitat Block is
clear of the 24-block leash.

**No water is placed.** The water is the lake's; roots are `mangrove_roots[waterlogged=true]` only on wet columns above the
bed and at or under y100 (a waterlogged block on dry land is a leaking source: the generator and audit both hold this).
No block of `data/spawn_blocks.json` is written (no lily pad, sugar cane, seagrass, propagule, oak leaves), so no spawn
table changes and contract C4's built-pack check has nothing to flag. Every clear box starts at y101, because
`#minecraft:replaceable` holds water and a clear into the lake would drain it.

## State model (multiplayer, principle 12)

| Case | What happens |
|---|---|
| Two players arrive together | One Hummock. The first within 14 blocks wakes it for both. |
| A player arrives early (cap 40) | It is there, awake for them; they meet a L52. The sign is the only courtesy. |
| A player at six badges throws a ball | Refused by their own cap (the level-cap refusal, per thrower). At seven: allowed. |
| It is caught, knocked out or killed | Gone for the server; back 30 minutes later (36,000 ticks) only with a player within 96 and none within 48. |
| It beats a player | It becomes the claim's guardian (contract C17); the keeper only counts it until it is beaten, caught or killed. |
| A player leaves mid-fight | It settles back asleep on its mound when nobody is within leash + 16. |
| Restart | The respawn clock lives in the scoreboard (`cobblers.hmere`), the entity is `PersistenceRequired`. |
| Re-export | The world is new: R9HM rebuilds the grove, R18HM summons the Hummock (guarded on tag AND species). |

## Verified and not verified

Ran: the generator (559 build commands, 14 files), the audit (0 problems), `tests/test_hummock_mere.py` (21 pass), and
the neighbours' tests that read `reapply.py` and the C4 contract. The audit already earned its keep once: it found the
builder's first trunk joined by corners, not faces, and the first draft's waterlogged roots on dry land.

**Not verified, not run in any Minecraft:** that the pack applies, that the blocks land, that the Hummock spawns,
wakes, leashes or stays on a 3-high mud mound (all unproven in game for this pack; the keeper's behaviour is proven for
Codex's residents), that `scale_modifier=2.2` looks right (the rendered size by `baseScale x scale_modifier` is an
assumption, `creature_choice.assumed`), that it fits under the crowns, that wading a block-deep flat reads as an
approach, and the sign's position against `tools/signposts.py`'s own posts (its plan needs `build/paint`). A wild-Pokemon
size roll (`tools/size_outliers.py`, the 1-in-N outlier) can overwrite its ScaleModifier once; not guarded.

## Not built

No Habitat Block / outskirts brood: the Marshy Marsh's tables already carry Totodile, Tympole and, in its heart, Swampert and
Toxicroak, and a block is an edit to the shared `habitat_blocks.json` and `spawns.json`. No NPC or dialogue. Probes are
written; `tools/presence_audit.py --only extra` runs them over RCON on staging.
