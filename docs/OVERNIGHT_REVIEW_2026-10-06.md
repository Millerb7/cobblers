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
