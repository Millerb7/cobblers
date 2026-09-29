# Session handover (2026-09-28, session 419ff6d9, ended past its threshold at ~400k context per turn)

For a cold start: read CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before starting. STATE holds the
durable facts; this holds where work stopped. Rewrite it at the end of every session (CLAUDE.md "Session length").

## 1. Branches and PRs

- #84, #85 and #86 are **merged**; heads `7ed47cf`, `482754f` and `175afd2` verified on main (2026-09-28).
- This file is on `handover/flight-list` (its own draft PR against `main`).
- `.codex/config.toml` is modified in the session worktree and **never committed** (Codex's; HANDOVER_CODEX item
  29). `git commit -a` sweeps it in: stage files by name.
- Removable now that #84 has merged: the `worktree-agent-*` branches, `.claude/worktrees/agent-*`, and
  `.claude/worktrees/night-towns-shrines` (builder A's re-material, already applied).

## 2. Where the job stopped

- **Staging is up for the owner's flight, and the lock is held on purpose.** World `cobblers-dryrun11`,
  `--universe C:/Users/wnd/Documents/github/cobblers-runtime-proof/dryrun11`, `-Xmx16G`, port 25565. Lock owner
  string: "Claude Code session cobblers-session-start-531d15 (overnight: ambient workers proof and builds on staging
  dryrun11)". Everything below is on it (the 2026-09-28 integration run: every place 0 gaps, audits clean). **Do not
  stop it, re-apply or export while the owner is flying.** When the owner says the flight is done:
  `python cobblers-server/rcon.py save-all`, then `stop`, then remove
  `C:\Users\wnd\Documents\github\.cobblers-server-agent.lock`, then record what the owner saw in STATE and the
  experiments (EXP-046 for the workers).
- **The owner prefers flying this world over the water export making another.** The export waits until the flight
  list below is flown and its findings are in.
- **Next job, its own session: sweep the tools for loops like the gulch's.** `zone_problems` rebuilt `band_columns()`
  123,131 times inside a comprehension (210 s of a 270 s build; fixed in #86). Recipe: `python -m cProfile -o
  <scratch>/x.prof tools/<tool>.py <args>` for each prepare job (`reapply.py prepare --list`; the slowest first:
  `vr_caves:build`, `deep_city:build`, `town:*`, `mines:build`), then `pstats` sorted by cumulative time. The shape
  is a pure function of loop-invariant arguments called per element (in a comprehension condition, a `min(...)`
  over all cells, a nested lookup), or pure-Python distance loops that vectorise. Fix only where output stays
  byte-identical (compare the pack before and after, as #86 did), and time prepare and the suite before and after.

## 3. The flight (most important first; what to check at each stop)

1. **Working Pokemon** (EXP-046; the one the owner wants most). Twenty workers, two carriers and four stationary per
   town at most.
   - Brock's mason yard (1781, 141, 3669): the Graveler carries stone to the pile (stone-hit and place sounds, the
     block on its back); the Machop at the bench (1786, 3689). Click one; hit one with a sword (it must not die or
     aggro); it is plainly the town's, not Brock's party.
   - Northlight square (7272, 117, 1602), the fire at (7280, 1577): the Timburr walks its 25 blocks on the trodden
     track, not under snow; the flame puff at the drop.
   - Carriers elsewhere: Koga's reeds (4578, 2396), Blaine's tuff samples (6041, 4993), Giovanni's supplies
     (3598, 6475), the Mining Town ore (6636, 5696). Each walks, drops, walks back; none wanders off after a reload.
   - Stationary, one look each: Koga's Venonat (4704, 2401), Sabrina's Natu (6131, 3317) and Abra (Sabrina's town,
     6196, 3398), Blaine's Magby (6103, 4976), Giovanni's Machop (3611, 6539), Erika's Bulbasaur (4300, 1540) and
     Bellossom (4318, 1570), the tea town Oddish (2660, 3520), Surge's Magnemite (1676, 1387), the Mining Town
     breakers (6640, 5692) and (6608, 5692), the Tableland Sandshrew (4797, 5672), the rim post Growlithe
     (3773, 3945).
   - Leave a town and come back: the workers are still there, one of each, at their stations.
2. **The level cap, in battle.** In a wild battle with a Pokemon above your cap, throw a ball: the chat says "It broke
   free! Your team isn't strong enough yet." and the ball never catches (a Master Ball too). One at or under the cap
   still catches normally.
3. **The stone faces** (22 faces at seven places). At each: the face shows its ore; mine it; walk away more than the
   restore range for 10 minutes and come back: it is restored. A chest placed in a face survives the restore. While
   you stand at a face it never restores under you.
   - Mining Town (6633, 5716): fire (6758, 138, 5783) and thunder (6762, 137, 5767); the **Assayer** on the plaza
     sells all ten stones and buys none.
   - Tea town: leaf (2634, 108, 3612), shiny (2665, 107, 3624).
   - Northlight: ice (7318, 110, 1591).
   - Gorge hamlet: dusk (6802, 107, 4310), dawn (6812, 108, 4288).
   - The Scar: sun (2080, 274, 964). Viltri Light: water (568, 68, 4496). Displaced City: moon (3330, 28, 1850),
     thunder (3390, 24, 1850).
4. **The southern gulch and its cove town.**
   - The gate: stand at the knock (4364, 116, 4706) without the sixth badge: turned back with the "sixth badge" title.
     With it: through to the arrival (4349, 111, 4706). The rockslide wall from outside reads as a wall to the crag
     tops; nothing reachable through the grille; Mining Fatigue at the plug.
   - The cove town square (4308, 88, 4848): the 69 buildings, every doorway walkable; the Cutters sell a keyed stone
     for two raw stones and a diamond; the crystal faces cannot be mined.
   - The Megas: Steelix (4446, 4852) and Excadrill (4428, 4834); do they attack in daylight; a gone one comes back
     only after its respawn time.
5. **Re-materialed houses** (16 sets on 156 houses in 10 towns). Fly Brock's (1743, 3628), Sabrina's (6196, 3398),
   Blaine's (6074, 4995), Giovanni's (3647, 6497) and the Mining Town (6633, 5716): each town in its own palette, no
   odd blocks (a pillar lying on its side, a stair facing wrong), doors and beds whole.
6. **The shrines** (six). Brock's cairn (1609, 3767), Misty's lantern stone (1700, 2877), Surge's niche
   (1699, 1501), Koga's niche (4509, 2303), the Tableland altar (4765, 5622), the Merian path cairn (2820, 1212):
   each reads as a shrine from the approach road, sits on the ground, and blocks nothing.
7. **The guardians and the blackout** (carried over, EXP-041 and EXP-042). The staging-only gated chambers of the
   retired spur section (chamber_1 at 3166, 52, 3094): a sword kill of a guardian, a kill by your Pokemon outside
   battle, a real loss (the blackout), and the Mining Fatigue at the mine door.

### Flight findings so far
1. **Flight finding 1 (the owner, 2026-09-28): the tea town's stone faces read as square pits beside the Centre, and have no bottom.** Seen at (2649, 114, 3614) and (2653, 114, 3625). (1) Too easy to find: all four faces sit 10-35 blocks from the town centre (2654, 3605), next to the Centre and Mart. (2) Not natural: a face is a fixed box (`data/mines.json` geometry: 9 wide, 5 high, 6 deep, vertical cut walls) meant to cut into a slope; the tea town is nearly flat (mean slope 2.4 degrees), so each becomes a square pit sunk into the meadow. (3) No bottom: the floor is cobblestone over the host stone, so a player cannot tell where the ore stops. Wanted: faces sited away from the plaza, in real rise (or shaped irregularly where there is none), and a distinct bottom layer under each face. Check the other six places for the same before redesigning (`tools/mines.py site`, `tools/mines_audit.py`).
   Next session: redesign the faces for this (the owner's three points), after the flight's other findings.

### Decisions waiting
- The Mega farms' zone: both sites are inside Victory Road's Z2 (8 badges); the design says after gym 6.
- The West Spur Dig reshape: not started, about 300k.
- The spur's daily crystal after gym 6 may give a free raw stone (against "not free").
- Workers for Pallet, and after the export for Misty's town, Sunset West and Viltri Light.
- ATM x MSD v4.0 adoption (`docs/research/CLIENT_MODEL_FIXES.md`): needs an in-game look.

## 4. Do not rediscover

- An isolated agent's worktree starts at the session's committed HEAD (`worktree.baseRef: "head"`); it hydrates kits
  from `C:/Users/wnd/Documents/cobblers-local`; the classifier refuses it `rift_heightmap.py --plan`;
  `.worktreeinclude` copies nothing.
- The Rift sculpt protects town footprints: `--plan` uses those `--apply` recorded (`data/world.json`), because the
  League and the rim post moved after the sculpt.
- `data/routes.json` was adjusted after routing; `data/route_paths.json` is committed, never regenerated.
- The harness's per-agent token figure is final context, not spend: `tools/session_cost.py`.
- Running one prepare tool alone can leave derived files half-made (a grove file without its augment broke six
  tests): use `reapply.py prepare --only <jobs>`, which runs the whole job.
- Bash heredocs here turn `\\n` into a newline inside Python source: write scripts with Write/Edit.
- Prepare leaves stale files in `build/` (14 stripped templates found); harmless, not yet cleaned.

## 5. What this session cost

`python tools/session_cost.py`: 38.6M weighted over about 700 turns (average 461k context per turn); its 16 agents
26.8M, the three throwaway launch tests 0.3M of that.
