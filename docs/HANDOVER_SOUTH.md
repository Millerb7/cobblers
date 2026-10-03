# Handover: the world audit and the south (2026-10-02)

For the session that holds the staging server (the owner's main session, lock `session-start-531d15`). This
session never touched the server or the lock; everything below is offline until you run it.

## 1. The branch

- **`claude/south-map-world-audit-2219f3`**, pushed (read its head with `git rev-parse`), no PR (fold it
  into the batch's one PR). Based on your local `build/2026-10-02-followups` at `d00114c`, plus Codex's PR #107
  (`data/resident_encounters.json`) merged in. Merge it into your branch:
  `git merge claude/south-map-world-audit-2219f3` (expect appends in `tools/reapply.py` and the shared `data/` files
  if you have moved since `d00114c`).

## 2. The audit the owner asked for, answered from the repository, NOT yet from the world

| Item | Verdict from git + the apply records (`derived/reapply/run_*.json`) |
|---|---|
| Mega mine and the 7 dens | **Applied** by R9S on 2026-10-01 17:10, from a head containing `5198d14` (dens unparked 15:09). Nothing re-ran R9S since. A den writes no block, and its keeper runs only while a PLAYER stands inside its approach box (128 square, anchor-24 to anchor+32) with nobody within 24 of the anchor. Flying over at height never spawns one, which is why none has been seen. B4 (`cbcff87`, den zones dropped) landed after the apply. |
| Hoopa underground | **Built, never applied.** `c7412a8` authored it, but no re-apply step existed. The world has the old SURFACE relic site (ring, arches, cordon) from R9DC and no hall. Now wired as R9RU, with the HQ's way down built for the first time. |
| Heaven's Arena | **Applied** by R9DC on 2026-10-01; that apply probed the crown floor at y127, the lobby at y5 and the stands' air. Champions seated by R17 on 2026-10-02. Centre (3609, 3249), beacon y129. |
| The Deep since the city | Only the arena (R9DC, 10-01). The relic hall and the HQ way down are offline (R9RU). The Rift gatehouse fixes (B11b `90b1222`, B12 `737cb90`, `db406fb`) landed AFTER the 10-01 apply, so the world's gatehouses are the impassable ones: **re-run R9Z**. |

**Settle it in the world first, before applying anything:**

```
python tools/presence_audit.py --only arena,gulch,dens,relic --out <scratch>/presence_before.tsv
```

`dens` WRITES: it drives each keeper from the console, so any due Mega spawns. Staging only. Expect `relic` to
report the surface ring and cordon still standing and the hall not carved: that is the "before".

## 3. The apply, batched (server stopped for the property, running for the steps)

1. `max-tick-time=-1` with the server stopped (put it back to 60000 after).
2. `python tools/reapply.py prepare` (full, because dialogue, spawns, habitat pools and seven new packs all change;
   the cheap gates are already clean: `validate_data` 0 errors, `validate` 0 errors over 1,254 files).
3. `install`, then boot. The restart loads the new dialogue classes.
4. `python tools/reapply.py run --only R9Z,R9RU,R9DU,R9HF,R9SO,R9MD,R9E,R18DU,R18HF,R18SO,R18R,R18RU`. It runs in PLAN order:
   the three block passes and R9RU before R9E (Habitat Blocks sit in their blocks), then the NPCs, then R18R.
5. Restart once (Habitat Blocks activate on load), then:
   `python tools/presence_audit.py --out <scratch>/presence_after.tsv` (adds `extra`: 223 block and 7 entity probes
   from `data/world_probes.json`) and `python tools/deep_city.py verify --world <staging>` (after R9RU).
6. `tools/trainer_world_audit.py` is unaffected; skip it unless R17 runs.

## 4. Where to fly (for the owner, once applied)

- **Arena**: (3609, 130, 3249), over the Deep.
- **Mega dens**: walk, don't fly, inside 32 blocks of height. Aggron (4528, 123, 4416), Pinsir (4576, 122, 4680),
  Manectric (4608, 133, 4944), Houndoom (4488, 145, 5216), Abomasnow (3944, 147, 3904), Tyranitar (4080, 149, 4168),
  Garchomp (4248, 129, 5328). Gulch square (4308, 88, 4848); Cutting Floor Megas via the adit (4332, 90, 4911).
- **Hoopa's hall**: HQ door (3443, 67, 3282), stair head (3429, 66, 3299), records room (3425, 1, 3306), doorway
  (3421, 2, 3306), hall (3390, 8, 3262).
- **Copperway Khan**: (6744, 149, 6207), gate. **Drovers' Hollow**: (3960, 101, 6023), barn door. **Old Orchard**:
  (2790, 66, 7048), press-house. Residents: see `docs/STATE.md` "The south".

## 5. Decided by the owner since (built, not applied)

- Split-Bark is level 63: no catch between the Elite Four and the Champion.
- Nothing spawns in Hoopa's hall (three spawn-free zones). The HQ door needs `rift_crisis_pending` or later: the plates
  are gone, a Compact guard at (3444, 67, 3283) moves the player through, step R18RU. A wall at z3278 closes the room off
  from the next HQ section's street door (3445, 67, 3252); without it the guard could be walked round (found by the
  relic audit over the BUILT city pack, which no builder worktree had).
- The Mega dens are dressed to be seen from the air (step R9MD, `docs/world-building/MEGA_DENS.md`): Aggron
  (4536, 126, 4419), Pinsir (4583, 123, 4683), Manectric (4605, 132, 4936), Houndoom (4482, 145, 5210), Abomasnow
  (3937, 152, 3909), Tyranitar (4071, 146, 4168), Garchomp (4243, 125, 5321).

Still open: the guards' lines are placeholders; keep the inside guard? Drovers' Hollow is a barn, not a cave (no
wall there to cut).

## 6. Do not rediscover

- `COBBLERS_SOURCE_ROOT` did NOT reach this session's shell or three of six agents on 2026-10-02 (CLAUDE.md says it
  does). Pass `C:/Users/wnd/Documents` explicitly.
- `cobblers_ursaluna_cave` was in the global datapacks folder despite its own comment. It is in `WORLD_LOCAL` now, so
  the next install moves it.
- The Old Orchard owns the Orchard Sleeper's ground. The residents' own orchard dressing is kept unbuilt under
  `build.superseded_dressing`.
- `tools/lakebed_repair.py` seeds its noise from world.json `seed` (null) + 17, while `paint_maps.py` uses
  20260914 + 17. They likely disagree (found by the Hoopa builder; not fixed).
- `tests/test_deep_city.py`'s order test needs `derived/ambient/plan.json`; it errors in any worktree.

## 7. Cost

`tools/session_cost.py`: this session 141 turns, 3.9M weighted. Its six agents together **22.8M**, about four times
the 5-7M estimated up front.
