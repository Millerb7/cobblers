# Overnight review, 2026-10-05/06: defects recorded, not chased

The owner's rule for the night: record defects, fix one only if it blocks what is being built. Each line: what, where,
who found it. Fixed items are not listed here; they are in the commits.

| # | Defect | Where | Found by |
|---|---|---|---|
| N1 | `test_system_contracts.py::test_contract_c4...` fails on `tools/bank.py` (already at 1c24f76) | tests/test_system_contracts.py | orchestrator |
| N2 | Coastal strips outside their sub-region polygons have NO campaign spawn pool: the polygons predate the water export, which moved coasts 10-16 blocks (measured on the south-east dunes; likely on every coast) | data/regions.json subregions vs the water-shaped heightmap | orchestrator |
| N3 | The ambient generator does not enforce the pets/placed/situations shares or cross-town variety (the independent audit does) | tools/ambient_idle.py | ambient builder |
| N4 | `tools/plaza_centre.py` and `tools/mines.py` steer clear of data/ambient.json's workers only, not town-file workers | tools/plaza_centre.py, tools/mines.py | ambient builder |
| N5 | Two tests edited by the implementer for intended changes need a second reader: `tests/test_articuno_tower.py`, `tests/test_gym_waystones.py`; the orchestrator also edited the auditor's `tools/ambient_composition_audit.py` share bands | tests/, tools/ | orchestrator |
| N6 | The bird towers' summit barrels keep their loot (gems, diamond boots, trident, netherite template): owner to decide | data/placements.json, data/adopted_legendary_sites.json | orchestrator |
| N7 | Same-species sleepers within 4 blocks in the OLD idle plan (Slowpoke in Viltri Quay, Sunset West, Steepside; Galvantula; Vanillite): superseded by the town files where present | derived/ambient/idle_plan.json | ambient auditor |
| N8 | **Owner decision**: a player with a starter and NO badges can talk to all ten tellers in turn and reach `rift_crisis_pending`; the relic HQ guard then admits them and Nia speaks. The tellers' locked lines accept "the badge OR the previous teller's account" | data/quests.json, data/dialogue.json (Codex's) | beats builder |
| N9 | `crater_operation_stopped` has no setter: the Craters climax event does not exist (Blaine's beat does not depend on it) | data/progression.json | beats builder |
| N10 | `data/quests.json` still marks the 8 evidence objects "unbuilt" (Codex's file, left unedited; `tools/reveal_evidence.py` builds them) | data/quests.json | beats builder |
| N11 | `test_no_swallowed_crashes` flags far_south_audit, jungle_temples_audit, test_ambient_idle and test_apricorn_farm | tests/ | beats builder |
| N12 | The premise "nothing invokes the story" was wrong: the 13 tellers are seated and the chain Oak -> League compiles and runs (60 chain tests); what was missing was the evidence displays and anyone talking to them in game | - | beats builder |
| N13 | Pacifidlog's ambient file is refused by the generator: all ~8,000 deck cells are within 8 of a water-export column, and a deck earthwork is refused as worker ground | tools/ambient.py, tools/ambient_idle.py vs data/ambient_towns/sea_town.json | author B |
| N14 | Rimwatch and the West Spur Dig place no NPC or stall keeper, so they have no pets; the dig is written as an outpost (6) | data/ambient_towns/ | author B |
| N15 | Cinderlee's two mast birds: the mast is dressing, not a building template, so compose cannot check they sit on its head | data/ambient_towns/gym7_town.json | author B |
| N16 | `tools/rift_skin.py` (line 489) and `tools/rift_deep.py` crash on Path(None) without --source-root: neither uses terrain.env_source_root() | tools/ | finale builder |
| N17 | Stale claims that the finale has no setter or cradle: STATE (two lines), CRITICAL_PATH_WALK_2 item 10, REVIEW 16, data/relic_underground.json zone.pass.why_not_the_finale_flag | docs/, data/ | finale builder |
| N18 | Hoopa has species data but no model or texture in the 1.8.0 jar (draws as a placeholder); no actor built, the release's particles and sound stand in; other mods not checked | - | finale builder |
| N19 | Three placeholder lines for Codex in dlg_main_relic_hq_guard (admit_pending, turned_away_2) and dlg_main_relic_hall_release (confront_003) | data/dialogue.json | finale builder |
| N20 | Pacifidlog's ambient file is HELD (data/ambient_towns_held/sea_town.json): after the deck fix it still clashes (a pet with no open cell beside its owner pacifidlog_fishers_row; one situation moved 2 east off the lifeguard). 19 of 20 towns compose; the audit's scope check will name it | data/ambient_towns_held/sea_town.json | orchestrator |
| N21 | No shard exists in the evolution-stone chain (every *shard* item checked); the gate is the ore. Stones were only sold by the Mining Town Assayer, never seen to sell (P-7); Steepside now sells all ten at 2,100 (unverified purchase) | data/markets.json | obtainability |
| N22 | TMs are dead: none of 3,596 TM recipes is craftable from renewable inputs (805 need a type gem, Nether-chest-only); fossils (14 of 15), mint seeds, Z-Moves and Dynamax have no supply; Nether mobs are all MobsBeGone-blacklisted (blaze rods, ghast tears, wither skulls) | docs/research/OBTAINABILITY_SWEEP_2026-10-05.md | obtainability |
| N23 | Owner calls proposed: a TM counter, mint seeds, a brewing-stand line, fossil faces, Z/Dynamax config, Giovanni's Ancient DNA grant, plain bottle caps; the Ability Capsule at Northlight gated gym 6 for 10,000 is a proposal price | docs/research/OBTAINABILITY_SWEEP_2026-10-05.md | obtainability |
| N24 | No no-crafting audit exists for the owner's rule; progression_pack upstream_neutralised cannot empty a recipe (9 LumyMon locator recipes live); rewards_pack's jar check cannot point at an offline snapshot | tools/ | obtainability |
